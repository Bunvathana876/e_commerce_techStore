import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_api_root():
    response = client.get("/?format=json")
    assert response.status_code == 200
    assert response.json()["status"] == "success"

def test_categories_and_products():
    # Test categories
    cat_res = client.get("/api/categories")
    assert cat_res.status_code == 200
    cat_data = cat_res.json()
    assert cat_data["success"] is True
    assert len(cat_data["data"]) > 0

    # Test products
    prod_res = client.get("/api/products")
    assert prod_res.status_code == 200
    prod_data = prod_res.json()
    assert prod_data["success"] is True
    assert len(prod_data["data"]["items"]) > 0

    # Test price sorting
    sort_asc_res = client.get("/api/products?sort=price_asc")
    assert sort_asc_res.status_code == 200
    items_asc = sort_asc_res.json()["data"]["items"]
    assert len(items_asc) > 0

    # Test min_rating filter
    rating_res = client.get("/api/products?min_rating=4.0")
    assert rating_res.status_code == 200
    rating_items = rating_res.json()["data"]["items"]
    for item in rating_items:
        assert float(item["rating"]) >= 4.0

    # Test search filter
    search_res = client.get("/api/products?search=Nike")
    assert search_res.status_code == 200


def test_image_upload(admin_headers):
    import io
    import struct

    valid_jpeg_bytes = (
        b"\xff\xd8"
        + b"\xff\xdb" + struct.pack(">HB", 67, 0) + (b"\x08" * 64)
        + b"\xff\xc0" + struct.pack(">HBHHBBBB", 11, 8, 1, 1, 1, 1, 0x11, 0)
        + b"\xff\xda" + struct.pack(">HBBBBBB", 8, 1, 1, 0x00, 0, 63, 0)
        + b"\x7f"
        + b"\xff\xd9"
    )
    valid_image = io.BytesIO(valid_jpeg_bytes)

    response = client.post(
        "/api/upload/image",
        files={"file": ("test_product.jpg", valid_image, "image/jpeg")},
        headers=admin_headers,
    )
    assert response.status_code == 201
    json_data = response.json()
    assert json_data["success"] is True
    assert "prod_" in json_data["data"]["filename"]
    assert "test_product.jpg" not in json_data["data"]["filename"]
    assert "/uploads/products/" in json_data["data"]["url"]

    # Verify static file serving
    relative_url = json_data["data"]["relative_url"]
    static_res = client.get(relative_url)
    assert static_res.status_code == 200
    assert static_res.content == valid_jpeg_bytes



def test_full_user_flow(admin_headers):
    import uuid
    unique_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    
    # 1. Register
    reg_res = client.post(
        "/api/auth/register",
        json={
            "email": unique_email,
            "password": "Password123!",
            "name": "Integration Tester",
            "phone": "1234567890",
        },
    )
    assert reg_res.status_code == 201
    token = reg_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Get Profile
    me_res = client.get("/api/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["data"]["email"] == unique_email

    # 3. Add to Cart
    prod_res = client.get("/api/products")
    product_id = prod_res.json()["data"]["items"][0]["id"]
    
    cart_add_res = client.post(
        "/api/cart/items",
        json={"product_id": product_id, "quantity": 2},
        headers=headers,
    )
    assert cart_add_res.status_code in [200, 201]
    
    cart_get_res = client.get("/api/cart", headers=headers)
    assert cart_get_res.status_code == 200
    assert len(cart_get_res.json()["data"]["items"]) == 1

    # 4. Add to Favorites
    fav_res = client.post(f"/api/favorites/{product_id}", headers=headers)
    assert fav_res.status_code in [200, 201]
    fav_list_res = client.get("/api/favorites", headers=headers)
    assert fav_list_res.status_code == 200
    assert len(fav_list_res.json()["data"]) == 1

    # 5. Create Address
    addr_res = client.post(
        "/api/addresses",
        json={
            "full_name": "Integration Tester",
            "phone": "012345678",
            "address_line": "123 Test Street",
            "city": "Phnom Penh",
            "province": "Phnom Penh",
            "postal_code": "12000",
            "is_default": True,
        },
        headers=headers,
    )
    assert addr_res.status_code == 201
    address_id = addr_res.json()["data"]["id"]

    # 5.5 Validate Coupons
    avail_coupons_res = client.get("/api/coupons/available")
    assert avail_coupons_res.status_code == 200
    assert len(avail_coupons_res.json()["data"]) >= 1

    # Invalid coupon code
    invalid_coupon_res = client.post(
        "/api/coupons/validate",
        json={"code": "INVALID99", "subtotal": 100.0},
    )
    assert invalid_coupon_res.status_code == 404

    # Valid coupon code WELCOME10 (10% off)
    valid_coupon_res = client.post(
        "/api/coupons/validate",
        json={"code": "WELCOME10", "subtotal": 100.0},
    )
    assert valid_coupon_res.status_code == 200
    assert valid_coupon_res.json()["data"]["valid"] is True
    assert float(valid_coupon_res.json()["data"]["discount_amount"]) == 10.0

    # 6. Place Order with Coupon
    order_res = client.post(
        "/api/orders",
        json={
            "shipping_address_id": address_id,
            "payment_method": "Cash on Delivery",
            "shipping_fee": 2.0,
            "coupon_code": "WELCOME10",
        },
        headers=headers,
    )
    assert order_res.status_code == 201
    order_data = order_res.json()["data"]
    assert order_data["status"] == "pending"
    assert order_data["coupon_code"] == "WELCOME10"
    assert float(order_data["discount_amount"]) > 0
    assert len(order_data["items"]) == 1

    # 7. Verify Cart is now empty
    cart_after_order = client.get("/api/cart", headers=headers)
    assert len(cart_after_order.json()["data"]["items"]) == 0


    # 8. Get Orders list
    orders_res = client.get("/api/orders", headers=headers)
    assert orders_res.status_code == 200
    assert len(orders_res.json()["data"]) >= 1

    # 9. Get Order Details
    order_detail_res = client.get(f"/api/orders/{order_data['id']}", headers=headers)
    assert order_detail_res.status_code == 200
    assert order_detail_res.json()["data"]["id"] == order_data["id"]

    # 10. Update Profile (Name and Phone)
    update_profile_res = client.put(
        "/api/auth/me",
        json={"name": "Updated Tester Name", "phone": "0987654321"},
        headers=headers,
    )
    assert update_profile_res.status_code == 200
    assert update_profile_res.json()["data"]["name"] == "Updated Tester Name"
    assert update_profile_res.json()["data"]["phone"] == "0987654321"

    # 11. Change Password (fail on wrong current password)
    wrong_pw_res = client.put(
        "/api/auth/change-password",
        json={"current_password": "WrongPassword!", "new_password": "NewPassword123!"},
        headers=headers,
    )
    assert wrong_pw_res.status_code == 400

    # 12. Change Password (successful)
    change_pw_res = client.put(
        "/api/auth/change-password",
        json={"current_password": "Password123!", "new_password": "NewPassword123!"},
        headers=headers,
    )
    assert change_pw_res.status_code == 200

    # 13. Login with new password
    login_new_res = client.post(
        "/api/auth/login",
        json={"email": unique_email, "password": "NewPassword123!"},
    )
    assert login_new_res.status_code == 200
    user_id = login_new_res.json()["data"]["user"]["id"]
    assert login_new_res.json()["data"]["user"]["name"] == "Updated Tester Name"

    # 14. Delete user (admin / test cleanup)
    del_res = client.delete(f"/api/users/{user_id}", headers=admin_headers)
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # 15. Verify deleted user no longer exists
    get_del_res = client.get(f"/api/users/{user_id}", headers=admin_headers)
    assert get_del_res.status_code == 404


def test_password_policy_enforcement(client):
    """Test that NIST SP 800-63B password policy is enforced on registration."""
    # 1. Too short (< 8 chars)
    res_short = client.post(
        "/api/auth/register",
        json={"email": "short@example.com", "password": "short", "name": "Short Pwd"},
    )
    assert res_short.status_code == 400
    assert "at least 8 characters" in res_short.json()["detail"]

    # 2. Single repeated character
    res_repeat = client.post(
        "/api/auth/register",
        json={"email": "repeat@example.com", "password": "aaaaaaaaaaaa", "name": "Repeat Pwd"},
    )
    assert res_repeat.status_code == 400
    assert "single repeated character" in res_repeat.json()["detail"]

    # 3. Common trivial password
    res_trivial = client.post(
        "/api/auth/register",
        json={"email": "trivial@example.com", "password": "password123", "name": "Trivial Pwd"},
    )
    assert res_trivial.status_code == 400
    assert "too common or easily guessed" in res_trivial.json()["detail"]


def test_readiness_probe_and_security_headers(client):
    """Test /readyz database health probe and standard security headers."""
    # Liveness probe
    health_res = client.get("/health")
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "healthy"
    assert health_res.headers.get("X-Content-Type-Options") == "nosniff"
    assert health_res.headers.get("X-Frame-Options") == "DENY"

    # Readiness probe with database connectivity check
    ready_res = client.get("/readyz")
    assert ready_res.status_code == 200
    assert ready_res.json()["status"] == "ready"
    assert ready_res.json()["database"] == "connected"
    assert ready_res.headers.get("X-Content-Type-Options") == "nosniff"


def test_readiness_failure_does_not_expose_database_details(client):
    from app.db.database import get_db
    from app.main import app

    class UnavailableDatabase:
        def execute(self, statement):
            raise RuntimeError("private-host password=do-not-disclose")

    app.app.dependency_overrides[get_db] = lambda: UnavailableDatabase()
    try:
        response = client.get("/readyz")
        assert response.status_code == 503
        assert response.json() == {"detail": "Database is unavailable"}
        assert "private-host" not in response.text
    finally:
        app.app.dependency_overrides.pop(get_db, None)


def test_test_infrastructure_is_isolated():
    from app.core.config import settings
    from app.core.rate_limit import get_rate_limiter_manager, MemoryRateLimitStorage

    assert not settings.RATE_LIMIT_STORAGE_URL
    assert isinstance(get_rate_limiter_manager().storage, MemoryRateLimitStorage)
