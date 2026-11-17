import pytest
from decimal import Decimal
from app.db.database import SessionLocal
from app.models.order import Order, OrderItem


def _create_order(
    user_id: int = 2,
    total: Decimal = Decimal("50.00"),
    status: str = "pending",
    payment_status: str = "pending",
    payment_method: str = "Cash on Delivery",
) -> int:
    """Helper to insert an order record directly into test database."""
    with SessionLocal() as db:
        order = Order(
            user_id=user_id,
            total=total,
            subtotal=total,
            discount_amount=Decimal("0.00"),
            shipping_fee=Decimal("0.00"),
            status=status,
            payment_status=payment_status,
            payment_method=payment_method,
            shipping_address="Phnom Penh, Cambodia",
        )
        db.add(order)
        db.flush()
        order_item = OrderItem(
            order_id=order.id,
            product_id=1,
            product_name="Fixture product",
            price=Decimal("20.00"),
            quantity=1,
            subtotal=Decimal("20.00"),
        )
        db.add(order_item)
        db.commit()
        return order.id


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_stats_zero_orders(client, admin_headers, prefix):
    """When no orders exist in the system, revenue is 0.00 and order count is 0."""
    res = client.get(f"{prefix}/stats/overview", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["total_orders"] == 0
    assert data["total_revenue"] == 0.0
    assert data["pending_orders_count"] == 0
    assert data["processing_orders_count"] == 0
    assert data["delivered_orders_count"] == 0


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_stats_pending_orders_do_not_count_as_revenue(client, admin_headers, prefix):
    """
    CRITICAL REGRESSION TEST:
    Verifies that unpaid/pending orders (such as newly placed COD orders)
    do NOT count as recognized revenue.
    The prior buggy behavior fell back to summing all orders when paid revenue was 0.
    """
    # Create 3 pending orders with total value $150.00
    _create_order(user_id=2, total=Decimal("50.00"), status="pending", payment_status="pending")
    _create_order(user_id=2, total=Decimal("60.00"), status="pending", payment_status="pending")
    _create_order(user_id=3, total=Decimal("40.00"), status="processing", payment_status="pending")

    res = client.get(f"{prefix}/stats/overview", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()["data"]

    # Order counts are accurately tracked
    assert data["total_orders"] == 3
    assert data["pending_orders_count"] == 2
    assert data["processing_orders_count"] == 1

    # Recognized revenue MUST BE EXACTLY ZERO, NOT $150.00!
    assert data["total_revenue"] == 0.0, (
        f"Expected total_revenue to be 0.0 for pending orders, got {data['total_revenue']}"
    )


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_stats_paid_orders_recognized(client, admin_headers, prefix):
    """Orders with payment_status='paid' are correctly summed into total_revenue."""
    _create_order(user_id=2, total=Decimal("120.50"), status="delivered", payment_status="paid")
    _create_order(user_id=3, total=Decimal("79.50"), status="processing", payment_status="paid")

    res = client.get(f"{prefix}/stats/overview", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()["data"]

    assert data["total_orders"] == 2
    assert data["total_revenue"] == 200.0  # 120.50 + 79.50


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_stats_cancelled_orders_excluded_from_revenue(client, admin_headers, prefix):
    """Cancelled orders are never counted as recognized revenue."""
    # Cancelled order with payment_status='paid' (e.g. prior to refund recording) or 'pending'
    _create_order(user_id=2, total=Decimal("200.00"), status="cancelled", payment_status="paid")
    _create_order(user_id=3, total=Decimal("100.00"), status="cancelled", payment_status="pending")

    res = client.get(f"{prefix}/stats/overview", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()["data"]

    assert data["total_orders"] == 2
    assert data["total_revenue"] == 0.0


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_stats_mixed_payment_statuses(client, admin_headers, prefix):
    """In a mixed environment, only active paid orders contribute to total_revenue."""
    # 1. Paid active order -> contributes $100.00
    _create_order(user_id=2, total=Decimal("100.00"), status="processing", payment_status="paid")

    # 2. Paid delivered order -> contributes $250.00
    _create_order(user_id=3, total=Decimal("250.00"), status="delivered", payment_status="paid")

    # 3. Pending COD order -> should NOT contribute
    _create_order(user_id=2, total=Decimal("75.00"), status="pending", payment_status="pending")

    # 4. Failed payment order -> should NOT contribute
    _create_order(user_id=3, total=Decimal("150.00"), status="pending", payment_status="failed")

    # 5. Refunded order -> should NOT contribute
    _create_order(user_id=2, total=Decimal("50.00"), status="delivered", payment_status="refunded")

    # 6. Cancelled order -> should NOT contribute
    _create_order(user_id=3, total=Decimal("80.00"), status="cancelled", payment_status="paid")

    res = client.get(f"{prefix}/stats/overview", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()["data"]

    assert data["total_orders"] == 6
    # Total revenue must be exactly 100.00 + 250.00 = 350.00
    assert data["total_revenue"] == 350.0


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_stats_cod_order_lifecycle_revenue_recognition(client, admin_headers, headers, prefix):
    """
    Verifies COD revenue recognition lifecycle:
    1. Order created with payment_status='pending' -> Revenue is $0.00.
    2. Admin confirms delivery and cash collection (payment_status='paid') -> Revenue becomes $62.00.
    3. Order is refunded (payment_status='refunded') -> Revenue drops back to $0.00.
    """
    user_header = headers(2)

    # 1. Customer places COD order for Product 1 (qty 3 = $60 + $2 shipping = $62)
    client.post(f"{prefix}/cart/items", json={"product_id": 1, "quantity": 3}, headers=user_header)
    order_res = client.post(
        f"{prefix}/orders",
        json={"shipping_address": "Street 2004, Phnom Penh", "payment_method": "Cash on Delivery"},
        headers=user_header,
    )
    assert order_res.status_code in (200, 201)
    order_id = order_res.json()["data"]["id"]
    order_total = order_res.json()["data"]["total"]

    # Initial check: Revenue must be 0.00
    stats1 = client.get(f"{prefix}/stats/overview", headers=admin_headers).json()["data"]
    assert stats1["total_orders"] == 1
    assert stats1["pending_orders_count"] == 1
    assert stats1["total_revenue"] == 0.0

    # 2. Dispatch order (processing -> shipped -> delivered)
    client.put(f"{prefix}/orders/{order_id}/status", json={"status": "processing"}, headers=admin_headers)
    client.put(f"{prefix}/orders/{order_id}/status", json={"status": "shipped"}, headers=admin_headers)
    client.put(f"{prefix}/orders/{order_id}/status", json={"status": "delivered"}, headers=admin_headers)

    # Still unpaid (delivery courier has not settled cash yet) -> Revenue must remain 0.00
    stats2 = client.get(f"{prefix}/stats/overview", headers=admin_headers).json()["data"]
    assert stats2["delivered_orders_count"] == 1
    assert stats2["total_revenue"] == 0.0

    # 3. Cash collected & verified -> Admin updates payment_status to 'paid' with required audit reason
    pay_res = client.put(
        f"{prefix}/orders/{order_id}/status",
        json={"payment_status": "paid", "reason": "Courier COD cash collection #12345"},
        headers=admin_headers,
    )
    assert pay_res.status_code == 200
    assert pay_res.json()["data"]["payment_status"] == "paid"

    # Now revenue is recognized!
    stats3 = client.get(f"{prefix}/stats/overview", headers=admin_headers).json()["data"]
    assert stats3["total_revenue"] == order_total  # Exactly 62.0

    # 4. If refunded later -> payment_status set to 'refunded' with required audit reason
    ref_res = client.put(
        f"{prefix}/orders/{order_id}/status",
        json={"payment_status": "refunded", "reason": "Customer return receipt #12345"},
        headers=admin_headers,
    )
    assert ref_res.status_code == 200
    stats4 = client.get(f"{prefix}/stats/overview", headers=admin_headers).json()["data"]
    assert stats4["total_revenue"] == 0.0
