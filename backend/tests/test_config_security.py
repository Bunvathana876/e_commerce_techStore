"""Backend secrets, environment configuration, and demo credentials tests (S08)."""

from pathlib import Path
import shutil
import subprocess

from pydantic import ValidationError
import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.db.database import SessionLocal
from app.models.user import User
from app.db.seed_data import seed_database


TEST_DB_URL = "sqlite:///:memory:"


def test_1_missing_production_jwt_secret_causes_configuration_failure():
    for empty_secret in ["", "   "]:
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                ENVIRONMENT="production",
                DATABASE_URL=TEST_DB_URL,
                JWT_SECRET_KEY=empty_secret,
            )
        err_msg = str(exc_info.value)
        assert "JWT_SECRET_KEY must be explicitly configured" in err_msg


def test_2_insecure_default_and_short_production_jwt_secrets_rejected():
    insecure_keys = [
        "dev_secret_key_change_me_super_secure_12345",
        "secret",
        "changeme",
        "password",
        "too_short_secret_key_123",  # 24 chars (< 32)
    ]
    for bad_key in insecure_keys:
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                ENVIRONMENT="production",
                DATABASE_URL=TEST_DB_URL,
                JWT_SECRET_KEY=bad_key,
            )
        err_msg = str(exc_info.value)
        assert (
            "cannot use default" in err_msg
            or "must be at least 32 characters long" in err_msg
        )


def test_3_valid_configured_production_secret_accepted():
    strong_key = "a" * 32
    prod_settings = Settings(
        ENVIRONMENT="production",
        DATABASE_URL=TEST_DB_URL,
        JWT_SECRET_KEY=strong_key,
    )
    assert prod_settings.is_production is True
    assert prod_settings.JWT_SECRET_KEY == strong_key


def test_4_development_and_test_configurations_work_with_defaults(monkeypatch):
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    dev_settings = Settings(
        ENVIRONMENT="development",
        DATABASE_URL=TEST_DB_URL,
    )
    assert dev_settings.is_production is False
    assert dev_settings.JWT_SECRET_KEY == "dev_secret_key_change_me_super_secure_12345"

    test_settings = Settings(
        ENVIRONMENT="test",
        DATABASE_URL=TEST_DB_URL,
    )
    assert test_settings.is_production is False


def test_5_production_never_enables_demo_credentials_automatically(monkeypatch):
    from app.core import config

    # Mock settings.is_production = True
    monkeypatch.setattr(config.settings, "ENVIRONMENT", "production")

    with SessionLocal() as db:
        db.query(User).delete()
        db.commit()

    # Call seed_database without force -> must refuse to seed demo accounts
    seed_database(force=False)

    with SessionLocal() as verify_db:
        demo_users = verify_db.scalars(
            select(User).where(
                User.email.in_(
                    [
                        "admin@ecommerce.com",
                        "customer@ecommerce.com",
                        "seller@ecommerce.com",
                        "seller2@ecommerce.com",
                    ]
                )
            )
        ).all()
        assert len(demo_users) == 0


def test_6_private_environment_files_are_ignored_by_git():
    repo_root = Path(__file__).resolve().parents[2]
    backend_root = Path(__file__).resolve().parents[1]

    if shutil.which("git") is None or not (repo_root / ".git").exists():
        pytest.skip("Git repository is unavailable in the backend container.")

    for env_file in [".env", ".env.local", ".env.production", ".env.backup"]:
        res_backend = subprocess.run(
            ["git", "check-ignore", env_file],
            cwd=backend_root,
            capture_output=True,
            text=True,
        )
        assert res_backend.returncode == 0, f"backend/.gitignore must ignore {env_file}"

        res_root = subprocess.run(
            ["git", "check-ignore", env_file],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        assert res_root.returncode == 0, f"root .gitignore must ignore {env_file}"


def test_7_error_messages_do_not_reveal_sensitive_configuration_values():
    sensitive_token = "SuperSecretLeakCandidate123456"
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            DATABASE_URL=TEST_DB_URL,
            JWT_SECRET_KEY=sensitive_token,
        )

    error_text = str(exc_info.value)
    # The sensitive token value itself must NOT be present in the exception message
    assert sensitive_token not in error_text
    assert "must be at least 32 characters long" in error_text


def test_8_database_pool_configuration_parameters():
    """Verify database connection pool parameters are configurable."""
    cfg = Settings(
        DATABASE_URL=TEST_DB_URL,
        DB_POOL_SIZE=25,
        DB_MAX_OVERFLOW=15,
        DB_POOL_TIMEOUT=45,
        DB_POOL_RECYCLE=3600,
    )
    assert cfg.DB_POOL_SIZE == 25
    assert cfg.DB_MAX_OVERFLOW == 15
    assert cfg.DB_POOL_TIMEOUT == 45
    assert cfg.DB_POOL_RECYCLE == 3600


def test_9_cors_origins_and_trusted_proxies_comma_separated_env_parsing(monkeypatch):
    """Verify CORS_ORIGINS and TRUSTED_PROXY_IPS correctly parse comma-separated strings."""
    monkeypatch.setenv("DATABASE_URL", TEST_DB_URL)
    monkeypatch.setenv("CORS_ORIGINS", "https://storefront.example.com, https://admin.example.com")
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "10.0.0.1, 192.168.1.1")
    cfg = Settings()
    assert cfg.CORS_ORIGINS == ["https://storefront.example.com", "https://admin.example.com"]
    assert cfg.TRUSTED_PROXY_IPS == ["10.0.0.1", "192.168.1.1"]
