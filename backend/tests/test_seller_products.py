import pytest
from sqlalchemy import select

from app.db.database import SessionLocal
from app.models.category import Category
from app.models.product import Product
from app.models.seller import Seller
from app.models.user import User


@pytest.fixture(params=["/api", "/api/v1"])
def prefix(request):
    return request.param


# ---------------------------------------------------------------------------
# 1. Seller sees only their products
# ---------------------------------------------------------------------------
def test_seller_sees_only_own_products(client, headers, prefix):
    # User 4 is seller for Store 1 (owns Product 1: "Fixture product")
    response = client.get(f"{prefix}/seller/products", headers=headers(4))
    assert response.status_code == 200
    data = response.json()["data"]
    assert "items" in data
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == 1
    assert data["items"][0]["name"] == "Fixture product"
    assert data["items"][0]["seller_id"] == 1

    # Also verify alias /sellers/products
    alias_response = client.get(f"{prefix}/sellers/products", headers=headers(4))
    assert alias_response.status_code == 200
    assert alias_response.json()["data"]["items"][0]["name"] == "Fixture product"


# ---------------------------------------------------------------------------
# 2. Seller cannot see another seller's products
# ---------------------------------------------------------------------------
def test_seller_cannot_see_other_seller_products(client, headers, prefix):
    # User 4 (Seller 1) gets products
    res1 = client.get(f"{prefix}/seller/products", headers=headers(4))
    item_ids_1 = [p["id"] for p in res1.json()["data"]["items"]]
    assert 1 in item_ids_1
    assert 2 not in item_ids_1

    # User 5 (Seller 2) gets products (owns Product 2: "Other product")
    res2 = client.get(f"{prefix}/seller/products", headers=headers(5))
    assert res2.status_code == 200
    item_ids_2 = [p["id"] for p in res2.json()["data"]["items"]]
    assert 2 in item_ids_2
    assert 1 not in item_ids_2

    # Even if User 4 attempts to pass seller_id=2 in query params, it is ignored
    res_tamper = client.get(f"{prefix}/seller/products?seller_id=2", headers=headers(4))
    assert res_tamper.status_code == 200
    tampered_ids = [p["id"] for p in res_tamper.json()["data"]["items"]]
    assert tampered_ids == [1]
    assert 2 not in tampered_ids


# ---------------------------------------------------------------------------
# 3. Customer access is rejected with 403 Forbidden
# ---------------------------------------------------------------------------
def test_customer_cannot_access_seller_products(client, headers, prefix):
    # User 2 is a customer
    res = client.get(f"{prefix}/seller/products", headers=headers(2))
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# 4. Unauthenticated access is rejected with 401 Unauthorized
# ---------------------------------------------------------------------------
def test_unauthenticated_cannot_access_seller_products(client, prefix):
    res = client.get(f"{prefix}/seller/products")
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# 5. Search by product name and description
# ---------------------------------------------------------------------------
def test_seller_products_search(client, headers, prefix):
    # Match existing product
    res_match = client.get(f"{prefix}/seller/products?search=Fixture", headers=headers(4))
    assert res_match.status_code == 200
    assert res_match.json()["data"]["total"] == 1
    assert res_match.json()["data"]["items"][0]["name"] == "Fixture product"

    # Search with no match
    res_nomatch = client.get(f"{prefix}/seller/products?search=NonExistentProduct", headers=headers(4))
    assert res_nomatch.status_code == 200
    assert res_nomatch.json()["data"]["total"] == 0
    assert len(res_nomatch.json()["data"]["items"]) == 0


# ---------------------------------------------------------------------------
# 6. Category filtering
# ---------------------------------------------------------------------------
def test_seller_products_category_filter(client, headers, prefix):
    # Category 1 exists
    res_cat1 = client.get(f"{prefix}/seller/products?category_id=1", headers=headers(4))
    assert res_cat1.status_code == 200
    assert res_cat1.json()["data"]["total"] == 1

    # Category 999 does not exist for this seller
    res_cat999 = client.get(f"{prefix}/seller/products?category_id=999", headers=headers(4))
    assert res_cat999.status_code == 200
    assert res_cat999.json()["data"]["total"] == 0


# ---------------------------------------------------------------------------
# 7. Status filtering (active, inactive, stock status)
# ---------------------------------------------------------------------------
def test_seller_products_status_filter(client, headers, prefix):
    # Product 1 for Seller 1 is active (is_active=True, stock=20)
    res_active = client.get(f"{prefix}/seller/products?status=active", headers=headers(4))
    assert res_active.status_code == 200
    assert res_active.json()["data"]["total"] == 1

    res_inactive = client.get(f"{prefix}/seller/products?status=inactive", headers=headers(4))
    assert res_inactive.status_code == 200
    assert res_inactive.json()["data"]["total"] == 0

    # Product 2 for Seller 2 is inactive (is_active=False)
    res_s2_inactive = client.get(f"{prefix}/seller/products?status=inactive", headers=headers(5))
    assert res_s2_inactive.status_code == 200
    assert res_s2_inactive.json()["data"]["total"] == 1

    res_s2_active = client.get(f"{prefix}/seller/products?status=active", headers=headers(5))
    assert res_s2_active.status_code == 200
    assert res_s2_active.json()["data"]["total"] == 0


# ---------------------------------------------------------------------------
# 8. Server-side pagination is bounded
# ---------------------------------------------------------------------------
def test_seller_products_pagination_bounded(client, headers, prefix):
    res = client.get(f"{prefix}/seller/products?page=1&limit=500", headers=headers(4))
    assert res.status_code == 200
    data = res.json()["data"]
    # Limit must be clamped to at most 100
    assert data["limit"] == 100
    assert data["page"] == 1

    # Negative or 0 page is clamped to 1
    res_neg = client.get(f"{prefix}/seller/products?page=1&limit=1", headers=headers(4))
    assert res_neg.status_code == 200
    assert res_neg.json()["data"]["limit"] == 1


# ---------------------------------------------------------------------------
# 9. Empty product list for seller with no products
# ---------------------------------------------------------------------------
def test_empty_product_list_works(client, headers, prefix, password_hash):
    # Create seller 3 with no products
    with SessionLocal() as db:
        new_seller_user = User(
            id=50,
            name="Empty Store Owner",
            email="empty_store@example.com",
            role="seller",
            password_hash=password_hash,
            is_active=True,
        )
        db.add(new_seller_user)
        db.flush()
        new_seller = Seller(
            id=50,
            user_id=50,
            name="Empty Store",
            owner_name="Empty Store Owner",
            email="empty_store@example.com",
            status="Active",
        )
        db.add(new_seller)
        db.commit()

    res = client.get(f"{prefix}/seller/products", headers=headers(50))
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["items"] == []
    assert data["total"] == 0
    assert data["total_pages"] == 1


# ---------------------------------------------------------------------------
# 10. Pending and suspended account behavior
# ---------------------------------------------------------------------------
def test_pending_and_suspended_seller_can_view_products(client, headers, prefix, password_hash):
    with SessionLocal() as db:
        # Pending seller with 1 product
        p_user = User(id=60, name="Pending Seller", email="pend_prod@example.com", role="seller", password_hash=password_hash, is_active=True)
        db.add(p_user)
        db.flush()
        p_seller = Seller(id=60, user_id=60, name="Pending Store", owner_name="Owner P", email="pend_prod@example.com", status="Pending")
        db.add(p_seller)
        db.flush()
        db.add(Product(id=60, category_id=1, seller_id=60, name="Pending Product", price=15, stock=5, is_active=False))

        # Suspended seller with 1 product
        s_user = User(id=61, name="Suspended Seller", email="susp_prod@example.com", role="seller", password_hash=password_hash, is_active=True)
        db.add(s_user)
        db.flush()
        s_seller = Seller(id=61, user_id=61, name="Suspended Store", owner_name="Owner S", email="susp_prod@example.com", status="Suspended")
        db.add(s_seller)
        db.flush()
        db.add(Product(id=61, category_id=1, seller_id=61, name="Suspended Product", price=25, stock=10, is_active=False))
        db.commit()

    # Pending seller reads own products
    res_pending = client.get(f"{prefix}/seller/products", headers=headers(60))
    assert res_pending.status_code == 200
    assert res_pending.json()["data"]["total"] == 1
    assert res_pending.json()["data"]["items"][0]["name"] == "Pending Product"

    # Suspended seller reads own products
    res_suspended = client.get(f"{prefix}/seller/products", headers=headers(61))
    assert res_suspended.status_code == 200
    assert res_suspended.json()["data"]["total"] == 1
    assert res_suspended.json()["data"]["items"][0]["name"] == "Suspended Product"


# ---------------------------------------------------------------------------
# 11. Seller account without a store returns 404
# ---------------------------------------------------------------------------
def test_seller_without_store_returns_404(client, headers, prefix, password_hash):
    with SessionLocal() as db:
        orphan = User(id=70, name="Orphan", email="orphan_prod@example.com", role="seller", password_hash=password_hash, is_active=True)
        db.add(orphan)
        db.commit()

    res = client.get(f"{prefix}/seller/products", headers=headers(70))
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()
