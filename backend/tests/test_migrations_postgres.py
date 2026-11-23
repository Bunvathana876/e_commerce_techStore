"""PostgreSQL migration verification tests on isolated disposable databases.

Validates that:
1. Fresh database upgrades cleanly to initial revision then to head.
2. Populated databases upgrade without data loss.
3. Runtime-created tables are safely preserved.
4. Missing columns are added safely.
5. Migration is fully idempotent.
6. Duplicate category names trigger clear error and prevent constraint creation.
7. Negative stock triggers clear error.
8. Invalid review ratings trigger clear error.
9. Negative coupon used_count triggers clear error.
10. Orphan foreign-key references trigger clear error.
11. Failed migrations roll back and do not stamp the head revision.
12. Downgrade cleanly reverts to initial revision on disposable databases.
"""
from pathlib import Path
import secrets
import pytest
import sqlalchemy as sa

from alembic import command
from alembic.config import Config


ALEMBIC_INI_PATH = Path(__file__).resolve().parent.parent / "alembic.ini"
REVISION_HEAD = "g3b4c5d6e7f8"
REVISION_PHASE2 = "f2a3b4c5d6e7"
REVISION_IDEMPOTENCY = "e1f2a3b4c5d6"
REVISION_LEGACY_REVOCATION = "d7e8f9012abc"
REVISION_SESSIONS = "a1b2c3d4e5f6"
REVISION_CONSOLIDATED = "c4b8d91a2e3f"
REVISION_INITIAL = "f904b613102f"
POSTGRES_BASE_URL = None


@pytest.fixture(scope="module", autouse=True)
def isolated_migration_cluster(pg_cluster):
    global POSTGRES_BASE_URL
    engine, data_dir = pg_cluster
    with engine.connect() as conn:
        assert Path(conn.exec_driver_sql("SHOW data_directory").scalar_one()).resolve() == data_dir
        assert conn.exec_driver_sql("SHOW listen_addresses").scalar_one() == ""
    POSTGRES_BASE_URL = engine.url
    yield
    POSTGRES_BASE_URL = None


class DisposablePostgresDB:
    """Manages creation and teardown of an isolated disposable PostgreSQL test database."""

    def __init__(self, prefix: str = "bluepanda_mig_"):
        self.db_name = f"{prefix}{secrets.token_hex(6)}"
        assert POSTGRES_BASE_URL is not None
        assert POSTGRES_BASE_URL.host is None
        self.base_engine = sa.create_engine(POSTGRES_BASE_URL, isolation_level="AUTOCOMMIT")
        self.db_url = POSTGRES_BASE_URL.set(database=self.db_name)

    def __enter__(self):
        with self.base_engine.connect() as conn:
            conn.execute(sa.text(f'CREATE DATABASE "{self.db_name}"'))
        self.engine = sa.create_engine(self.db_url)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self, "engine"):
            self.engine.dispose()
        with self.base_engine.connect() as conn:
            conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{self.db_name}" WITH (FORCE)'))
        self.base_engine.dispose()

    def get_alembic_config(self) -> Config:
        cfg = Config(str(ALEMBIC_INI_PATH))
        cfg.set_main_option("sqlalchemy.url", self.db_url.render_as_string(hide_password=False).replace("%", "%%"))
        return cfg


def test_1_fresh_database_migration():
    """Verify fresh PostgreSQL database migrates cleanly to initial revision then to head."""
    with DisposablePostgresDB("test_fresh_") as disp:
        cfg = disp.get_alembic_config()

        # Step 1: Migrate to initial
        command.upgrade(cfg, REVISION_INITIAL)
        inspector = sa.inspect(disp.engine)
        tables_initial = set(inspector.get_table_names())
        assert tables_initial == {
            "users", "categories", "products", "addresses",
            "orders", "cart_items", "favorites", "order_items",
            "alembic_version"
        }

        # Step 2: Migrate to consolidated revision
        command.upgrade(cfg, REVISION_CONSOLIDATED)
        inspector = sa.inspect(disp.engine)
        tables_consolidated = set(inspector.get_table_names())
        expected_consolidated = {
            "users", "categories", "products", "addresses",
            "orders", "cart_items", "favorites", "order_items",
            "sellers", "coupons", "notifications", "reviews",
            "alembic_version"
        }
        assert tables_consolidated == expected_consolidated

        # Step 3: Migrate to head, including the legacy revocation barrier and idempotency records
        command.upgrade(cfg, "head")
        inspector = sa.inspect(disp.engine)
        tables_head = set(inspector.get_table_names())
        expected_tables = {
            "users", "categories", "products", "addresses",
            "orders", "cart_items", "favorites", "order_items",
            "sellers", "coupons", "notifications", "reviews",
            "user_sessions", "refresh_tokens",
            "idempotency_records",
            "password_reset_tokens", "payment_transactions",
            "suppliers", "warehouses", "warehouse_stocks",
            "inventory_journal_entries", "inventory_ledger_lines",
            "purchase_orders", "purchase_order_items",
            "warehouse_transfers", "warehouse_transfer_items",
            "refunds", "refund_ledger_entries",
            "coupon_redemptions", "store_settings",
            "order_shipments", "order_tracking_events",
            "alembic_version",
        }
        assert tables_head == expected_tables

        # Verify added columns on existing tables
        product_cols = {c["name"] for c in inspector.get_columns("products")}
        assert "seller_id" in product_cols
        order_cols = {c["name"] for c in inspector.get_columns("orders")}
        assert "discount_amount" in order_cols
        assert "coupon_code" in order_cols

        # Verify check constraints
        prod_checks = {ck["name"] for ck in inspector.get_check_constraints("products")}
        assert "ck_products_stock_non_negative" in prod_checks
        coupon_checks = {ck["name"] for ck in inspector.get_check_constraints("coupons")}
        assert "ck_coupons_used_count_non_negative" in coupon_checks
        assert "ck_coupons_usage_limit_valid" in coupon_checks


def test_2_existing_populated_database_preserves_records():
    """Verify populated database migrates without losing existing records."""
    with DisposablePostgresDB("test_populated_") as disp:
        cfg = disp.get_alembic_config()
        command.upgrade(cfg, REVISION_INITIAL)

        # Seed existing records into initial tables
        with disp.engine.begin() as conn:
            conn.execute(sa.text("""
                INSERT INTO users (id, name, email, password_hash, role, is_active)
                VALUES (1, 'Alice Test', 'alice@test.com', 'hash123', 'customer', true)
            """))
            conn.execute(sa.text("""
                INSERT INTO categories (id, name, is_active)
                VALUES (1, 'Apparel', true)
            """))
            conn.execute(sa.text("""
                INSERT INTO products (id, category_id, name, price, stock, rating, is_active)
                VALUES (101, 1, 'Running Shoes', 89.99, 15, 0.00, true)
            """))
            conn.execute(sa.text("""
                INSERT INTO orders (id, user_id, status, subtotal, shipping_fee, total, payment_method, payment_status, shipping_address)
                VALUES (501, 1, 'pending', 89.99, 5.00, 94.99, 'cod', 'pending', '123 Test St')
            """))

        # Upgrade to head
        command.upgrade(cfg, "head")

        # Verify records are preserved
        with disp.engine.connect() as conn:
            user = conn.execute(sa.text("SELECT email, name FROM users WHERE id = 1")).fetchone()
            assert user == ("alice@test.com", "Alice Test")

            product = conn.execute(sa.text("SELECT name, stock, seller_id FROM products WHERE id = 101")).fetchone()
            assert product == ("Running Shoes", 15, None)

            order = conn.execute(sa.text("SELECT total, discount_amount, coupon_code FROM orders WHERE id = 501")).fetchone()
            assert float(order[0]) == 94.99
            assert float(order[1]) == 0.00
            assert order[2] is None


def test_3_existing_database_with_runtime_created_tables():
    """Verify database with runtime-created tables (Base.metadata.create_all) preserves data."""
    with DisposablePostgresDB("test_runtime_") as disp:
        cfg = disp.get_alembic_config()
        command.upgrade(cfg, REVISION_INITIAL)

        # Simulate previous runtime create_all() creating sellers and coupons
        with disp.engine.begin() as conn:
            conn.execute(sa.text("""
                CREATE TABLE sellers (
                    id SERIAL PRIMARY KEY,
                    user_id INT,
                    name VARCHAR(150) NOT NULL,
                    owner_name VARCHAR(100) NOT NULL,
                    email VARCHAR(255) NOT NULL,
                    phone VARCHAR(50),
                    address VARCHAR(255),
                    description TEXT,
                    logo VARCHAR(500),
                    status VARCHAR(20) DEFAULT 'Active' NOT NULL,
                    rating NUMERIC(3, 2) DEFAULT 5.00 NOT NULL,
                    products_count INT DEFAULT 0 NOT NULL,
                    orders_count INT DEFAULT 0 NOT NULL,
                    total_revenue NUMERIC(12, 2) DEFAULT 0.00 NOT NULL,
                    created_at TIMESTAMP DEFAULT now() NOT NULL,
                    updated_at TIMESTAMP DEFAULT now() NOT NULL
                );
                INSERT INTO sellers (id, name, owner_name, email)
                VALUES (10, 'Existing Store', 'Bob Owner', 'bob@store.com');
            """))
            conn.execute(sa.text("""
                CREATE TABLE coupons (
                    id SERIAL PRIMARY KEY,
                    code VARCHAR(50) UNIQUE NOT NULL,
                    description VARCHAR(255),
                    discount_type VARCHAR(20) DEFAULT 'percent' NOT NULL,
                    discount_value NUMERIC(10, 2) NOT NULL,
                    min_order_amount NUMERIC(10, 2) DEFAULT 0.00 NOT NULL,
                    max_discount_amount NUMERIC(10, 2),
                    is_active BOOLEAN DEFAULT true NOT NULL,
                    expires_at TIMESTAMP,
                    usage_limit INT,
                    used_count INT DEFAULT 0 NOT NULL,
                    created_at TIMESTAMP DEFAULT now() NOT NULL
                );
                INSERT INTO coupons (code, discount_type, discount_value, used_count)
                VALUES ('EXISTING20', 'percent', 20.00, 3);
            """))

        # Upgrade to head
        command.upgrade(cfg, "head")

        # Verify existing data was untouched
        with disp.engine.connect() as conn:
            seller = conn.execute(sa.text("SELECT name, email FROM sellers WHERE id = 10")).fetchone()
            assert seller == ("Existing Store", "bob@store.com")

            coupon = conn.execute(sa.text("SELECT code, used_count FROM coupons WHERE code = 'EXISTING20'")).fetchone()
            assert coupon == ("EXISTING20", 3)


def test_4_existing_database_missing_selected_columns():
    """Verify missing columns (discount_amount, coupon_code, seller_id) are added safely."""
    with DisposablePostgresDB("test_cols_") as disp:
        cfg = disp.get_alembic_config()
        command.upgrade(cfg, REVISION_INITIAL)

        with disp.engine.begin() as conn:
            conn.execute(sa.text("""
                INSERT INTO users (id, name, email, password_hash, role, is_active) VALUES (1, 'User 1', 'u1@test.com', 'h', 'customer', true);
                INSERT INTO orders (id, user_id, status, subtotal, shipping_fee, total, payment_method, payment_status, shipping_address)
                VALUES (1, 1, 'pending', 50.00, 0.00, 50.00, 'cod', 'pending', 'Addr');
            """))

        command.upgrade(cfg, "head")

        inspector = sa.inspect(disp.engine)
        order_cols = {c["name"] for c in inspector.get_columns("orders")}
        assert "discount_amount" in order_cols
        assert "coupon_code" in order_cols

        with disp.engine.connect() as conn:
            row = conn.execute(sa.text("SELECT discount_amount, coupon_code FROM orders WHERE id = 1")).fetchone()
            assert float(row[0]) == 0.00
            assert row[1] is None


def test_5_already_compatible_existing_schema_idempotency():
    """Verify re-running migration on an already upgraded database is an idempotent no-op."""
    with DisposablePostgresDB("test_idempotent_") as disp:
        cfg = disp.get_alembic_config()
        command.upgrade(cfg, "head")
        # Second run should succeed cleanly
        command.upgrade(cfg, "head")

        inspector = sa.inspect(disp.engine)
        tables = set(inspector.get_table_names())
        assert "sellers" in tables
        assert "coupons" in tables


def test_6_duplicate_category_names_raises_clear_error():
    """Verify migration raises clear error if duplicate categories exist before unique constraint."""
    with DisposablePostgresDB("test_dupe_cat_") as disp:
        cfg = disp.get_alembic_config()
        command.upgrade(cfg, REVISION_INITIAL)

        with disp.engine.begin() as conn:
            conn.execute(sa.text("""
                INSERT INTO categories (id, name, is_active) VALUES (1, 'Electronics', true);
                INSERT INTO categories (id, name, is_active) VALUES (2, 'Electronics', true);
            """))

        with pytest.raises(Exception) as exc_info:
            command.upgrade(cfg, "head")

        msg = str(exc_info.value)
        assert "duplicate categories found" in msg or "duplicate category" in msg.lower()


def test_7_negative_stock_raises_clear_error():
    """Verify migration raises clear error if negative stock exists before check constraint."""
    with DisposablePostgresDB("test_neg_stock_") as disp:
        cfg = disp.get_alembic_config()
        command.upgrade(cfg, REVISION_INITIAL)

        with disp.engine.begin() as conn:
            conn.execute(sa.text("INSERT INTO categories (id, name, is_active) VALUES (1, 'Cat 1', true)"))
            conn.execute(sa.text("""
                INSERT INTO products (id, category_id, name, price, stock, rating, is_active)
                VALUES (1, 1, 'Defective Item', 10.00, -5, 0.00, true)
            """))

        with pytest.raises(Exception) as exc_info:
            command.upgrade(cfg, "head")

        msg = str(exc_info.value)
        assert "negative stock" in msg.lower()


def test_8_invalid_review_ratings_raises_clear_error():
    """Verify migration raises clear error if invalid review ratings exist."""
    with DisposablePostgresDB("test_invalid_review_") as disp:
        cfg = disp.get_alembic_config()
        command.upgrade(cfg, REVISION_INITIAL)

        with disp.engine.begin() as conn:
            conn.execute(sa.text("INSERT INTO users (id, name, email, password_hash, role, is_active) VALUES (1, 'U', 'u@test.com', 'h', 'customer', true)"))
            conn.execute(sa.text("INSERT INTO categories (id, name, is_active) VALUES (1, 'C', true)"))
            conn.execute(sa.text("INSERT INTO products (id, category_id, name, price, stock, rating, is_active) VALUES (1, 1, 'P', 10.00, 10, 0.00, true)"))
            conn.execute(sa.text("""
                CREATE TABLE reviews (
                    id SERIAL PRIMARY KEY,
                    product_id INT NOT NULL,
                    user_id INT NOT NULL,
                    order_id INT,
                    rating INT NOT NULL,
                    comment TEXT NOT NULL,
                    status VARCHAR(30) DEFAULT 'pending' NOT NULL,
                    admin_reply TEXT,
                    admin_replied_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT now() NOT NULL,
                    updated_at TIMESTAMP DEFAULT now() NOT NULL
                );
                INSERT INTO reviews (product_id, user_id, rating, comment)
                VALUES (1, 1, 9, 'Impossible 9-star rating');
            """))

        with pytest.raises(Exception) as exc_info:
            command.upgrade(cfg, "head")

        msg = str(exc_info.value)
        assert "outside 1..5" in msg or "rating" in msg.lower()


def test_9_coupon_usage_counters_validation():
    """Verify migration raises clear error if coupon used_count is negative."""
    with DisposablePostgresDB("test_invalid_coupon_") as disp:
        cfg = disp.get_alembic_config()
        command.upgrade(cfg, REVISION_INITIAL)

        with disp.engine.begin() as conn:
            conn.execute(sa.text("""
                CREATE TABLE coupons (
                    id SERIAL PRIMARY KEY,
                    code VARCHAR(50) UNIQUE NOT NULL,
                    description VARCHAR(255),
                    discount_type VARCHAR(20) DEFAULT 'percent' NOT NULL,
                    discount_value NUMERIC(10, 2) NOT NULL,
                    min_order_amount NUMERIC(10, 2) DEFAULT 0.00 NOT NULL,
                    max_discount_amount NUMERIC(10, 2),
                    is_active BOOLEAN DEFAULT true NOT NULL,
                    expires_at TIMESTAMP,
                    usage_limit INT,
                    used_count INT DEFAULT -2 NOT NULL,
                    created_at TIMESTAMP DEFAULT now() NOT NULL
                );
                INSERT INTO coupons (code, discount_type, discount_value, used_count)
                VALUES ('CORRUPT', 'percent', 10.00, -2);
            """))

        with pytest.raises(Exception) as exc_info:
            command.upgrade(cfg, "head")

        msg = str(exc_info.value)
        assert "used_count < 0" in msg or "used_count" in msg.lower()


def test_10_foreign_key_and_orphan_consistency():
    """Verify orphan foreign-key references are detected and block constraint creation."""
    with DisposablePostgresDB("test_orphan_fk_") as disp:
        cfg = disp.get_alembic_config()
        command.upgrade(cfg, REVISION_INITIAL)

        # Existing products table has orphan seller_id = 999
        with disp.engine.begin() as conn:
            conn.execute(sa.text("ALTER TABLE products ADD COLUMN seller_id INT"))
            conn.execute(sa.text("INSERT INTO categories (id, name, is_active) VALUES (1, 'C', true)"))
            conn.execute(sa.text("""
                INSERT INTO products (id, category_id, name, price, stock, rating, is_active, seller_id)
                VALUES (1, 1, 'P', 10.00, 10, 0.00, true, 999)
            """))

        with pytest.raises(Exception) as exc_info:
            command.upgrade(cfg, "head")

        msg = str(exc_info.value)
        assert "orphan product" in msg.lower() or "sellers" in msg.lower()


def test_11_migration_failure_handling_and_rollback():
    """Verify that migration errors cause rollback and do not advance the alembic_version."""
    with DisposablePostgresDB("test_rollback_") as disp:
        cfg = disp.get_alembic_config()
        command.upgrade(cfg, REVISION_INITIAL)

        # Trigger conflict: duplicate categories
        with disp.engine.begin() as conn:
            conn.execute(sa.text("""
                INSERT INTO categories (id, name, is_active)
                VALUES (1, 'Shoes', true), (2, 'Shoes', true)
            """))

        try:
            command.upgrade(cfg, "head")
        except Exception:
            pass

        # Version must still be f904b613102f, NOT head
        with disp.engine.connect() as conn:
            current_rev = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
            assert current_rev == REVISION_INITIAL


def test_12_downgrade_behavior():
    """Verify downgrade on a disposable database cleanly reverts to initial revision."""
    with DisposablePostgresDB("test_downgrade_") as disp:
        cfg = disp.get_alembic_config()
        command.upgrade(cfg, "head")

        # Downgrade back to initial revision f904b613102f
        command.downgrade(cfg, REVISION_INITIAL)

        inspector = sa.inspect(disp.engine)
        tables = set(inspector.get_table_names())
        assert "user_sessions" not in tables
        assert "refresh_tokens" not in tables
        assert "idempotency_records" not in tables
        assert "sellers" not in tables
        assert "coupons" not in tables
        assert "notifications" not in tables
        assert "reviews" not in tables
        for added_tbl in (
            "password_reset_tokens",
            "payment_transactions",
            "suppliers",
            "warehouses",
            "warehouse_stocks",
            "inventory_journal_entries",
            "inventory_ledger_lines",
            "purchase_orders",
            "purchase_order_items",
            "warehouse_transfers",
            "warehouse_transfer_items",
            "refunds",
            "refund_ledger_entries",
        ):
            assert added_tbl not in tables

        order_cols = {c["name"] for c in inspector.get_columns("orders")}
        assert "discount_amount" not in order_cols
        assert "coupon_code" not in order_cols

        product_cols = {c["name"] for c in inspector.get_columns("products")}
        assert "seller_id" not in product_cols


def test_13_user_sessions_and_refresh_tokens_migration_and_constraints():
    """Verify user_sessions and refresh_tokens tables, columns, indexes, FKs, and cascades."""
    from datetime import datetime, timedelta, timezone
    from alembic.migration import MigrationContext
    from alembic.autogenerate import compare_metadata
    from app.db.database import Base
    import app.models  # noqa: F401

    with DisposablePostgresDB("test_sessions_") as disp:
        cfg = disp.get_alembic_config()
        command.upgrade(cfg, "head")

        inspector = sa.inspect(disp.engine)
        tables = set(inspector.get_table_names())
        assert "user_sessions" in tables
        assert "refresh_tokens" in tables

        # Verify columns and nullable constraints
        session_cols = {c["name"]: c for c in inspector.get_columns("user_sessions")}
        assert session_cols["session_id"]["nullable"] is False
        assert session_cols["user_id"]["nullable"] is False
        assert session_cols["token_family"]["nullable"] is False
        assert session_cols["is_revoked"]["nullable"] is False
        assert session_cols["expires_at"]["nullable"] is False
        assert session_cols["created_at"]["nullable"] is False
        assert session_cols["last_activity_at"]["nullable"] is False

        token_cols = {c["name"]: c for c in inspector.get_columns("refresh_tokens")}
        assert token_cols["session_id"]["nullable"] is False
        assert token_cols["token_hash"]["nullable"] is False
        assert token_cols["is_revoked"]["nullable"] is False
        assert token_cols["expires_at"]["nullable"] is False
        assert token_cols["created_at"]["nullable"] is False
        assert token_cols["used_at"]["nullable"] is True

        # Verify unique indexes
        session_indexes = {ix["name"]: ix for ix in inspector.get_indexes("user_sessions")}
        assert "ix_user_sessions_session_id" in session_indexes
        assert session_indexes["ix_user_sessions_session_id"]["unique"] is True
        assert "ix_user_sessions_user_id" in session_indexes
        assert "ix_user_sessions_token_family" in session_indexes
        assert "ix_user_sessions_expires_at" in session_indexes

        token_indexes = {ix["name"]: ix for ix in inspector.get_indexes("refresh_tokens")}
        assert "ix_refresh_tokens_token_hash" in token_indexes
        assert token_indexes["ix_refresh_tokens_token_hash"]["unique"] is True
        assert "ix_refresh_tokens_session_id" in token_indexes
        assert "ix_refresh_tokens_expires_at" in token_indexes

        # Verify foreign keys with CASCADE delete
        session_fks = {fk["name"]: fk for fk in inspector.get_foreign_keys("user_sessions")}
        assert session_fks["fk_user_sessions_user_id_users"]["referred_table"] == "users"
        assert session_fks["fk_user_sessions_user_id_users"]["options"].get("ondelete") == "CASCADE"

        token_fks = {fk["name"]: fk for fk in inspector.get_foreign_keys("refresh_tokens")}
        assert token_fks["fk_refresh_tokens_session_id_user_sessions"]["referred_table"] == "user_sessions"
        assert token_fks["fk_refresh_tokens_session_id_user_sessions"]["referred_columns"] == ["session_id"]
        assert token_fks["fk_refresh_tokens_session_id_user_sessions"]["options"].get("ondelete") == "CASCADE"

        # Verify zero schema drift against Base.metadata
        with disp.engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            diff = compare_metadata(ctx, Base.metadata)
            session_diff = [d for d in diff if "session" in str(d) or "refresh" in str(d)]
            assert len(session_diff) == 0, f"Schema drift detected: {session_diff}"

        # Seed valid data and verify operations
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=7)
        with disp.engine.begin() as conn:
            conn.execute(sa.text("""
                INSERT INTO users (id, name, email, password_hash, role, is_active)
                VALUES (1, 'Alice Test', 'alice@test.com', 'hashed_pwd', 'customer', true)
            """))
            conn.execute(sa.text("""
                INSERT INTO user_sessions (session_id, user_id, token_family, expires_at)
                VALUES ('sess-uuid-1', 1, 'fam-uuid-1', :exp)
            """), {"exp": expires})
            conn.execute(sa.text("""
                INSERT INTO refresh_tokens (session_id, token_hash, expires_at)
                VALUES ('sess-uuid-1', :hash, :exp)
            """), {"hash": "a" * 64, "exp": expires})

        # Verify duplicate session_id rejection
        with pytest.raises(Exception):
            with disp.engine.begin() as conn:
                conn.execute(sa.text("""
                    INSERT INTO user_sessions (session_id, user_id, token_family, expires_at)
                    VALUES ('sess-uuid-1', 1, 'fam-uuid-2', now())
                """))

        # Verify duplicate token_hash rejection
        with pytest.raises(Exception):
            with disp.engine.begin() as conn:
                conn.execute(sa.text("""
                    INSERT INTO refresh_tokens (session_id, token_hash, expires_at)
                    VALUES ('sess-uuid-1', :hash, now())
                """), {"hash": "a" * 64})

        # Verify invalid user_id foreign key rejection
        with pytest.raises(Exception):
            with disp.engine.begin() as conn:
                conn.execute(sa.text("""
                    INSERT INTO user_sessions (session_id, user_id, token_family, expires_at)
                    VALUES ('sess-orphan', 9999, 'fam-orphan', now())
                """))

        # Verify invalid session_id foreign key rejection
        with pytest.raises(Exception):
            with disp.engine.begin() as conn:
                conn.execute(sa.text("""
                    INSERT INTO refresh_tokens (session_id, token_hash, expires_at)
                    VALUES ('nonexistent-session', :hash, now())
                """), {"hash": "b" * 64})

        # Verify cascade deletion: User -> UserSession -> RefreshToken
        with disp.engine.begin() as conn:
            conn.execute(sa.text("DELETE FROM users WHERE id = 1"))

        with disp.engine.connect() as conn:
            assert conn.execute(sa.text("SELECT COUNT(*) FROM user_sessions WHERE user_id = 1")).scalar() == 0
            assert conn.execute(sa.text("SELECT COUNT(*) FROM refresh_tokens WHERE session_id = 'sess-uuid-1'")).scalar() == 0


def test_14_user_sessions_step_downgrade_and_reupgrade():
    """Verify downgrade to the pre-session revision, then restoration on a disposable DB."""
    with DisposablePostgresDB("test_step_down_") as disp:
        cfg = disp.get_alembic_config()
        command.upgrade(cfg, "head")

        # Explicit target: the new legacy barrier revision follows session creation.
        command.downgrade(cfg, REVISION_CONSOLIDATED)

        inspector = sa.inspect(disp.engine)
        tables = set(inspector.get_table_names())
        assert "user_sessions" not in tables
        assert "refresh_tokens" not in tables
        assert "idempotency_records" not in tables
        # Prior tables must remain untouched
        assert "sellers" in tables
        assert "coupons" in tables
        assert "notifications" in tables
        assert "reviews" in tables
        assert "users" in tables
        assert "products" in tables

        # Re-upgrade to head
        command.upgrade(cfg, "head")
        inspector_re = sa.inspect(disp.engine)
        tables_re = set(inspector_re.get_table_names())
        assert "user_sessions" in tables_re
        assert "refresh_tokens" in tables_re
        assert "idempotency_records" in tables_re


def test_15_legacy_barrier_preserves_admin_seller_and_session_records():
    """The additive marker must not reset credentials, roles, ownership, or sessions."""
    with DisposablePostgresDB("test_legacy_barrier_") as disp:
        cfg = disp.get_alembic_config()
        command.upgrade(cfg, REVISION_SESSIONS)
        with disp.engine.begin() as conn:
            conn.execute(sa.text("""
                INSERT INTO users (id, name, email, password_hash, role, is_active)
                VALUES (1, 'Existing Admin', 'admin@example.invalid', 'unchanged-admin-hash', 'admin', true),
                       (2, 'Existing Seller', 'seller@example.invalid', 'unchanged-seller-hash', 'seller', true)
            """))
            conn.execute(sa.text("""
                INSERT INTO sellers (id, user_id, name, owner_name, email)
                VALUES (1, 2, 'Existing Store', 'Existing Seller', 'store@example.invalid')
            """))
            conn.execute(sa.text("""
                INSERT INTO user_sessions (session_id, user_id, token_family, expires_at)
                VALUES ('preserved-session', 1, 'preserved-family', now() + interval '1 day')
            """))
            before = conn.execute(sa.text("SELECT id, password_hash, role FROM users ORDER BY id")).fetchall()
        command.upgrade(cfg, "head")
        command.upgrade(cfg, "head")
        with disp.engine.connect() as conn:
            assert conn.execute(sa.text("SELECT id, password_hash, role FROM users ORDER BY id")).fetchall() == before
            assert conn.execute(sa.text("SELECT user_id FROM sellers WHERE id = 1")).scalar() == 2
            assert conn.execute(sa.text("SELECT count(*) FROM user_sessions")).scalar() == 1
            assert conn.execute(sa.text("SELECT count(*) FROM users WHERE legacy_tokens_revoked_at IS NOT NULL")).scalar() == 0
        # Step rollback verified ONLY on this throwaway DB. Runtime rollback must
        # retain the marker because dropping it would erase revocation history.
        command.downgrade(cfg, REVISION_SESSIONS)
        assert "legacy_tokens_revoked_at" not in {c["name"] for c in sa.inspect(disp.engine).get_columns("users")}
        assert "user_sessions" in sa.inspect(disp.engine).get_table_names()
        command.upgrade(cfg, "head")
        with disp.engine.connect() as conn:
            assert conn.execute(sa.text("SELECT id, password_hash, role FROM users ORDER BY id")).fetchall() == before


def test_16_idempotency_records_migration_and_constraints():
    """Verify idempotency_records table, columns, indexes, FKs, unique constraint, cascades, and zero schema drift."""
    from alembic.migration import MigrationContext
    from alembic.autogenerate import compare_metadata
    from app.db.database import Base
    import app.models  # noqa: F401

    with DisposablePostgresDB("test_idem_") as disp:
        cfg = disp.get_alembic_config()
        command.upgrade(cfg, "head")

        inspector = sa.inspect(disp.engine)
        tables = set(inspector.get_table_names())
        assert "idempotency_records" in tables

        # Verify columns and nullable constraints
        cols = {c["name"]: c for c in inspector.get_columns("idempotency_records")}
        assert cols["id"]["nullable"] is False
        assert cols["user_id"]["nullable"] is False
        assert cols["key"]["nullable"] is False
        assert cols["status"]["nullable"] is False
        assert cols["order_id"]["nullable"] is True
        assert cols["response_data"]["nullable"] is True
        assert cols["created_at"]["nullable"] is False
        assert cols["updated_at"]["nullable"] is False

        # Verify indexes
        indexes = {idx["name"]: idx for idx in inspector.get_indexes("idempotency_records")}
        assert "ix_idempotency_records_user_id" in indexes
        assert "ix_idempotency_records_key" in indexes
        assert "ix_idempotency_records_order_id" in indexes

        # Verify unique constraint on (user_id, key)
        unique_cons = inspector.get_unique_constraints("idempotency_records")
        assert any(
            set(uc["column_names"]) == {"user_id", "key"} for uc in unique_cons
        ), f"Missing unique constraint on (user_id, key): {unique_cons}"

        # Verify foreign keys
        fks = {fk["name"]: fk for fk in inspector.get_foreign_keys("idempotency_records")}
        assert fks["fk_idempotency_records_user_id_users"]["referred_table"] == "users"
        assert fks["fk_idempotency_records_user_id_users"]["options"].get("ondelete") == "CASCADE"

        assert fks["fk_idempotency_records_order_id_orders"]["referred_table"] == "orders"
        assert fks["fk_idempotency_records_order_id_orders"]["options"].get("ondelete") == "SET NULL"

        # Verify zero schema drift against Base.metadata
        with disp.engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            diff = compare_metadata(ctx, Base.metadata)
            idem_diff = [d for d in diff if "idempotency" in str(d)]
            assert len(idem_diff) == 0, f"Schema drift detected: {idem_diff}"

        # Seed valid data and verify operations
        with disp.engine.begin() as conn:
            conn.execute(sa.text("""
                INSERT INTO users (id, name, email, password_hash, role, is_active)
                VALUES (1, 'Alice Test', 'alice@test.com', 'hashed_pwd', 'customer', true),
                       (2, 'Bob Test', 'bob@test.com', 'hashed_pwd', 'customer', true)
            """))
            conn.execute(sa.text("""
                INSERT INTO orders (id, user_id, status, subtotal, shipping_fee, total, payment_method, payment_status, shipping_address)
                VALUES (501, 1, 'pending', 50.00, 5.00, 55.00, 'cod', 'pending', '123 Test St')
            """))
            conn.execute(sa.text("""
                INSERT INTO idempotency_records (user_id, key, status, order_id, response_data)
                VALUES (1, 'key-alice-1', 'completed', 501, '{"id": 501}')
            """))

        # Verify duplicate (user_id, key) is rejected by DB unique constraint
        with pytest.raises(Exception):
            with disp.engine.begin() as conn:
                conn.execute(sa.text("""
                    INSERT INTO idempotency_records (user_id, key, status)
                    VALUES (1, 'key-alice-1', 'processing')
                """))

        # Verify same key for DIFFERENT user succeeds (customer namespace isolation)
        with disp.engine.begin() as conn:
            conn.execute(sa.text("""
                INSERT INTO idempotency_records (user_id, key, status)
                VALUES (2, 'key-alice-1', 'processing')
            """))

        # Verify deleting order sets order_id to NULL (ON DELETE SET NULL)
        with disp.engine.begin() as conn:
            conn.execute(sa.text("DELETE FROM orders WHERE id = 501"))

        with disp.engine.connect() as conn:
            rec = conn.execute(sa.text("SELECT order_id, status FROM idempotency_records WHERE user_id = 1")).fetchone()
            assert rec[0] is None
            assert rec[1] == "completed"

        # Verify deleting user cascades to idempotency records (ON DELETE CASCADE)
        with disp.engine.begin() as conn:
            conn.execute(sa.text("DELETE FROM users WHERE id = 1"))

        with disp.engine.connect() as conn:
            assert conn.execute(sa.text("SELECT COUNT(*) FROM idempotency_records WHERE user_id = 1")).scalar() == 0
            assert conn.execute(sa.text("SELECT COUNT(*) FROM idempotency_records WHERE user_id = 2")).scalar() == 1

        # Step downgrade to legacy revocation barrier drops idempotency_records cleanly
        command.downgrade(cfg, REVISION_LEGACY_REVOCATION)
        inspector_down = sa.inspect(disp.engine)
        assert "idempotency_records" not in set(inspector_down.get_table_names())
        assert "user_sessions" in set(inspector_down.get_table_names())
        assert "users" in set(inspector_down.get_table_names())

        # Re-upgrade to head restores idempotency_records
        command.upgrade(cfg, "head")
        inspector_up = sa.inspect(disp.engine)
        assert "idempotency_records" in set(inspector_up.get_table_names())


def test_17_payments_recovery_inventory_suppliers_refunds_migration_and_immutability():
    """Verify 13 new tables, zero schema drift, downgrade/upgrade, and PG ledger immutability triggers."""
    from alembic.migration import MigrationContext
    from alembic.autogenerate import compare_metadata
    from app.db.database import Base
    import app.models  # noqa: F401

    new_tables = (
        "password_reset_tokens",
        "payment_transactions",
        "suppliers",
        "warehouses",
        "warehouse_stocks",
        "inventory_journal_entries",
        "inventory_ledger_lines",
        "purchase_orders",
        "purchase_order_items",
        "warehouse_transfers",
        "warehouse_transfer_items",
        "refunds",
        "refund_ledger_entries",
    )

    with DisposablePostgresDB("test_phase2_features_") as disp:
        cfg = disp.get_alembic_config()
        command.upgrade(cfg, "head")

        inspector = sa.inspect(disp.engine)
        tables = set(inspector.get_table_names())
        for table_name in new_tables:
            assert table_name in tables, f"Missing migrated table {table_name}"

        # Zero Alembic metadata drift across all new tables
        with disp.engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            diff = compare_metadata(ctx, Base.metadata)
            new_table_diffs = [
                d
                for d in diff
                if any(t in str(d) for t in new_tables)
            ]
            assert len(new_table_diffs) == 0, f"Schema drift detected: {new_table_diffs}"

        # Seed valid baseline + immutable ledger records
        with disp.engine.begin() as conn:
            conn.execute(sa.text("""
                INSERT INTO users (id, name, email, password_hash, role, is_active)
                VALUES (1, 'Admin', 'admin@test.com', 'hash', 'admin', true)
            """))
            conn.execute(sa.text("""
                INSERT INTO categories (id, name, is_active)
                VALUES (1, 'Electronics', true)
            """))
            conn.execute(sa.text("""
                INSERT INTO products (id, category_id, name, price, stock, rating, is_active)
                VALUES (1, 1, 'Router', 50.00, 10, 0.00, true)
            """))
            conn.execute(sa.text("""
                INSERT INTO orders (id, user_id, status, subtotal, shipping_fee, total, payment_method, payment_status, shipping_address)
                VALUES (501, 1, 'delivered', 50.00, 0.00, 50.00, 'Cash on Delivery', 'paid', 'Phnom Penh')
            """))
            conn.execute(sa.text("""
                INSERT INTO warehouses (id, code, name, is_default, is_active)
                VALUES (1, 'WH-MAIN', 'Main Warehouse', true, true)
            """))
            conn.execute(sa.text("""
                INSERT INTO suppliers (id, code, name, contact_name, email)
                VALUES (1, 'SUP-001', 'Acme Supply', 'Jane Doe', 'jane@acme.test')
            """))
            conn.execute(sa.text("""
                INSERT INTO inventory_journal_entries (id, entry_number, entry_type, reason, created_by_user_id)
                VALUES (1, 'INV-JRN-0001', 'opening', 'Seed test', 1)
            """))
            conn.execute(sa.text("""
                INSERT INTO inventory_ledger_lines (id, journal_entry_id, product_id, product_name, warehouse_id, account_type, debit_qty, credit_qty, unit_cost, balance_after)
                VALUES (1, 1, 1, 'Router', 1, 'INVENTORY_ON_HAND', 10, 0, 25.00, 10)
            """))
            conn.execute(sa.text("""
                INSERT INTO refunds (id, refund_number, order_id, customer_id, amount, currency, refund_method, status, reason)
                VALUES (1, 'REF-0001', 501, 1, 50.00, 'USD', 'Cash on Delivery', 'approved', 'Defective item')
            """))
            conn.execute(sa.text("""
                INSERT INTO refund_ledger_entries (id, journal_ref, refund_id, order_id, entry_type, account_code, account_name, debit_amount, credit_amount, currency)
                VALUES (1, 'REF-GL-0001', 1, 501, 'accrual', '4100', 'Sales Returns & Refunds', 50.00, 0.00, 'USD')
            """))

        # PostgreSQL triggers must block UPDATE & DELETE on all 3 immutable ledger tables
        for stmt in (
            "UPDATE inventory_journal_entries SET reason = 'Tampered' WHERE id = 1",
            "DELETE FROM inventory_journal_entries WHERE id = 1",
            "UPDATE inventory_ledger_lines SET debit_qty = 999 WHERE id = 1",
            "DELETE FROM inventory_ledger_lines WHERE id = 1",
            "UPDATE refund_ledger_entries SET debit_amount = 999.00 WHERE id = 1",
            "DELETE FROM refund_ledger_entries WHERE id = 1",
        ):
            with pytest.raises(Exception):
                with disp.engine.begin() as conn:
                    conn.execute(sa.text(stmt))

        # Downgrade one step to REVISION_IDEMPOTENCY drops all 13 tables cleanly
        command.downgrade(cfg, REVISION_IDEMPOTENCY)
        inspector_down = sa.inspect(disp.engine)
        down_tables = set(inspector_down.get_table_names())
        for table_name in new_tables:
            assert table_name not in down_tables, f"{table_name} still present after downgrade"
        assert "idempotency_records" in down_tables

        # Re-upgrade to head restores everything cleanly
        command.upgrade(cfg, "head")
        inspector_up = sa.inspect(disp.engine)
        up_tables = set(inspector_up.get_table_names())
        for table_name in new_tables:
            assert table_name in up_tables, f"{table_name} missing after re-upgrade"


def test_18_store_settings_shipments_coupon_redemptions_migration():
    """Verify g3b4c5d6e7f8 tables/columns, zero metadata drift, and clean downgrade/re-upgrade."""
    from alembic.migration import MigrationContext
    from alembic.autogenerate import compare_metadata
    from app.db.database import Base
    import app.models  # noqa: F401

    phase3_tables = (
        "coupon_redemptions",
        "store_settings",
        "order_shipments",
        "order_tracking_events",
    )

    with DisposablePostgresDB("test_phase3_features_") as disp:
        cfg = disp.get_alembic_config()
        command.upgrade(cfg, "head")

        inspector = sa.inspect(disp.engine)
        tables = set(inspector.get_table_names())
        for table_name in phase3_tables:
            assert table_name in tables, f"Missing migrated table {table_name}"
        coupon_cols = {c["name"] for c in inspector.get_columns("coupons")}
        assert "per_user_limit" in coupon_cols

        with disp.engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            diff = compare_metadata(ctx, Base.metadata)
            relevant_diffs = [
                d for d in diff
                if any(t in str(d) for t in (*phase3_tables, "per_user_limit"))
            ]
            assert len(relevant_diffs) == 0, f"Schema drift detected: {relevant_diffs}"

        command.downgrade(cfg, REVISION_PHASE2)
        inspector_down = sa.inspect(disp.engine)
        down_tables = set(inspector_down.get_table_names())
        for table_name in phase3_tables:
            assert table_name not in down_tables
        assert "per_user_limit" not in {c["name"] for c in inspector_down.get_columns("coupons")}

        command.upgrade(cfg, "head")
        inspector_up = sa.inspect(disp.engine)
        up_tables = set(inspector_up.get_table_names())
        for table_name in phase3_tables:
            assert table_name in up_tables
