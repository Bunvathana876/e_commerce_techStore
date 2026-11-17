"""Production CORS origin, credentialed requests, and API diagnostics security tests (S09)."""

import json

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from app.core.config import Settings, settings
from app.db.database import SessionLocal
from app.main import create_app
from app.models.user import User
from app.services.auth_service import AuthService


TEST_DB_URL = "sqlite:///:memory:"
STRONG_PROD_JWT_KEY = "a" * 32
TRUSTED_PROD_ORIGIN = "https://store.bluepanda.com"
MANAGEMENT_ORIGIN = "https://blue-panda-management.vercel.app"
# Synthetic fixture; actual previews require a separate ownership/code review.
REVIEWED_PREVIEW_ORIGIN = "https://blue-panda-management-reviewed-preview.vercel.app"


def management_settings() -> Settings:
    return Settings(
        _env_file=None,
        ENVIRONMENT="production",
        DATABASE_URL=TEST_DB_URL,
        JWT_SECRET_KEY=STRONG_PROD_JWT_KEY,
        CORS_ORIGINS=[MANAGEMENT_ORIGIN, REVIEWED_PREVIEW_ORIGIN],
        AUTO_INIT_DB=False,
    )


@pytest.mark.parametrize("source", ["environment", "dotenv"])
@pytest.mark.parametrize("format_name", ["csv", "json", "quoted_csv", "quoted_json"])
def test_management_origins_parse_from_environment(monkeypatch, tmp_path, source, format_name):
    origins = [MANAGEMENT_ORIGIN, REVIEWED_PREVIEW_ORIGIN]
    raw = json.dumps(origins) if "json" in format_name else ", ".join(origins)
    if format_name.startswith("quoted"):
        raw = f"'{raw}'"
    if source == "environment":
        monkeypatch.setenv("CORS_ORIGINS", raw)
        env_file = None
    else:
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
        env_file = tmp_path / ".env"
        env_file.write_text(f"CORS_ORIGINS={raw}\n", encoding="utf-8")
    cfg = Settings(
        _env_file=env_file,
        ENVIRONMENT="production",
        DATABASE_URL=TEST_DB_URL,
        JWT_SECRET_KEY=STRONG_PROD_JWT_KEY,
        AUTO_INIT_DB=False,
    )
    assert cfg.CORS_ORIGINS == origins


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
@pytest.mark.parametrize("origin", [MANAGEMENT_ORIGIN, REVIEWED_PREVIEW_ORIGIN])
def test_management_login_preflight_and_auth_responses(prefix, origin):
    with TestClient(create_app(management_settings())) as client:
        preflight = client.options(
            f"{prefix}/auth/login",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,authorization",
            },
        )
        assert preflight.status_code == 200
        assert preflight.headers["access-control-allow-origin"] == origin
        assert "origin" in preflight.headers["vary"].lower()
        for payload, expected_status in [
            ({}, 422),
            ({"email": "user1@example.com", "password": "Incorrect-password"}, 401),
            ({"email": "user1@example.com", "password": "Fixture-password-123"}, 200),
        ]:
            response = client.post(f"{prefix}/auth/login", json=payload, headers={"Origin": origin})
            assert response.status_code == expected_status
            assert response.headers["access-control-allow-origin"] == origin
            assert response.headers["access-control-allow-credentials"] == "true"
            if expected_status == 200:
                assert response.json()["success"] is True
                assert response.json()["data"]["user"]["role"] == "admin"
            else:
                assert "data" not in response.json()


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
@pytest.mark.parametrize("origin", [
    "https://another-project.vercel.app",
    "https://blue-panda-management-unreviewed.vercel.app",
    "https://blue-panda-management.vercel.app.attacker.example",
])
def test_unreviewed_previews_and_lookalike_origins_are_denied(prefix, origin):
    with TestClient(create_app(management_settings())) as client:
        response = client.options(f"{prefix}/auth/login", headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        })
        assert response.status_code == 400
        assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_disabled_login_and_rate_limit_keep_cors(prefix):
    with SessionLocal() as db:
        db.get(User, 1).is_active = False
        db.commit()

    with TestClient(create_app(management_settings())) as client:
        for _ in range(settings.RATE_LIMIT_AUTH_LOGIN):
            denied = client.post(f"{prefix}/auth/login", headers={"Origin": MANAGEMENT_ORIGIN}, json={
                "email": "user1@example.com", "password": "Fixture-password-123",
            })
            assert denied.status_code == 403
            assert denied.headers["access-control-allow-origin"] == MANAGEMENT_ORIGIN
            assert "data" not in denied.json()
        limited = client.post(f"{prefix}/auth/login", headers={"Origin": MANAGEMENT_ORIGIN}, json={})
        assert limited.status_code == 429
        assert limited.headers["access-control-allow-origin"] == MANAGEMENT_ORIGIN
        assert int(limited.headers["retry-after"]) > 0


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
@pytest.mark.parametrize("origin", [MANAGEMENT_ORIGIN, REVIEWED_PREVIEW_ORIGIN, "https://another-project.vercel.app"])
def test_unhandled_login_errors_keep_cors_for_trusted_origins_only(monkeypatch, prefix, origin):
    def unavailable_login(*args, **kwargs):
        raise RuntimeError("Internal diagnostic must not reach the browser")

    monkeypatch.setattr(AuthService, "login", unavailable_login)
    with TestClient(create_app(management_settings()), raise_server_exceptions=False) as client:
        response = client.post(f"{prefix}/auth/login", headers={"Origin": origin}, json={
            "email": "user1@example.com", "password": "Fixture-password-123",
        })
    assert response.status_code == 500
    assert response.text == "Internal Server Error"
    if origin in (MANAGEMENT_ORIGIN, REVIEWED_PREVIEW_ORIGIN):
        assert response.headers.get("access-control-allow-origin") == origin
        assert response.headers["access-control-allow-credentials"] == "true"
    else:
        assert "access-control-allow-origin" not in response.headers


# ---------------------------------------------------------------------------
# 1, 2, 4. Production CORS origin filtering and credential safety
# ---------------------------------------------------------------------------


def test_1_and_2_and_4_production_cors_origin_filtering_and_credentials():
    prod_settings = Settings(
        ENVIRONMENT="production",
        DATABASE_URL=TEST_DB_URL,
        JWT_SECRET_KEY=STRONG_PROD_JWT_KEY,
        CORS_ORIGINS=[TRUSTED_PROD_ORIGIN, "https://admin.bluepanda.com"],
        AUTO_INIT_DB=False,
    )
    prod_app = create_app(prod_settings)

    with TestClient(prod_app) as client:
        # Preflight OPTIONS request from trusted origin
        preflight_trusted = client.options(
            "/api/products",
            headers={
                "Origin": TRUSTED_PROD_ORIGIN,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization, Content-Type",
            },
        )
        assert preflight_trusted.status_code == 200
        assert (
            preflight_trusted.headers.get("access-control-allow-origin")
            == TRUSTED_PROD_ORIGIN
        )
        assert (
            preflight_trusted.headers.get("access-control-allow-credentials") == "true"
        )
        assert (
            "GET" in preflight_trusted.headers.get("access-control-allow-methods", "")
        )

        # GET request with trusted origin
        get_trusted = client.get(
            "/api/products",
            headers={"Origin": TRUSTED_PROD_ORIGIN},
        )
        assert get_trusted.status_code == 200
        assert (
            get_trusted.headers.get("access-control-allow-origin")
            == TRUSTED_PROD_ORIGIN
        )
        assert get_trusted.headers.get("access-control-allow-credentials") == "true"

        # Untrusted origin request
        untrusted_origin = "https://malicious-attacker.evil"
        get_untrusted = client.get(
            "/api/products",
            headers={"Origin": untrusted_origin},
        )
        assert get_untrusted.status_code == 200
        # CORS allow origin header must NOT be reflected for untrusted origin
        assert "access-control-allow-origin" not in get_untrusted.headers

        # Preflight OPTIONS request from untrusted origin is rejected with 400
        preflight_untrusted = client.options(
            "/api/products",
            headers={
                "Origin": untrusted_origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert preflight_untrusted.status_code == 400
        assert "access-control-allow-origin" not in preflight_untrusted.headers


# ---------------------------------------------------------------------------
# 3. Wildcard production CORS configuration is rejected
# ---------------------------------------------------------------------------


def test_3_wildcard_production_cors_rejected_at_startup():
    wildcard_cases = [
        ["*"],
        [TRUSTED_PROD_ORIGIN, "*"],
        '["*"]',
        "*,https://other.com",
    ]
    for bad_origins in wildcard_cases:
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                ENVIRONMENT="production",
                DATABASE_URL=TEST_DB_URL,
                JWT_SECRET_KEY=STRONG_PROD_JWT_KEY,
                CORS_ORIGINS=bad_origins,
                AUTO_INIT_DB=False,
            )
        assert (
            "wildcard '*' CORS origins are strictly prohibited"
            in str(exc_info.value)
        )


# ---------------------------------------------------------------------------
# 5. Local development origins remain functional in development mode
# ---------------------------------------------------------------------------


def test_5_development_mode_origins_functional():
    dev_settings = Settings(
        ENVIRONMENT="development",
        DATABASE_URL=TEST_DB_URL,
        AUTO_INIT_DB=False,
    )
    dev_app = create_app(dev_settings)

    with TestClient(dev_app) as client:
        for dev_origin in ["http://localhost:3000", "http://10.0.2.2:8000"]:
            res = client.get(
                "/api/products",
                headers={"Origin": dev_origin},
            )
            assert res.status_code == 200
            assert res.headers.get("access-control-allow-origin") == dev_origin
            assert res.headers.get("access-control-allow-credentials") == "true"


# ---------------------------------------------------------------------------
# 6. Development-only diagnostics disabled or restricted in production
# ---------------------------------------------------------------------------


def test_6_diagnostics_disabled_in_production(admin_headers):
    # Production without explicit ENABLE_DOCS_IN_PRODUCTION
    prod_settings = Settings(
        ENVIRONMENT="production",
        DATABASE_URL=TEST_DB_URL,
        JWT_SECRET_KEY=STRONG_PROD_JWT_KEY,
        CORS_ORIGINS=[TRUSTED_PROD_ORIGIN],
        AUTO_INIT_DB=False,
    )
    prod_app = create_app(prod_settings)

    with TestClient(prod_app) as client:
        # /docs, /redoc, /openapi.json must return 404
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404
        assert client.get("/openapi.json").status_code == 404

        # /db-test must return 404 in production, even with admin authorization
        assert client.get("/db-test", headers=admin_headers).status_code == 404
        assert client.get("/db-test").status_code == 404

        # /health remains open for orchestrator health checks
        health_res = client.get("/health")
        assert health_res.status_code == 200
        assert health_res.json()["status"] == "healthy"

        # Root landing page returns clean JSON in production without internal links
        root_res = client.get("/")
        assert root_res.status_code == 200
        assert root_res.headers.get("content-type", "").startswith("application/json")
        assert "E-Commerce API is running" in root_res.json()["message"]


def test_6b_diagnostics_enabled_in_development(client, admin_headers):
    # In default development/test client:
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/health").status_code == 200
    # /db-test is accessible to admin in dev/test
    db_res = client.get("/db-test", headers=admin_headers)
    assert db_res.status_code == 200
    assert db_res.json()["connection"] == "success"


# ---------------------------------------------------------------------------
# 7. Existing authorized backend requests still work
# ---------------------------------------------------------------------------


def test_7_authorized_requests_work_normally(client, headers):
    # Public catalog endpoint
    cat_res = client.get("/api/products")
    assert cat_res.status_code == 200

    # User profile with JWT bearer token
    user_res = client.get("/api/auth/me", headers=headers(2))
    assert user_res.status_code == 200
    assert user_res.json()["data"]["id"] == 2


# ---------------------------------------------------------------------------
# 8. Invalid production origin configuration fails safely
# ---------------------------------------------------------------------------


def test_8_invalid_production_origin_configuration_fails_safely():
    invalid_cases = [
        [],  # Empty origins in production
        [""],
        ["not_a_url"],
        ["ftp://invalid-scheme.com"],
        ["https://valid-domain.com/path"],  # Path not allowed in origin
        ["https://valid-domain.com/"],  # Trailing slash not allowed in origin
    ]
    for bad_input in invalid_cases:
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                ENVIRONMENT="production",
                DATABASE_URL=TEST_DB_URL,
                JWT_SECRET_KEY=STRONG_PROD_JWT_KEY,
                CORS_ORIGINS=bad_input,
                AUTO_INIT_DB=False,
            )
        err = str(exc_info.value)
        assert (
            "at least one trusted CORS origin" in err
            or "Invalid CORS origin" in err
        )
