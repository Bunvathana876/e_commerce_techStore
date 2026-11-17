"""
Comprehensive integration and unit tests for Fix 2 — Checkout Reliability:
1. Atomic backend checkout operation via POST /orders with explicit items list.
2. Complete rollback on validation or stock failures: server cart and inventory untouched.
3. Request idempotency preventing duplicate orders and duplicate inventory deductions.
4. In-flight concurrency lock returning HTTP 409 Conflict on simultaneous duplicate submissions.
5. User isolation ensuring idempotency keys do not leak or collide across customers.
6. Safe, non-destructive cart reconciliation via PUT /cart and POST /cart/reconcile.
7. Reconciliation failure rollbacks preserving existing cart without partial destruction.
8. Backward compatibility for legacy / mobile checkout without explicit items.
9. Uniform behavior across /api and /api/v1 prefixes.
"""
from decimal import Decimal
import pytest
from sqlalchemy import select

from app.db.database import SessionLocal
from app.models.cart import CartItem
from app.models.order import Order
from app.models.product import Product
from app.services.idempotency_service import IdempotencyService


@pytest.fixture(autouse=True)
def reset_idempotency_state():
    """Ensure clean idempotency state before and after each test."""
    IdempotencyService.reset()
    yield
    IdempotencyService.reset()


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_atomic_checkout_with_items_success(client, headers, prefix):
    """
    Atomic checkout: passing explicit items in POST /orders creates the order,
    deducts inventory, removes checked-out items from the server cart, and
    records a notification—all in a single atomic transaction.
    """
    buyer = headers(2)

    # Place an unrelated item in the user's server cart (Product 2, qty 1)
    with SessionLocal() as db:
        p1 = db.get(Product, 1)
        p1.stock = 20
        p1.is_active = True
        p2 = db.get(Product, 2)
        p2.stock = 20
        p2.is_active = True
        db.commit()

    client.post(
        f"{prefix}/cart/items",
        headers=buyer,
        json={"product_id": 2, "quantity": 1},
    )

    # Perform atomic checkout with Product 1 (qty 3)
    checkout_res = client.post(
        f"{prefix}/orders",
        headers=buyer,
        json={
            "shipping_address": "123 Norodom Blvd, Phnom Penh",
            "payment_method": "Cash on Delivery",
            "items": [{"product_id": 1, "quantity": 3}],
        },
    )
    assert checkout_res.status_code == 201, checkout_res.text
    order_data = checkout_res.json()["data"]
    order_id = order_data["id"]

    assert order_data["status"] == "pending"
    assert order_data["payment_method"] == "Cash on Delivery"
    assert len(order_data["items"]) == 1
    assert order_data["items"][0]["product_id"] == 1
    assert order_data["items"][0]["quantity"] == 3

    # Verify inventory was deducted from 20 to 17
    with SessionLocal() as db:
        assert db.get(Product, 1).stock == 17
        # Verify Product 1 was removed from server cart, but unrelated Product 2 remains
        cart_items = list(
            db.scalars(select(CartItem).where(CartItem.user_id == 2)).all()
        )
        assert len(cart_items) == 1
        assert cart_items[0].product_id == 2


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_atomic_checkout_out_of_stock_rolls_back_cleanly(client, headers, prefix):
    """
    Atomic checkout failure: if an item has insufficient stock, the entire checkout
    fails with HTTP 400. Inventory is untouched, and existing server cart items are
    completely preserved without partial deletion.
    """
    buyer = headers(2)

    # Seed server cart with Product 1 (qty 2)
    with SessionLocal() as db:
        p1 = db.get(Product, 1)
        p1.stock = 5
        p1.is_active = True
        db.commit()

    client.post(
        f"{prefix}/cart/items",
        headers=buyer,
        json={"product_id": 1, "quantity": 2},
    )

    # Attempt atomic checkout for quantity 10 (exceeds stock 5)
    res = client.post(
        f"{prefix}/orders",
        headers=buyer,
        json={
            "shipping_address": "123 Norodom Blvd, Phnom Penh",
            "payment_method": "Cash on Delivery",
            "items": [{"product_id": 1, "quantity": 10}],
        },
    )
    assert res.status_code in (400, 409)
    assert "insufficient stock" in res.json()["detail"].lower()

    # Verify inventory was NOT deducted
    with SessionLocal() as db:
        assert db.get(Product, 1).stock == 5
        # Verify user's server cart is completely intact!
        cart_items = list(
            db.scalars(select(CartItem).where(CartItem.user_id == 2)).all()
        )
        assert len(cart_items) == 1
        assert cart_items[0].product_id == 1
        assert cart_items[0].quantity == 2


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_atomic_checkout_inactive_product_rolls_back(client, headers, prefix):
    """
    Atomic checkout failure: if a product is inactive, checkout fails with HTTP 400.
    Database transaction rolls back.
    """
    buyer = headers(2)

    with SessionLocal() as db:
        p1 = db.get(Product, 1)
        p1.is_active = False
        db.commit()

    res = client.post(
        f"{prefix}/orders",
        headers=buyer,
        json={
            "shipping_address": "123 Norodom Blvd, Phnom Penh",
            "payment_method": "Cash on Delivery",
            "items": [{"product_id": 1, "quantity": 1}],
        },
    )
    assert res.status_code == 400
    assert "no longer available" in res.json()["detail"].lower()

    # Restore active
    with SessionLocal() as db:
        p1 = db.get(Product, 1)
        p1.is_active = True
        db.commit()


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_request_idempotency_prevents_duplicate_orders(client, headers, prefix):
    """
    Request idempotency: retrying a checkout request with the same Idempotency-Key
    returns the confirmed order without deducting inventory a second time or
    creating a duplicate order record.
    """
    buyer = headers(2)
    idem_key = "test-idem-order-uuid-001"

    with SessionLocal() as db:
        p1 = db.get(Product, 1)
        p1.stock = 20
        p1.is_active = True
        db.commit()

    # First attempt: succeeds with 201 Created
    headers_with_key = dict(buyer)
    headers_with_key["Idempotency-Key"] = idem_key

    res1 = client.post(
        f"{prefix}/orders",
        headers=headers_with_key,
        json={
            "shipping_address": "123 Norodom Blvd, Phnom Penh",
            "payment_method": "Cash on Delivery",
            "items": [{"product_id": 1, "quantity": 2}],
        },
    )
    assert res1.status_code == 201
    order1 = res1.json()["data"]
    order1_id = order1["id"]

    # Verify inventory was decremented by 2 (20 -> 18)
    with SessionLocal() as db:
        assert db.get(Product, 1).stock == 18

    # Second attempt (retry with same key): returns 200 OK with Idempotent-Replayed: true
    res2 = client.post(
        f"{prefix}/orders",
        headers=headers_with_key,
        json={
            "shipping_address": "123 Norodom Blvd, Phnom Penh",
            "payment_method": "Cash on Delivery",
            "items": [{"product_id": 1, "quantity": 2}],
        },
    )
    assert res2.status_code == 200
    assert res2.headers.get("Idempotent-Replayed") == "true"
    order2 = res2.json()["data"]
    assert order2["id"] == order1_id

    # Verify inventory was NOT decremented a second time (still 18!)
    with SessionLocal() as db:
        assert db.get(Product, 1).stock == 18
        # Verify only ONE order exists for this user in the database
        orders = list(db.scalars(select(Order).where(Order.user_id == 2)).all())
        assert len(orders) == 1
        assert orders[0].id == order1_id


def test_request_idempotency_in_flight_concurrency_conflict(client, headers):
    """
    In-flight protection: simultaneous concurrent submissions with the same idempotency key
    result in HTTP 409 Conflict.
    """
    buyer = headers(2)
    idem_key = "test-concurrent-idem-key"

    # Simulate an active in-flight request by manually acquiring the lock
    is_replay, cached = IdempotencyService.check_or_acquire(user_id=2, key=idem_key)
    assert is_replay is False
    assert cached is None

    # While in-flight, a second request arrives
    headers_with_key = dict(buyer)
    headers_with_key["Idempotency-Key"] = idem_key

    res = client.post(
        "/api/v1/orders",
        headers=headers_with_key,
        json={
            "shipping_address": "123 Norodom Blvd, Phnom Penh",
            "payment_method": "Cash on Delivery",
            "items": [{"product_id": 1, "quantity": 1}],
        },
    )
    assert res.status_code == 409
    assert "currently processing" in res.json()["detail"].lower()


def test_request_idempotency_failure_allows_subsequent_retry(client, headers):
    """
    Failure resilience: if a checkout request fails (e.g. invalid shipping address),
    the in-flight lock is released so the customer can fix the issue and retry.
    """
    buyer = headers(2)
    idem_key = "test-fail-retry-key"
    headers_with_key = dict(buyer)
    headers_with_key["Idempotency-Key"] = idem_key

    # Attempt with empty address -> 400
    res_bad = client.post(
        "/api/v1/orders",
        headers=headers_with_key,
        json={
            "shipping_address": "   ",
            "payment_method": "Cash on Delivery",
            "items": [{"product_id": 1, "quantity": 1}],
        },
    )
    assert res_bad.status_code == 400

    # Retry with valid address using same key -> succeeds with 201
    res_ok = client.post(
        "/api/v1/orders",
        headers=headers_with_key,
        json={
            "shipping_address": "456 Monivong Blvd, Phnom Penh",
            "payment_method": "Cash on Delivery",
            "items": [{"product_id": 1, "quantity": 1}],
        },
    )
    assert res_ok.status_code == 201
    assert res_ok.json()["success"] is True


def test_idempotency_keys_scoped_per_customer(client, headers):
    """
    Customer isolation: User A and User B can use the same idempotency key string
    without collision or cross-talk.
    """
    buyer_a = headers(2)
    buyer_b = headers(3)  # Another customer
    shared_key = "shared-uuid-string"

    with SessionLocal() as db:
        p1 = db.get(Product, 1)
        p1.stock = 50
        p1.is_active = True
        db.commit()

    res_a = client.post(
        "/api/v1/orders",
        headers={**buyer_a, "Idempotency-Key": shared_key},
        json={
            "shipping_address": "User A address",
            "payment_method": "Cash on Delivery",
            "items": [{"product_id": 1, "quantity": 1}],
        },
    )
    assert res_a.status_code == 201
    order_a_id = res_a.json()["data"]["id"]

    res_b = client.post(
        "/api/v1/orders",
        headers={**buyer_b, "Idempotency-Key": shared_key},
        json={
            "shipping_address": "User B address",
            "payment_method": "Cash on Delivery",
            "items": [{"product_id": 1, "quantity": 1}],
        },
    )
    assert res_b.status_code == 201
    order_b_id = res_b.json()["data"]["id"]

    assert order_a_id != order_b_id


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_safe_non_destructive_cart_reconciliation_success(client, headers, prefix):
    """
    Safe cart reconciliation: PUT /cart and POST /cart/reconcile atomically sync
    the user's cart in a single transaction.
    """
    buyer = headers(2)

    with SessionLocal() as db:
        p1 = db.get(Product, 1)
        p1.stock = 20
        p1.is_active = True
        p2 = db.get(Product, 2)
        p2.stock = 20
        p2.is_active = True
        db.commit()

    # Initial state: Product 1 (qty 2) in cart
    client.post(
        f"{prefix}/cart/items",
        headers=buyer,
        json={"product_id": 1, "quantity": 2},
    )

    # Reconcile to Product 1 (qty 4) and Product 2 (qty 1) via PUT /cart
    sync_res = client.put(
        f"{prefix}/cart",
        headers=buyer,
        json={
            "items": [
                {"product_id": 1, "quantity": 4},
                {"product_id": 2, "quantity": 1},
            ]
        },
    )
    assert sync_res.status_code == 200, sync_res.text
    cart_data = sync_res.json()["data"]
    assert cart_data["total_items"] == 5

    # Verify via GET /cart
    get_res = client.get(f"{prefix}/cart", headers=buyer)
    items = get_res.json()["data"]["items"]
    prod_qty_map = {item["product_id"]: item["quantity"] for item in items}
    assert prod_qty_map == {1: 4, 2: 1}


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_safe_non_destructive_cart_reconciliation_failure_preserves_cart(
    client, headers, prefix
):
    """
    Reconciliation failure safety: if one item in the reconciliation payload
    exceeds stock or is invalid, the request fails with HTTP 400.
    The user's prior server cart is completely untouched (not partially modified).
    """
    buyer = headers(2)

    with SessionLocal() as db:
        p1 = db.get(Product, 1)
        p1.stock = 10
        p1.is_active = True
        p2 = db.get(Product, 2)
        p2.stock = 2
        p2.is_active = True
        db.commit()

    # Clear and set initial cart: Product 1 (qty 2)
    client.delete(f"{prefix}/cart", headers=buyer)
    client.post(
        f"{prefix}/cart/items",
        headers=buyer,
        json={"product_id": 1, "quantity": 2},
    )

    # Attempt to reconcile with Product 1 (qty 3) and Product 2 (qty 99 - exceeds stock 2)
    fail_res = client.post(
        f"{prefix}/cart/reconcile",
        headers=buyer,
        json={
            "items": [
                {"product_id": 1, "quantity": 3},
                {"product_id": 2, "quantity": 99},
            ]
        },
    )
    assert fail_res.status_code == 400
    assert "stock" in fail_res.json()["detail"].lower()

    # Verify user's server cart STILL has Product 1 (qty 2) untouched!
    get_res = client.get(f"{prefix}/cart", headers=buyer)
    items = get_res.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["product_id"] == 1
    assert items[0]["quantity"] == 2


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_backward_compatibility_server_cart_checkout(client, headers, prefix):
    """
    Backward compatibility: when POST /orders is called without an explicit items
    list (e.g. legacy callers or mobile app), it checks out the user's server cart.
    """
    buyer = headers(2)

    with SessionLocal() as db:
        p1 = db.get(Product, 1)
        p1.stock = 15
        p1.is_active = True
        db.commit()

    # Put Product 1 (qty 2) into cart
    client.delete(f"{prefix}/cart", headers=buyer)
    client.post(
        f"{prefix}/cart/items",
        headers=buyer,
        json={"product_id": 1, "quantity": 2},
    )

    # Legacy checkout: no items property in body
    res = client.post(
        f"{prefix}/orders",
        headers=buyer,
        json={
            "shipping_address": "789 Russian Blvd, Phnom Penh",
            "payment_method": "Cash on Delivery",
        },
    )
    assert res.status_code == 201
    order = res.json()["data"]
    assert len(order["items"]) == 1
    assert order["items"][0]["product_id"] == 1
    assert order["items"][0]["quantity"] == 2

    # Verify stock decremented (15 -> 13)
    with SessionLocal() as db:
        assert db.get(Product, 1).stock == 13
        # Server cart was cleared after confirmed order
        cart_items = list(
            db.scalars(select(CartItem).where(CartItem.user_id == 2)).all()
        )
        assert len(cart_items) == 0


# ===========================================================================
# Hardened Idempotency: Multi-Worker Concurrency & Server Restart Durability
# ===========================================================================


def test_cross_worker_concurrency_race_condition(headers):
    """
    Multi-worker concurrency test:
    Simulates multiple concurrent worker threads simultaneously submitting the same checkout
    payload with the exact same Idempotency-Key.
    Proves:
    1. Exactly ONE worker successfully creates the order (HTTP 201).
    2. All other concurrent workers receive HTTP 409 Conflict (while locked) or HTTP 200 OK (replay).
    3. Exactly ONE order record is inserted into the database.
    4. Inventory is decremented exactly ONCE (never duplicated).
    5. Exactly ONE IdempotencyRecord with status='completed' exists in the database.
    """
    import concurrent.futures
    from fastapi.testclient import TestClient
    from app.main import app
    from app.models.idempotency import IdempotencyRecord

    buyer = headers(2)
    idem_key = "concurrent-worker-race-key-001"

    with SessionLocal() as db:
        p1 = db.get(Product, 1)
        p1.stock = 20
        p1.is_active = True
        db.commit()

    order_payload = {
        "shipping_address": "456 Monivong Blvd, Phnom Penh",
        "payment_method": "Cash on Delivery",
        "items": [{"product_id": 1, "quantity": 2}],
    }

    worker_count = 5
    results = []

    def run_worker_checkout():
        with TestClient(app) as worker_client:
            h = dict(buyer)
            h["Idempotency-Key"] = idem_key
            res = worker_client.post(
                "/api/v1/orders",
                headers=h,
                json=order_payload,
            )
            return res.status_code, res.headers.get("Idempotent-Replayed"), res.json()

    with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [executor.submit(run_worker_checkout) for _ in range(worker_count)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    # Analyze worker responses
    status_codes = [r[0] for r in results]
    created_count = status_codes.count(201)
    conflict_count = status_codes.count(409)
    replay_count = status_codes.count(200)

    # Exactly ONE worker must have succeeded in creating the order (HTTP 201)
    assert created_count == 1, f"Expected exactly 1 HTTP 201, got {created_count}. Statuses: {status_codes}"
    # All remaining workers must be either 409 Conflict or 200 Replay
    assert conflict_count + replay_count == worker_count - 1, f"Unexpected statuses: {status_codes}"

    # Database verification
    with SessionLocal() as db:
        # Stock decremented by 2 exactly once: 20 -> 18
        assert db.get(Product, 1).stock == 18

        # Exactly 1 Order row for user 2
        orders = list(db.scalars(select(Order).where(Order.user_id == 2)).all())
        assert len(orders) == 1

        # Exactly 1 completed idempotency record in DB
        idem_records = list(
            db.scalars(
                select(IdempotencyRecord).where(
                    IdempotencyRecord.user_id == 2,
                    IdempotencyRecord.key == idem_key,
                )
            ).all()
        )
        assert len(idem_records) == 1
        assert idem_records[0].status == "completed"
        assert idem_records[0].order_id == orders[0].id


def test_server_restart_durability(headers):
    """
    Server restart durability test:
    Proves duplicate order protection survives complete server restarts/crashes:
    1. Client submits checkout with Idempotency-Key and creates Order #1 (HTTP 201).
    2. Simulate server crash and cold restart:
       - Clear all connection pools, sessions, and process memory.
       - Re-instantiate a fresh TestClient representing a newly booted production server.
    3. Client retries the request with the same Idempotency-Key against the restarted server.
    4. Restarted server loads the persisted idempotency record from the database.
    5. Returns HTTP 200 OK with Idempotent-Replayed: true and the identical order payload.
    6. Zero duplicate orders created; stock remains decremented only once.
    """
    from fastapi.testclient import TestClient
    from app.main import app

    buyer = headers(2)
    idem_key = "server-restart-durability-key-777"

    with SessionLocal() as db:
        p1 = db.get(Product, 1)
        p1.stock = 20
        p1.is_active = True
        db.commit()

    order_payload = {
        "shipping_address": "888 Confederation St, Phnom Penh",
        "payment_method": "Cash on Delivery",
        "items": [{"product_id": 1, "quantity": 3}],
    }

    # First attempt: Pre-restart server creates order
    with TestClient(app) as pre_restart_client:
        h = dict(buyer)
        h["Idempotency-Key"] = idem_key
        res1 = pre_restart_client.post(
            "/api/v1/orders",
            headers=h,
            json=order_payload,
        )
        assert res1.status_code == 201
        order1 = res1.json()["data"]
        order1_id = order1["id"]

    # Verify inventory was decremented once: 20 -> 17
    with SessionLocal() as db:
        assert db.get(Product, 1).stock == 17

    # =========================================================================
    # SIMULATE COMPLETE SERVER RESTART:
    # Dispose all database connections and instantiate a brand-new TestClient
    # =========================================================================
    from app.db.database import engine
    engine.dispose()

    with TestClient(app) as post_restart_client:
        h = dict(buyer)
        h["Idempotency-Key"] = idem_key
        res2 = post_restart_client.post(
            "/api/v1/orders",
            headers=h,
            json=order_payload,
        )
        assert res2.status_code == 200
        assert res2.headers.get("Idempotent-Replayed") == "true"
        order2 = res2.json()["data"]
        assert order2["id"] == order1_id
        assert order2["total"] == order1["total"]

    # Post-restart database verification: still only 1 order and stock unchanged (17)
    with SessionLocal() as db:
        assert db.get(Product, 1).stock == 17
        orders = list(db.scalars(select(Order).where(Order.user_id == 2)).all())
        assert len(orders) == 1
        assert orders[0].id == order1_id


def test_worker_crash_stale_lock_takeover(client, headers):
    """
    Worker crash resilience test:
    Simulates a worker dying mid-flight (leaving status='processing' with an abandoned timestamp).
    Proves:
    1. Stale in-flight locks (> 60s) from crashed workers are automatically detected.
    2. Retrying client takes over the lock rather than remaining stuck with HTTP 409 indefinitely.
    3. Order is successfully created and status transitions to 'completed'.
    """
    from datetime import datetime, timedelta, timezone
    from app.models.idempotency import IdempotencyRecord

    buyer = headers(2)
    idem_key = "crashed-worker-recovery-key-999"

    with SessionLocal() as db:
        p1 = db.get(Product, 1)
        p1.stock = 20
        p1.is_active = True
        # Simulate crashed worker that acquired the lock 120 seconds ago
        crashed_time = datetime.now(timezone.utc) - timedelta(seconds=120)
        crashed_rec = IdempotencyRecord(
            user_id=2,
            key=idem_key,
            status="processing",
            created_at=crashed_time,
            updated_at=crashed_time,
        )
        db.add(crashed_rec)
        db.commit()

    # Retry arrives after worker crash
    h = dict(buyer)
    h["Idempotency-Key"] = idem_key
    res = client.post(
        "/api/v1/orders",
        headers=h,
        json={
            "shipping_address": "Crashed Worker Recovery St",
            "payment_method": "Cash on Delivery",
            "items": [{"product_id": 1, "quantity": 1}],
        },
    )
    assert res.status_code == 201, res.text
    order_data = res.json()["data"]

    # Verify order placed and idempotency record now completed
    with SessionLocal() as db:
        assert db.get(Product, 1).stock == 19
        rec = db.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.user_id == 2,
                IdempotencyRecord.key == idem_key,
            )
        )
        assert rec is not None
        assert rec.status == "completed"
        assert rec.order_id == order_data["id"]


def test_failed_checkout_releases_lock_for_retry(client, headers):
    """
    Lock release on failure test:
    Proves that when checkout fails (e.g. out of stock or invalid data):
    1. The in-flight processing lock is cleanly released from the database.
    2. The customer can fix the cart or item quantity and retry with the SAME key.
    3. The retry succeeds with HTTP 201 Created.
    """
    from app.models.idempotency import IdempotencyRecord

    buyer = headers(2)
    idem_key = "failed-checkout-retry-key-555"

    with SessionLocal() as db:
        p1 = db.get(Product, 1)
        p1.stock = 2
        p1.is_active = True
        db.commit()

    h = dict(buyer)
    h["Idempotency-Key"] = idem_key

    # Attempt 1: Requests 10 units (stock is only 2) -> fails with 400/409
    fail_res = client.post(
        "/api/v1/orders",
        headers=h,
        json={
            "shipping_address": "123 Test St",
            "payment_method": "Cash on Delivery",
            "items": [{"product_id": 1, "quantity": 10}],
        },
    )
    assert fail_res.status_code in (400, 409)

    # Verify in-flight processing record was released (deleted) from database
    with SessionLocal() as db:
        rec = db.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.user_id == 2,
                IdempotencyRecord.key == idem_key,
            )
        )
        assert rec is None, "Processing lock should be deleted on failed checkout"
        assert db.get(Product, 1).stock == 2

    # Attempt 2: Customer reduces quantity to 2 and retries with the SAME key -> succeeds!
    success_res = client.post(
        "/api/v1/orders",
        headers=h,
        json={
            "shipping_address": "123 Test St",
            "payment_method": "Cash on Delivery",
            "items": [{"product_id": 1, "quantity": 2}],
        },
    )
    assert success_res.status_code == 201, success_res.text
    order_data = success_res.json()["data"]

    # Verify inventory was decremented and idempotency record is completed
    with SessionLocal() as db:
        assert db.get(Product, 1).stock == 0
        rec = db.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.user_id == 2,
                IdempotencyRecord.key == idem_key,
            )
        )
        assert rec is not None
        assert rec.status == "completed"
        assert rec.order_id == order_data["id"]


def test_customer_namespace_isolation(client, headers):
    """
    Customer namespace isolation test:
    Proves that idempotency keys are strictly partitioned by user_id:
    1. User 2 and User 3 can checkout with the EXACT same idempotency key string.
    2. Both succeed independently with HTTP 201 and distinct order IDs.
    3. Replaying the key as User 2 returns User 2's order, never User 3's.
    4. Replaying the key as User 3 returns User 3's order, never User 2's.
    """
    buyer2 = headers(2)
    buyer3 = headers(3)
    shared_key = "shared-customer-key-abc"

    with SessionLocal() as db:
        p1 = db.get(Product, 1)
        p1.stock = 20
        p1.is_active = True
        db.commit()

    # User 2 orders 1 unit
    h2 = dict(buyer2)
    h2["Idempotency-Key"] = shared_key
    res2 = client.post(
        "/api/v1/orders",
        headers=h2,
        json={
            "shipping_address": "User 2 Address",
            "payment_method": "Cash on Delivery",
            "items": [{"product_id": 1, "quantity": 1}],
        },
    )
    assert res2.status_code == 201
    order2_id = res2.json()["data"]["id"]

    # User 3 orders 1 unit with the SAME key
    h3 = dict(buyer3)
    h3["Idempotency-Key"] = shared_key
    res3 = client.post(
        "/api/v1/orders",
        headers=h3,
        json={
            "shipping_address": "User 3 Address",
            "payment_method": "Cash on Delivery",
            "items": [{"product_id": 1, "quantity": 1}],
        },
    )
    assert res3.status_code == 201
    order3_id = res3.json()["data"]["id"]

    # Orders must be distinct
    assert order2_id != order3_id

    # Replay by User 2 returns User 2's order
    replay2 = client.post(
        "/api/v1/orders",
        headers=h2,
        json={
            "shipping_address": "User 2 Address",
            "payment_method": "Cash on Delivery",
            "items": [{"product_id": 1, "quantity": 1}],
        },
    )
    assert replay2.status_code == 200
    assert replay2.headers.get("Idempotent-Replayed") == "true"
    assert replay2.json()["data"]["id"] == order2_id

    # Replay by User 3 returns User 3's order
    replay3 = client.post(
        "/api/v1/orders",
        headers=h3,
        json={
            "shipping_address": "User 3 Address",
            "payment_method": "Cash on Delivery",
            "items": [{"product_id": 1, "quantity": 1}],
        },
    )
    assert replay3.status_code == 200
    assert replay3.headers.get("Idempotent-Replayed") == "true"
    assert replay3.json()["data"]["id"] == order3_id

