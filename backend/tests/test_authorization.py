from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.db.database import SessionLocal
from app.models.notification import Notification
from app.models.order import Order
from app.models.product import Product
from app.models.review import Review
from app.models.seller import Seller
from app.models.user import User


ADMIN_OPERATIONS = [
    ("GET", "/users", None), ("GET", "/users/2", None),
    ("POST", "/users", {"name": "New", "email": "new@example.com", "password": "Test-password-123", "role": "admin"}),
    ("PUT", "/users/2", {"role": "admin"}), ("DELETE", "/users/2", None),
    ("POST", "/categories", {"name": "New"}),
    ("PUT", "/categories/1", {"name": "Changed"}), ("DELETE", "/categories/1", None),
    ("POST", "/sellers", {"name": "New Store", "owner_name": "Owner", "email": "new@example.com"}),
    ("PUT", "/sellers/1", {"status": "Suspended"}), ("DELETE", "/sellers/1", None),
    ("GET", "/orders/all", None), ("PUT", "/orders/1/status", {"status": "delivered"}),
    ("DELETE", "/orders/1", None), ("GET", "/stats/overview", None),
    ("PUT", "/reviews/1/status", {"status": "approved"}), ("DELETE", "/reviews/1", None),
    ("POST", "/notifications", {"title": "Fake", "message": "Fake", "user_id": 3}),
    ("POST", "/pos/checkout", {"items": [{"product_id": 1, "quantity": 1}]}),
    ("GET", "/pos/summary", None), ("GET", "/pos/customers", None),
    ("GET", "/coupons", None),
    ("POST", "/coupons", {"code": "ADMINTEST", "discount_type": "percent", "discount_value": 10}),
]
SELLER_OPERATIONS = [
    ("POST", "/products", {"category_id": 1, "seller_id": 1, "name": "New", "price": 12}),
    ("PUT", "/products/1", {"price": 1}), ("DELETE", "/products/1", None),
    ("PUT", "/reviews/1/reply", {"admin_reply": "Reply"}),
]


@pytest.fixture(params=["/api", "/api/v1"])
def prefix(request):
    return request.param


@pytest.mark.parametrize("method,path,payload", ADMIN_OPERATIONS + SELLER_OPERATIONS)
@pytest.mark.parametrize("user_id,expected", [(None, 401), (2, 403), (6, 403), (7, 403), (8, 403)])
def test_privileged_denials(client, headers, prefix, method, path, payload, user_id, expected):
    response = client.request(method, prefix + path, json=payload,
                              headers=headers(user_id) if user_id else {})
    assert response.status_code == expected, response.text


@pytest.mark.parametrize("method,path,payload", ADMIN_OPERATIONS)
def test_seller_cannot_use_global_admin_operations(client, headers, prefix, method, path, payload):
    assert client.request(method, prefix + path, json=payload, headers=headers(4)).status_code == 403


def test_admin_and_role_validation(client, headers, prefix):
    assert client.get(prefix + "/users", headers=headers(1)).status_code == 200
    assert client.post(prefix + "/categories", json={"name": "Authorized"}, headers=headers(1)).status_code == 201
    assert client.put(prefix + "/users/2", json={"role": "invalid"}, headers=headers(1)).status_code == 422
    assert client.put(prefix + "/users/2", json={"role": "seller"}, headers=headers(1)).status_code == 200
    response = client.post(prefix + "/auth/register", json={"name": "New", "email": "register@example.com",
                           "password": "Register-password-123", "role": "admin"})
    assert response.status_code == 201
    assert response.json()["data"]["user"]["role"] == "customer"
    client.put(prefix + "/auth/me", json={"role": "admin"}, headers=headers(3))
    assert client.get(prefix + "/auth/me", headers=headers(3)).json()["data"]["role"] == "customer"


def test_seller_product_ownership(client, headers, prefix):
    assert client.put(prefix + "/products/1", json={"price": 25}, headers=headers(4)).status_code == 200
    assert client.put(prefix + "/products/2", json={"price": 1}, headers=headers(4)).status_code == 404
    assert client.delete(prefix + "/products/2", headers=headers(4)).status_code == 404
    for seller_id in (2, None):
        assert client.put(prefix + "/products/1", json={"seller_id": seller_id}, headers=headers(4)).status_code == 403
        assert client.post(prefix + "/products", json={"name": "Forged", "category_id": 1,
                           "seller_id": seller_id, "price": 1}, headers=headers(4)).status_code == 403
    assert client.post(prefix + "/products", json={"name": "Owned", "category_id": 1,
                       "seller_id": 1, "price": 15}, headers=headers(4)).status_code == 201
    with SessionLocal() as db:
        assert db.get(Product, 2).price == 30


def make_order():
    with SessionLocal() as db:
        order = Order(user_id=2, subtotal=20, total=22, shipping_fee=2,
                      shipping_address="Private address", payment_method="Cash on Delivery")
        db.add(order)
        db.commit()
        return order.id


def test_private_orders(client, headers, prefix):
    order_id = make_order()
    for user_id, expected in [(None, 401), (1, 200), (2, 200), (3, 404), (4, 404)]:
        response = client.get(f"{prefix}/orders/{order_id}", headers=headers(user_id) if user_id else {})
        assert response.status_code == expected
    assert client.get(prefix + "/orders", headers=headers(3)).json()["data"] == []


def test_notification_scope(client, headers, prefix):
    with SessionLocal() as db:
        db.add_all([Notification(id=1, user_id=2, title="Own", message="Private"),
                    Notification(id=2, user_id=3, title="Other", message="Private"),
                    Notification(id=3, title="Operational", message="Private")])
        db.commit()
    for method, path in [("GET", "/notifications"), ("GET", "/notifications/unread-count"),
                         ("POST", "/notifications/read-all"), ("DELETE", "/notifications"),
                         ("PATCH", "/notifications/2/read"), ("DELETE", "/notifications/2")]:
        assert client.request(method, prefix + path).status_code == 401
    data = client.get(prefix + "/notifications", headers=headers(2)).json()
    assert [n["id"] for n in data["data"]] == [1]
    assert data["unread_count"] == 1
    for notification_id in (2, 3):
        assert client.patch(f"{prefix}/notifications/{notification_id}/read", headers=headers(2)).status_code == 404
        assert client.delete(f"{prefix}/notifications/{notification_id}", headers=headers(2)).status_code == 404
    assert client.post(prefix + "/notifications/read-all", headers=headers(2)).json()["updated_count"] == 1
    assert client.delete(prefix + "/notifications", headers=headers(2)).json()["deleted_count"] == 1
    with SessionLocal() as db:
        assert not db.get(Notification, 2).read
        assert not db.get(Notification, 3).read
    assert client.get(prefix + "/notifications", headers=headers(1)).json()["data"] == []
    assert [n["id"] for n in client.get(prefix + "/notifications/admin", headers=headers(1)).json()["data"]] == [3]


def test_public_visibility_and_seller_privacy(client, headers, prefix):
    for path in ["/products", "/products/search", "/products/featured", "/categories/1/products"]:
        response = client.get(prefix + path)
        assert response.status_code == 200
        assert [p["id"] for p in response.json()["data"]["items"]] == [1]
        assert "email" not in response.json()["data"]["items"][0]["seller"]
    assert client.get(prefix + "/products/2").status_code == 404
    assert client.get(prefix + "/products/2", headers=headers(4)).status_code == 404
    assert client.get(prefix + "/products/2", headers=headers(5)).status_code == 200
    assert client.get(prefix + "/products/2", headers=headers(1)).status_code == 200
    for user_id in (None, 2, 4):
        data = client.get(prefix + "/sellers/2", headers=headers(user_id) if user_id else {}).json()["data"]
        assert "total_revenue" not in data and "email" not in data and "user_id" not in data
    assert "total_revenue" in client.get(prefix + "/sellers/2", headers=headers(5)).json()["data"]


def test_reviews(client, headers, prefix):
    with SessionLocal() as db:
        db.add_all([Review(id=1, user_id=2, product_id=1, rating=4, comment="Pending", status="pending"),
                    Review(id=2, user_id=3, product_id=2, rating=5, comment="Approved", status="approved")])
        db.commit()
    reviews = client.get(prefix + "/reviews?status=all").json()["data"]
    assert [r["id"] for r in reviews] == [2]
    assert "email" not in reviews[0]["user"]
    assert client.get(prefix + "/reviews/1").status_code == 404
    assert client.get(prefix + "/reviews/1", headers=headers(2)).status_code == 200
    assert client.put(prefix + "/reviews/2/reply", json={"admin_reply": "Forged"}, headers=headers(4)).status_code == 404
    response = client.put(prefix + "/reviews/1/reply", json={"admin_reply": "Owned"}, headers=headers(4))
    assert response.status_code == 200
    assert "email" not in response.json()["data"]["user"]
    assert client.put(prefix + "/reviews/1/status", json={"status": "approved"}, headers=headers(1)).status_code == 200


def test_expired_invalid_and_inactive_sessions(client, headers, prefix):
    expired = create_access_token({"sub": "1"}, expires_delta=timedelta(seconds=-1))
    for token in ["invalid", expired]:
        for path in ["/users", "/notifications", "/products"]:
            assert client.get(prefix + path, headers={"Authorization": f"Bearer {token}"}).status_code == 401
    with SessionLocal() as db:
        db.get(User, 1).is_active = False
        db.commit()
    assert client.get(prefix + "/users", headers=headers(1)).status_code == 403


def _valid_png_fixture() -> bytes:
    import struct
    import zlib

    def chunk(tag: bytes, payload: bytes) -> bytes:
        crc = zlib.crc32(tag + payload) & 0xFFFFFFFF
        return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\x12\x34\x56")
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def test_upload_access(client, headers, prefix):
    png_bytes = _valid_png_fixture()
    for user_id, expected in [(None, 401), (2, 403), (6, 403), (4, 201), (1, 201)]:
        response = client.post(prefix + "/upload/image", files={"file": ("fixture.png", png_bytes, "image/png")},
                               headers=headers(user_id) if user_id else {})
        assert response.status_code == expected


def test_customer_address_cart_favorite_ownership(client, headers, prefix):
    address = client.post(prefix + "/addresses", json={
        "full_name": "Owner", "phone": "123456789", "address_line": "Private",
        "city": "Test city", "user_id": 3,
    }, headers=headers(2))
    assert address.status_code == 201
    address_id = address.json()["data"]["id"]
    assert client.get(prefix + "/addresses", headers=headers(3)).json()["data"] == []
    for method, path, payload in [("PUT", f"/addresses/{address_id}", {"city": "Changed"}),
                                  ("PUT", f"/addresses/{address_id}/default", None),
                                  ("DELETE", f"/addresses/{address_id}", None)]:
        assert client.request(method, prefix + path, json=payload, headers=headers(3)).status_code == 404
    assert client.put(f"{prefix}/addresses/{address_id}", json={"city": "Owned"}, headers=headers(2)).status_code == 200
    assert client.post(prefix + "/cart/items", json={"product_id": 1, "quantity": 2, "user_id": 3}, headers=headers(2)).status_code in (200, 201)
    own_cart = client.get(prefix + "/cart", headers=headers(2)).json()["data"]
    item_id = own_cart["items"][0]["id"]
    assert client.get(prefix + "/cart", headers=headers(3)).json()["data"]["items"] == []
    for path in [f"/cart/{item_id}", f"/cart/items/{item_id}"]:
        assert client.put(prefix + path, json={"quantity": 1}, headers=headers(3)).status_code == 404
        assert client.delete(prefix + path, headers=headers(3)).status_code == 404
    client.delete(prefix + "/cart", headers=headers(3))
    assert len(client.get(prefix + "/cart", headers=headers(2)).json()["data"]["items"]) == 1
    assert client.post(prefix + "/favorites/1", headers=headers(2)).status_code in (200, 201)
    assert client.get(prefix + "/favorites", headers=headers(3)).json()["data"] == []
    client.delete(prefix + "/favorites/1", headers=headers(3))
    assert len(client.get(prefix + "/favorites", headers=headers(2)).json()["data"]) == 1


def test_review_cannot_reference_another_customers_order(client, headers, prefix):
    order_id = make_order()
    response = client.post(prefix + "/reviews/product/1", json={
        "rating": 5, "comment": "Forged purchase", "order_id": order_id,
    }, headers=headers(3))
    assert response.status_code == 404
    with SessionLocal() as db:
        assert db.scalar(select(Review.id)) is None


def test_unlinked_suspended_and_multiple_store_ownership(client, headers, prefix):
    with SessionLocal() as db:
        db.get(Seller, 1).status = "Suspended"
        db.commit()
    assert client.put(prefix + "/products/1", json={"stock": 1}, headers=headers(4)).status_code == 404
    assert client.post(prefix + "/upload/image", files={"file": ("fixture.png", b"fixture", "image/png")},
                       headers=headers(4)).status_code == 403
    with SessionLocal() as db:
        db.get(Seller, 1).user_id = None
        db.get(Seller, 1).status = "Active"
        db.commit()
    assert client.put(prefix + "/products/1", json={"stock": 1}, headers=headers(4)).status_code == 404
    with SessionLocal() as db:
        db.get(Seller, 1).user_id = 5
        db.commit()
    for product_id in (1, 2):
        assert client.put(f"{prefix}/products/{product_id}", json={"stock": 19}, headers=headers(5)).status_code == 200


def test_authorization_uses_database_role_not_token_claim(client, prefix):
    token = create_access_token({"sub": "2", "role": "admin"})
    assert client.get(prefix + "/users", headers={"Authorization": f"Bearer {token}"}).status_code == 403


def test_db_test_endpoint_requires_admin(client, headers):
    for user_id, expected in [(None, 401), (2, 403), (4, 403), (6, 403), (7, 403), (8, 403)]:
        response = client.get("/db-test", headers=headers(user_id) if user_id else {})
        assert response.status_code == expected, response.text

    forged = create_access_token({"sub": "2", "role": "admin"})
    assert client.get("/db-test", headers={"Authorization": f"Bearer {forged}"}).status_code == 403
    assert client.get("/db-test", headers={"Authorization": "Bearer invalid"}).status_code == 401

    admin_response = client.get("/db-test", headers=headers(1))
    assert admin_response.status_code == 200
    payload = admin_response.json()
    assert payload["connection"] == "success"
    assert payload["test_value"] == 1
    assert payload["database"] == "sqlite"
