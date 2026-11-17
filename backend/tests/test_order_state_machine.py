"""Isolated state-machine, payment verification, authorization, and rollback tests for S02."""

import pytest
from sqlalchemy import select

from app.db.database import SessionLocal
from app.models.cart import CartItem
from app.models.notification import Notification
from app.models.order import Order
from app.models.product import Product
from app.models.seller import Seller
from app.schemas.order import OrderCreateRequest
from app.services.order_service import OrderService


def _activate_product_2() -> None:
    with SessionLocal() as db:
        p2 = db.get(Product, 2)
        assert p2 is not None
        p2.is_active = True
        db.commit()


def _create_checkout_order(
    client,
    buyer_headers: dict[str, str],
    prefix: str = "/api/v1",
    *,
    items: list[tuple[int, int]] | None = None,
    payment_method: str = "Cash on Delivery",
    shipping_address: str = "Street 2004, Sen Sok, Phnom Penh",
) -> dict:
    cart_items = items or [(1, 2)]
    for product_id, quantity in cart_items:
        add_res = client.post(
            f"{prefix}/cart/items",
            headers=buyer_headers,
            json={"product_id": product_id, "quantity": quantity},
        )
        assert add_res.status_code in (200, 201), add_res.text

    res = client.post(
        f"{prefix}/orders",
        headers=buyer_headers,
        json={
            "shipping_address": shipping_address,
            "payment_method": payment_method,
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["success"] is True
    return body["data"]


# ---------------------------------------------------------------------------
# 1. Valid order status transitions & stock restoration on cancellation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_valid_forward_order_status_transitions(client, headers, admin_headers, prefix):
    order = _create_checkout_order(client, headers(2), prefix=prefix)
    order_id = order["id"]
    assert order["status"] == "pending"
    assert order["payment_status"] == "pending"

    for next_status in ("processing", "shipped", "delivered"):
        res = client.put(
            f"{prefix}/orders/{order_id}/status",
            headers=admin_headers,
            json={"status": next_status},
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["success"] is True
        assert body["data"]["status"] == next_status
        assert body["data"]["payment_status"] == "pending"


@pytest.mark.parametrize("cancel_from", ["pending", "processing"])
def test_valid_cancellation_from_pending_or_processing_restores_stock(
    client, headers, admin_headers, cancel_from
):
    order = _create_checkout_order(client, headers(2), items=[(1, 3)])
    order_id = order["id"]

    with SessionLocal() as db:
        assert db.get(Product, 1).stock == 17

    if cancel_from == "processing":
        step = client.put(
            f"/api/v1/orders/{order_id}/status",
            headers=admin_headers,
            json={"status": "processing"},
        )
        assert step.status_code == 200

    cancel_res = client.put(
        f"/api/v1/orders/{order_id}/status",
        headers=admin_headers,
        json={"status": "cancelled"},
    )
    assert cancel_res.status_code == 200, cancel_res.text
    assert cancel_res.json()["data"]["status"] == "cancelled"

    with SessionLocal() as db:
        assert db.get(Product, 1).stock == 20


# ---------------------------------------------------------------------------
# 2. Invalid backward, skipped, or reopened status transitions
# ---------------------------------------------------------------------------


def test_invalid_backward_skipped_and_reopened_order_transitions_rejected(
    client, headers, admin_headers
):
    # Skipped forward: pending -> shipped / delivered
    order = _create_checkout_order(client, headers(2))
    oid = order["id"]

    for skipped in ("shipped", "delivered"):
        res = client.put(
            f"/api/v1/orders/{oid}/status",
            headers=admin_headers,
            json={"status": skipped},
        )
        assert res.status_code == 409

    # Advance to processing, test backward -> pending and skipped -> delivered
    assert (
        client.put(
            f"/api/v1/orders/{oid}/status",
            headers=admin_headers,
            json={"status": "processing"},
        ).status_code
        == 200
    )
    assert (
        client.put(
            f"/api/v1/orders/{oid}/status",
            headers=admin_headers,
            json={"status": "pending"},
        ).status_code
        == 409
    )
    assert (
        client.put(
            f"/api/v1/orders/{oid}/status",
            headers=admin_headers,
            json={"status": "delivered"},
        ).status_code
        == 409
    )

    # Advance to shipped, test backward -> processing / pending
    assert (
        client.put(
            f"/api/v1/orders/{oid}/status",
            headers=admin_headers,
            json={"status": "shipped"},
        ).status_code
        == 200
    )
    for backward in ("pending", "processing"):
        assert (
            client.put(
                f"/api/v1/orders/{oid}/status",
                headers=admin_headers,
                json={"status": backward},
            ).status_code
            == 409
        )

    # Advance to delivered, test backward -> shipped / processing / pending
    assert (
        client.put(
            f"/api/v1/orders/{oid}/status",
            headers=admin_headers,
            json={"status": "delivered"},
        ).status_code
        == 200
    )
    for backward in ("pending", "processing", "shipped"):
        assert (
            client.put(
                f"/api/v1/orders/{oid}/status",
                headers=admin_headers,
                json={"status": backward},
            ).status_code
            == 409
        )

    # Cancelled order cannot be reopened
    cancelled_order = _create_checkout_order(client, headers(2), items=[(1, 1)])
    coid = cancelled_order["id"]
    assert (
        client.put(
            f"/api/v1/orders/{coid}/status",
            headers=admin_headers,
            json={"status": "cancelled"},
        ).status_code
        == 200
    )
    for reopen in ("pending", "processing", "shipped", "delivered"):
        assert (
            client.put(
                f"/api/v1/orders/{coid}/status",
                headers=admin_headers,
                json={"status": reopen},
            ).status_code
            == 409
        )


# ---------------------------------------------------------------------------
# 3. Unauthorized customer & unprivileged role status changes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_unauthorized_customer_and_non_admin_roles_denied(client, headers, prefix):
    order = _create_checkout_order(client, headers(2), prefix=prefix)
    oid = order["id"]

    # Anonymous -> 401
    anon_res = client.put(f"{prefix}/orders/{oid}/status", json={"status": "processing"})
    assert anon_res.status_code == 401

    # Buyer customer (2), other customer (3), staff (6), employee (7), super_admin (8) -> 403
    for uid in (2, 3, 6, 7, 8):
        res = client.put(
            f"{prefix}/orders/{oid}/status",
            headers=headers(uid),
            json={"status": "processing"},
        )
        assert res.status_code == 403, f"Expected 403 for user {uid}, got {res.status_code}"

        pay_res = client.put(
            f"{prefix}/orders/{oid}/status",
            headers=headers(uid),
            json={"payment_status": "paid", "reason": "Attempted bypass"},
        )
        assert pay_res.status_code == 403


# ---------------------------------------------------------------------------
# 4. Seller ownership & fulfillment action restrictions
# ---------------------------------------------------------------------------


def test_seller_ownership_and_action_restrictions(client, headers):
    _activate_product_2()

    # Order exclusively containing Seller 4's product (Product 1 -> Store A)
    own_order = _create_checkout_order(client, headers(2), items=[(1, 1)])
    own_id = own_order["id"]

    # Seller 4 can advance pending -> processing -> shipped on own order
    for allowed_step in ("processing", "shipped"):
        res = client.put(
            f"/api/v1/orders/{own_id}/status",
            headers=headers(4),
            json={"status": allowed_step},
        )
        assert res.status_code == 200, res.text
        assert res.json()["data"]["status"] == allowed_step

    # Seller 4 cannot mark delivered, cancelled, or modify payment_status even on own order
    assert (
        client.put(
            f"/api/v1/orders/{own_id}/status",
            headers=headers(4),
            json={"status": "delivered"},
        ).status_code
        == 403
    )
    assert (
        client.put(
            f"/api/v1/orders/{own_id}/status",
            headers=headers(4),
            json={"payment_status": "paid", "reason": "Seller cash"},
        ).status_code
        == 403
    )

    own_order_2 = _create_checkout_order(client, headers(2), items=[(1, 1)])
    assert (
        client.put(
            f"/api/v1/orders/{own_order_2['id']}/status",
            headers=headers(4),
            json={"status": "cancelled"},
        ).status_code
        == 403
    )

    # Order belonging to Seller 5 (Product 2 -> Store B): Seller 4 denied (403)
    other_seller_order = _create_checkout_order(client, headers(2), items=[(2, 1)])
    assert (
        client.put(
            f"/api/v1/orders/{other_seller_order['id']}/status",
            headers=headers(4),
            json={"status": "processing"},
        ).status_code
        == 403
    )

    # Mixed-seller order (Product 1 + Product 2): neither Seller 4 nor Seller 5 may mutate whole order
    mixed_order = _create_checkout_order(client, headers(2), items=[(1, 1), (2, 1)])
    for seller_uid in (4, 5):
        assert (
            client.put(
                f"/api/v1/orders/{mixed_order['id']}/status",
                headers=headers(seller_uid),
                json={"status": "processing"},
            ).status_code
            == 403
        )

    # Suspended seller account cannot update even an owned order
    suspended_target = _create_checkout_order(client, headers(2), items=[(1, 1)])
    with SessionLocal() as db:
        seller_row = db.get(Seller, 1)
        seller_row.status = "Suspended"
        db.commit()

    assert (
        client.put(
            f"/api/v1/orders/{suspended_target['id']}/status",
            headers=headers(4),
            json={"status": "processing"},
        ).status_code
        == 403
    )


# ---------------------------------------------------------------------------
# 5. Invalid payment & order status values and unsupported payment methods
# ---------------------------------------------------------------------------


def test_invalid_order_and_payment_status_values_rejected(client, headers, admin_headers):
    order = _create_checkout_order(client, headers(2))
    oid = order["id"]

    invalid_payloads = [
        {},
        {"status": "archived"},
        {"status": ""},
        {"payment_status": "completed"},
        {"payment_status": "settled"},
        {"payment_status": ""},
    ]
    for payload in invalid_payloads:
        res = client.put(
            f"/api/v1/orders/{oid}/status",
            headers=admin_headers,
            json=payload,
        )
        assert res.status_code == 400, f"Payload {payload} returned {res.status_code}"

    # Unsupported checkout payment method rejected at order creation
    add_res = client.post(
        "/api/v1/cart/items",
        headers=headers(2),
        json={"product_id": 1, "quantity": 1},
    )
    assert add_res.status_code in (200, 201)
    bad_checkout = client.post(
        "/api/v1/orders",
        headers=headers(2),
        json={
            "shipping_address": "123 Street, Phnom Penh",
            "payment_method": "FakeCryptoWallet",
        },
    )
    assert bad_checkout.status_code == 400


# ---------------------------------------------------------------------------
# 6. Unverified electronic payment marked paid
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "electronic_method",
    ["KHQR Scan & Pay", "Credit / Debit Card", "Apple Pay"],
)
def test_unverified_electronic_payment_cannot_be_marked_paid(
    client, headers, admin_headers, electronic_method
):
    order = _create_checkout_order(
        client,
        headers(2),
        items=[(1, 1)],
        payment_method=electronic_method,
    )
    oid = order["id"]
    assert order["payment_status"] == "pending"

    # Even admin with a reason cannot mark unintegrated electronic payment as paid
    res = client.put(
        f"/api/v1/orders/{oid}/status",
        headers=admin_headers,
        json={"payment_status": "paid", "reason": "Manual override attempt"},
    )
    assert res.status_code == 409, res.text

    with SessionLocal() as db:
        persisted = db.get(Order, oid)
        assert persisted.payment_status == "pending"


def test_cancelled_order_cannot_be_marked_paid(client, headers, admin_headers):
    order = _create_checkout_order(client, headers(2), payment_method="Cash on Delivery")
    oid = order["id"]

    assert (
        client.put(
            f"/api/v1/orders/{oid}/status",
            headers=admin_headers,
            json={"status": "cancelled"},
        ).status_code
        == 200
    )

    res = client.put(
        f"/api/v1/orders/{oid}/status",
        headers=admin_headers,
        json={"payment_status": "paid", "reason": "Collected cash by mistake"},
    )
    assert res.status_code == 409


# ---------------------------------------------------------------------------
# 7. Cancellation of delivered and shipped orders
# ---------------------------------------------------------------------------


def test_cannot_cancel_shipped_or_delivered_orders(client, headers, admin_headers):
    order = _create_checkout_order(client, headers(2), items=[(1, 2)])
    oid = order["id"]

    assert (
        client.put(
            f"/api/v1/orders/{oid}/status",
            headers=admin_headers,
            json={"status": "processing"},
        ).status_code
        == 200
    )
    assert (
        client.put(
            f"/api/v1/orders/{oid}/status",
            headers=admin_headers,
            json={"status": "shipped"},
        ).status_code
        == 200
    )

    # Shipped -> cancelled rejected
    shipped_cancel = client.put(
        f"/api/v1/orders/{oid}/status",
        headers=admin_headers,
        json={"status": "cancelled"},
    )
    assert shipped_cancel.status_code == 409

    # Advance to delivered, delivered -> cancelled rejected
    assert (
        client.put(
            f"/api/v1/orders/{oid}/status",
            headers=admin_headers,
            json={"status": "delivered"},
        ).status_code
        == 200
    )
    delivered_cancel = client.put(
        f"/api/v1/orders/{oid}/status",
        headers=admin_headers,
        json={"status": "cancelled"},
    )
    assert delivered_cancel.status_code == 409

    # Stock and delivered status remain intact
    with SessionLocal() as db:
        assert db.get(Order, oid).status == "delivered"
        assert db.get(Product, 1).stock == 18


# ---------------------------------------------------------------------------
# 8. Transaction rollback after validation or commit failure
# ---------------------------------------------------------------------------


def test_combined_status_and_invalid_payment_update_rolls_back_atomically(
    client, headers, admin_headers
):
    order = _create_checkout_order(
        client,
        headers(2),
        items=[(1, 1)],
        payment_method="KHQR Scan & Pay",
    )
    oid = order["id"]

    with SessionLocal() as db:
        notif_count_before = len(db.scalars(select(Notification)).all())

    res = client.put(
        f"/api/v1/orders/{oid}/status",
        headers=admin_headers,
        json={
            "status": "processing",
            "payment_status": "paid",
            "reason": "Unverified QR screenshot",
        },
    )
    assert res.status_code == 409

    with SessionLocal() as db:
        persisted = db.get(Order, oid)
        assert persisted.status == "pending"
        assert persisted.payment_status == "pending"
        assert len(db.scalars(select(Notification)).all()) == notif_count_before


def test_database_commit_failure_rolls_back_order_stock_and_notifications(
    client, headers, monkeypatch
):
    # Rollback on create_order commit failure
    with SessionLocal() as db:
        db.add(CartItem(user_id=2, product_id=1, quantity=4))
        db.commit()

    with SessionLocal() as db:
        def _boom():
            raise RuntimeError("Simulated DB commit failure")

        monkeypatch.setattr(db, "commit", _boom)
        with pytest.raises(RuntimeError, match="Simulated DB commit failure"):
            OrderService.create_order(
                db=db,
                user_id=2,
                request=OrderCreateRequest(
                    shipping_address="Rollback Street, Phnom Penh",
                    payment_method="Cash on Delivery",
                ),
            )

    with SessionLocal() as verify_db:
        assert verify_db.get(Product, 1).stock == 20
        assert verify_db.scalars(select(Order)).all() == []
        assert len(verify_db.scalars(select(CartItem)).all()) == 1

    # Clear cart and test rollback on update_order_status commit failure
    with SessionLocal() as clean_db:
        clean_db.query(CartItem).delete()
        clean_db.commit()

    created = _create_checkout_order(client, headers(2), items=[(1, 2)])
    oid = created["id"]

    with SessionLocal() as db:
        admin_user = db.get(Order, oid)
        assert admin_user is not None
        from app.models.user import User

        actor = db.get(User, 1)

        def _boom_update():
            raise RuntimeError("Simulated status commit failure")

        monkeypatch.setattr(db, "commit", _boom_update)
        with pytest.raises(RuntimeError, match="Simulated status commit failure"):
            OrderService.update_order_status(
                db=db,
                order_id=oid,
                status_val="cancelled",
                actor=actor,
            )

    with SessionLocal() as verify_db:
        persisted = verify_db.get(Order, oid)
        assert persisted.status == "pending"
        assert verify_db.get(Product, 1).stock == 18


# ---------------------------------------------------------------------------
# 9. Existing Cash on Delivery order lifecycle, cash settlement & refund audit
# ---------------------------------------------------------------------------


def test_cash_on_delivery_lifecycle_settlement_and_refund_audit(
    client, headers, admin_headers
):
    order = _create_checkout_order(
        client,
        headers(2),
        items=[(1, 2)],
        payment_method="Cash on Delivery",
    )
    oid = order["id"]
    assert order["payment_method"] == "Cash on Delivery"
    assert order["status"] == "pending"
    assert order["payment_status"] == "pending"

    # Cannot mark COD paid before shipment/delivery
    early_pay = client.put(
        f"/api/v1/orders/{oid}/status",
        headers=admin_headers,
        json={"payment_status": "paid", "reason": "Courier receipt #100"},
    )
    assert early_pay.status_code == 409

    # Advance through processing -> shipped -> delivered
    for step in ("processing", "shipped", "delivered"):
        res = client.put(
            f"/api/v1/orders/{oid}/status",
            headers=admin_headers,
            json={"status": step},
        )
        assert res.status_code == 200
        assert res.json()["data"]["payment_status"] == "pending"

    # Missing reason for manual COD cash settlement -> 400
    missing_reason = client.put(
        f"/api/v1/orders/{oid}/status",
        headers=admin_headers,
        json={"payment_status": "paid"},
    )
    assert missing_reason.status_code == 400

    # Valid admin COD settlement with receipt reference -> 200 + operational audit log
    settled = client.put(
        f"/api/v1/orders/{oid}/status",
        headers=admin_headers,
        json={"payment_status": "paid", "reason": "Courier COD receipt #901"},
    )
    assert settled.status_code == 200, settled.text
    assert settled.json()["data"]["payment_status"] == "paid"

    # Paid cannot revert to pending or failed
    for invalid_revert in ("pending", "failed"):
        assert (
            client.put(
                f"/api/v1/orders/{oid}/status",
                headers=admin_headers,
                json={"payment_status": invalid_revert, "reason": "Mistake"},
            ).status_code
            == 409
        )

    # Paid -> refunded requires reason
    assert (
        client.put(
            f"/api/v1/orders/{oid}/status",
            headers=admin_headers,
            json={"payment_status": "refunded"},
        ).status_code
        == 400
    )

    refunded = client.put(
        f"/api/v1/orders/{oid}/status",
        headers=admin_headers,
        json={"payment_status": "refunded", "reason": "Return approved #R-44"},
    )
    assert refunded.status_code == 200
    assert refunded.json()["data"]["payment_status"] == "refunded"

    # Refunded is terminal
    assert (
        client.put(
            f"/api/v1/orders/{oid}/status",
            headers=admin_headers,
            json={"payment_status": "paid", "reason": "Re-charge"},
        ).status_code
        == 409
    )

    # Verify persistent admin-only audit notifications recorded actor + reason
    with SessionLocal() as db:
        audits = list(
            db.scalars(
                select(Notification).where(
                    Notification.user_id.is_(None),
                    Notification.title == f"Payment Audit: Order #{oid}",
                )
            ).all()
        )
        assert len(audits) == 2
        assert "Courier COD receipt #901" in audits[0].message
        assert "Return approved #R-44" in audits[1].message


# ---------------------------------------------------------------------------
# 10. Existing order API response contract compatibility
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_order_endpoints_preserve_response_envelope_and_schema(
    client, headers, admin_headers, prefix
):
    created_res = _create_checkout_order(client, headers(2), prefix=prefix)
    oid = created_res["id"]

    expected_order_keys = {
        "id",
        "user_id",
        "status",
        "subtotal",
        "discount_amount",
        "coupon_code",
        "shipping_fee",
        "total",
        "payment_method",
        "payment_status",
        "shipping_address",
        "created_at",
        "updated_at",
        "items",
        "user",
    }
    assert expected_order_keys.issubset(created_res.keys())

    # GET /orders (buyer list)
    list_res = client.get(f"{prefix}/orders", headers=headers(2))
    assert list_res.status_code == 200
    list_body = list_res.json()
    assert set(list_body.keys()) >= {"success", "message", "data"}
    assert list_body["success"] is True
    assert any(o["id"] == oid for o in list_body["data"])

    # GET /orders/{id} (buyer detail)
    detail_res = client.get(f"{prefix}/orders/{oid}", headers=headers(2))
    assert detail_res.status_code == 200
    detail_body = detail_res.json()
    assert detail_body["success"] is True
    assert expected_order_keys.issubset(detail_body["data"].keys())

    # GET /orders/all (admin list)
    all_res = client.get(f"{prefix}/orders/all", headers=admin_headers)
    assert all_res.status_code == 200
    all_body = all_res.json()
    assert all_body["success"] is True
    assert any(o["id"] == oid for o in all_body["data"])

    # PUT /orders/{id}/status
    upd_res = client.put(
        f"{prefix}/orders/{oid}/status",
        headers=admin_headers,
        json={"status": "processing"},
    )
    assert upd_res.status_code == 200
    upd_body = upd_res.json()
    assert upd_body["success"] is True
    assert expected_order_keys.issubset(upd_body["data"].keys())
    assert upd_body["data"]["status"] == "processing"

