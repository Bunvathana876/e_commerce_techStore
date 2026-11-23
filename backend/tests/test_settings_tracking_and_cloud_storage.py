"""Tests for Store Settings, RBAC Roles, Real Shipment Tracking, and Cloud Storage uploads."""

import pytest
import httpx

from app.core.config import Settings
from app.services.storage_service import StorageService
from tests.test_upload_security import make_png_bytes


def test_store_settings_and_roles_api(client, admin_headers, headers):
    # Public settings accessible without auth
    pub = client.get("/api/v1/settings/public")
    assert pub.status_code == 200
    assert pub.json()["data"]["store_name"] == "Blue Panda"

    # Admin settings & roles reject customer/seller
    for uid in (2, 4):
        assert client.get("/api/v1/settings", headers=headers(uid)).status_code == 403
        assert client.get("/api/v1/settings/roles", headers=headers(uid)).status_code == 403

    # Admin reads settings & live infrastructure table list
    adm = client.get("/api/v1/settings", headers=admin_headers)
    assert adm.status_code == 200, adm.text
    infra = adm.json()["data"]["infrastructure"]
    assert infra["database_connected"] is True
    assert infra["table_count"] >= 25
    assert "store_settings" in infra["table_names"]
    assert "order_shipments" in infra["table_names"]

    # Reject disabling both payment methods
    invalid_pay = client.put(
        "/api/v1/settings",
        json={
            **adm.json()["data"]["settings"],
            "enable_card_payment": False,
            "enable_cod_payment": False,
        },
        headers=admin_headers,
    )
    assert invalid_pay.status_code == 422

    # Valid update persists across reads and public endpoint
    updated = client.put(
        "/api/v1/settings",
        json={
            **adm.json()["data"]["settings"],
            "store_name": "Blue Panda Flagship",
            "free_shipping_min": 75.0,
            "standard_shipping_fee": 3.5,
        },
        headers=admin_headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["settings"]["store_name"] == "Blue Panda Flagship"
    assert float(client.get("/api/v1/settings/public").json()["data"]["free_shipping_min"]) == 75.0

    # Roles & permissions endpoint returns live user counts
    roles_res = client.get("/api/v1/settings/roles", headers=admin_headers)
    assert roles_res.status_code == 200
    roles = {r["id"]: r for r in roles_res.json()["data"]}
    assert "admin" in roles and "seller" in roles and "customer" in roles
    assert roles["admin"]["users_count"] >= 1
    assert roles["seller"]["users_count"] >= 2
    assert roles["admin"]["permissions_count"] > roles["seller"]["permissions_count"]


def test_order_shipment_tracking_lifecycle(client, admin_headers, headers):
    order_res = client.post(
        "/api/v1/orders",
        json={
            "shipping_address": "123 Kampuchea Krom, Phnom Penh",
            "payment_method": "Cash on Delivery",
            "items": [{"product_id": 1, "quantity": 1}],
        },
        headers=headers(2),
    )
    assert order_res.status_code == 201
    order_id = order_res.json()["data"]["id"]

    # Buyer can read baseline derived timeline; other customer gets 404; foreign seller gets 404
    buyer_track = client.get(f"/api/v1/orders/{order_id}/tracking", headers=headers(2))
    assert buyer_track.status_code == 200
    assert buyer_track.json()["data"]["has_shipment_record"] is False
    assert buyer_track.json()["data"]["events"][0]["title"] == "Order Placed"
    assert client.get(f"/api/v1/orders/{order_id}/tracking", headers=headers(3)).status_code == 404
    assert client.get(f"/api/v1/orders/{order_id}/tracking", headers=headers(5)).status_code == 404

    # Buyer cannot write tracking; foreign seller cannot write tracking
    assert client.put(
        f"/api/v1/orders/{order_id}/tracking",
        json={"carrier": "Virak Buntham", "status": "in_transit"},
        headers=headers(2),
    ).status_code == 403
    assert client.put(
        f"/api/v1/orders/{order_id}/tracking",
        json={"carrier": "Virak Buntham", "status": "in_transit"},
        headers=headers(5),
    ).status_code == 403

    # Invalid URL scheme rejected
    assert client.put(
        f"/api/v1/orders/{order_id}/tracking",
        json={"carrier": "DHL", "tracking_url": "javascript:alert(1)", "status": "in_transit"},
        headers=headers(4),
    ).status_code == 422

    # Owning seller updates real carrier & tracking number
    upd = client.put(
        f"/api/v1/orders/{order_id}/tracking",
        json={
            "carrier": "J&T Express",
            "tracking_number": "JT-88990011",
            "tracking_url": "https://track.example.com/JT-88990011",
            "status": "in_transit",
            "location": "Phnom Penh Sorting Hub",
            "event_title": "Dispatched to Sorting Hub",
        },
        headers=headers(4),
    )
    assert upd.status_code == 200, upd.text
    payload = upd.json()["data"]
    assert payload["has_shipment_record"] is True
    assert payload["shipment"]["carrier"] == "J&T Express"
    assert payload["shipment"]["tracking_number"] == "JT-88990011"
    assert payload["events"][-1]["location"] == "Phnom Penh Sorting Hub"


def test_cloud_storage_backends_supabase_and_s3(monkeypatch):
    png = make_png_bytes()

    # 1. Auto defaults to local when no cloud keys configured
    local_cfg = Settings(_env_file=None, DATABASE_URL="sqlite:///:memory:", ENVIRONMENT="test")
    assert StorageService.resolve_backend(local_cfg) == "local"

    # 2. Supabase storage upload & public URL construction
    supa_cfg = Settings(
        _env_file=None,
        DATABASE_URL="sqlite:///:memory:",
        ENVIRONMENT="test",
        UPLOAD_STORAGE_BACKEND="auto",
        SUPABASE_URL="https://demo.supabase.co",
        SUPABASE_SERVICE_ROLE_KEY="service-role-key-secret",
        SUPABASE_STORAGE_BUCKET="media",
    )
    assert StorageService.resolve_backend(supa_cfg) == "supabase"

    seen = {}

    def fake_supa_post(url, content, headers, timeout):
        seen["url"] = url
        seen["headers"] = headers
        seen["len"] = len(content)
        return httpx.Response(200, json={"Key": "media/products/test.png"})

    monkeypatch.setattr(httpx, "post", fake_supa_post)
    supa_res = StorageService.store_product_image(png, canonical_ext=".png", content_type="image/png", cfg=supa_cfg)
    assert supa_res.storage_backend == "supabase"
    assert seen["url"].startswith("https://demo.supabase.co/storage/v1/object/media/products/")
    assert seen["headers"]["Authorization"] == "Bearer service-role-key-secret"
    assert supa_res.url.startswith("https://demo.supabase.co/storage/v1/object/public/media/products/")

    # Upstream Supabase failure raises 502
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: httpx.Response(500, text="error"))
    with pytest.raises(Exception) as exc_supa:
        StorageService.store_product_image(png, canonical_ext=".png", content_type="image/png", cfg=supa_cfg)
    assert "502" in str(exc_supa.value) or "Supabase" in str(exc_supa.value)

    # 3. S3 / R2 SigV4 signed PUT upload
    s3_cfg = Settings(
        _env_file=None,
        DATABASE_URL="sqlite:///:memory:",
        ENVIRONMENT="test",
        UPLOAD_STORAGE_BACKEND="s3",
        S3_BUCKET="bluepanda-assets",
        S3_REGION="auto",
        S3_ENDPOINT_URL="https://r2.example.cloudflarestorage.com",
        S3_ACCESS_KEY_ID="AKIA_TEST",
        S3_SECRET_ACCESS_KEY="SECRET_TEST_KEY",
        S3_PUBLIC_BASE_URL="https://cdn.bluepanda.com",
    )

    s3_seen = {}

    def fake_s3_put(url, content, headers, timeout):
        s3_seen["url"] = url
        s3_seen["headers"] = headers
        return httpx.Response(200)

    monkeypatch.setattr(httpx, "put", fake_s3_put)
    s3_res = StorageService.store_product_image(png, canonical_ext=".png", content_type="image/png", cfg=s3_cfg)
    assert s3_res.storage_backend == "s3"
    assert s3_res.url.startswith("https://cdn.bluepanda.com/products/")
    assert s3_seen["headers"]["Authorization"].startswith("AWS4-HMAC-SHA256 Credential=AKIA_TEST/")
    assert "x-amz-content-sha256" in s3_seen["headers"]
    assert "x-amz-date" in s3_seen["headers"]


def test_store_settings_enforced_in_checkout_and_payments_config(client, admin_headers, headers):
    baseline = client.get("/api/v1/settings", headers=admin_headers).json()["data"]["settings"]

    try:
        # Configure custom shipping rules (free >= $500, flat $6.50) and disable COD
        upd = client.put(
            "/api/v1/settings",
            json={
                **baseline,
                "free_shipping_min": 500.0,
                "standard_shipping_fee": 6.5,
                "enable_card_payment": True,
                "enable_cod_payment": False,
            },
            headers=admin_headers,
        )
        assert upd.status_code == 200, upd.text

        # /payments/config hides disabled COD
        cfg = client.get("/api/v1/payments/config").json()["data"]
        assert cfg["enable_card_payment"] is True
        assert cfg["enable_cod_payment"] is False
        assert "Cash on Delivery" not in cfg["supported_methods"]

        # Disabled COD rejected at order creation
        cod_denied = client.post(
            "/api/v1/orders",
            json={
                "shipping_address": "St 1, Phnom Penh",
                "payment_method": "Cash on Delivery",
                "items": [{"product_id": 1, "quantity": 1}],
            },
            headers=headers(2),
        )
        assert cod_denied.status_code == 400
        assert "disabled" in cod_denied.json()["detail"].lower()

        # Card order succeeds and applies live $6.50 shipping fee (below $500 threshold)
        card_ok = client.post(
            "/api/v1/orders",
            json={
                "shipping_address": "St 1, Phnom Penh",
                "payment_method": "Credit / Debit Card",
                "items": [{"product_id": 1, "quantity": 1}],
            },
            headers=headers(2),
        )
        assert card_ok.status_code == 201, card_ok.text
        order_data = card_ok.json()["data"]
        assert float(order_data["shipping_fee"]) == 6.5

        # Now disable card payments too (keep COD enabled)
        upd2 = client.put(
            "/api/v1/settings",
            json={
                **baseline,
                "free_shipping_min": 10.0,
                "standard_shipping_fee": 6.5,
                "enable_card_payment": False,
                "enable_cod_payment": True,
            },
            headers=admin_headers,
        )
        assert upd2.status_code == 200
        cfg2 = client.get("/api/v1/payments/config").json()["data"]
        assert cfg2["enable_card_payment"] is False
        assert cfg2["card_gateway_configured"] is False

        # Existing unpaid card order cannot start a new PaymentIntent when card is disabled
        intent_denied = client.post(
            "/api/v1/payments/card/intent",
            json={"order_id": order_data["id"]},
            headers=headers(2),
        )
        assert intent_denied.status_code == 400
    finally:
        # Restore baseline store settings cleanly
        client.put("/api/v1/settings", json=baseline, headers=admin_headers)
