from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.db.database import SessionLocal
from app.models.notification import Notification
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.models.user import User
from app.schemas.pos import PosCheckoutRequest, PosItemInput
from app.services.pos_service import PosService


@pytest.fixture(params=["/api", "/api/v1"])
def prefix(request: pytest.FixtureRequest) -> str:
    return request.param


def test_1_authorized_cash_cod_and_unverified_non_cash_pos_transactions(
    client, admin_headers, prefix
):
    # Set discount_price on Product 1? Keep Product 1 at $20.00 first, test cash sale + change calc
    res = client.post(
        f"{prefix}/pos/checkout",
        json={
            "items": [{"product_id": 1, "quantity": 2}],
            "customer_id": 2,
            "payment_method": "Cash",
            "discount_amount": "5.00",
            "tax_amount": "3.50",
            "amount_paid": "50.00",
            "change_due": "999.99",  # Forged client change_due must be ignored
            "notes": "Register 1",
        },
        headers=admin_headers,
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["success"] is True
    receipt = body["data"]
    assert Decimal(str(receipt["subtotal"])) == Decimal("40.00")
    assert Decimal(str(receipt["discount_amount"])) == Decimal("5.00")
    assert Decimal(str(receipt["tax_amount"])) == Decimal("3.50")
    assert Decimal(str(receipt["total"])) == Decimal("38.50")
    assert Decimal(str(receipt["amount_paid"])) == Decimal("50.00")
    assert Decimal(str(receipt["change_due"])) == Decimal("11.50")
    assert receipt["payment_method"] == "Cash"
    assert receipt["payment_status"] == "paid"
    assert receipt["customer_name"] == "Fixture 2"

    # Unverified QR Pay & Cash on Delivery must NOT be marked paid
    qr_res = client.post(
        f"{prefix}/pos/checkout",
        json={
            "items": [{"product_id": 1, "quantity": 1}],
            "payment_method": "QR Pay",
            "amount_paid": "20.00",
        },
        headers=admin_headers,
    )
    assert qr_res.status_code == 201
    assert qr_res.json()["data"]["payment_status"] == "pending"
    assert Decimal(str(qr_res.json()["data"]["amount_paid"])) == Decimal("0.00")
    assert Decimal(str(qr_res.json()["data"]["change_due"])) == Decimal("0.00")

    cod_res = client.post(
        f"{prefix}/pos/checkout",
        json={
            "items": [{"product_id": 1, "quantity": 1}],
            "payment_method": "Cash on Delivery",
            "amount_paid": "0.00",
        },
        headers=admin_headers,
    )
    assert cod_res.status_code == 201
    assert cod_res.json()["data"]["payment_status"] == "pending"

    # Daily summary counts only verified paid orders ($38.50), not pending QR/COD orders
    summary_res = client.get(f"{prefix}/pos/summary", headers=admin_headers)
    assert summary_res.status_code == 200
    summary = summary_res.json()["data"]
    assert summary["today_orders_count"] == 1
    assert Decimal(str(summary["today_total_sales"])) == Decimal("38.50")
    assert Decimal(str(summary["today_cash_sales"])) == Decimal("38.50")
    assert Decimal(str(summary["today_qr_sales"])) == Decimal("0.00")

    with SessionLocal() as db:
        assert db.get(Product, 1).stock == 16  # 20 - 2 - 1 - 1


def test_2_invalid_or_manipulated_client_price_rejected(
    client, admin_headers, prefix
):
    for manipulated_price in ["0.01", "0.00", "-5.00", "19.99", "999.00"]:
        res = client.post(
            f"{prefix}/pos/checkout",
            json={
                "items": [{"product_id": 1, "quantity": 1, "price": manipulated_price}],
                "payment_method": "Cash",
                "amount_paid": "1000.00",
            },
            headers=admin_headers,
        )
        assert res.status_code == 400, f"Expected 400 for price={manipulated_price}"

    with SessionLocal() as db:
        assert db.get(Product, 1).stock == 20
        assert db.scalar(select(func.count(Order.id))) == 0

    # Matching catalog price ($20.00) or discount_price ($15.00) succeeds
    with SessionLocal() as db:
        db.get(Product, 1).discount_price = Decimal("15.00")
        db.commit()

    stale_regular_res = client.post(
        f"{prefix}/pos/checkout",
        json={
            "items": [{"product_id": 1, "quantity": 1, "price": "20.00"}],
            "payment_method": "Cash",
            "amount_paid": "20.00",
        },
        headers=admin_headers,
    )
    assert stale_regular_res.status_code == 400

    matching_discount_res = client.post(
        f"{prefix}/pos/checkout",
        json={
            "items": [{"product_id": 1, "quantity": 2, "price": "15.00"}],
            "payment_method": "Cash",
            "amount_paid": "30.00",
        },
        headers=admin_headers,
    )
    assert matching_discount_res.status_code == 201
    assert Decimal(str(matching_discount_res.json()["data"]["total"])) == Decimal("30.00")


def test_3_incorrect_cash_and_non_cash_tender_rejected(
    client, admin_headers, prefix
):
    # Zero or underpaid cash tender for $40.00 due must be rejected
    for insufficient_cash in ["0.00", "10.00", "39.99"]:
        res = client.post(
            f"{prefix}/pos/checkout",
            json={
                "items": [{"product_id": 1, "quantity": 2}],
                "payment_method": "Cash",
                "amount_paid": insufficient_cash,
            },
            headers=admin_headers,
        )
        assert res.status_code == 400

    # Negative cash tender rejected at schema validation
    neg_tender = client.post(
        f"{prefix}/pos/checkout",
        json={
            "items": [{"product_id": 1, "quantity": 1}],
            "payment_method": "Cash",
            "amount_paid": "-1.00",
        },
        headers=admin_headers,
    )
    assert neg_tender.status_code == 422

    # COD with upfront cash or QR Pay with mismatched partial tender rejected
    cod_with_cash = client.post(
        f"{prefix}/pos/checkout",
        json={
            "items": [{"product_id": 1, "quantity": 1}],
            "payment_method": "Cash on Delivery",
            "amount_paid": "20.00",
        },
        headers=admin_headers,
    )
    assert cod_with_cash.status_code == 400

    qr_mismatch = client.post(
        f"{prefix}/pos/checkout",
        json={
            "items": [{"product_id": 1, "quantity": 1}],
            "payment_method": "QR Pay",
            "amount_paid": "12.00",
        },
        headers=admin_headers,
    )
    assert qr_mismatch.status_code == 400

    with SessionLocal() as db:
        assert db.get(Product, 1).stock == 20
        assert db.scalar(select(func.count(Order.id))) == 0


def test_4_negative_or_excessive_discount_tax_and_quantity_rejected(
    client, admin_headers, prefix
):
    # Negative discount, negative tax, zero/negative quantity via HTTP -> 422
    for bad_payload in [
        {
            "items": [{"product_id": 1, "quantity": 0}],
            "payment_method": "Cash",
            "amount_paid": "20.00",
        },
        {
            "items": [{"product_id": 1, "quantity": -2}],
            "payment_method": "Cash",
            "amount_paid": "20.00",
        },
        {
            "items": [{"product_id": 1, "quantity": 1}],
            "payment_method": "Cash",
            "discount_amount": "-5.00",
            "amount_paid": "25.00",
        },
        {
            "items": [{"product_id": 1, "quantity": 1}],
            "payment_method": "Cash",
            "tax_amount": "-2.00",
            "amount_paid": "20.00",
        },
    ]:
        res = client.post(f"{prefix}/pos/checkout", json=bad_payload, headers=admin_headers)
        assert res.status_code == 422

    # Discount > subtotal or Tax > subtotal -> 400
    for excessive_payload in [
        {
            "items": [{"product_id": 1, "quantity": 1}],
            "payment_method": "Cash",
            "discount_amount": "25.00",
            "amount_paid": "20.00",
        },
        {
            "items": [{"product_id": 1, "quantity": 1}],
            "payment_method": "Cash",
            "tax_amount": "25.00",
            "amount_paid": "50.00",
        },
    ]:
        res = client.post(f"{prefix}/pos/checkout", json=excessive_payload, headers=admin_headers)
        assert res.status_code == 400

    # Direct service-level guard even if Pydantic validation is bypassed via model_construct
    with SessionLocal() as db:
        cashier = db.get(User, 1)
        bypassed_req = PosCheckoutRequest.model_construct(
            items=[PosItemInput.model_construct(product_id=1, quantity=-1, price=None)],
            customer_id=None,
            customer_name="Walk-in",
            customer_phone=None,
            payment_method="Cash",
            amount_paid=Decimal("20.00"),
            change_due=Decimal("0.00"),
            discount_amount=Decimal("-1.00"),
            tax_amount=Decimal("0.00"),
            notes=None,
        )
        with pytest.raises(HTTPException) as exc_info:
            PosService.process_checkout(db, cashier, bypassed_req)
        assert exc_info.value.status_code == 400


def test_5_notification_creation_for_sale_and_low_stock(
    client, admin_headers, prefix
):
    # Buy 16 of 20 units -> remaining stock is 4 (<= 5), triggering BOTH notifications
    res = client.post(
        f"{prefix}/pos/checkout",
        json={
            "items": [{"product_id": 1, "quantity": 16}],
            "payment_method": "Cash",
            "amount_paid": "320.00",
        },
        headers=admin_headers,
    )
    assert res.status_code == 201, res.text
    order_id = res.json()["data"]["order_id"]

    with SessionLocal() as db:
        notifs = db.scalars(
            select(Notification).order_by(Notification.id.asc())
        ).all()
        assert len(notifs) == 2

        inv_notif = next(n for n in notifs if n.type == "inventory")
        assert inv_notif.user_id == 1
        assert inv_notif.read is False
        assert "4 units remaining" in inv_notif.message

        order_notif = next(n for n in notifs if n.type == "order")
        assert order_notif.user_id == 1
        assert order_notif.read is False
        assert order_notif.link == f"/admin/orders/{order_id}"


def test_6_transaction_rollback_on_validation_or_db_failure(
    client, admin_headers, prefix, monkeypatch
):
    # Case A: Multi-item request where item 1 is valid (low-stock threshold) & item 2 is inactive (Product 2)
    res_inactive = client.post(
        f"{prefix}/pos/checkout",
        json={
            "items": [
                {"product_id": 1, "quantity": 16},
                {"product_id": 2, "quantity": 1},
            ],
            "payment_method": "Cash",
            "amount_paid": "500.00",
        },
        headers=admin_headers,
    )
    assert res_inactive.status_code == 400

    # Case B: Duplicate product lines exceeding stock (12 + 10 = 22 > 20) -> 409 Conflict
    res_dup_overflow = client.post(
        f"{prefix}/pos/checkout",
        json={
            "items": [
                {"product_id": 1, "quantity": 12},
                {"product_id": 1, "quantity": 10},
            ],
            "payment_method": "Cash",
            "amount_paid": "500.00",
        },
        headers=admin_headers,
    )
    assert res_dup_overflow.status_code == 409

    # Case C: Mid-transaction failure during db.flush rolls back stock, Order, OrderItem, and Notification
    with SessionLocal() as db:
        cashier = db.get(User, 1)

        def boom():
            raise RuntimeError("Simulated mid-transaction database error")

        monkeypatch.setattr(db, "flush", boom)
        valid_req = PosCheckoutRequest(
            items=[PosItemInput(product_id=1, quantity=16)],
            payment_method="Cash",
            amount_paid=Decimal("320.00"),
        )
        with pytest.raises(RuntimeError, match="Simulated mid-transaction"):
            PosService.process_checkout(db, cashier, valid_req)

    with SessionLocal() as db:
        assert db.get(Product, 1).stock == 20
        assert db.scalar(select(func.count(Order.id))) == 0
        assert db.scalar(select(func.count(OrderItem.id))) == 0
        assert db.scalar(select(func.count(Notification.id))) == 0


def test_7_unauthorized_customer_and_non_admin_pos_access_denied(
    client, headers, prefix
):
    payload = {
        "items": [{"product_id": 1, "quantity": 1}],
        "payment_method": "Cash",
        "amount_paid": "20.00",
    }

    # Anonymous -> 401
    assert client.post(f"{prefix}/pos/checkout", json=payload).status_code == 401
    assert client.get(f"{prefix}/pos/summary").status_code == 401
    assert client.get(f"{prefix}/pos/customers").status_code == 401

    # Customer (2), Seller (4), Staff (6), Employee (7), SuperAdmin (8) -> 403
    for user_id in (2, 4, 6, 7, 8):
        assert (
            client.post(f"{prefix}/pos/checkout", json=payload, headers=headers(user_id)).status_code
            == 403
        )
        assert client.get(f"{prefix}/pos/summary", headers=headers(user_id)).status_code == 403
        assert client.get(f"{prefix}/pos/customers", headers=headers(user_id)).status_code == 403

    with SessionLocal() as db:
        assert db.get(Product, 1).stock == 20
        assert db.scalar(select(func.count(Order.id))) == 0

