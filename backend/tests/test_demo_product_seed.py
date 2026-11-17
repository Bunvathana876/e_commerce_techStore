"""Seed safety tests use only the temporary SQLite database from conftest."""

import pytest
from sqlalchemy import func, select

from app.db.database import engine
from app.models import Category, Product, Seller, User
from scripts.seed_demo_products import (
    DEMO, MARKER, SeedError, build_plan, insert_plan, require_database_owner, target_url,
)


def catalog():
    return {model.__tablename__: model.__table__ for model in (Category, Product, User, Seller)}


def test_dry_run_leaves_database_unchanged():
    with engine.connect() as conn:
        plan = build_plan(conn, catalog())
        assert plan["inserts"] == {"categories": 7, "products": 8}
        assert plan["counts_before"]["products"] == 2
        assert conn.scalar(select(func.count()).select_from(Product)) == 2
        assert all(p["data"]["seller_id"] is None and p["data"]["rating"] == 0
                   and MARKER in p["data"]["description"] for p in plan["products"])


def test_repeated_seed_preserves_existing_data_and_inserts_once():
    with engine.begin() as conn:
        existing = conn.execute(select(Product.__table__)).all()
        accounts = conn.execute(select(User.__table__)).all()
        sellers = conn.execute(select(Seller.__table__)).all()
        first = build_plan(conn, catalog())
        insert_plan(conn, catalog(), first)
        second = build_plan(conn, catalog())
        assert second["inserts"] == {"categories": 0, "products": 0}
        insert_plan(conn, catalog(), second)
        assert conn.scalar(select(func.count()).select_from(Product)) == 10
        assert conn.execute(select(Product.__table__).where(Product.id.in_([1, 2]))).all() == existing
        assert conn.execute(select(User.__table__)).all() == accounts
        assert conn.execute(select(Seller.__table__)).all() == sellers
        for spec in DEMO:
            rows = conn.execute(select(Product.__table__, Category.name.label("category_name"))
                                .join(Category, Category.id == Product.category_id)
                                .where(Product.name == spec[0])).mappings().all()
            assert len(rows) == 1
            assert rows[0]["category_name"] == spec[2]
            assert rows[0]["stock"] == spec[3]


def test_existing_real_product_conflict_refuses_overwrite():
    with engine.begin() as conn:
        conn.execute(Product.__table__.insert().values(
            name="  macbook air m3  ", category_id=1, price=1, stock=3))
        with pytest.raises(SeedError, match="conflicts"):
            build_plan(conn, catalog())


def test_duplicate_category_names_stop_seed():
    with engine.begin() as conn:
        conn.execute(Category.__table__.insert(), [{"name": "Audio"}, {"name": " audio "}])
        with pytest.raises(SeedError, match="Ambiguous"):
            build_plan(conn, catalog())


def test_inactive_category_stops_seed():
    with engine.begin() as conn:
        conn.execute(Category.__table__.insert().values(name="Audio", is_active=False))
        with pytest.raises(SeedError, match="inactive"):
            build_plan(conn, catalog())


def test_failure_rolls_back_all_seed_inserts():
    with pytest.raises(RuntimeError, match="simulate failure"):
        with engine.begin() as conn:
            insert_plan(conn, catalog(), build_plan(conn, catalog()))
            raise RuntimeError("simulate failure")
    with engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(Product)) == 2
        assert conn.scalar(select(func.count()).select_from(Category)) == 1


def test_missing_admin_does_not_require_fabricated_accounts():
    with engine.begin() as conn:
        conn.execute(User.__table__.update().where(User.id == 1).values(is_active=False))
        plan = build_plan(conn, catalog())
        assert plan["active_admin_count"] == 0
        assert "Admin API unavailable" in plan["account_setup"]
        assert all(p["data"]["seller_id"] is None for p in plan["products"])


@pytest.mark.parametrize("permissions", [[], [
    {"table_name": "categories", "owns_table": True, "can_select": True, "can_insert": True, "sequence_usage": True},
    {"table_name": "products", "owns_table": False, "can_select": True, "can_insert": True, "sequence_usage": True},
]])
def test_database_owner_authorization_cannot_be_skipped(permissions):
    class Result:
        def mappings(self):
            return self

        def all(self):
            return permissions

    class Connection:
        def execute(self, statement):
            return Result()

    with pytest.raises(SeedError, match="database role"):
        require_database_owner(Connection())


def test_target_rejects_local_database_even_with_supabase_process_env(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://ignored:ignored@ignored.pooler.supabase.com:5432/postgres")
    config = tmp_path / "target.env"
    config.write_text("DATABASE_URL=postgresql://demo:demo@127.0.0.1:5432/ecommerce_db\n")
    with pytest.raises(SeedError, match="Refusing"):
        target_url(config)


def test_target_enforces_encrypted_supabase_session_pooler(tmp_path):
    config = tmp_path / "target.env"
    config.write_text("DATABASE_URL=postgresql://postgres.example:placeholder@example.pooler.supabase.com:5432/postgres?sslmode=disable\n")
    assert target_url(config).query["sslmode"] == "require"
