"""Bootstrap security checks; conftest confines all writes to temporary SQLite."""

import json
from pathlib import Path
import secrets
from unittest.mock import Mock

import httpx
import pytest
from sqlalchemy import func, select

from app.core.security import hash_password, verify_password
from app.models.user import User
from scripts import bootstrap_admin as bootstrap


@pytest.fixture
def empty_users():
    # Preserve the normal fixtures; use a separate temporary in-memory database.
    from sqlalchemy import create_engine
    isolated = create_engine("sqlite://")
    User.__table__.create(isolated)
    yield isolated
    isolated.dispose()


@pytest.fixture
def plan():
    return {"users": 0, "active_admins": 0, "inactive_admins": 0,
            "target_schema_fingerprint": "test-schema"}


class LockedTestConnection:
    """Exercise real transactions; SQLite has no PostgreSQL lock/SET syntax."""

    def __init__(self, conn):
        self.conn = conn
        self.commands = []

    def __getattr__(self, name):
        return getattr(self.conn, name)

    def exec_driver_sql(self, sql):
        self.commands.append(sql)


@pytest.fixture
def bootstrap_db(monkeypatch, empty_users, plan):
    monkeypatch.setattr(bootstrap, "inspect_database", lambda conn: dict(plan))
    monkeypatch.setattr(bootstrap, "Table", lambda *args, **kwargs: User.__table__)
    with empty_users.connect() as conn:
        yield LockedTestConnection(conn)


def test_inserts_only_one_active_admin_with_backend_hash(bootstrap_db, plan):
    password = secrets.token_urlsafe(24)
    hashed = hash_password(password)
    user_id = bootstrap.insert_admin(bootstrap_db, bootstrap.plan_hash(plan),
                                     "Owner", "owner@example.com", hashed)
    row = bootstrap_db.conn.execute(select(User.__table__)).mappings().one()
    assert row["id"] == user_id
    assert row["role"] == "admin" and row["is_active"] is True
    assert verify_password(password, row["password_hash"])
    assert "LOCK TABLE public.users IN SHARE ROW EXCLUSIVE MODE" in bootstrap_db.commands


@pytest.mark.parametrize("field", ["active_admins", "inactive_admins"])
def test_rechecks_existing_admin_under_lock(bootstrap_db, plan, field):
    approved = bootstrap.plan_hash(plan)
    plan[field] = 1
    with pytest.raises(bootstrap.BootstrapError, match="already exists"):
        bootstrap.insert_admin(bootstrap_db, approved, "Owner", "owner@example.com", "unused")
    assert bootstrap_db.conn.scalar(select(func.count()).select_from(User)) == 0


def test_refuses_changed_plan(bootstrap_db, plan):
    approved = bootstrap.plan_hash(plan)
    plan["users"] = 1
    with pytest.raises(bootstrap.BootstrapError, match="state changed"):
        bootstrap.insert_admin(bootstrap_db, approved, "Owner", "owner@example.com", "unused")
    assert bootstrap_db.conn.scalar(select(func.count()).select_from(User)) == 0


def test_refuses_duplicate_email_without_elevating_user(bootstrap_db, plan):
    with bootstrap_db.conn.begin():
        bootstrap_db.conn.execute(User.__table__.insert().values(
            name="Existing", email=" OWNER@example.com ", password_hash="untouched",
            role="customer", is_active=False,
        ))
    with pytest.raises(bootstrap.BootstrapError, match="no user will be changed"):
        bootstrap.insert_admin(bootstrap_db, bootstrap.plan_hash(plan),
                               "Owner", "owner@example.com", "unused")
    row = bootstrap_db.conn.execute(select(User.__table__)).mappings().one()
    assert row["role"] == "customer" and row["is_active"] is False
    assert row["password_hash"] == "untouched"


def test_rolls_back_insert_on_failure(bootstrap_db, plan, monkeypatch):
    original = bootstrap_db.conn.scalar

    def fail_after_insert(statement, *args, **kwargs):
        result = original(statement, *args, **kwargs)
        if statement.is_insert:
            raise RuntimeError("simulated write failure")
        return result

    monkeypatch.setattr(bootstrap_db.conn, "scalar", fail_after_insert)
    with pytest.raises(RuntimeError, match="simulated write failure"):
        bootstrap.insert_admin(bootstrap_db, bootstrap.plan_hash(plan),
                               "Owner", "owner@example.com", "unused")
    assert original(select(func.count()).select_from(User)) == 0


@pytest.mark.parametrize("database_owner,table_owner", [(False, True), (True, False)])
def test_requires_actual_database_and_table_ownership(database_owner, table_owner):
    conn = Mock()
    conn.scalar.return_value = database_owner
    conn.execute.return_value.mappings.return_value.one.return_value = {
        "owned": table_owner, "can_select": True, "can_insert": True,
        "rls": False, "forced_rls": False,
    }
    with pytest.raises(bootstrap.BootstrapError, match="ownership"):
        bootstrap.inspect_database(conn)
    assert conn.execute.call_count == 1


@pytest.mark.parametrize("target", [
    "sqlite://", "postgresql://postgres@localhost:5432/postgres",
    "postgresql://postgres.demo@db.pooler.supabase.com:6543/postgres",
])
def test_rejects_wrong_database_target(monkeypatch, target):
    monkeypatch.setattr(bootstrap, "dotenv_values", lambda _: {"DATABASE_URL": target})
    with pytest.raises(bootstrap.BootstrapError):
        bootstrap.target_url(Path("unused"))


def test_rejects_noninteractive_apply_before_connecting(monkeypatch):
    monkeypatch.setattr(bootstrap.sys.stdin, "isatty", lambda: False)
    connector = Mock()
    monkeypatch.setattr(bootstrap, "create_engine", connector)
    assert bootstrap.main(["--apply", "--approved-plan", "test"]) == 1
    connector.assert_not_called()


@pytest.mark.parametrize("failure", ["short", "byte_limit", "mismatch", "invalid_email", "echo_fallback"])
def test_private_input_rejects_unsafe_credentials(monkeypatch, failure):
    monkeypatch.setattr(bootstrap.sys.stdin, "isatty", lambda: True)
    password = secrets.token_urlsafe(24)
    if failure == "short":
        password = secrets.token_hex(4)
    if failure == "byte_limit":
        password = secrets.token_urlsafe(60)
    email = "invalid" if failure == "invalid_email" else "owner@example.com"
    prompts = iter(["Owner", email, password,
                    secrets.token_urlsafe(24) if failure == "mismatch" else password])

    def hidden_input(_):
        if failure == "echo_fallback":
            bootstrap.warnings.warn("No hidden input available", bootstrap.getpass.GetPassWarning)
        return next(prompts)

    monkeypatch.setattr(bootstrap.getpass, "getpass", hidden_input)
    error_type = bootstrap.getpass.GetPassWarning if failure == "echo_fallback" else bootstrap.BootstrapError
    with pytest.raises(error_type):
        bootstrap.read_credentials()


@pytest.mark.parametrize("failure", [None, "login_role", "me_role", "redirect", "wrong_id", "missing_token"])
def test_verifies_deployed_login_and_me_without_printing_secrets(monkeypatch, capsys, failure):
    password, token = secrets.token_urlsafe(24), secrets.token_urlsafe(32)
    expected = {"id": 5, "email": "owner@example.com", "role": "admin", "is_active": True}
    seen = []

    def handle(request):
        seen.append(request.url.path)
        assert request.url.scheme == "https"
        assert request.url.host == "e-commerce-techstore-bhu7.onrender.com"
        if request.url.path.endswith("/login"):
            assert json.loads(request.content) == {"email": expected["email"], "password": password}
            if failure == "redirect":
                return httpx.Response(302, headers={"Location": "https://example.com/"})
            user = {**expected, **({"role": "customer"} if failure == "login_role" else {})}
            data = {"user": user, "access_token": token if failure != "missing_token" else None}
        else:
            assert request.headers["Authorization"] == f"Bearer {token}"
            data = {**expected, **({"role": "customer"} if failure == "me_role" else {}),
                    **({"id": 6} if failure == "wrong_id" else {})}
        return httpx.Response(200, json={"success": True, "data": data})

    client_type = httpx.Client
    monkeypatch.setattr(bootstrap.httpx, "Client", lambda **kwargs: client_type(
        transport=httpx.MockTransport(handle), **kwargs,
    ))
    if failure:
        with pytest.raises(bootstrap.BootstrapError):
            bootstrap.verify_account(expected["email"], password, expected["id"])
    else:
        bootstrap.verify_account(expected["email"], password, expected["id"])
        assert seen == ["/api/auth/login", "/api/auth/me"]
    output = capsys.readouterr()
    assert password not in output.out + output.err
    assert token not in output.out + output.err


def test_error_output_withholds_driver_secrets(monkeypatch, capsys):
    secret = secrets.token_urlsafe(32)
    monkeypatch.setattr(bootstrap, "target_url", Mock(side_effect=RuntimeError(secret)))
    assert bootstrap.main([]) == 1
    output = capsys.readouterr()
    assert secret not in output.out + output.err
