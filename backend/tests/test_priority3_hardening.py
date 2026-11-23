"""Regression tests for Priority 3 backend hardening fixes."""

import json
import secrets
from fastapi import HTTPException
from sqlalchemy import select

from app.core.security import hash_password, verify_password
from app.db.database import SessionLocal
from app.main import create_app
from app.models.coupon import Coupon
from app.models.order import Order, OrderItem
from app.models.seller import Seller
from app.models.user import User
from scripts import bootstrap_admin


def test_long_passwords_over_72_bytes_register_and_login(client):
    long_password = "BluePandaLongPassphrase-" + ("X9z!" * 22)  # 112 ASCII bytes > 72
    assert len(long_password.encode("utf-8")) > 72

    reg = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Long Password User",
            "email": "longpass@example.com",
            "password": long_password,
        },
    )
    assert reg.status_code == 201, reg.text
    assert reg.json()["data"]["user"]["email"] == "longpass@example.com"

    ok_login = client.post(
        "/api/v1/auth/login",
        json={"email": "longpass@example.com", "password": long_password},
    )
    assert ok_login.status_code == 200

    bad_login = client.post(
        "/api/v1/auth/login",
        json={"email": "longpass@example.com", "password": long_password + "wrong"},
    )
    assert bad_login.status_code == 401

    # Backward compatibility for legacy <= 72 byte bcrypt hashes
    legacy_hash = hash_password("ShortValidPass!9")
    assert not legacy_hash.startswith("sha256$")
    assert verify_password("ShortValidPass!9", legacy_hash) is True
    assert verify_password(long_password, legacy_hash) is False


def test_register_missing_or_blank_name_returns_422(client):
    for payload in [
        {"email": "noname1@example.com", "password": "Strong-password-123"},
        {"name": "   ", "email": "noname2@example.com", "password": "Strong-password-123"},
        {"full_name": "", "email": "noname3@example.com", "password": "Strong-password-123"},
    ]:
        res = client.post("/api/v1/auth/register", json=payload)
        assert res.status_code == 422, res.text


def test_admin_user_route_security_guards(client, admin_headers, headers):
    # Weak password on admin create rejected
    weak_create = client.post(
        "/api/v1/users",
        json={"name": "Weak", "email": "weak@example.com", "password": "123"},
        headers=admin_headers,
    )
    assert weak_create.status_code == 400

    # Short/weak password on admin update rejected instead of silently ignored
    weak_update = client.put(
        "/api/v1/users/2",
        json={"password": "short"},
        headers=admin_headers,
    )
    assert weak_update.status_code == 400

    # Self-delete, self-disable, self-demote rejected
    assert client.delete("/api/v1/users/1", headers=admin_headers).status_code == 400
    assert client.put("/api/v1/users/1", json={"is_active": False}, headers=admin_headers).status_code == 400
    assert client.put("/api/v1/users/1", json={"role": "customer"}, headers=admin_headers).status_code == 400

    # Log in as customer #3 so their session is active, then change role -> existing token revoked
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "user3@example.com", "password": "Fixture-password-123"},
    )
    assert login.status_code == 200
    customer_token = login.json()["data"]["access_token"]
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {customer_token}"}).status_code == 200

    role_change = client.put("/api/v1/users/3", json={"role": "seller"}, headers=admin_headers)
    assert role_change.status_code == 200
    after_role_change = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {customer_token}"})
    assert after_role_change.status_code == 401

    # Re-login and then disable account -> blocked immediately
    login_2 = client.post(
        "/api/v1/auth/login",
        json={"email": "user3@example.com", "password": "Fixture-password-123"},
    )
    assert login_2.status_code == 200
    new_token = login_2.json()["data"]["access_token"]
    disable = client.put("/api/v1/users/3", json={"is_active": False}, headers=admin_headers)
    assert disable.status_code == 200
    after_disable = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {new_token}"})
    assert after_disable.status_code == 403


def test_seller_creation_avoids_hardcoded_password_and_upgrades_customer(client, admin_headers):
    res = client.post(
        "/api/v1/sellers",
        json={
            "name": "Secure Tech Store",
            "owner_name": "Alice Owner",
            "email": "alice.store@example.com",
        },
        headers=admin_headers,
    )
    assert res.status_code == 201, res.text
    with SessionLocal() as db:
        created_user = db.scalar(select(User).where(User.email == "alice.store@example.com"))
        assert created_user is not None
        assert created_user.role == "seller"
        assert verify_password("Seller123!", created_user.password_hash) is False

    # Creating seller for existing customer upgrades role to seller
    upgrade_res = client.post(
        "/api/v1/sellers",
        json={
            "name": "User2 Store",
            "owner_name": "Fixture 2",
            "email": "user2@example.com",
        },
        headers=admin_headers,
    )
    assert upgrade_res.status_code == 201, upgrade_res.text
    with SessionLocal() as db:
        upgraded = db.get(User, 2)
        assert upgraded.role == "seller"


def test_product_validation_and_readonly_rating(client, admin_headers):
    assert client.post(
        "/api/v1/products",
        json={"category_id": 1, "name": "Bad Price", "price": -5, "stock": 10},
        headers=admin_headers,
    ).status_code == 422
    assert client.post(
        "/api/v1/products",
        json={"category_id": 1, "name": "Bad Stock", "price": 10, "stock": -1},
        headers=admin_headers,
    ).status_code == 422
    assert client.post(
        "/api/v1/products",
        json={"category_id": 1, "name": "Bad Discount", "price": 20, "discount_price": 25, "stock": 5},
        headers=admin_headers,
    ).status_code == 422

    created = client.post(
        "/api/v1/products",
        json={"category_id": 1, "name": "Clean Phone", "price": 200, "discount_price": 180, "stock": 5, "rating": 5.0},
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text
    assert float(created.json()["data"]["rating"]) == 0.0

    # Partial update cannot make existing price < discount_price or overwrite rating
    prod_id = created.json()["data"]["id"]
    bad_patch = client.put(
        f"/api/v1/products/{prod_id}",
        json={"price": 150},
        headers=admin_headers,
    )
    assert bad_patch.status_code == 422

    rating_patch = client.put(
        f"/api/v1/products/{prod_id}",
        json={"rating": 4.9, "name": "Clean Phone Pro"},
        headers=admin_headers,
    )
    assert rating_patch.status_code == 200
    assert float(rating_patch.json()["data"]["rating"]) == 0.0


def test_bootstrap_admin_expected_columns_matches_user_table():
    model_cols = {c.name for c in User.__table__.columns}
    assert bootstrap_admin.EXPECTED_COLUMNS == model_cols
    assert "legacy_tokens_revoked_at" in bootstrap_admin.EXPECTED_COLUMNS


def test_unhandled_exception_returns_structured_json_500_with_cors():
    from fastapi.testclient import TestClient

    test_app = create_app()

    @test_app.app.get("/api/test-boom")
    def _boom():
        raise RuntimeError("sensitive internal connection string leaked")

    with TestClient(test_app, raise_server_exceptions=False) as tc:
        res = tc.get("/api/test-boom", headers={"Origin": "http://localhost:3000"})
        assert res.status_code == 500
        assert res.text == "Internal Server Error"
        assert "sensitive internal connection string" not in res.text
        assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_coupon_per_user_limit_and_cancellation_restore(client, admin_headers, headers):
    c_res = client.post(
        "/api/v1/coupons",
        json={
            "code": "ONCEPERUSER",
            "discount_type": "fixed",
            "discount_value": 5,
            "per_user_limit": 1,
        },
        headers=admin_headers,
    )
    assert c_res.status_code == 201, c_res.text

    # Customer 2 redeems ONCEPERUSER on Order 1
    o1 = client.post(
        "/api/v1/orders",
        json={
            "shipping_address": "123 Main St",
            "payment_method": "Cash on Delivery",
            "coupon_code": "ONCEPERUSER",
            "items": [{"product_id": 1, "quantity": 1}],
        },
        headers=headers(2),
    )
    assert o1.status_code == 201, o1.text
    order1_id = o1.json()["data"]["id"]

    # Customer 2 cannot redeem a second time
    v2 = client.post(
        "/api/v1/coupons/validate",
        json={"code": "ONCEPERUSER", "subtotal": 20},
        headers=headers(2),
    )
    assert v2.status_code == 409

    o2 = client.post(
        "/api/v1/orders",
        json={
            "shipping_address": "123 Main St",
            "payment_method": "Cash on Delivery",
            "coupon_code": "ONCEPERUSER",
            "items": [{"product_id": 1, "quantity": 1}],
        },
        headers=headers(2),
    )
    assert o2.status_code == 409

    # Customer 3 CAN redeem their own allocation
    o3 = client.post(
        "/api/v1/orders",
        json={
            "shipping_address": "456 Other St",
            "payment_method": "Cash on Delivery",
            "coupon_code": "ONCEPERUSER",
            "items": [{"product_id": 1, "quantity": 1}],
        },
        headers=headers(3),
    )
    assert o3.status_code == 201

    # Admin cancels Customer 2's order -> Customer 2 can use the coupon again
    cancel = client.delete(f"/api/v1/orders/{order1_id}?reason=Changed+mind", headers=admin_headers)
    assert cancel.status_code == 200
    o2_retry = client.post(
        "/api/v1/orders",
        json={
            "shipping_address": "123 Main St",
            "payment_method": "Cash on Delivery",
            "coupon_code": "ONCEPERUSER",
            "items": [{"product_id": 1, "quantity": 1}],
        },
        headers=headers(2),
    )
    assert o2_retry.status_code == 201


def test_review_requires_verified_purchase_and_prevents_duplicates(client, admin_headers, headers):
    # Customer 2 has not purchased product 1 -> 403
    no_purchase = client.post(
        "/api/v1/reviews/product/1",
        json={"rating": 5, "comment": "Never bought it"},
        headers=headers(2),
    )
    assert no_purchase.status_code == 403

    # Cancelled order does not count as verified purchase -> 403
    cancelled = client.post(
        "/api/v1/orders",
        json={
            "shipping_address": "Addr",
            "payment_method": "Cash on Delivery",
            "items": [{"product_id": 1, "quantity": 1}],
        },
        headers=headers(2),
    )
    cancelled_id = cancelled.json()["data"]["id"]
    client.delete(f"/api/v1/orders/{cancelled_id}?reason=Cancel", headers=admin_headers)
    after_cancel = client.post(
        "/api/v1/reviews/product/1",
        json={"rating": 5, "comment": "Cancelled purchase"},
        headers=headers(2),
    )
    assert after_cancel.status_code == 403

    # Active order enables review, automatically links order_id, and blocks duplicate review
    active = client.post(
        "/api/v1/orders",
        json={
            "shipping_address": "Addr",
            "payment_method": "Cash on Delivery",
            "items": [{"product_id": 1, "quantity": 1}],
        },
        headers=headers(2),
    )
    active_id = active.json()["data"]["id"]
    ok = client.post(
        "/api/v1/reviews/product/1",
        json={"rating": 5, "comment": "Great hardware"},
        headers=headers(2),
    )
    assert ok.status_code == 201, ok.text
    assert ok.json()["data"]["order_id"] == active_id

    dup = client.post(
        "/api/v1/reviews/product/1",
        json={"rating": 4, "comment": "Duplicate attempt"},
        headers=headers(2),
    )
    assert dup.status_code == 409
