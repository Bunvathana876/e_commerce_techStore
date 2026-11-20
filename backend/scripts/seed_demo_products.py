"""Read-only by default. Run from backend with python -m scripts.seed_demo_products.

Writes require a reviewed plan hash, explicit confirmation, and verified database ownership.
No application startup, migrations, account creation, or configuration writes.
"""

import argparse
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import sys
from urllib.parse import quote
from urllib.request import Request, urlopen

from dotenv import dotenv_values
from sqlalchemy import MetaData, Table, create_engine, func, insert, select, text
from sqlalchemy.engine import Connection, URL, make_url
from sqlalchemy.pool import NullPool

from app.schemas.category import CategoryCreate
from app.schemas.product import ProductCreate


API = os.getenv("API_URL", "https://e-commerce-techstore-bhu7.onrender.com/api")
MARKER = "[Blue Panda demonstration content v1]"
DEMO = (
    ("MacBook Air M3", "999.00", "Laptops", 12,
     "Lightweight laptop for everyday work, study, and browsing."),
    ("Sony WH-1000XM5", "299.00", "Audio", 20,
     "Wireless over-ear headphones for music, calls, and focused listening."),
    ("Logitech MX Master 3S", "99.00", "Accessories", 30,
     "Wireless productivity mouse for a comfortable desktop workspace."),
    ("Samsung Galaxy S24", "699.00", "Smartphones", 15,
     "Everyday smartphone for communication, photography, and mobile apps."),
    ("iPad Air", "599.00", "Tablets", 18,
     "Portable tablet for reading, notes, entertainment, and creative tasks."),
    ("Keychron K2 Mechanical Keyboard", "89.00", "Accessories", 25,
     "Compact mechanical keyboard for everyday typing and desk setups."),
    ("Dell UltraSharp 27-inch Monitor", "399.00", "Monitors", 10,
     "27-inch desktop monitor for documents, multitasking, and creative work."),
    ("HyperX Cloud III Headset", "99.00", "Gaming", 22,
     "Over-ear gaming headset for game audio and team voice chat."),
)


class SeedError(Exception):
    """An operator-facing validation error containing no secrets."""


def target_url(env_file: Path) -> URL:
    # Deliberately ignore .env and process DATABASE_URL: neither can select a target.
    raw = dotenv_values(env_file, interpolate=False).get("DATABASE_URL")
    if not raw:
        raise SeedError("DATABASE_URL missing from the explicit Supabase env file.")
    try:
        url = make_url(raw)
    except Exception:
        raise SeedError("Invalid database URL; value withheld.") from None
    host = url.host or ""
    if not (
        url.get_backend_name() in {"postgres", "postgresql"}
        and host.endswith(".pooler.supabase.com")
        and url.database == "postgres"
        and url.port == 5432
        and (url.username or "").startswith("postgres.")
    ):
        raise SeedError("Refusing a non-Supabase session-pooler target or local database.")
    return url.set(drivername="postgresql+psycopg2", query={**url.query, "sslmode": "require"})


def tables(conn: Connection) -> dict[str, Table]:
    metadata = MetaData()
    return {name: Table(name, metadata, schema="public", autoload_with=conn)
            for name in ("categories", "products", "users", "sellers")}


def payload(spec: tuple, category_id: int) -> dict:
    name, price, _, stock, description = spec
    data = ProductCreate(
        category_id=category_id, seller_id=None, name=name,
        description=f"{MARKER} {description} Demo price and inventory; sample listing for storefront testing.",
        price=Decimal(price), discount_price=None, stock=stock,
        image_url=None, rating=Decimal("0.00"), is_active=True,
    ).model_dump()
    if len(name) > 200 or data["price"] <= 0 or stock <= 0:
        raise SeedError("Invalid demo product specification.")
    return data


def category_payload(name: str) -> dict:
    return CategoryCreate(
        name=name, description=f"{MARKER} Sample {name.lower()} category for storefront testing.",
        image=None, is_active=True,
    ).model_dump()


def normalized_name(column):
    return func.lower(func.trim(column))


def build_plan(conn: Connection, catalog: dict[str, Table]) -> dict:
    categories, products, users = (catalog[n] for n in ("categories", "products", "users"))
    category_rows = []
    product_rows = []
    for name in sorted({p[2] for p in DEMO}):
        matches = conn.execute(select(categories).where(normalized_name(categories.c.name) == name.lower())).mappings().all()
        if len(matches) > 1 or (matches and not matches[0]["is_active"]):
            raise SeedError(f"Ambiguous or inactive category: {name}; no records changed.")
        category_rows.append({"name": name, "action": "reuse" if matches else "insert",
                              "id": matches[0]["id"] if matches else None,
                              "data": category_payload(name) if not matches else None})
    by_name = {c["name"]: c for c in category_rows}
    for spec in DEMO:
        data = payload(spec, by_name[spec[2]]["id"] or 1)
        matches = conn.execute(select(products).where(normalized_name(products.c.name) == spec[0].lower())).mappings().all()
        if len(matches) > 1:
            raise SeedError(f"Duplicate existing product: {spec[0]}; manual review required.")
        if matches:
            expected = {**data, "category_id": by_name[spec[2]]["id"]}
            if any(matches[0][key] != value for key, value in expected.items()):
                raise SeedError(f"Existing product conflicts with demo specification: {spec[0]}; refusing to overwrite or duplicate.")
        data.pop("category_id")
        product_rows.append({"category": spec[2], "action": "reuse" if matches else "insert",
                             "id": matches[0]["id"] if matches else None, "data": data})
    admin_count = conn.scalar(select(func.count()).select_from(users).where(users.c.role == "admin", users.c.is_active.is_(True)))
    return {
        "counts_before": {name: conn.scalar(select(func.count()).select_from(table)) for name, table in catalog.items()},
        "active_admin_count": admin_count,
        "account_setup": "No seller is required for sellerless catalog maintenance."
                         + (" Admin API unavailable: no active app admin exists." if not admin_count else ""),
        "categories": category_rows, "products": product_rows,
        "inserts": {"categories": sum(c["action"] == "insert" for c in category_rows),
                    "products": sum(p["action"] == "insert" for p in product_rows)},
        "seller_id": None,
    }


def check_schema(conn: Connection, catalog: dict[str, Table]) -> None:
    required = {
        "categories": {"id", "name", "description", "image", "is_active", "created_at", "updated_at"},
        "products": {"id", "category_id", "seller_id", "name", "description", "price", "discount_price", "stock", "image_url", "rating", "is_active", "created_at", "updated_at"},
    }
    for name, columns in required.items():
        if set(catalog[name].c.keys()) != columns:
            raise SeedError(f"Unexpected {name} schema; review before inserting.")
    triggers = conn.scalar(text("""
        SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relname IN ('products','categories')
          AND NOT t.tgisinternal
    """))
    if triggers:
        raise SeedError("Custom catalog triggers require review before guaranteeing insert-only effects.")
    if not catalog["products"].c.seller_id.nullable:
        raise SeedError("Sellerless products are not supported by this database.")


def api_get(path: str) -> dict:
    request = Request(API + path)
    try:
        with urlopen(request, timeout=40) as response:
            body = json.load(response)
        if body.get("success") is not True:
            raise ValueError("API unsuccessful")
        return body["data"]
    except Exception:
        raise SeedError("Live API request failed; response and credentials withheld.") from None


def require_database_owner(conn: Connection) -> list[dict]:
    # Database maintenance uses the existing authenticated DB role, never an assumed
    # application identity or a generated JWT. Ownership also permits catalog locks.
    rows = conn.execute(text("""
        SELECT c.relname AS table_name, pg_has_role(c.relowner, 'USAGE') AS owns_table,
               has_table_privilege(c.oid, 'SELECT') AS can_select,
               has_table_privilege(c.oid, 'INSERT') AS can_insert,
               has_sequence_privilege(pg_get_serial_sequence('public.' || c.relname, 'id'), 'USAGE') AS sequence_usage
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relname IN ('products','categories')
        ORDER BY c.relname
    """)).mappings().all()
    if len(rows) != 2 or any(not all(row[key] for key in ("owns_table", "can_select", "can_insert", "sequence_usage")) for row in rows):
        raise SeedError("Existing database role must own both catalog tables and have SELECT, INSERT, and sequence USAGE.")
    return [dict(row) for row in rows]


def insert_plan(conn: Connection, catalog: dict[str, Table], plan: dict) -> None:
    # The caller holds catalog write locks and owns the one encompassing transaction.
    categories, products = catalog["categories"], catalog["products"]
    category_ids = {}
    for category in plan["categories"]:
        category_ids[category["name"]] = category["id"] if category["action"] == "reuse" else conn.scalar(
            insert(categories).values(**category["data"]).returning(categories.c.id))
    for product in plan["products"]:
        if product["action"] == "insert":
            conn.execute(insert(products).values(**product["data"], category_id=category_ids[product["category"]]))


def digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def verify_public() -> None:
    for spec in DEMO:
        result = api_get("/products?limit=100&search=" + quote(spec[0]))
        exact = [p for p in result["items"] if p["name"] == spec[0]]
        if len(exact) != 1:
            raise SeedError(f"Public verification failed for {spec[0]}.")
        product = exact[0]
        expected = payload(spec, product["category_id"])
        if any((Decimal(str(product[key])) != value if isinstance(value, Decimal) else product.get(key) != value)
               for key, value in expected.items()) or (product.get("category") or {}).get("name", "").strip().lower() != spec[2].lower():
            raise SeedError(f"Public data mismatch for {spec[0]}.")
    print("Verified all 8 demo listings, prices, stocks, active flags, and category links through public /api/products.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(__file__).resolve().parents[1] / ".env.supabase")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approved-plan", help="SHA-256 from the reviewed, unblocked dry-run report")
    args = parser.parse_args()
    engine = None
    committed = False
    try:
        url = target_url(args.env_file)
        engine = create_engine(url, echo=False, hide_parameters=True, poolclass=NullPool,
                               connect_args={"connect_timeout": 10, "sslmode": "require"})
        with engine.connect() as conn, conn.begin():
            conn.execute(text("SET TRANSACTION READ ONLY"))
            conn.execute(text("SET LOCAL search_path TO public"))
            if conn.scalar(text("SELECT current_database()")) != "postgres" or not conn.connection.driver_connection.info.ssl_in_use:
                raise SeedError("Unexpected database identity or unencrypted client connection.")
            catalog = tables(conn)
            check_schema(conn, catalog)
            database_authorization = require_database_owner(conn)
            plan = build_plan(conn, catalog)
            report = {"target_host": url.host, "database": url.database,
                      "target_fingerprint": digest({"host": url.host, "port": url.port, "database": url.database, "project": url.username}),
                      "migration": conn.execute(text("SELECT version_num FROM public.alembic_version")).scalars().all(),
                      "authorization_method": "Existing authenticated Supabase database owner; explicit operator-approved catalog maintenance.",
                      "database_authorization": database_authorization,
                      "plan": plan}
        approved_hash = digest(report)
        print(json.dumps({**report, "plan_sha256": approved_hash}, indent=2, default=str))
        if not args.apply:
            print("READ ONLY: no rows inserted or updated. Explicit user approval is required for database-owner maintenance.")
            return
        if args.approved_plan != approved_hash:
            raise SeedError("A current, explicitly reviewed plan hash is required; no insertion performed.")
        if not sys.stdin.isatty():
            raise SeedError("Apply mode requires an interactive terminal and explicit confirmation.")
        if input("Type INSERT BLUE PANDA DEMO to approve this exact plan: ") != "INSERT BLUE PANDA DEMO":
            raise SeedError("Cancelled; no insertion performed.")
        with engine.connect() as conn, conn.begin():
            conn.execute(text("SET LOCAL search_path TO public"))
            conn.execute(text("SET LOCAL lock_timeout = '5s'"))
            conn.execute(text("SET LOCAL statement_timeout = '30s'"))
            # Conflicts with ordinary INSERT/UPDATE/DELETE, including API writers.
            # Necessary because products.name has no UNIQUE constraint.
            conn.execute(text("LOCK TABLE public.categories, public.products IN SHARE ROW EXCLUSIVE MODE"))
            check_schema(conn, catalog)
            require_database_owner(conn)
            if build_plan(conn, catalog) != plan:
                raise SeedError("Database changed after review; obtain a new dry-run plan and approval.")
            insert_plan(conn, catalog, plan)
            final = build_plan(conn, catalog)
            if any(final["inserts"].values()):
                raise SeedError("Inserted data did not match the plan; rolling back.")
            for name in ("categories", "products", "users", "sellers"):
                if final["counts_before"][name] != plan["counts_before"][name] + plan["inserts"].get(name, 0):
                    raise SeedError("Unexpected row counts; rolling back.")
        committed = True
        print("Committed the reviewed inserts in one transaction; existing records were not updated.")
        verify_public()
    except SeedError as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        if committed:
            print("Database inserts were committed; public verification needs investigation. No automatic rollback or deletion.", file=sys.stderr)
        raise SystemExit(1) from None
    except Exception as exc:
        print(f"STOP: {type(exc).__name__}; details withheld to protect credentials. "
              + ("Inserts committed; inspect public verification." if committed else "Any pending transaction was rolled back."), file=sys.stderr)
        raise SystemExit(1) from None
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    main()
