"""Tests for controlled order cancellation and archival replacing direct deletion."""

from decimal import Decimal
import pytest
from sqlalchemy import select

from app.db.database import SessionLocal
from app.models.coupon import Coupon
from app.models.notification import Notification
from app.models.order import Order, OrderItem
from app.models.product import Product


def _create_order(
    client,
    buyer_headers: dict[str, str],
    prefix: str = "/api/v1",
    *,
    quantity: int = 2,
    coupon_code: str | None = None,
    payment_method: str = "Cash on Delivery",
) -> dict:
    """Helper to place an order through standard checkout."""
    cart_payload = {"product_id": 1, "quantity": quantity}
    cart_res = client.post(f"{prefix}/cart/items", headers=buyer_headers, json=cart_payload)
    assert cart_res.status_code in (200, 201), cart_res.text

    order_payload = {
        "shipping_address": "Building 4, Street 2004, Phnom Penh",
        "payment_method": payment_method,
    }
    if coupon_code:
        order_payload["coupon_code"] = coupon_code

    res = client.post(f"{prefix}/orders", headers=buyer_headers, json=order_payload)
    assert res.status_code == 201, res.text
    return res.json()["data"]


# ---------------------------------------------------------------------------
# 1. Pending order cancellation and archival
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_pending_order_deletion_cancels_archives_and_restores_stock_and_coupon(
    client, headers, admin_headers, prefix
):
    """Admin DELETE on a pending order cancels and archives it, restoring inventory and coupon usage."""
    # Product 1 starts with stock = 20
    with SessionLocal() as db:
        prod = db.get(Product, 1)
        assert prod is not None
        assert prod.stock == 20
        coup = db.scalar(select(Coupon).where(Coupon.code == "WELCOME10"))
        assert coup is not None
        assert coup.used_count == 0

    order_data = _create_order(
        client,
        headers(2),
        prefix=prefix,
        quantity=3,
        coupon_code="WELCOME10",
    )
    order_id = order_data["id"]

    # Stock should be deducted: 20 - 3 = 17, coupon used_count = 1
    with SessionLocal() as db:
        assert db.get(Product, 1).stock == 17
        coup = db.scalar(select(Coupon).where(Coupon.code == "WELCOME10"))
        assert coup.used_count == 1

    # Admin calls delete endpoint with audit reason
    del_res = client.delete(
        f"{prefix}/orders/{order_id}?reason=Customer+requested+cancellation",
        headers=admin_headers,
    )
    assert del_res.status_code == 200, del_res.text
    del_body = del_res.json()
    assert del_body["success"] is True
    assert "cancelled and archived" in del_body["message"].lower()
    assert del_body["data"]["status"] == "cancelled"

    # CRITICAL: Order and items must NOT be removed from the database
    with SessionLocal() as db:
        persisted_order = db.get(Order, order_id)
        assert persisted_order is not None, "Order must NOT be hard deleted from database"
        assert persisted_order.status == "cancelled"
        assert persisted_order.total == Decimal(str(order_data["total"]))

        # Items must remain intact for audit and financial tracking
        persisted_items = list(
            db.scalars(select(OrderItem).where(OrderItem.order_id == order_id)).all()
        )
        assert len(persisted_items) == 1
        assert persisted_items[0].product_id == 1
        assert persisted_items[0].quantity == 3

        # Stock must be restored: 17 + 3 = 20
        assert db.get(Product, 1).stock == 20

        # Coupon usage count must be restored: 1 -> 0
        coup = db.scalar(select(Coupon).where(Coupon.code == "WELCOME10"))
        assert coup.used_count == 0

        # Audit notifications must exist: admin audit + customer notification
        admin_audit = db.scalars(
            select(Notification).where(
                Notification.title.like("%Cancelled & Archived%"),
                Notification.message.like(f"%Order #{order_id}%"),
            )
        ).first()
        assert admin_audit is not None
        assert "Customer requested cancellation" in admin_audit.message

        cust_notif = db.scalars(
            select(Notification).where(
                Notification.user_id == 2,
                Notification.title.like(f"%Order #{order_id} Cancelled%"),
            )
        ).first()
        assert cust_notif is not None

    # Detail GET must still succeed and reflect cancelled status
    detail_res = client.get(f"{prefix}/orders/{order_id}", headers=admin_headers)
    assert detail_res.status_code == 200
    assert detail_res.json()["data"]["status"] == "cancelled"


# ---------------------------------------------------------------------------
# 2. Paid order deletion rejection (Financial Protection)
# ---------------------------------------------------------------------------


def test_paid_order_deletion_rejected_to_preserve_financial_records(
    client, headers, admin_headers
):
    """Paid orders cannot be deleted or cancelled without first recording a refund."""
    order_data = _create_order(
        client,
        headers(2),
        quantity=2,
    )
    order_id = order_data["id"]

    # Directly set payment_status='paid' while fulfillment is pending/processing
    with SessionLocal() as db:
        order = db.get(Order, order_id)
        assert order is not None
        order.payment_status = "paid"
        db.commit()

    # Stock at this point: 20 - 2 = 18, payment_status is 'paid'
    with SessionLocal() as db:
        assert db.get(Product, 1).stock == 18
        assert db.get(Order, order_id).payment_status == "paid"
        assert db.get(Order, order_id).status == "pending"

    # Attempting to delete a paid order must be rejected with 409 Conflict
    del_res = client.delete(
        f"/api/v1/orders/{order_id}",
        headers=admin_headers,
    )
    assert del_res.status_code == 409, del_res.text
    assert "paid" in del_res.json()["detail"].lower()
    assert "refund" in del_res.json()["detail"].lower()

    # Verify order is intact, financial revenue preserved, and stock was NOT restored
    with SessionLocal() as db:
        persisted = db.get(Order, order_id)
        assert persisted is not None
        assert persisted.status == "pending"
        assert persisted.payment_status == "paid"
        assert db.get(Product, 1).stock == 18


def test_shipped_paid_order_deletion_rejected(client, headers, admin_headers):
    """A shipped order that is also paid cannot be cancelled or deleted."""
    order_data = _create_order(
        client,
        headers(2),
        quantity=2,
        payment_method="Cash on Delivery",
    )
    order_id = order_data["id"]

    assert client.put(
        f"/api/v1/orders/{order_id}/status",
        headers=admin_headers,
        json={"status": "processing"},
    ).status_code == 200
    assert client.put(
        f"/api/v1/orders/{order_id}/status",
        headers=admin_headers,
        json={"status": "shipped"},
    ).status_code == 200
    assert client.put(
        f"/api/v1/orders/{order_id}/status",
        headers=admin_headers,
        json={"payment_status": "paid", "reason": "Courier cash receipt #991"},
    ).status_code == 200

    del_res = client.delete(f"/api/v1/orders/{order_id}", headers=admin_headers)
    assert del_res.status_code == 409
    assert "paid" in del_res.json()["detail"].lower() or "shipped" in del_res.json()["detail"].lower()

    with SessionLocal() as db:
        assert db.get(Product, 1).stock == 18
        persisted = db.get(Order, order_id)
        assert persisted is not None
        assert persisted.status == "shipped"


# ---------------------------------------------------------------------------
# 3. Shipped order deletion rejection
# ---------------------------------------------------------------------------


def test_shipped_order_deletion_rejected(client, headers, admin_headers):
    """Shipped orders cannot be cancelled or deleted because physical goods are in transit."""
    order_data = _create_order(client, headers(2), quantity=1)
    order_id = order_data["id"]

    assert client.put(
        f"/api/v1/orders/{order_id}/status",
        headers=admin_headers,
        json={"status": "processing"},
    ).status_code == 200
    assert client.put(
        f"/api/v1/orders/{order_id}/status",
        headers=admin_headers,
        json={"status": "shipped"},
    ).status_code == 200

    with SessionLocal() as db:
        assert db.get(Product, 1).stock == 19

    # Attempting to delete shipped order must be rejected
    del_res = client.delete(f"/api/v1/orders/{order_id}", headers=admin_headers)
    assert del_res.status_code == 409, del_res.text
    assert "shipped" in del_res.json()["detail"].lower()

    # Order must remain shipped and stock must not be restored
    with SessionLocal() as db:
        order = db.get(Order, order_id)
        assert order is not None
        assert order.status == "shipped"
        assert db.get(Product, 1).stock == 19


# ---------------------------------------------------------------------------
# 4. Delivered order deletion rejection
# ---------------------------------------------------------------------------


def test_delivered_order_deletion_rejected(client, headers, admin_headers):
    """Delivered orders cannot be cancelled or deleted to protect audit and customer history."""
    order_data = _create_order(client, headers(2), quantity=1)
    order_id = order_data["id"]

    for next_st in ("processing", "shipped", "delivered"):
        assert client.put(
            f"/api/v1/orders/{order_id}/status",
            headers=admin_headers,
            json={"status": next_st},
        ).status_code == 200

    with SessionLocal() as db:
        assert db.get(Product, 1).stock == 19

    # Attempting to delete delivered order must be rejected
    del_res = client.delete(f"/api/v1/orders/{order_id}", headers=admin_headers)
    assert del_res.status_code == 409, del_res.text
    assert "delivered" in del_res.json()["detail"].lower()

    # Order must remain delivered and stock intact
    with SessionLocal() as db:
        order = db.get(Order, order_id)
        assert order is not None
        assert order.status == "delivered"
        assert db.get(Product, 1).stock == 19


# ---------------------------------------------------------------------------
# 5. Already-cancelled order deletion rejection (Duplicate Restoration Prevention)
# ---------------------------------------------------------------------------


def test_already_cancelled_order_deletion_rejected(client, headers, admin_headers):
    """Deleting an already-cancelled order is rejected to avoid duplicate stock and coupon restoration."""
    order_data = _create_order(
        client,
        headers(2),
        quantity=2,
        coupon_code="WELCOME10",
    )
    order_id = order_data["id"]

    # Stock is 20 - 2 = 18, coupon used_count = 1
    with SessionLocal() as db:
        assert db.get(Product, 1).stock == 18
        coup = db.scalar(select(Coupon).where(Coupon.code == "WELCOME10"))
        assert coup.used_count == 1

    # First cancellation via normal status transition
    first_cancel = client.put(
        f"/api/v1/orders/{order_id}/status",
        headers=admin_headers,
        json={"status": "cancelled"},
    )
    assert first_cancel.status_code == 200
    assert first_cancel.json()["data"]["status"] == "cancelled"

    # Stock restored once: 18 + 2 = 20, coupon used_count = 0
    with SessionLocal() as db:
        assert db.get(Product, 1).stock == 20
        coup = db.scalar(select(Coupon).where(Coupon.code == "WELCOME10"))
        assert coup.used_count == 0

    # Second cancellation via DELETE endpoint must be rejected with 409 Conflict
    second_cancel = client.delete(f"/api/v1/orders/{order_id}", headers=admin_headers)
    assert second_cancel.status_code == 409, second_cancel.text
    assert "already cancelled" in second_cancel.json()["detail"].lower()

    # Stock and coupon count must NOT have been restored again (no duplicate inflation)
    with SessionLocal() as db:
        assert db.get(Product, 1).stock == 20
        coup = db.scalar(select(Coupon).where(Coupon.code == "WELCOME10"))
        assert coup.used_count == 0
        persisted = db.get(Order, order_id)
        assert persisted is not None
        assert persisted.status == "cancelled"


# ---------------------------------------------------------------------------
# 6. Refunded order cancellation and archival
# ---------------------------------------------------------------------------


def test_refunded_order_cancellation_allowed(client, headers, admin_headers):
    """An order whose payment was properly refunded can be cancelled and archived."""
    order_data = _create_order(
        client,
        headers(2),
        quantity=2,
        payment_method="Cash on Delivery",
    )
    order_id = order_data["id"]

    # Advance to processing, pay with cash receipt, then approve refund
    assert client.put(
        f"/api/v1/orders/{order_id}/status",
        headers=admin_headers,
        json={"status": "processing"},
    ).status_code == 200

    # Note: for cash settlement on processing order, cash settlement method like "Cash" allows payment
    with SessionLocal() as db:
        order = db.get(Order, order_id)
        order.payment_method = "Cash"
        db.commit()

    assert client.put(
        f"/api/v1/orders/{order_id}/status",
        headers=admin_headers,
        json={"payment_status": "paid", "reason": "Cash paid in store"},
    ).status_code == 200

    # Now refund it
    assert client.put(
        f"/api/v1/orders/{order_id}/status",
        headers=admin_headers,
        json={"payment_status": "refunded", "reason": "Full refund issued to customer"},
    ).status_code == 200

    with SessionLocal() as db:
        assert db.get(Product, 1).stock == 18
        assert db.get(Order, order_id).payment_status == "refunded"

    # Now cancellation / archival should succeed because refund was properly recorded
    del_res = client.delete(
        f"/api/v1/orders/{order_id}?reason=Archiving+refunded+order",
        headers=admin_headers,
    )
    assert del_res.status_code == 200, del_res.text
    assert del_res.json()["data"]["status"] == "cancelled"

    # Stock should be restored
    with SessionLocal() as db:
        assert db.get(Product, 1).stock == 20
        persisted = db.get(Order, order_id)
        assert persisted is not None
        assert persisted.status == "cancelled"
        assert persisted.payment_status == "refunded"


# ---------------------------------------------------------------------------
# 7. Authorization and boundary checks
# ---------------------------------------------------------------------------


def test_deletion_authorization_enforced(client, headers, admin_headers):
    """Non-admin roles cannot cancel or archive orders."""
    order_data = _create_order(client, headers(2), quantity=1)
    order_id = order_data["id"]

    # Unauthenticated
    unauth_res = client.delete(f"/api/v1/orders/{order_id}")
    assert unauth_res.status_code in (401, 403)

    # Customer (user 2)
    cust_res = client.delete(f"/api/v1/orders/{order_id}", headers=headers(2))
    assert cust_res.status_code == 403

    # Seller (user 4)
    seller_res = client.delete(f"/api/v1/orders/{order_id}", headers=headers(4))
    assert seller_res.status_code == 403

    # Order must remain pending and intact
    with SessionLocal() as db:
        order = db.get(Order, order_id)
        assert order is not None
        assert order.status == "pending"


def test_delete_nonexistent_order_returns_404(client, admin_headers):
    """Deleting a non-existent order ID returns 404 Not Found."""
    res = client.delete("/api/v1/orders/99999", headers=admin_headers)
    assert res.status_code == 404
    assert res.json()["detail"] == "Order not found."
