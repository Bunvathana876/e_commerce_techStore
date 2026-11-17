"""Set isolation before collection imports the application or its database engine."""
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
from tempfile import TemporaryDirectory

import pytest

if "app.db.database" in sys.modules or "app.core.config" in sys.modules:
    raise RuntimeError("Test isolation must be configured before application imports.")

_temporary = TemporaryDirectory(prefix="blue-panda-tests-")
_root = Path(_temporary.name).resolve()
os.environ["DATABASE_URL"] = f"sqlite:///{_root / 'test.sqlite'}"
os.environ["JWT_SECRET_KEY"] = secrets.token_hex(32)
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["AUTO_INIT_DB"] = "false"
os.environ["SEED_DEMO_DATA"] = "false"
# Never connect to or flush an operator's Redis during test fixture resets.
os.environ["RATE_LIMIT_STORAGE_URL"] = ""
os.environ["ENVIRONMENT"] = "test"
os.environ["UPLOAD_DIR"] = str(_root / "uploads")

from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL
from fastapi.testclient import TestClient
from app.db.database import Base, SessionLocal, engine
from app.core.rate_limit import reset_rate_limiter_storage
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.user import User
from app.models.seller import Seller
from app.models.product import Product
from app.models.category import Category
from app.models.coupon import Coupon


@event.listens_for(engine, "connect")
def enforce_foreign_keys(connection, _):
    connection.execute("PRAGMA foreign_keys=ON")


def assert_isolated():
    if engine.url.get_backend_name() != "sqlite":
        raise RuntimeError("Refusing to reset a non-test database.")
    if Path(engine.url.database).resolve() != _root / "test.sqlite":
        raise RuntimeError("Refusing to reset a database outside the temporary directory.")


@pytest.fixture(scope="session")
def password_hash():
    return hash_password("Fixture-password-123")


@pytest.fixture(autouse=True)
def database(password_hash):
    assert_isolated()
    reset_rate_limiter_storage()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        for i, role in enumerate(["admin", "customer", "customer", "seller", "seller", "staff", "employee", "super_admin"], 1):
            db.add(User(id=i, name=f"Fixture {i}", email=f"user{i}@example.com",
                        role=role, password_hash=password_hash, is_active=True))
        db.add(Category(id=1, name="Fixture category", is_active=True))
        db.flush()
        db.add_all([
            Seller(id=1, user_id=4, name="Store A", owner_name="Owner A", email="a@example.com", status="Active"),
            Seller(id=2, user_id=5, name="Store B", owner_name="Owner B", email="b@example.com", status="Active"),
        ])
        db.flush()
        db.add_all([
            Product(id=1, category_id=1, seller_id=1, name="Fixture product", price=20, stock=20, is_active=True),
            Product(id=2, category_id=1, seller_id=2, name="Other product", price=30, stock=20, is_active=False),
            Coupon(code="WELCOME10", discount_type="percent", discount_value=10, min_order_amount=0, is_active=True),
        ])
        db.commit()
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def headers():
    def for_user(user_id):
        return {"Authorization": f"Bearer {create_access_token({'sub': str(user_id)})}"}
    return for_user


@pytest.fixture
def admin_headers(headers):
    return headers(1)


def pytest_sessionfinish(session, exitstatus):
    engine.dispose()
    _temporary.cleanup()


@pytest.fixture(scope="session")
def pg_cluster():
    initdb_bin = shutil.which("initdb")
    pg_ctl_bin = shutil.which("pg_ctl")
    if not initdb_bin or not pg_ctl_bin:
        pytest.skip("PostgreSQL initdb/pg_ctl binaries are not installed locally.")

    tmp_dir = tempfile.TemporaryDirectory(dir="/tmp", prefix="bp-pg-")
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
            assert conn.exec_driver_sql("SHOW listen_addresses").scalar_one() == ""
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
