"""Stock concurrency, atomic deduction, rollback, and cancellation restock tests (S10).

Includes both isolated SQLite HTTP/service tests and real multi-session PostgreSQL
concurrency tests running against a disposable, Unix-socket-only temporary cluster
created under /tmp (never connecting to any TCP port or existing database).
"""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
import threading

from fastapi import HTTPException
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.core.security import hash_password
from app.db.database import Base, SessionLocal
from app.models.cart import CartItem
from app.models.category import Category
from app.models.notification import Notification
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.models.seller import Seller
from app.models.user import User
from app.schemas.order import OrderCreateRequest
from app.schemas.pos import PosCheckoutRequest, PosItemInput
from app.services.inventory_service import InventoryService
from app.services.order_service import OrderService
from app.services.pos_service import PosService
from app.services.idempotency_service import IdempotencyService


def _activate_product_2(session_factory=SessionLocal, stock: int = 20) -> None:
    with session_factory() as db:
        p2 = db.get(Product, 2)
        assert p2 is not None
        p2.is_active = True
        p2.stock = stock
        db.commit()


@pytest.mark.parametrize("abandoned_record", [False, True])
def test_expired_checkout_cannot_be_taken_over_while_worker_is_alive(
    pg_session_factory, monkeypatch, abandoned_record
):
    """Elapsed time alone must not unlock a transaction still creating an order."""
    from datetime import datetime, timedelta, timezone
    from app.models.idempotency import IdempotencyRecord

    key = "slow-checkout"
    with pg_session_factory() as db:
        db.get(Product, 1).stock = 10
        if abandoned_record:
            db.add(IdempotencyRecord(
                user_id=2, key=key, status="processing",
                created_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            ))
        db.commit()

    entered = threading.Event()
    resume = threading.Event()
    deduct = InventoryService.deduct_stock

    def delayed_deduct(db, *args, **kwargs):
        if threading.current_thread().name.startswith("slow-checkout"):
            entered.set()
            assert resume.wait(10), "Timed out waiting for competing checkout"
        return deduct(db, *args, **kwargs)

    monkeypatch.setattr(InventoryService, "deduct_stock", delayed_deduct)
    # Simulate an attempt whose duration exceeds the processing timeout.
    monkeypatch.setattr(IdempotencyService, "_is_stale", lambda *_args: True)
    request = OrderCreateRequest(
        shipping_address="123 Test Street",
        items=[{"product_id": 1, "quantity": 2}],
    )

    def checkout():
        with pg_session_factory() as db:
            return OrderService.create_order(db, 2, request, idempotency_key=key)

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="slow-checkout") as pool:
        first = pool.submit(checkout)
        try:
            assert entered.wait(10)
            with pytest.raises(HTTPException) as conflict:
                checkout()
            assert conflict.value.status_code == 409
        finally:
            resume.set()
        original = first.result(timeout=10)

    replay = checkout()
    assert replay.id == original.id
    with pg_session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Order)) == 1
        assert db.get(Product, 1).stock == 8


def test_postgres_checkout_failure_rolls_back_key_and_retries(
    pg_session_factory, monkeypatch
):
    from app.models.idempotency import IdempotencyRecord

    request = OrderCreateRequest(
        shipping_address="123 Test Street",
        items=[{"product_id": 1, "quantity": 1}],
    )
    key = "rollback-checkout"
    with pg_session_factory() as db:
        with pytest.raises(HTTPException):
            OrderService.create_order(
                db, 2, request.model_copy(update={"shipping_address": " "}),
                idempotency_key=key,
            )
    with pg_session_factory() as db:
        assert db.scalar(select(func.count()).select_from(IdempotencyRecord)) == 0
        assert db.scalar(select(func.count()).select_from(Order)) == 0
        assert db.get(Product, 1).stock == 1

    def unexpected_write(*_args, **_kwargs):
        pytest.fail("A confirmed order must not require a second idempotency commit")

    monkeypatch.setattr(IdempotencyService, "complete", unexpected_write)
    with pg_session_factory() as db:
        order = OrderService.create_order(db, 2, request, idempotency_key=key)
    with pg_session_factory() as db:
        replay = OrderService.create_order(db, 2, request, idempotency_key=key)
        assert replay.id == order.id
        assert db.get(Product, 1).stock == 0


@pytest.mark.parametrize("cancel_via_delete", [False, True])
@pytest.mark.parametrize("first_action", ["cancel", "settle"])
def test_cash_settlement_and_cancellation_cannot_both_succeed(
    pg_session_factory, cancel_via_delete, first_action
):
    with pg_session_factory() as db:
        placed = OrderService.create_order(db, 2, OrderCreateRequest(
            shipping_address="123 Test Street",
            items=[{"product_id": 1, "quantity": 1}],
        ))
        db.get(Order, placed.id).payment_method = "Cash"
        db.commit()

    entered = threading.Event()
    resume = threading.Event()

    def transition(action, delay=False):
        with pg_session_factory() as db:
            if delay:
                execute = db.execute

                def delayed_execute(statement, *args, **kwargs):
                    if getattr(statement, "is_update", False) and not entered.is_set():
                        entered.set()
                        assert resume.wait(10)
                    return execute(statement, *args, **kwargs)

                db.execute = delayed_execute
            admin = db.get(User, 1)
            if action == "settle":
                return OrderService.update_order_status(
                    db, placed.id, payment_status_val="paid", actor=admin,
                    reason="Cash receipt 123",
                )
            if cancel_via_delete:
                return OrderService.cancel_or_archive_order(db, placed.id, actor=admin)
            return OrderService.update_order_status(
                db, placed.id, status_val="cancelled", actor=admin,
            )

    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(transition, first_action, True)
        try:
            assert entered.wait(10)
            transition("settle" if first_action == "cancel" else "cancel")
        finally:
            resume.set()
        with pytest.raises(HTTPException) as conflict:
            first.result(timeout=10)
        assert conflict.value.status_code == 409

    with pg_session_factory() as db:
        order = db.get(Order, placed.id)
        if first_action == "cancel":
            assert (order.status, order.payment_status) == ("pending", "paid")
            assert db.get(Product, 1).stock == 0
        else:
            assert (order.status, order.payment_status) == ("cancelled", "pending")
            assert db.get(Product, 1).stock == 1


# ---------------------------------------------------------------------------
# Ephemeral, TCP-disabled PostgreSQL cluster fixture for real concurrency tests
# ---------------------------------------------------------------------------


@pytest.fixture
def pg_session_factory(pg_cluster, password_hash):
    pg_engine, expected_data_dir = pg_cluster
    with pg_engine.connect() as conn:
        actual_data_dir = Path(
            conn.exec_driver_sql("SHOW data_directory").scalar_one()
        ).resolve()
        assert actual_data_dir == expected_data_dir

    Base.metadata.drop_all(pg_engine)
    Base.metadata.create_all(pg_engine)

    factory = sessionmaker(bind=pg_engine, autoflush=False, autocommit=False)
    with factory() as db:
        db.add(
            User(
                id=1,
                name="PG Admin",
                email="admin@pg.test",
                role="admin",
                password_hash=password_hash,
                is_active=True,
            )
        )
        for uid in range(2, 12):
            db.add(
                User(
                    id=uid,
                    name=f"PG Customer {uid}",
                    email=f"cust{uid}@pg.test",
                    role="customer",
                    password_hash=password_hash,
                    is_active=True,
                )
            )
        db.add(
            User(
                id=20,
                name="PG Seller",
                email="seller@pg.test",
                role="seller",
                password_hash=password_hash,
                is_active=True,
            )
        )
        db.add(Category(id=1, name="Electronics", is_active=True))
        db.flush()
        db.add(
            Seller(
                id=1,
                user_id=20,
                name="PG Store",
                owner_name="PG Owner",
                email="store@pg.test",
                status="Active",
            )
        )
        db.flush()
        db.add_all(
            [
                Product(
                    id=1,
                    category_id=1,
                    seller_id=1,
                    name="Limited Edition Headphones",
                    price=Decimal("25.00"),
                    stock=1,
                    is_active=True,
                ),
                Product(
                    id=2,
                    category_id=1,
                    seller_id=1,
                    name="USB-C Charger",
                    price=Decimal("15.00"),
                    stock=1,
                    is_active=True,
                ),
            ]
        )
        db.commit()
    return factory


# ---------------------------------------------------------------------------
# 1. Successful checkout with sufficient stock (customer & POS)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_1_successful_customer_and_pos_checkout_with_sufficient_stock(
    client, headers, admin_headers, prefix
):
    add_res = client.post(
        f"{prefix}/cart/items",
        headers=headers(2),
        json={"product_id": 1, "quantity": 3},
    )
    assert add_res.status_code in (200, 201)

    order_res = client.post(
        f"{prefix}/orders",
        headers=headers(2),
        json={
            "shipping_address": "123 Norodom Blvd, Phnom Penh",
            "payment_method": "Cash on Delivery",
        },
    )
    assert order_res.status_code == 201, order_res.text
    assert order_res.json()["success"] is True

    pos_res = client.post(
        f"{prefix}/pos/checkout",
        headers=admin_headers,
        json={
            "items": [{"product_id": 1, "quantity": 4}],
            "payment_method": "Cash",
            "amount_paid": "80.00",
        },
    )
    assert pos_res.status_code == 201, pos_res.text
    assert pos_res.json()["success"] is True

    with SessionLocal() as db:
        assert db.get(Product, 1).stock == 13  # 20 - 3 - 4


# ---------------------------------------------------------------------------
# 2. Checkout rejected with HTTP 409 when stock is insufficient
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_2_insufficient_stock_returns_409_and_preserves_cart_and_stock(
    client, headers, admin_headers, prefix
):
    with SessionLocal() as db:
        db.get(Product, 1).stock = 2
        db.add(CartItem(user_id=2, product_id=1, quantity=3))
        db.commit()

    # Customer checkout requesting 3 when 2 available -> 409 Conflict + cart preserved
    cust_res = client.post(
        f"{prefix}/orders",
        headers=headers(2),
        json={
            "shipping_address": "Street 51, Phnom Penh",
            "payment_method": "Cash on Delivery",
        },
    )
    assert cust_res.status_code == 409
    assert "Insufficient stock" in cust_res.json()["detail"]

    # POS checkout requesting 3 when 2 available -> 409 Conflict
    pos_res = client.post(
        f"{prefix}/pos/checkout",
        headers=admin_headers,
        json={
            "items": [{"product_id": 1, "quantity": 3}],
            "payment_method": "Cash",
            "amount_paid": "100.00",
        },
    )
    assert pos_res.status_code == 409
    assert "Insufficient stock" in pos_res.json()["detail"]

    with SessionLocal() as db:
        assert db.get(Product, 1).stock == 2
        assert db.scalar(select(func.count(Order.id))) == 0
        cart_row = db.scalar(select(CartItem).where(CartItem.user_id == 2))
        assert cart_row is not None and cart_row.quantity == 3


# ---------------------------------------------------------------------------
# 3. Real PostgreSQL concurrency: multiple customers purchasing the last item
# ---------------------------------------------------------------------------


def test_3_postgres_concurrent_customers_purchasing_last_item(pg_session_factory):
    buyer_ids = [2, 3, 4, 5, 6, 7]
    with pg_session_factory() as setup_db:
        setup_db.get(Product, 1).stock = 1
        for uid in buyer_ids:
            setup_db.add(CartItem(user_id=uid, product_id=1, quantity=1))
        setup_db.commit()

    barrier = threading.Barrier(len(buyer_ids), timeout=10.0)

    def _attempt_customer_checkout(uid: int) -> tuple[str, int | str]:
        with pg_session_factory() as db:
            barrier.wait()
            try:
                order = OrderService.create_order(
                    db=db,
                    user_id=uid,
                    request=OrderCreateRequest(
                        shipping_address=f"Buyer {uid} Address, Phnom Penh",
                        payment_method="Cash on Delivery",
                    ),
                )
                return ("ok", order.id)
            except HTTPException as exc:
                return ("http_error", exc.status_code)

    with ThreadPoolExecutor(max_workers=len(buyer_ids)) as pool:
        outcomes = list(pool.map(_attempt_customer_checkout, buyer_ids))

    winners = [o for o in outcomes if o[0] == "ok"]
    conflicts = [o for o in outcomes if o == ("http_error", 409)]

    assert len(winners) == 1, f"Expected exactly 1 winner, got: {outcomes}"
    assert len(conflicts) == len(buyer_ids) - 1, f"Expected all losers to get 409: {outcomes}"

    with pg_session_factory() as verify_db:
        product = verify_db.get(Product, 1)
        assert product.stock == 0
        assert verify_db.scalar(select(func.count(Order.id))) == 1
        assert verify_db.scalar(select(func.count(OrderItem.id))) == 1
        # Losing customers still have their cart items preserved
        remaining_carts = verify_db.scalar(select(func.count(CartItem.id)))
        assert remaining_carts == len(buyer_ids) - 1


# ---------------------------------------------------------------------------
# 4. Real PostgreSQL concurrency: simultaneous POS and customer checkouts
# ---------------------------------------------------------------------------


def test_4_postgres_concurrent_pos_and_customer_checkout_same_product(pg_session_factory):
    # Case A: 1 unit left, 1 customer + 1 POS cashier race head-to-head
    with pg_session_factory() as setup_db:
        setup_db.get(Product, 1).stock = 1
        setup_db.add(CartItem(user_id=2, product_id=1, quantity=1))
        setup_db.commit()

    barrier_two = threading.Barrier(2, timeout=10.0)

    def _customer_worker() -> tuple[str, int]:
        with pg_session_factory() as db:
            barrier_two.wait()
            try:
                res = OrderService.create_order(
                    db=db,
                    user_id=2,
                    request=OrderCreateRequest(
                        shipping_address="Customer Race St, Phnom Penh",
                        payment_method="Cash on Delivery",
                    ),
                )
                return ("customer_ok", res.id)
            except HTTPException as exc:
                return ("customer_err", exc.status_code)

    def _pos_worker() -> tuple[str, int]:
        with pg_session_factory() as db:
            cashier = db.get(User, 1)
            barrier_two.wait()
            try:
                res = PosService.process_checkout(
                    db=db,
                    cashier=cashier,
                    request=PosCheckoutRequest(
                        items=[PosItemInput(product_id=1, quantity=1)],
                        payment_method="Cash",
                        amount_paid=Decimal("25.00"),
                    ),
                )
                return ("pos_ok", res.order_id)
            except HTTPException as exc:
                return ("pos_err", exc.status_code)

    with ThreadPoolExecutor(max_workers=2) as pool:
        f_cust = pool.submit(_customer_worker)
        f_pos = pool.submit(_pos_worker)
        pair_results = [f_cust.result(), f_pos.result()]

    pair_ok = [r for r in pair_results if r[0].endswith("_ok")]
    pair_409 = [r for r in pair_results if r[0].endswith("_err") and r[1] == 409]
    assert len(pair_ok) == 1, f"Expected 1 winner between POS and customer: {pair_results}"
    assert len(pair_409) == 1, f"Expected 1 HTTP 409 conflict: {pair_results}"

    with pg_session_factory() as verify_db:
        assert verify_db.get(Product, 1).stock == 0
        assert verify_db.scalar(select(func.count(Order.id))) == 1

    # Case B: 3 units available across 3 concurrent customers + 3 concurrent POS checkouts (6 total)
    with pg_session_factory() as setup_db:
        setup_db.query(CartItem).delete()
        setup_db.get(Product, 1).stock = 3
        for uid in (3, 4, 5):
            setup_db.add(CartItem(user_id=uid, product_id=1, quantity=1))
        setup_db.commit()

    barrier_six = threading.Barrier(6, timeout=10.0)

    def _mixed_actor(idx: int) -> int:
        with pg_session_factory() as db:
            if idx < 3:
                uid = 3 + idx
                barrier_six.wait()
                try:
                    OrderService.create_order(
                        db=db,
                        user_id=uid,
                        request=OrderCreateRequest(
                            shipping_address=f"Mixed St {uid}, Phnom Penh",
                            payment_method="Cash on Delivery",
                        ),
                    )
                    return 201
                except HTTPException as exc:
                    return exc.status_code
            else:
                cashier = db.get(User, 1)
                barrier_six.wait()
                try:
                    PosService.process_checkout(
                        db=db,
                        cashier=cashier,
                        request=PosCheckoutRequest(
                            items=[PosItemInput(product_id=1, quantity=1)],
                            payment_method="Cash",
                            amount_paid=Decimal("25.00"),
                        ),
                    )
                    return 201
                except HTTPException as exc:
                    return exc.status_code

    with ThreadPoolExecutor(max_workers=6) as pool:
        codes = list(pool.map(_mixed_actor, range(6)))

    assert codes.count(201) == 3, f"Expected 3 successful orders for 3 stock, got {codes}"
    assert codes.count(409) == 3, f"Expected 3 conflicts (409), got {codes}"

    with pg_session_factory() as verify_db:
        assert verify_db.get(Product, 1).stock == 0
        assert verify_db.scalar(select(func.count(Order.id))) == 4  # 1 from Case A + 3 from Case B


# ---------------------------------------------------------------------------
# 5. Duplicate product lines exceeding available stock
# ---------------------------------------------------------------------------


def test_5_duplicate_product_lines_exceeding_stock_rejected_with_409(
    client, admin_headers
):
    # Product 1 has stock=20; three duplicate POS lines (8 + 8 + 5 = 21 > 20) must return 409
    res = client.post(
        "/api/v1/pos/checkout",
        headers=admin_headers,
        json={
            "items": [
                {"product_id": 1, "quantity": 8},
                {"product_id": 1, "quantity": 8},
                {"product_id": 1, "quantity": 5},
            ],
            "payment_method": "Cash",
            "amount_paid": "500.00",
        },
    )
    assert res.status_code == 409
    assert "Insufficient stock" in res.json()["detail"]

    # Shared InventoryService also aggregates duplicate lines directly
    with SessionLocal() as db:
        with pytest.raises(HTTPException) as exc_info:
            InventoryService.deduct_stock(db, [(1, 15), (1, 6)])
        assert exc_info.value.status_code == 409
        db.rollback()

    with SessionLocal() as db:
        assert db.get(Product, 1).stock == 20
        assert db.scalar(select(func.count(Order.id))) == 0


# ---------------------------------------------------------------------------
# 6. Multi-product checkout where one item is unavailable + deadlock-free order
# ---------------------------------------------------------------------------


def test_6_multi_product_checkout_partial_unavailability_rolls_back_all_items(
    client, headers, admin_headers, pg_session_factory
):
    # SQLite: Product 1 has 20 in stock (deducted first by ID), Product 2 is active with only 1 in stock
    _activate_product_2(SessionLocal, stock=1)

    with SessionLocal() as db:
        db.add_all(
            [
                CartItem(user_id=2, product_id=2, quantity=2),  # Exceeds Product 2 stock
                CartItem(user_id=2, product_id=1, quantity=5),  # Sufficient for Product 1
            ]
        )
        db.commit()

    cust_res = client.post(
        "/api/v1/orders",
        headers=headers(2),
        json={
            "shipping_address": "Multi Item St, Phnom Penh",
            "payment_method": "Cash on Delivery",
        },
    )
    assert cust_res.status_code == 409

    pos_res = client.post(
        "/api/v1/pos/checkout",
        headers=admin_headers,
        json={
            "items": [
                {"product_id": 2, "quantity": 2},
                {"product_id": 1, "quantity": 5},
            ],
            "payment_method": "Cash",
            "amount_paid": "500.00",
        },
    )
    assert pos_res.status_code == 409

    # Neither Product 1 nor Product 2 lost any stock!
    with SessionLocal() as db:
        assert db.get(Product, 1).stock == 20
        assert db.get(Product, 2).stock == 1
        assert db.scalar(select(func.count(Order.id))) == 0

    # PostgreSQL concurrent opposite-order multi-product race ([1, 2] vs [2, 1], stock=1 each)
    with pg_session_factory() as setup_db:
        setup_db.get(Product, 1).stock = 1
        setup_db.get(Product, 2).stock = 1
        setup_db.add_all(
            [
                CartItem(user_id=2, product_id=1, quantity=1),
                CartItem(user_id=2, product_id=2, quantity=1),
            ]
        )
        setup_db.commit()

    barrier = threading.Barrier(2, timeout=10.0)

    def _cust_1_then_2() -> int:
        with pg_session_factory() as db:
            barrier.wait()
            try:
                OrderService.create_order(
                    db=db,
                    user_id=2,
                    request=OrderCreateRequest(
                        shipping_address="Deadlock Test St, Phnom Penh",
                        payment_method="Cash on Delivery",
                    ),
                )
                return 201
            except HTTPException as exc:
                return exc.status_code

    def _pos_2_then_1() -> int:
        with pg_session_factory() as db:
            cashier = db.get(User, 1)
            barrier.wait()
            try:
                PosService.process_checkout(
                    db=db,
                    cashier=cashier,
                    request=PosCheckoutRequest(
                        items=[
                            PosItemInput(product_id=2, quantity=1),
                            PosItemInput(product_id=1, quantity=1),
                        ],
                        payment_method="Cash",
                        amount_paid=Decimal("40.00"),
                    ),
                )
                return 201
            except HTTPException as exc:
                return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(_cust_1_then_2)
        f2 = pool.submit(_pos_2_then_1)
        results = [f1.result(), f2.result()]

    assert sorted(results) == [201, 409], f"Expected clean [201, 409] without deadlock: {results}"
    with pg_session_factory() as verify_db:
        assert verify_db.get(Product, 1).stock == 0
        assert verify_db.get(Product, 2).stock == 0
        assert verify_db.scalar(select(func.count(Order.id))) == 1


# ---------------------------------------------------------------------------
# 7. Full rollback after a failed transaction (post-deduction failure)
# ---------------------------------------------------------------------------


def test_7_full_rollback_after_failed_customer_or_pos_transaction(monkeypatch):
    with SessionLocal() as db:
        db.add(CartItem(user_id=2, product_id=1, quantity=4))
        db.commit()

    # Invalid coupon after InventoryService.deduct_stock rolls back Product.stock & keeps CartItem
    with SessionLocal() as db:
        with pytest.raises(HTTPException) as exc_info:
            OrderService.create_order(
                db=db,
                user_id=2,
                request=OrderCreateRequest(
                    shipping_address="Coupon Rollback St, Phnom Penh",
                    payment_method="Cash on Delivery",
                    coupon_code="NON_EXISTENT_PROMO",
                ),
            )
        assert exc_info.value.status_code == 404

    with SessionLocal() as verify_db:
        assert verify_db.get(Product, 1).stock == 20
        assert verify_db.scalar(select(func.count(Order.id))) == 0
        assert verify_db.scalar(select(func.count(Notification.id))) == 0
        assert verify_db.scalar(select(func.count(CartItem.id))) == 1

    # Simulated DB commit error in POS checkout rolls back atomic SQL stock deduction
    with SessionLocal() as db:
        cashier = db.get(User, 1)

        def _commit_boom():
            raise RuntimeError("Simulated commit crash")

        monkeypatch.setattr(db, "commit", _commit_boom)
        with pytest.raises(RuntimeError, match="Simulated commit crash"):
            PosService.process_checkout(
                db=db,
                cashier=cashier,
                request=PosCheckoutRequest(
                    items=[PosItemInput(product_id=1, quantity=5)],
                    payment_method="Cash",
                    amount_paid=Decimal("100.00"),
                ),
            )

    with SessionLocal() as verify_db:
        assert verify_db.get(Product, 1).stock == 20
        assert verify_db.scalar(select(func.count(Order.id))) == 0
        assert verify_db.scalar(select(func.count(OrderItem.id))) == 0
        assert verify_db.scalar(select(func.count(Notification.id))) == 0


# ---------------------------------------------------------------------------
# 8 & 9. Cancellation stock restoration & repeated/concurrent cancel protection
# ---------------------------------------------------------------------------


def test_8_and_9_cancellation_restores_stock_once_sequentially_and_concurrently(
    client, headers, admin_headers, pg_session_factory
):
    _activate_product_2(SessionLocal, stock=10)

    # Sequential multi-item order + cancel + repeated cancel
    for pid, qty in ((1, 3), (2, 4)):
        res = client.post(
            "/api/v1/cart/items",
            headers=headers(2),
            json={"product_id": pid, "quantity": qty},
        )
        assert res.status_code in (200, 201)

    order_res = client.post(
        "/api/v1/orders",
        headers=headers(2),
        json={
            "shipping_address": "Cancel Test Rd, Phnom Penh",
            "payment_method": "Cash on Delivery",
        },
    )
    assert order_res.status_code == 201
    oid = order_res.json()["data"]["id"]

    with SessionLocal() as db:
        assert db.get(Product, 1).stock == 17
        assert db.get(Product, 2).stock == 6

    # First cancellation restores stock to 20 and 10
    first_cancel = client.put(
        f"/api/v1/orders/{oid}/status",
        headers=admin_headers,
        json={"status": "cancelled"},
    )
    assert first_cancel.status_code == 200
    assert first_cancel.json()["data"]["status"] == "cancelled"

    with SessionLocal() as db:
        assert db.get(Product, 1).stock == 20
        assert db.get(Product, 2).stock == 10

    # Repeated sequential cancellation requests are rejected (409) and never increase stock again
    for _ in range(2):
        repeat_cancel = client.put(
            f"/api/v1/orders/{oid}/status",
            headers=admin_headers,
            json={"status": "cancelled"},
        )
        assert repeat_cancel.status_code == 409

    with SessionLocal() as db:
        assert db.get(Product, 1).stock == 20
        assert db.get(Product, 2).stock == 10

    # Real PostgreSQL concurrency: 4 concurrent admin sessions racing to cancel the same order
    with pg_session_factory() as setup_db:
        setup_db.get(Product, 1).stock = 10
        setup_db.add(CartItem(user_id=2, product_id=1, quantity=3))
        setup_db.commit()

    with pg_session_factory() as order_db:
        pg_order = OrderService.create_order(
            db=order_db,
            user_id=2,
            request=OrderCreateRequest(
                shipping_address="PG Cancel St, Phnom Penh",
                payment_method="Cash on Delivery",
            ),
        )
        pg_order_id = pg_order.id

    with pg_session_factory() as check_db:
        assert check_db.get(Product, 1).stock == 7

    cancel_barrier = threading.Barrier(4, timeout=10.0)

    def _concurrent_cancel(_idx: int) -> int:
        with pg_session_factory() as db:
            admin = db.get(User, 1)
            cancel_barrier.wait()
            try:
                OrderService.update_order_status(
                    db=db,
                    order_id=pg_order_id,
                    status_val="cancelled",
                    actor=admin,
                )
                return 200
            except HTTPException as exc:
                return exc.status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        cancel_codes = list(pool.map(_concurrent_cancel, range(4)))

    assert cancel_codes.count(200) == 1, f"Expected 1 successful cancel, got {cancel_codes}"
    assert cancel_codes.count(409) == 3, f"Expected 3 conflict responses, got {cancel_codes}"

    with pg_session_factory() as verify_db:
        assert verify_db.get(Order, pg_order_id).status == "cancelled"
        assert verify_db.get(Product, 1).stock == 10  # Restored once (7 + 3 = 10), never 13/16/19


# ---------------------------------------------------------------------------
# 10. Existing POS Cash and COD functionality remains intact
# ---------------------------------------------------------------------------


def test_10_existing_pos_cash_and_cod_flows_remain_correct(client, admin_headers):
    # POS Cash sale with change calculation + low-stock alert
    cash_res = client.post(
        "/api/v1/pos/checkout",
        headers=admin_headers,
        json={
            "items": [{"product_id": 1, "quantity": 15}],
            "payment_method": "Cash",
            "discount_amount": "10.00",
            "tax_amount": "5.00",
            "amount_paid": "300.00",
        },
    )
    assert cash_res.status_code == 201, cash_res.text
    cash_data = cash_res.json()["data"]
    assert Decimal(str(cash_data["subtotal"])) == Decimal("300.00")
    assert Decimal(str(cash_data["total"])) == Decimal("295.00")
    assert Decimal(str(cash_data["change_due"])) == Decimal("5.00")
    assert cash_data["payment_status"] == "paid"

    # POS Cash on Delivery sale starts pending + $0 tender
    cod_res = client.post(
        "/api/v1/pos/checkout",
        headers=admin_headers,
        json={
            "items": [{"product_id": 1, "quantity": 2}],
            "payment_method": "Cash on Delivery",
            "amount_paid": "0.00",
        },
    )
    assert cod_res.status_code == 201, cod_res.text
    cod_data = cod_res.json()["data"]
    assert cod_data["payment_method"] == "Cash on Delivery"
    assert cod_data["payment_status"] == "pending"
    assert Decimal(str(cod_data["total"])) == Decimal("40.00")

    # Settle POS COD order through processing -> shipped -> delivered -> paid
    cod_oid = cod_data["order_id"]
    for step in ("processing", "shipped", "delivered"):
        assert (
            client.put(
                f"/api/v1/orders/{cod_oid}/status",
                headers=admin_headers,
                json={"status": step},
            ).status_code
            == 200
        )
    settled = client.put(
        f"/api/v1/orders/{cod_oid}/status",
        headers=admin_headers,
        json={"payment_status": "paid", "reason": "POS courier cash collected"},
    )
    assert settled.status_code == 200
    assert settled.json()["data"]["payment_status"] == "paid"

    with SessionLocal() as db:
        assert db.get(Product, 1).stock == 3  # 20 - 15 - 2

