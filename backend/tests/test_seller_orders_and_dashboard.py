"""Tests for Seller Orders, Seller Dashboard, and Order Detail seller scoping."""

from app.db.database import SessionLocal
from app.models.product import Product


def test_seller_dashboard_and_orders_endpoints(client, admin_headers, headers):
    # Customers are denied
    assert client.get("/api/v1/seller/dashboard", headers=headers(2)).status_code == 403
    assert client.get("/api/v1/seller/orders", headers=headers(2)).status_code == 403

    # Activate product 2 (seller 2) so we can test a multi-seller order as well
    with SessionLocal() as db:
        prod2 = db.get(Product, 2)
        prod2.is_active = True
        prod1 = db.get(Product, 1)
        prod1.stock = 5  # low stock (< 10)
        db.commit()

    # Order 1: single-seller (Seller 1 only)
    o1 = client.post(
        "/api/v1/orders",
        json={
            "shipping_address": "Phnom Penh Street 1",
            "payment_method": "Cash on Delivery",
            "items": [{"product_id": 1, "quantity": 2}],
        },
        headers=headers(2),
    )
    assert o1.status_code == 201
    o1_id = o1.json()["data"]["id"]

    # Order 2: multi-seller (Seller 1 + Seller 2)
    o2 = client.post(
        "/api/v1/orders",
        json={
            "shipping_address": "Siem Reap Street 2",
            "payment_method": "Cash on Delivery",
            "items": [
                {"product_id": 1, "quantity": 1},
                {"product_id": 2, "quantity": 1},
            ],
        },
        headers=headers(3),
    )
    assert o2.status_code == 201
    o2_id = o2.json()["data"]["id"]

    # Order 3: Seller 2 only (Seller 1 must NOT see it!)
    o3 = client.post(
        "/api/v1/orders",
        json={
            "shipping_address": "Battambang Street 3",
            "payment_method": "Cash on Delivery",
            "items": [{"product_id": 2, "quantity": 1}],
        },
        headers=headers(3),
    )
    assert o3.status_code == 201
    o3_id = o3.json()["data"]["id"]

    # Seller 1 dashboard KPIs
    dash_res = client.get("/api/v1/seller/dashboard", headers=headers(4))
    assert dash_res.status_code == 200, dash_res.text
    dash = dash_res.json()["data"]
    assert dash["seller_id"] == 1
    assert dash["total_products"] == 1
    assert dash["low_stock_products_count"] == 1
    assert dash["total_orders"] == 2
    assert dash["pending_orders"] == 2
    # Product 1 is $20; 2 + 1 = 3 units sold across o1 & o2 => $60.00
    assert float(dash["gross_revenue"]) == 60.0

    # Seller 1 orders listing
    orders_res = client.get("/api/v1/seller/orders", headers=headers(4))
    assert orders_res.status_code == 200, orders_res.text
    items = orders_res.json()["data"]["items"]
    returned_ids = [o["id"] for o in items]
    assert returned_ids == [o2_id, o1_id]
    assert o3_id not in returned_ids

    o1_row = next(o for o in items if o["id"] == o1_id)
    assert o1_row["can_update_status"] is True
    assert float(o1_row["seller_subtotal"]) == 40.0

    o2_row = next(o for o in items if o["id"] == o2_id)
    assert o2_row["can_update_status"] is False
    assert len(o2_row["seller_items"]) == 1
    assert float(o2_row["seller_subtotal"]) == 20.0

    # Search filter by address / order ID
    search_res = client.get("/api/v1/seller/orders?search=Siem", headers=headers(4))
    assert [o["id"] for o in search_res.json()["data"]["items"]] == [o2_id]

    # Seller 1 can advance status on single-seller order o1, and view o1 & o2 detail, but gets 404 for o3
    assert client.put(f"/api/v1/orders/{o1_id}/status", json={"status": "processing"}, headers=headers(4)).status_code == 200
    assert client.get(f"/api/v1/orders/{o1_id}", headers=headers(4)).status_code == 200
    assert client.get(f"/api/v1/orders/{o2_id}", headers=headers(4)).status_code == 200
    assert client.get(f"/api/v1/orders/{o3_id}", headers=headers(4)).status_code == 404
