"""Coupon security, transaction integrity, concurrency, and seeding tests (S11).

Tests coupon validation, expiration, usage limits, atomic redemption, rollback,
and disposable PostgreSQL concurrency testing.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading

from fastapi import HTTPException
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

from app.core.security import hash_password
from app.db.database import Base, SessionLocal
from app.models.cart import CartItem
from app.models.category import Category
from app.models.coupon import Coupon
from app.models.order import Order
from app.models.product import Product
from app.models.seller import Seller
from app.models.user import User
from app.schemas.order import OrderCreateRequest
from app.services.coupon_service import CouponService
from app.services.order_service import OrderService


# ---------------------------------------------------------------------------
# Ephemeral, TCP-disabled PostgreSQL cluster fixture for real concurrency tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def pg_cluster():
    initdb_bin = shutil.which("initdb")
    pg_ctl_bin = shutil.which("pg_ctl")
    if not initdb_bin or not pg_ctl_bin:
        pytest.skip("PostgreSQL initdb/pg_ctl binaries are not installed locally.")

    tmp_dir = tempfile.TemporaryDirectory(dir="/tmp", prefix="bp-pg-coupon-")
    root = Path(tmp_dir.name).resolve()
    data_dir = root / "data"
    sock_dir = root / "sock"
    log_file = root / "postgres.log"
    sock_dir.mkdir(parents=True, exist_ok=True)

    pg_engine = None
    started = False
    try:
        subprocess.run(
            [
                initdb_bin,
                "-D",
                str(data_dir),
                "-U",
                "bp_test",
                "-A",
                "trust",
                "--no-locale",
                "-E",
                "UTF8",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [
                pg_ctl_bin,
                "-D",
                str(data_dir),
                "-l",
                str(log_file),
                "-w",
                "-o",
                f"-k {sock_dir} -h '' -F",
                "start",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        started = True

        pg_url = URL.create(
            "postgresql+psycopg2",
            username="bp_test",
            database="postgres",
            query={"host": str(sock_dir)},
        )
        pg_engine = create_engine(
            pg_url,
            pool_pre_ping=True,
            pool_size=12,
            max_overflow=12,
        )

        with pg_engine.connect() as conn:
            assert pg_engine.url.get_backend_name() == "postgresql"
            actual_data_dir = Path(
                conn.exec_driver_sql("SHOW data_directory").scalar_one()
            ).resolve()
            if actual_data_dir != data_dir:
                raise RuntimeError(
                    f"Refusing to run against unexpected PostgreSQL data_directory: {actual_data_dir}"
                )

        yield pg_engine, data_dir
    finally:
        if pg_engine is not None:
            pg_engine.dispose()
        if started:
            subprocess.run(
                [pg_ctl_bin, "-D", str(data_dir), "-m", "immediate", "stop"],
                check=False,
                capture_output=True,
                text=True,
            )
        tmp_dir.cleanup()


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
        for uid in range(2, 10):
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
        db.add(Category(id=1, name="Electronics", is_active=True))
        db.flush()
        db.add(
            Seller(
                id=1,
                user_id=1,
                name="PG Store",
                owner_name="PG Owner",
                email="store@pg.test",
                status="Active",
            )
        )
        db.flush()
        db.add(
            Product(
                id=1,
                category_id=1,
                seller_id=1,
                name="Wireless Headphones",
                price=Decimal("50.00"),
                stock=50,
                is_active=True,
            )
        )
        db.add(
            Coupon(
                code="LIMITED1",
                description="One-time promotional code",
                discount_type="fixed",
                discount_value=Decimal("15.00"),
                min_order_amount=Decimal("20.00"),
                is_active=True,
                usage_limit=1,
                used_count=0,
            )
        )
        db.commit()
    return factory


# ---------------------------------------------------------------------------
# 1. Valid coupon application
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_1_valid_coupon_application_percent_and_fixed(client, headers, prefix):
    with SessionLocal() as db:
        db.add_all(
            [
                Coupon(
                    code="FIXED10",
                    discount_type="fixed",
                    discount_value=Decimal("10.00"),
                    min_order_amount=Decimal("20.00"),
                    is_active=True,
                ),
                Coupon(
                    code="PERC15",
                    discount_type="percent",
                    discount_value=Decimal("15.00"),
                    min_order_amount=Decimal("30.00"),
                    is_active=True,
                ),
            ]
        )
        db.commit()

    # Validate FIXED10 via endpoint
    val_res = client.post(
        f"{prefix}/coupons/validate",
        json={"code": "fixed10", "subtotal": 50.0},
    )
    assert val_res.status_code == 200
    data = val_res.json()["data"]
    assert data["valid"] is True
    assert Decimal(str(data["discount_amount"])) == Decimal("10.00")
    assert Decimal(str(data["new_subtotal"])) == Decimal("40.00")

    # Checkout with FIXED10 applies discount and increments used_count
    client.post(
        f"{prefix}/cart/items",
        headers=headers(2),
        json={"product_id": 1, "quantity": 2},  # 2 * 20 = $40 subtotal
    )
    order_res = client.post(
        f"{prefix}/orders",
        headers=headers(2),
        json={
            "shipping_address": "Street 101, Phnom Penh",
            "payment_method": "Cash on Delivery",
            "coupon_code": "FIXED10",
        },
    )
    assert order_res.status_code == 201, order_res.text
    order_data = order_res.json()["data"]
    assert Decimal(str(order_data["subtotal"])) == Decimal("40.00")
    assert Decimal(str(order_data["discount_amount"])) == Decimal("10.00")
    assert order_data["coupon_code"] == "FIXED10"

    with SessionLocal() as db:
        c = db.scalar(select(Coupon).where(Coupon.code == "FIXED10"))
        assert c.used_count == 1


# ---------------------------------------------------------------------------
# 2. Invalid or expired coupon rejection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_2_invalid_and_expired_coupon_rejection(client, headers, prefix):
    # Non-existent promo code
    not_found_res = client.post(
        f"{prefix}/coupons/validate",
        json={"code": "DOES_NOT_EXIST", "subtotal": 100.0},
    )
    assert not_found_res.status_code == 404

    # Expired coupon (both timezone-naive and timezone-aware stored dates)
    with SessionLocal() as db:
        yesterday_naive = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
        yesterday_aware = datetime.now(timezone.utc) - timedelta(days=1)
        db.add_all(
            [
                Coupon(
                    code="EXPIRED_NAIVE",
                    discount_type="fixed",
                    discount_value=Decimal("5.00"),
                    min_order_amount=Decimal("0.00"),
                    is_active=True,
                    expires_at=yesterday_naive,
                ),
                Coupon(
                    code="EXPIRED_AWARE",
                    discount_type="percent",
                    discount_value=Decimal("10.00"),
                    min_order_amount=Decimal("0.00"),
                    is_active=True,
                    expires_at=yesterday_aware,
                ),
            ]
        )
        db.commit()

    for code in ("EXPIRED_NAIVE", "EXPIRED_AWARE"):
        res = client.post(
            f"{prefix}/coupons/validate",
            json={"code": code, "subtotal": 50.0},
        )
        assert res.status_code == 400
        assert "expired" in res.json()["detail"].lower()

    # Checkout using expired coupon is rejected (400)
    client.post(
        f"{prefix}/cart/items",
        headers=headers(2),
        json={"product_id": 1, "quantity": 1},
    )
    bad_checkout = client.post(
        f"{prefix}/orders",
        headers=headers(2),
        json={
            "shipping_address": "Street 102, Phnom Penh",
            "payment_method": "Cash on Delivery",
            "coupon_code": "EXPIRED_NAIVE",
        },
    )
    assert bad_checkout.status_code == 400
    assert "expired" in bad_checkout.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 3. Inactive coupon rejection
# ---------------------------------------------------------------------------


def test_3_inactive_coupon_rejection(client, headers):
    with SessionLocal() as db:
        db.add(
            Coupon(
                code="INACTIVE_CODE",
                discount_type="fixed",
                discount_value=Decimal("5.00"),
                is_active=False,
            )
        )
        db.commit()

    res = client.post(
        "/api/v1/coupons/validate",
        json={"code": "INACTIVE_CODE", "subtotal": 50.0},
    )
    assert res.status_code == 400
    assert "no longer active" in res.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 4. Minimum order amount validation
# ---------------------------------------------------------------------------


def test_4_minimum_order_amount_validation(client, headers):
    with SessionLocal() as db:
        db.add(
            Coupon(
                code="MIN100",
                discount_type="fixed",
                discount_value=Decimal("20.00"),
                min_order_amount=Decimal("100.00"),
                is_active=True,
            )
        )
        db.commit()

    # Subtotal $80 < $100 -> 400
    res = client.post(
        "/api/v1/coupons/validate",
        json={"code": "MIN100", "subtotal": 80.0},
    )
    assert res.status_code == 400
    assert "minimum subtotal" in res.json()["detail"].lower()

    # Subtotal $100 >= $100 -> 200
    res_ok = client.post(
        "/api/v1/coupons/validate",
        json={"code": "MIN100", "subtotal": 100.0},
    )
    assert res_ok.status_code == 200
    assert res_ok.json()["data"]["valid"] is True


# ---------------------------------------------------------------------------
# 5. Maximum discount enforcement
# ---------------------------------------------------------------------------


def test_5_maximum_discount_enforcement(client, headers):
    with SessionLocal() as db:
        db.add(
            Coupon(
                code="CAP50",
                discount_type="percent",
                discount_value=Decimal("20.00"),  # 20%
                min_order_amount=Decimal("0.00"),
                max_discount_amount=Decimal("30.00"),  # Capped at $30
                is_active=True,
            )
        )
        db.commit()

    # Subtotal $300 -> 20% is $60, but capped at $30
    res = client.post(
        "/api/v1/coupons/validate",
        json={"code": "CAP50", "subtotal": 300.0},
    )
    assert res.status_code == 200
    assert Decimal(str(res.json()["data"]["discount_amount"])) == Decimal("30.00")
    assert Decimal(str(res.json()["data"]["new_subtotal"])) == Decimal("270.00")


# ---------------------------------------------------------------------------
# 6. Coupon usage limit reached
# ---------------------------------------------------------------------------


def test_6_coupon_usage_limit_reached(client, headers):
    with SessionLocal() as db:
        db.add(
            Coupon(
                code="LIMIT_REACHED",
                discount_type="fixed",
                discount_value=Decimal("5.00"),
                usage_limit=2,
                used_count=2,  # Already at limit
                is_active=True,
            )
        )
        db.commit()

    # Validation rejects at limit -> 409
    res = client.post(
        "/api/v1/coupons/validate",
        json={"code": "LIMIT_REACHED", "subtotal": 50.0},
    )
    assert res.status_code == 409
    assert "usage limit" in res.json()["detail"].lower()

    # Checkout rejects at limit -> 409
    client.post(
        "/api/v1/cart/items",
        headers=headers(2),
        json={"product_id": 1, "quantity": 1},
    )
    checkout_res = client.post(
        "/api/v1/orders",
        headers=headers(2),
        json={
            "shipping_address": "Street 103, Phnom Penh",
            "payment_method": "Cash on Delivery",
            "coupon_code": "LIMIT_REACHED",
        },
    )
    assert checkout_res.status_code == 409
    assert "usage limit" in checkout_res.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 7. Real PostgreSQL concurrency: racing for the last coupon redemption
# ---------------------------------------------------------------------------


def test_7_postgres_concurrent_checkouts_racing_for_last_coupon_redemption(
    pg_session_factory,
):
    buyer_ids = [2, 3, 4, 5]
    with pg_session_factory() as setup_db:
        # Product 1 has stock=50, Coupon LIMITED1 has usage_limit=1, used_count=0
        for uid in buyer_ids:
            setup_db.add(CartItem(user_id=uid, product_id=1, quantity=1))
        setup_db.commit()

    barrier = threading.Barrier(len(buyer_ids), timeout=10.0)

    def _attempt_coupon_checkout(uid: int) -> tuple[str, int]:
        with pg_session_factory() as db:
            barrier.wait()
            try:
                res = OrderService.create_order(
                    db=db,
                    user_id=uid,
                    request=OrderCreateRequest(
                        shipping_address=f"PG Coupon Buyer {uid}, Phnom Penh",
                        payment_method="Cash on Delivery",
                        coupon_code="LIMITED1",
                    ),
                )
                return ("ok", res.id)
            except HTTPException as exc:
                return ("http_error", exc.status_code)

    with ThreadPoolExecutor(max_workers=len(buyer_ids)) as pool:
        outcomes = list(pool.map(_attempt_coupon_checkout, buyer_ids))

    winners = [o for o in outcomes if o[0] == "ok"]
    conflicts = [o for o in outcomes if o == ("http_error", 409)]

    assert len(winners) == 1, f"Expected exactly 1 winner, got {outcomes}"
    assert len(conflicts) == len(buyer_ids) - 1, f"Expected 3 conflicts (409), got {outcomes}"

    with pg_session_factory() as verify_db:
        coupon = verify_db.scalar(select(Coupon).where(Coupon.code == "LIMITED1"))
        assert coupon.used_count == 1
        assert verify_db.scalar(select(func.count(Order.id))) == 1


# ---------------------------------------------------------------------------
# 8. Failed checkout rolling back coupon usage
# ---------------------------------------------------------------------------


def test_8_failed_checkout_rolls_back_coupon_usage(client, headers, monkeypatch):
    with SessionLocal() as db:
        db.add(
            Coupon(
                code="ROLLBACK_COUPON",
                discount_type="fixed",
                discount_value=Decimal("5.00"),
                is_active=True,
                usage_limit=1,
                used_count=0,
            )
        )
        db.add(CartItem(user_id=2, product_id=1, quantity=1))
        db.commit()

    # Simulate database commit crash inside OrderService.create_order
    with SessionLocal() as db:
        def boom():
            raise RuntimeError("Simulated crash after coupon deduction")

        monkeypatch.setattr(db, "commit", boom)

        with pytest.raises(RuntimeError, match="Simulated crash"):
            OrderService.create_order(
                db=db,
                user_id=2,
                request=OrderCreateRequest(
                    shipping_address="Crash Street, Phnom Penh",
                    payment_method="Cash on Delivery",
                    coupon_code="ROLLBACK_COUPON",
                ),
            )

    with SessionLocal() as verify_db:
        c = verify_db.scalar(select(Coupon).where(Coupon.code == "ROLLBACK_COUPON"))
        assert c.used_count == 0
        assert verify_db.scalar(select(func.count(Order.id))) == 0


# ---------------------------------------------------------------------------
# 9. Failed stock deduction leaving coupon usage unchanged
# ---------------------------------------------------------------------------


def test_9_failed_stock_deduction_leaves_coupon_usage_unchanged(client, headers):
    with SessionLocal() as db:
        db.get(Product, 1).stock = 0  # Zero stock
        db.add(
            Coupon(
                code="STOCK_FAIL_COUPON",
                discount_type="fixed",
                discount_value=Decimal("5.00"),
                is_active=True,
                usage_limit=1,
                used_count=0,
            )
        )
        db.add(CartItem(user_id=2, product_id=1, quantity=1))
        db.commit()

    res = client.post(
        "/api/v1/orders",
        headers=headers(2),
        json={
            "shipping_address": "Street 104, Phnom Penh",
            "payment_method": "Cash on Delivery",
            "coupon_code": "STOCK_FAIL_COUPON",
        },
    )
    assert res.status_code == 409
    assert "insufficient stock" in res.json()["detail"].lower()

    with SessionLocal() as db:
        c = db.scalar(select(Coupon).where(Coupon.code == "STOCK_FAIL_COUPON"))
        assert c.used_count == 0


# ---------------------------------------------------------------------------
# 10. No automatic coupon seeding during validation
# ---------------------------------------------------------------------------


def test_10_no_automatic_coupon_seeding_during_validation_or_available(client):
    with SessionLocal() as db:
        db.query(Coupon).delete()
        db.commit()

    # Validate non-existent code on empty DB returns 404, does NOT seed
    val_res = client.post(
        "/api/v1/coupons/validate",
        json={"code": "WELCOME10", "subtotal": 100.0},
    )
    assert val_res.status_code == 404

    # Available coupons on empty DB returns empty list, does NOT seed
    avail_res = client.get("/api/v1/coupons/available")
    assert avail_res.status_code == 200
    assert avail_res.json()["data"] == []

    with SessionLocal() as db:
        assert db.scalar(select(func.count(Coupon.id))) == 0


# ---------------------------------------------------------------------------
# 11. Unauthorized coupon administration rejection
# ---------------------------------------------------------------------------


def test_11_unauthorized_coupon_administration_rejection(client, headers, admin_headers):
    # Anonymous -> 401
    assert client.get("/api/v1/coupons").status_code == 401
    assert client.post("/api/v1/coupons", json={"code": "T1", "discount_value": 5}).status_code == 401

    # Customer (2) and Seller (4) -> 403
    for uid in (2, 4):
        assert client.get("/api/v1/coupons", headers=headers(uid)).status_code == 403
        assert client.post(
            "/api/v1/coupons",
            headers=headers(uid),
            json={"code": "T1", "discount_value": 5},
        ).status_code == 403
        assert client.put(
            "/api/v1/coupons/1",
            headers=headers(uid),
            json={"description": "Hacked"},
        ).status_code == 403
        assert client.delete("/api/v1/coupons/1", headers=headers(uid)).status_code == 403

    # Admin -> CRUD works
    create_res = client.post(
        "/api/v1/coupons",
        headers=admin_headers,
        json={
            "code": "ADMIN_PROMO",
            "description": "Admin created promo",
            "discount_type": "percent",
            "discount_value": "25.00",
            "usage_limit": 50,
        },
    )
    assert create_res.status_code == 201, create_res.text
    new_cid = create_res.json()["data"]["id"]

    list_res = client.get("/api/v1/coupons", headers=admin_headers)
    assert list_res.status_code == 200
    assert any(c["id"] == new_cid for c in list_res.json()["data"])

    upd_res = client.put(
        f"/api/v1/coupons/{new_cid}",
        headers=admin_headers,
        json={"description": "Updated promo description"},
    )
    assert upd_res.status_code == 200
    assert upd_res.json()["data"]["description"] == "Updated promo description"

    del_res = client.delete(f"/api/v1/coupons/{new_cid}", headers=admin_headers)
    assert del_res.status_code == 200


# ---------------------------------------------------------------------------
# 12. Existing non-coupon checkout functionality remains correct
# ---------------------------------------------------------------------------


def test_12_existing_non_coupon_checkout_remains_correct(client, headers):
    client.post(
        "/api/v1/cart/items",
        headers=headers(2),
        json={"product_id": 1, "quantity": 2},
    )
    order_res = client.post(
        "/api/v1/orders",
        headers=headers(2),
        json={
            "shipping_address": "Street 105, Phnom Penh",
            "payment_method": "Cash on Delivery",
        },
    )
    assert order_res.status_code == 201
    data = order_res.json()["data"]
    assert data["coupon_code"] is None
    assert Decimal(str(data["discount_amount"])) == Decimal("0.00")
    assert Decimal(str(data["subtotal"])) == Decimal("40.00")
    assert Decimal(str(data["total"])) == Decimal("42.00")  # 40 + 2 shipping

