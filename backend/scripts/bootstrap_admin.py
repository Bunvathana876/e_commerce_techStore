"""Owner-only first-admin bootstrap. Read-only unless --apply is explicit.

Run from backend: python -m scripts.bootstrap_admin
Credentials are accepted only through an interactive terminal, never arguments.
This module never imports the application, starts it, or changes its schema.
"""

import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import sys
import warnings

from dotenv import dotenv_values
from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import MetaData, Table, create_engine, func, insert, select, text
from sqlalchemy.engine import Connection, URL, make_url
from sqlalchemy.pool import NullPool
import httpx


API = os.getenv("API_URL", "https://e-commerce-techstore-bhu7.onrender.com/api")
APPROVAL = "AUTHORIZE FIRST ADMIN"
EXPECTED_COLUMNS = {
    "id", "name", "email", "password_hash", "phone", "avatar", "role",
    "is_active", "created_at", "updated_at",
}


class BootstrapError(Exception):
    """Only fixed, credential-free messages may be raised with this type."""


def target_url(env_file: Path) -> URL:
    raw = dotenv_values(env_file).get("DATABASE_URL")
    try:
        url = make_url(raw or "")
    except Exception:
        raise BootstrapError("Database configuration is invalid; value withheld.") from None
    if not (
        url.get_backend_name() in {"postgres", "postgresql"}
        and (url.host or "").endswith(".pooler.supabase.com")
        and url.port == 5432
        and url.database == "postgres"
        and (url.username or "").startswith("postgres.")
        and url.password
    ):
        raise BootstrapError("Expected a Supabase owner session-pooler connection on port 5432.")
    # Discard connection options that could redirect the target or disable TLS.
    return url.set(drivername="postgresql+psycopg2", query={"sslmode": "require"})


def inspect_database(conn: Connection) -> dict:
    owner = conn.scalar(text("""
        SELECT pg_get_userbyid(datdba) = current_user
        FROM pg_database WHERE datname = current_database()
    """))
    table = conn.execute(text("""
        SELECT pg_get_userbyid(relowner) = current_user AS owned,
               relrowsecurity AS rls, relforcerowsecurity AS forced_rls,
               has_table_privilege(current_user, oid, 'SELECT') AS can_select,
               has_table_privilege(current_user, oid, 'INSERT') AS can_insert
        FROM pg_class WHERE oid = 'public.users'::regclass AND relkind = 'r'
    """)).mappings().one()
    if not owner or not table["owned"] or not table["can_select"] or not table["can_insert"]:
        raise BootstrapError("Database and users-table ownership are required.")
    if table["rls"] or table["forced_rls"]:
        raise BootstrapError("Users RLS requires a separate owner review; bootstrap refused.")
    hooks = conn.scalar(text("""
        SELECT (SELECT count(*) FROM pg_trigger
                WHERE tgrelid='public.users'::regclass AND NOT tgisinternal)
             + (SELECT count(*) FROM pg_rewrite
                WHERE ev_class='public.users'::regclass AND rulename <> '_RETURN')
    """))
    if hooks:
        raise BootstrapError("Custom users triggers or rules require review; bootstrap refused.")
    columns = [dict(row) for row in conn.execute(text("""
        SELECT column_name, data_type, is_nullable, character_maximum_length,
               column_default
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name='users' ORDER BY ordinal_position
    """)).mappings()]
    if {c["column_name"] for c in columns} != EXPECTED_COLUMNS:
        raise BootstrapError("Unexpected users schema; bootstrap refused.")
    constraints = [dict(row) for row in conn.execute(text("""
        SELECT contype, array_agg(a.attname ORDER BY k.ord) AS columns
        FROM pg_constraint c
        CROSS JOIN LATERAL unnest(c.conkey) WITH ORDINALITY k(attnum, ord)
        JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=k.attnum
        WHERE c.conrelid='public.users'::regclass AND c.contype IN ('p','u')
        GROUP BY c.oid,c.contype ORDER BY c.contype
    """)).mappings()]
    if not any(c["contype"] == "p" and c["columns"] == ["id"] for c in constraints):
        raise BootstrapError("Expected the users ID primary key.")
    email_unique = conn.scalar(text("""
        SELECT EXISTS (
            SELECT 1 FROM pg_index i JOIN pg_attribute a
              ON a.attrelid=i.indrelid AND a.attnum=i.indkey[0]
            WHERE i.indrelid='public.users'::regclass
              AND i.indisunique AND i.indisvalid AND i.indisready
              AND i.indnkeyatts=1 AND i.indpred IS NULL AND i.indexprs IS NULL
              AND a.attname='email'
        )
    """))
    if not email_unique:
        raise BootstrapError("Expected an unconditional unique users email index.")
    if not conn.scalar(text("""
        SELECT has_sequence_privilege(
            current_user, pg_get_serial_sequence('public.users','id'), 'USAGE')
    """)):
        raise BootstrapError("Users ID sequence permission is required.")
    counts = dict(conn.execute(text("""
        SELECT count(*) AS users,
               count(*) FILTER (WHERE role='admin' AND is_active IS TRUE) AS active_admins,
               count(*) FILTER (WHERE role='admin' AND is_active IS NOT TRUE) AS inactive_admins
        FROM public.users
    """)).mappings().one())
    identity = [conn.engine.url.host, conn.engine.url.port,
                conn.engine.url.database, conn.engine.url.username]
    fingerprint = hashlib.sha256(json.dumps(
        [identity, columns, constraints, email_unique], sort_keys=True, default=str,
    ).encode()).hexdigest()
    return {"target_schema_fingerprint": fingerprint, "database_owner": True,
            "users_table_owner": True, **counts,
            "planned_insert": {"table": "public.users", "role": "admin", "is_active": True},
            "updates": 0, "deletes": 0, "schema_changes": 0}


def plan_hash(plan: dict) -> str:
    return hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()


def require_first_admin(plan: dict) -> None:
    if plan["active_admins"] or plan["inactive_admins"]:
        raise BootstrapError("An administrator already exists; bootstrap refused. Use authorized account management or recovery.")


def read_credentials() -> tuple[str, str, str]:
    if not sys.stdin.isatty():
        raise BootstrapError("An interactive local terminal is required for hidden credential input.")
    with warnings.catch_warnings():
        # Never allow getpass to fall back to an echoed input stream.
        warnings.simplefilter("error", getpass.GetPassWarning)
        name = getpass.getpass("Administrator display name (hidden): ").strip()
        raw_email = getpass.getpass("Administrator email (hidden): ")
        password = getpass.getpass("Administrator password (hidden): ")
        confirmation = getpass.getpass("Repeat administrator password (hidden): ")
    if not name or len(name) > 100:
        raise BootstrapError("Display name must contain 1 to 100 characters.")
    try:
        email = str(TypeAdapter(EmailStr).validate_python(raw_email.strip())).lower()
    except ValidationError:
        raise BootstrapError("Administrator email is invalid; value withheld.") from None
    if len(email) > 255:
        raise BootstrapError("Administrator email is too long.")
    if password != confirmation:
        raise BootstrapError("Password confirmation does not match.")
    from app.core.password_policy import validate_password_strength

    valid, _ = validate_password_strength(password)
    # Apply the existing policy plus a stronger admin minimum and bcrypt's byte cap.
    if not valid or len(password) < 16 or len(password.encode("utf-8")) > 72:
        raise BootstrapError("Use a nontrivial password with at least 16 characters and at most 72 UTF-8 bytes that passes the backend policy.")
    return name, email, password


def insert_admin(conn: Connection, approved_hash: str, name: str,
                 email: str, password_hash: str) -> int:
    with conn.begin():
        conn.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
        conn.exec_driver_sql("SET LOCAL statement_timeout = '15s'")
        # Serialize all users writes, including registration and other bootstrap runs.
        # Reads remain available. No human input or network calls occur under this lock.
        conn.exec_driver_sql("LOCK TABLE public.users IN SHARE ROW EXCLUSIVE MODE")
        plan = inspect_database(conn)
        require_first_admin(plan)
        if plan_hash(plan) != approved_hash:
            raise BootstrapError("Database state changed after review; generate and approve a new plan.")
        users = Table("users", MetaData(), schema="public", autoload_with=conn)
        exists = conn.scalar(select(users.c.id).where(
            func.lower(func.trim(users.c.email)) == email,
        ).limit(1))
        if exists is not None:
            raise BootstrapError("This email already belongs to a user; no user will be changed or elevated.")
        user_id = conn.scalar(insert(users).values(
            name=name, email=email, password_hash=password_hash,
            role="admin", is_active=True,
        ).returning(users.c.id))
    return user_id


def verify_account(email: str, password: str, user_id: int) -> None:
    # Fixed HTTPS origin; no redirects, custom endpoint, token output, or disk storage.
    try:
        with httpx.Client(timeout=60, follow_redirects=False, trust_env=False) as client:
            response = client.post(f"{API}/auth/login", json={"email": email, "password": password})
            if response.status_code != 200:
                raise BootstrapError("Deployed login verification failed; response details withheld.")
            body = response.json()
            data = body.get("data", {})
            user = data.get("user", {})
            token = data.get("access_token")
            expected = {"id": user_id, "email": email, "role": "admin", "is_active": True}
            if body.get("success") is not True or not isinstance(token, str) or not token or any(
                user.get(k) != v for k, v in expected.items()
            ):
                raise BootstrapError("Deployed login returned an unexpected account; verification failed.")
            response = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})
            if response.status_code != 200:
                raise BootstrapError("Deployed /auth/me verification failed; response details withheld.")
            body = response.json()
            if body.get("success") is not True or any(
                body.get("data", {}).get(k) != v for k, v in expected.items()
            ):
                raise BootstrapError("Deployed /auth/me returned an unexpected account; verification failed.")
    except BootstrapError:
        raise
    except Exception:
        raise BootstrapError("Deployed verification could not complete; diagnostic details withheld.") from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env.supabase"))
    parser.add_argument("--apply", action="store_true", help="Requires explicit owner approval and hidden local input")
    parser.add_argument("--approved-plan", help="SHA-256 from the reviewed read-only plan")
    args = parser.parse_args(argv)
    engine = None
    write_attempted = False
    created = False
    try:
        if args.apply and (not args.approved_plan or not sys.stdin.isatty()):
            raise BootstrapError("Apply requires a reviewed plan hash and an interactive local terminal.")
        engine = create_engine(target_url(args.env_file), echo=False, hide_parameters=True,
                               poolclass=NullPool, connect_args={"connect_timeout": 10})
        with engine.connect() as conn, conn.begin():
            conn.exec_driver_sql("SET TRANSACTION READ ONLY")
            conn.exec_driver_sql("SET LOCAL statement_timeout = '15s'")
            plan = inspect_database(conn)
        print(json.dumps({"plan": plan, "approval_hash": plan_hash(plan)}, indent=2))
        require_first_admin(plan)
        if not args.apply:
            print("Read-only inspection complete. No account created. Obtain explicit owner approval before --apply.")
            return 0
        if args.approved_plan != plan_hash(plan):
            raise BootstrapError("Approved plan does not match the current database; no account created.")
        if input(f"After approval, type {APPROVAL} to authorize as database owner: ") != APPROVAL:
            raise BootstrapError("Owner authorization was not provided; no account created.")
        name, email, password = read_credentials()
        from app.core.security import hash_password, verify_password

        hashed = hash_password(password)
        if not verify_password(password, hashed):
            raise BootstrapError("Backend password hash verification failed; no account created.")
        with engine.connect() as conn:
            write_attempted = True
            user_id = insert_admin(conn, args.approved_plan, name, email, hashed)
        created = True
        print("Created one active administrator. Existing users were not modified.")
        verify_account(email, password, user_id)
        print("Verified deployed login and /auth/me: matching account ID, email, active status, and admin role.")
        return 0
    except (KeyboardInterrupt, EOFError):
        print("Operation interrupted. Check read-only status before retrying if creation was attempted.")
        return 1
    except Exception as exc:
        print(str(exc) if isinstance(exc, BootstrapError) else "Operation failed; diagnostic details withheld to protect credentials.")
        if created:
            print("The account remains created. Verification failed; do not rerun bootstrap or create another account.")
        elif write_attempted:
            print("Check read-only status before retrying; a commit may have occurred.")
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
