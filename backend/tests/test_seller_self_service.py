import pytest
from sqlalchemy import select

from app.db.database import SessionLocal
from app.models.seller import Seller
from app.models.user import User


@pytest.fixture(params=["/api", "/api/v1"])
def prefix(request):
    return request.param


# ---------------------------------------------------------------------------
# 1. Approved seller reads own store
# ---------------------------------------------------------------------------
def test_approved_seller_reads_own_store(client, headers, prefix):
    # User 4 is seller for Store A
    response = client.get(f"{prefix}/seller/me", headers=headers(4))
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["name"] == "Store A"
    assert payload["data"]["user_id"] == 4
    assert payload["data"]["status"] == "Active"

    # Also test plural alias /sellers/me
    alias_response = client.get(f"{prefix}/sellers/me", headers=headers(4))
    assert alias_response.status_code == 200
    assert alias_response.json()["data"]["name"] == "Store A"


# ---------------------------------------------------------------------------
# 2. Seller updates allowed fields
# ---------------------------------------------------------------------------
def test_seller_updates_allowed_fields(client, headers, prefix):
    update_data = {
        "name": "Updated Store A",
        "description": "Premium electronics store bio.",
        "phone": "+85512345678",
        "address": "Street 2004, Phnom Penh",
        "logo": "https://example.com/logo-updated.png",
    }
    response = client.put(f"{prefix}/seller/me", json=update_data, headers=headers(4))
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["name"] == "Updated Store A"
    assert data["description"] == "Premium electronics store bio."
    assert data["phone"] == "+85512345678"
    assert data["address"] == "Street 2004, Phnom Penh"
    assert data["logo"] == "https://example.com/logo-updated.png"

    # Verify persistence in database
    with SessionLocal() as db:
        store = db.scalar(select(Seller).where(Seller.id == 1))
        assert store.name == "Updated Store A"
        assert store.phone == "+85512345678"


# ---------------------------------------------------------------------------
# 3. Seller cannot update another seller's store
# ---------------------------------------------------------------------------
def test_seller_cannot_update_another_sellers_store(client, headers, prefix):
    # User 4 (Seller for Store 1) calls PUT /seller/me
    client.put(f"{prefix}/seller/me", json={"name": "Attacker Store Name"}, headers=headers(4))

    # Verify Store 2 (User 5) remains completely untouched
    with SessionLocal() as db:
        store_2 = db.scalar(select(Seller).where(Seller.id == 2))
        assert store_2.name == "Store B"
        assert store_2.user_id == 5

    # Seller attempting to directly call administrative PUT /sellers/2 is forbidden
    admin_call = client.put(f"{prefix}/sellers/2", json={"name": "Hacked Name"}, headers=headers(4))
    assert admin_call.status_code == 403


# ---------------------------------------------------------------------------
# 4. Seller cannot modify approval or privileged fields
# ---------------------------------------------------------------------------
def test_seller_cannot_modify_status_or_privileged_fields(client, headers, prefix):
    # Attempt to change status to Suspended or Pending
    res_status = client.put(f"{prefix}/seller/me", json={"status": "Suspended"}, headers=headers(4))
    assert res_status.status_code == 403
    assert "status" in res_status.json()["detail"].lower()

    # Attempt to change ownership (user_id)
    res_owner = client.put(f"{prefix}/seller/me", json={"user_id": 99}, headers=headers(4))
    assert res_owner.status_code == 403
    assert "ownership" in res_owner.json()["detail"].lower()

    # Attempt to alter email
    res_email = client.put(f"{prefix}/seller/me", json={"email": "attacker@evil.com"}, headers=headers(4))
    assert res_email.status_code == 403

    # Attempt to alter rating or revenue metrics
    res_metrics = client.put(f"{prefix}/seller/me", json={"rating": 5.0, "total_revenue": 1000000}, headers=headers(4))
    assert res_metrics.status_code == 403
    assert "metrics" in res_metrics.json()["detail"].lower()

    # Verify in DB that store was not changed
    with SessionLocal() as db:
        store = db.scalar(select(Seller).where(Seller.id == 1))
        assert store.status == "Active"
        assert store.user_id == 4
        assert store.email == "a@example.com"


# ---------------------------------------------------------------------------
# 5. Customer cannot use seller endpoints
# ---------------------------------------------------------------------------
def test_customer_and_unauthenticated_cannot_use_seller_endpoints(client, headers, prefix):
    # Unauthenticated requests return 401
    assert client.get(f"{prefix}/seller/me").status_code == 401
    assert client.put(f"{prefix}/seller/me", json={"name": "Test"}).status_code == 401

    # Customer (User 2) returns 403 Forbidden
    res_get = client.get(f"{prefix}/seller/me", headers=headers(2))
    assert res_get.status_code == 403
    res_put = client.put(f"{prefix}/seller/me", json={"name": "Test"}, headers=headers(2))
    assert res_put.status_code == 403


# ---------------------------------------------------------------------------
# 6. Admin behavior follows existing permission rules
# ---------------------------------------------------------------------------
def test_admin_behavior_follows_existing_rules(client, headers, prefix):
    # Admin (User 1) has no linked seller profile -> 404 Not Found
    res = client.get(f"{prefix}/seller/me", headers=headers(1))
    assert res.status_code == 404

    # Admin CAN manage any store via the admin /sellers/{id} endpoint
    admin_update = client.put(
        f"{prefix}/sellers/1",
        json={"name": "Admin Renamed Store", "status": "Active"},
        headers=headers(1),
    )
    assert admin_update.status_code == 200
    assert admin_update.json()["data"]["name"] == "Admin Renamed Store"

    # If an admin also has a linked seller profile, /seller/me resolves it
    with SessionLocal() as db:
        admin_seller = Seller(
            user_id=1,
            name="Admin Official Store",
            owner_name="Admin Owner",
            email="admin_store@example.com",
            status="Active",
        )
        db.add(admin_seller)
        db.commit()

    res_admin_store = client.get(f"{prefix}/seller/me", headers=headers(1))
    assert res_admin_store.status_code == 200
    assert res_admin_store.json()["data"]["name"] == "Admin Official Store"


# ---------------------------------------------------------------------------
# 7. Missing, pending, or suspended stores are handled correctly
# ---------------------------------------------------------------------------
def test_missing_pending_suspended_stores(client, headers, prefix, password_hash):
    # 7a. Seller account without a store -> 404 Not Found
    with SessionLocal() as db:
        orphan_seller_user = User(
            id=99,
            name="Storeless Seller",
            email="storeless@example.com",
            role="seller",
            password_hash=password_hash,
            is_active=True,
        )
        db.add(orphan_seller_user)
        db.commit()

    res_missing = client.get(f"{prefix}/seller/me", headers=headers(99))
    assert res_missing.status_code == 404
    assert "not found" in res_missing.json()["detail"].lower()

    # 7b. Pending seller store -> GET succeeds with status=Pending, PUT is rejected with 403
    with SessionLocal() as db:
        pending_user = User(
            id=100,
            name="Pending Seller User",
            email="pending@example.com",
            role="seller",
            password_hash=password_hash,
            is_active=True,
        )
        db.add(pending_user)
        db.flush()
        pending_seller = Seller(
            id=100,
            user_id=100,
            name="Pending Store",
            owner_name="Pending Owner",
            email="pending@example.com",
            status="Pending",
        )
        db.add(pending_seller)
        db.commit()

    # GET returns 200 so frontend can display pending status
    res_pending_get = client.get(f"{prefix}/seller/me", headers=headers(100))
    assert res_pending_get.status_code == 200
    assert res_pending_get.json()["data"]["status"] == "Pending"

    # PUT fails with 403 Forbidden because store is not approved yet
    res_pending_put = client.put(
        f"{prefix}/seller/me",
        json={"name": "Try Modify While Pending"},
        headers=headers(100),
    )
    assert res_pending_put.status_code == 403
    assert "pending approval" in res_pending_put.json()["detail"].lower()

    # 7c. Suspended seller store -> GET succeeds with status=Suspended, PUT is rejected with 403
    with SessionLocal() as db:
        suspended_user = User(
            id=101,
            name="Suspended Seller User",
            email="suspended@example.com",
            role="seller",
            password_hash=password_hash,
            is_active=True,
        )
        db.add(suspended_user)
        db.flush()
        suspended_seller = Seller(
            id=101,
            user_id=101,
            name="Suspended Store",
            owner_name="Suspended Owner",
            email="suspended@example.com",
            status="Suspended",
        )
        db.add(suspended_seller)
        db.commit()

    # GET returns 200 so frontend can display suspended alert
    res_suspended_get = client.get(f"{prefix}/seller/me", headers=headers(101))
    assert res_suspended_get.status_code == 200
    assert res_suspended_get.json()["data"]["status"] == "Suspended"

    # PUT fails with 403 Forbidden because store is suspended
    res_suspended_put = client.put(
        f"{prefix}/seller/me",
        json={"name": "Try Modify While Suspended"},
        headers=headers(101),
    )
    assert res_suspended_put.status_code == 403
    assert "suspended" in res_suspended_put.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 8. Invalid input returns a validation error (422)
# ---------------------------------------------------------------------------
def test_invalid_input_returns_validation_error(client, headers, prefix):
    # Name too short (< 2 characters)
    res_short_name = client.put(
        f"{prefix}/seller/me",
        json={"name": "A"},
        headers=headers(4),
    )
    assert res_short_name.status_code == 422

    # Phone too long (> 50 characters)
    res_long_phone = client.put(
        f"{prefix}/seller/me",
        json={"phone": "1" * 51},
        headers=headers(4),
    )
    assert res_long_phone.status_code == 422

    # Address too long (> 255 characters)
    res_long_address = client.put(
        f"{prefix}/seller/me",
        json={"address": "x" * 256},
        headers=headers(4),
    )
    assert res_long_address.status_code == 422
