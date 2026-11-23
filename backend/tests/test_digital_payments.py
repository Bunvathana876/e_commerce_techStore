"""Comprehensive tests for Card-only digital payments, COD settlement, and Stripe integration."""

from decimal import Decimal
import hashlib
import hmac
import json
import time

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.db.database import SessionLocal
from app.models.order import Order
from app.models.payment import PaymentTransaction


class _FakeHttpxResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        return self._payload


def _stripe_sig(body: bytes, secret: str, ts: int | None = None) -> str:
    timestamp = ts if ts is not None else int(time.time())
    signed = f"{timestamp}.".encode("utf-8") + body
    sig = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={sig}"


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_payment_config_restricts_to_card_and_cod(client, prefix):
    res = client.get(f"{prefix}/payments/config")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["supported_methods"] == ["Credit / Debit Card", "Cash on Delivery"]
    assert data["card_gateway_configured"] is False
    assert data["card_provider"] == "none"
    assert data["currency"] == "USD"


@pytest.mark.parametrize(
    "legacy_method",
    ["KHQR Scan & Pay", "ABA / KHQR Pay", "Apple Pay", "Wing Money", "QR Pay", "Bitcoin"],
)
def test_checkout_rejects_deprecated_methods(client, headers, legacy_method):
    res = client.post(
        "/api/v1/orders",
        headers=headers(2),
        json={
            "shipping_address": "123 Norodom Blvd, Phnom Penh",
            "payment_method": legacy_method,
            "items": [{"product_id": 1, "quantity": 1}],
        },
    )
    assert res.status_code == 400


def test_cod_order_creates_transaction_and_settles_on_admin_update(
    client, headers, admin_headers
):
    order_res = client.post(
        "/api/v1/orders",
        headers=headers(2),
        json={
            "shipping_address": "123 Norodom Blvd, Phnom Penh",
            "payment_method": "Cash on Delivery",
            "items": [{"product_id": 1, "quantity": 1}],
        },
    )
    assert order_res.status_code == 201
    oid = order_res.json()["data"]["id"]

    with SessionLocal() as db:
        tx = db.scalar(
            select(PaymentTransaction).where(PaymentTransaction.order_id == oid)
        )
        assert tx is not None
        assert tx.payment_method == "Cash on Delivery"
        assert tx.provider == "cod"
        assert tx.status == "pending"

    # Admin transitions order to delivered + marks COD paid
    deliver_res = client.put(
        f"/api/v1/orders/{oid}/status",
        headers=admin_headers,
        json={"status": "processing"},
    )
    assert deliver_res.status_code == 200
    ship_res = client.put(
        f"/api/v1/orders/{oid}/status",
        headers=admin_headers,
        json={"status": "shipped"},
    )
    assert ship_res.status_code == 200
    # Manual COD settlement requires an audit reason
    no_reason = client.put(
        f"/api/v1/orders/{oid}/status",
        headers=admin_headers,
        json={"status": "delivered", "payment_status": "paid"},
    )
    assert no_reason.status_code == 400

    paid_res = client.put(
        f"/api/v1/orders/{oid}/status",
        headers=admin_headers,
        json={
            "status": "delivered",
            "payment_status": "paid",
            "reason": "Cash collected upon delivery",
        },
    )
    assert paid_res.status_code == 200
    assert paid_res.json()["data"]["payment_status"] == "paid"


def test_card_intent_fails_closed_when_unconfigured(client, headers):
    order_res = client.post(
        "/api/v1/orders",
        headers=headers(2),
        json={
            "shipping_address": "123 Norodom Blvd, Phnom Penh",
            "payment_method": "Credit / Debit Card",
            "items": [{"product_id": 1, "quantity": 1}],
        },
    )
    assert order_res.status_code == 201
    oid = order_res.json()["data"]["id"]

    intent_res = client.post(
        "/api/v1/payments/card/intent",
        headers=headers(2),
        json={"order_id": oid},
    )
    assert intent_res.status_code == 503


def test_stripe_card_intent_confirm_and_admin_listing(
    client, headers, admin_headers, monkeypatch
):
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_fake_123")
    monkeypatch.setattr(settings, "STRIPE_PUBLISHABLE_KEY", "pk_test_fake_123")

    cfg_res = client.get("/api/payments/config")
    assert cfg_res.status_code == 200
    assert cfg_res.json()["data"]["card_gateway_configured"] is True
    assert cfg_res.json()["data"]["card_provider"] == "stripe"

    order_res = client.post(
        "/api/orders",
        headers=headers(2),
        json={
            "shipping_address": "123 Norodom Blvd, Phnom Penh",
            "payment_method": "Credit / Debit Card",
            "items": [{"product_id": 1, "quantity": 2}],
        },
    )
    assert order_res.status_code == 201
    oid = order_res.json()["data"]["id"]
    total_cents = int((Decimal(str(order_res.json()["data"]["total"])) * Decimal("100")).quantize(Decimal("1")))

    def fake_post(url, **kwargs):
        assert url.endswith("/payment_intents")
        return _FakeHttpxResponse(
            200,
            {"id": "pi_test_999", "client_secret": "pi_test_999_secret_abc"},
        )

    def fake_get(url, **kwargs):
        assert url.endswith("/payment_intents/pi_test_999")
        return _FakeHttpxResponse(
            200,
            {
                "id": "pi_test_999",
                "status": "succeeded",
                "amount_received": total_cents,
                "metadata": {"order_id": str(oid)},
                "charges": {
                    "data": [
                        {
                            "payment_method_details": {
                                "card": {"brand": "visa", "last4": "4242"}
                            }
                        }
                    ]
                },
            },
        )

    monkeypatch.setattr("app.services.payment_service.httpx.post", fake_post)
    monkeypatch.setattr("app.services.payment_service.httpx.get", fake_get)

    intent_res = client.post(
        "/api/payments/card/intent",
        headers=headers(2),
        json={"order_id": oid},
    )
    assert intent_res.status_code == 201
    assert intent_res.json()["data"]["payment_intent_id"] == "pi_test_999"

    # Other customer denied
    forbidden = client.post(
        "/api/payments/card/confirm",
        headers=headers(3),
        json={"order_id": oid, "payment_intent_id": "pi_test_999"},
    )
    assert forbidden.status_code == 403

    confirm_res = client.post(
        "/api/payments/card/confirm",
        headers=headers(2),
        json={"order_id": oid, "payment_intent_id": "pi_test_999"},
    )
    assert confirm_res.status_code == 200
    tx_data = confirm_res.json()["data"]
    assert tx_data["status"] == "captured"
    assert tx_data["card_brand"] == "visa"
    assert tx_data["card_last4"] == "4242"

    with SessionLocal() as db:
        order = db.get(Order, oid)
        assert order.payment_status == "paid"

    # Customer cannot list all payments; admin can inspect list & detail
    assert client.get("/api/payments", headers=headers(2)).status_code == 403
    list_res = client.get("/api/payments", headers=admin_headers)
    assert list_res.status_code == 200
    refs = [row["transaction_ref"] for row in list_res.json()["data"]]
    assert tx_data["transaction_ref"] in refs

    detail_res = client.get(
        f"/api/payments/{tx_data['transaction_ref']}", headers=admin_headers
    )
    assert detail_res.status_code == 200
    assert detail_res.json()["data"]["order_id"] == oid


def test_stripe_webhook_hmac_verification_and_capture(client, headers, monkeypatch):
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_test_secret_xyz")

    order_res = client.post(
        "/api/v1/orders",
        headers=headers(2),
        json={
            "shipping_address": "Street 2004, Phnom Penh",
            "payment_method": "Credit / Debit Card",
            "items": [{"product_id": 1, "quantity": 1}],
        },
    )
    assert order_res.status_code == 201
    oid = order_res.json()["data"]["id"]
    expected_cents = int((Decimal(str(order_res.json()["data"]["total"])) * Decimal("100")).quantize(Decimal("1")))

    payload = json.dumps(
        {
            "id": "evt_1",
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_webhook_1",
                    "amount_received": expected_cents,
                    "metadata": {"order_id": str(oid)},
                    "latest_charge": {
                        "payment_method_details": {
                            "card": {"brand": "mastercard", "last4": "5555"}
                        }
                    },
                }
            },
        }
    ).encode("utf-8")

    # Missing or invalid HMAC signature must fail with 400
    no_sig = client.post(
        "/api/v1/payments/webhooks/stripe",
        content=payload,
        headers={"Content-Type": "application/json"},
    )
    assert no_sig.status_code == 400

    bad_sig = client.post(
        "/api/v1/payments/webhooks/stripe",
        content=payload,
        headers={
            "Content-Type": "application/json",
            "Stripe-Signature": _stripe_sig(payload, "wrong_secret"),
        },
    )
    assert bad_sig.status_code == 400

    valid_sig = _stripe_sig(payload, "whsec_test_secret_xyz")
    ok_res = client.post(
        "/api/v1/payments/webhooks/stripe",
        content=payload,
        headers={
            "Content-Type": "application/json",
            "Stripe-Signature": valid_sig,
        },
    )
    assert ok_res.status_code == 200
    assert ok_res.json()["data"]["handled"] is True

    with SessionLocal() as db:
        order = db.get(Order, oid)
        assert order.payment_status == "paid"
        tx = db.scalar(
            select(PaymentTransaction).where(PaymentTransaction.order_id == oid)
        )
        assert tx.status == "captured"
        assert tx.card_brand == "mastercard"
        assert tx.card_last4 == "5555"
