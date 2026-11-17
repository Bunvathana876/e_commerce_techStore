"""Session security against temporary SQLite; no external service credentials."""
from datetime import timedelta
import json

import jwt
import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.core.security import create_access_token, decode_access_token, hash_refresh_token
from app.db.database import SessionLocal
from app.models.session import RefreshToken, UserSession
from app.models.seller import Seller
from app.models.user import User
from app.services.auth_session_service import AuthSessionService, utc_now
from app.services.auth_session_service import IssuedTokens

@pytest.fixture(autouse=True)
def enable_modern_sessions_for_security_tests(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "AUTH_ISSUE_SESSION_TOKENS", True)



FIXTURE_PASSWORD = "Fixture-password-123"
NEW_PASSWORD = "Replacement-password-456"


def login(client, user_id=2, refresh=True, prefix="/api/v1"):
    response = client.post(f"{prefix}/auth/login", json={
        "email": f"user{user_id}@example.com", "password": FIXTURE_PASSWORD,
        "use_refresh_tokens": refresh,
    })
    assert response.status_code == 200
    return response.json()["data"]


def bearer(data):
    return {"Authorization": f"Bearer {data['access_token']}"}


def rotate(client, data, prefix="/api/v1"):
    return client.post(f"{prefix}/auth/refresh", json={"refresh_token": data["refresh_token"]})


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
@pytest.mark.parametrize("user_id,role", [(1, "admin"), (2, "customer"), (4, "seller")])
def test_compatible_login_preserves_account_and_contract(client, prefix, user_id, role):
    with SessionLocal() as db:
        password_hash = db.get(User, user_id).password_hash
        sellers = list(db.scalars(select(Seller.id).where(Seller.user_id == user_id)))
    data = login(client, user_id, refresh=False, prefix=prefix)
    assert data["token"] == data["access_token"]
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    assert data["refresh_token"] is None
    assert data["user"]["role"] == role
    claims = decode_access_token(data["access_token"])
    assert claims["type"] == "access"
    assert claims["exp"] - claims["iat"] == data["expires_in"]
    assert client.get(f"{prefix}/auth/me", headers=bearer(data)).status_code == 200
    with SessionLocal() as db:
        assert db.get(User, user_id).password_hash == password_hash
        assert list(db.scalars(select(Seller.id).where(Seller.user_id == user_id))) == sellers


def test_default_request_needs_no_client_changes(client):
    response = client.post("/api/auth/login", json={"email": "user2@example.com", "password": FIXTURE_PASSWORD})
    assert response.status_code == 200
    assert response.json()["data"]["expires_in"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    assert response.json()["data"]["refresh_token"] is None


def test_refresh_opt_in_uses_short_lifetime_and_only_hashes_at_rest(client):
    data = login(client)
    claims = decode_access_token(data["access_token"])
    assert data["expires_in"] == settings.SESSION_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    assert claims["exp"] - claims["iat"] == data["expires_in"]
    assert claims["iss"] == settings.JWT_ISSUER
    assert claims["aud"] == settings.JWT_AUDIENCE
    assert claims["jti"] and claims["session_id"]
    with SessionLocal() as db:
        row = db.scalar(select(RefreshToken))
        assert row.token_hash == hash_refresh_token(data["refresh_token"])
        assert data["refresh_token"] not in row.token_hash
        assert row.session_id == claims["session_id"]
    assert "token_hash" not in json.dumps(data)


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_register_creates_customer_session_atomically(client, prefix):
    response = client.post(f"{prefix}/auth/register", json={
        "full_name": "New Customer", "email": "new@example.com", "password": NEW_PASSWORD,
        "use_refresh_tokens": True, "role": "admin",
    })
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["user"]["role"] == "customer"
    assert data["token"] == data["access_token"]
    assert data["refresh_token"]
    assert client.get(f"{prefix}/auth/me", headers=bearer(data)).status_code == 200


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_logout_revokes_only_associated_device_and_refresh(client, prefix):
    first, second = login(client), login(client)
    response = client.post(f"{prefix}/auth/logout", headers=bearer(first))
    assert response.status_code == 200
    assert client.get("/api/auth/me", headers=bearer(first)).status_code == 401
    assert rotate(client, first).status_code == 401
    assert client.get("/api/auth/me", headers=bearer(second)).status_code == 200
    assert rotate(client, second).status_code == 200
    assert client.post(f"{prefix}/auth/logout", headers=bearer(first)).status_code == 401


def test_rotated_refresh_replay_revokes_entire_family_but_other_device_survives(client, caplog):
    original, other_device = login(client), login(client)
    response = rotate(client, original, prefix="/api")
    assert response.status_code == 200
    rotated = response.json()["data"]
    assert rotated["refresh_token"] != original["refresh_token"]
    assert rotated["access_token"] != original["access_token"]
    assert rotated["token"] == rotated["access_token"]
    assert client.get("/api/auth/me", headers=bearer(rotated)).status_code == 200
    replay = rotate(client, original)
    assert replay.status_code == 401
    assert replay.json()["error_code"] == "TOKEN_REUSE_DETECTED"
    assert replay.headers["www-authenticate"] == "Bearer"
    assert client.get("/api/auth/me", headers=bearer(original)).status_code == 401
    assert client.get("/api/auth/me", headers=bearer(rotated)).status_code == 401
    assert rotate(client, rotated).status_code == 401
    assert client.get("/api/auth/me", headers=bearer(other_device)).status_code == 200
    assert original["refresh_token"] not in caplog.text
    assert rotated["refresh_token"] not in caplog.text
    assert original["access_token"] not in caplog.text
    with SessionLocal() as db:
        session_id = decode_access_token(original["access_token"])["session_id"]
        assert db.scalar(select(UserSession).where(UserSession.session_id == session_id)).is_revoked
        assert all(t.is_revoked for t in db.scalars(select(RefreshToken).where(RefreshToken.session_id == session_id)))


def test_repeated_rotations_preserve_family_and_absolute_expiration(client):
    data = login(client)
    with SessionLocal() as db:
        expiration = db.scalar(select(UserSession)).expires_at
    for _ in range(3):
        response = rotate(client, data)
        assert response.status_code == 200
        data = response.json()["data"]
    with SessionLocal() as db:
        assert db.scalar(select(func.count(UserSession.id))) == 1
        assert db.scalar(select(func.count(RefreshToken.id))) == 4
        assert db.scalar(select(UserSession)).expires_at == expiration
        assert all(token.expires_at == expiration for token in db.scalars(select(RefreshToken)))


@pytest.mark.parametrize("target", ["access", "session", "refresh", "revoked_refresh", "missing_session", "wrong_owner"])
def test_expired_revoked_missing_or_wrong_owner_session_denied(client, target):
    data = login(client)
    with SessionLocal() as db:
        session = db.scalar(select(UserSession))
        token = db.scalar(select(RefreshToken))
        if target == "access":
            data["access_token"] = create_access_token({"sub": "2"}, timedelta(seconds=-1), session_id=session.session_id)
        elif target == "session":
            session.expires_at = utc_now() - timedelta(seconds=1)
        elif target == "refresh":
            token.expires_at = utc_now() - timedelta(seconds=1)
        elif target == "revoked_refresh":
            token.is_revoked = True
        elif target == "missing_session":
            db.delete(session)
        elif target == "wrong_owner":
            session.user_id = 3
        db.commit()
    if target in {"access", "session", "missing_session", "wrong_owner"}:
        assert client.get("/api/auth/me", headers=bearer(data)).status_code == 401
    if target != "access":
        response = rotate(client, data)
        # A token's owner is its DB session owner; changing that relationship is
        # privileged DB tampering, so refresh binds to that owner, never JWT input.
        if target == "wrong_owner":
            assert response.status_code == 200
            assert decode_access_token(response.json()["data"]["access_token"])["sub"] == "3"
        else:
            assert response.status_code == 401


@pytest.mark.parametrize("changes", [
    {"type": "refresh"}, {"aud": "another-api"}, {"iss": "another-issuer"},
    {"exp": None}, {"exp": "9999999999"}, {"exp": True}, {"iat": "1"},
    {"sub": "invalid"}, {"session_id": ""}, {"jti": ""},
])
def test_invalid_signed_claims_cannot_fall_back_to_legacy(client, changes):
    data = login(client)
    payload = decode_access_token(data["access_token"])
    payload.update(changes)
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


@pytest.mark.parametrize("claim", ["exp", "sub", "iat", "jti", "session_id", "type", "iss", "aud"])
def test_required_modern_claims(client, claim):
    data = login(client)
    payload = decode_access_token(data["access_token"])
    payload.pop(claim)
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_password_change_revokes_all_devices_and_unseen_legacy_tokens(client):
    legacy_unseen = create_access_token({"sub": "2"})
    devices = [login(client), login(client)]
    response = client.put("/api/auth/change-password", headers=bearer(devices[0]), json={
        "current_password": FIXTURE_PASSWORD, "new_password": NEW_PASSWORD,
    })
    assert response.status_code == 200
    for data in devices:
        assert client.get("/api/auth/me", headers=bearer(data)).status_code == 401
        assert rotate(client, data).status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {legacy_unseen}"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "user2@example.com", "password": FIXTURE_PASSWORD}).status_code == 401
    fresh = client.post("/api/auth/login", json={"email": "user2@example.com", "password": NEW_PASSWORD})
    assert fresh.status_code == 200
    assert client.get("/api/auth/me", headers=bearer(fresh.json()["data"])).status_code == 200
    with SessionLocal() as db:
        assert db.get(User, 2).legacy_tokens_revoked_at is not None


@pytest.mark.parametrize("new_password,current_password", [(NEW_PASSWORD, "incorrect"), ("short", FIXTURE_PASSWORD)])
def test_failed_password_change_preserves_sessions(client, new_password, current_password):
    data = login(client)
    response = client.put("/api/auth/change-password", headers=bearer(data), json={
        "current_password": current_password, "new_password": new_password,
    })
    assert response.status_code == 400
    assert client.get("/api/auth/me", headers=bearer(data)).status_code == 200
    assert rotate(client, data).status_code == 200


def test_admin_password_reset_revokes_target_only(client):
    admin, target = login(client, 1), login(client, 4)
    legacy = create_access_token({"sub": "4"})
    response = client.put("/api/users/4", headers=bearer(admin), json={"password": NEW_PASSWORD})
    assert response.status_code == 200
    assert client.get("/api/auth/me", headers=bearer(target)).status_code == 401
    assert rotate(client, target).status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {legacy}"}).status_code == 401
    assert client.get("/api/users", headers=bearer(admin)).status_code == 200


def test_logout_all_is_user_scoped_and_blocks_unseen_legacy(client):
    first, second, other_user = login(client), login(client), login(client, 4)
    unseen = create_access_token({"sub": "2"})
    assert client.post("/api/auth/logout-all", headers=bearer(first)).status_code == 200
    for data in [first, second]:
        assert client.get("/api/auth/me", headers=bearer(data)).status_code == 401
        assert rotate(client, data).status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {unseen}"}).status_code == 401
    assert client.get("/api/auth/me", headers=bearer(other_user)).status_code == 200


def test_legacy_jwt_adopts_once_and_logout_is_persistent(client):
    token = create_access_token({"sub": "2"})
    headers = {"Authorization": f"Bearer {token}"}
    for _ in range(2):
        assert client.get("/api/auth/me", headers=headers).status_code == 200
    with SessionLocal() as db:
        assert db.scalar(select(func.count(UserSession.id))) == 1
        assert db.scalar(select(func.count(RefreshToken.id))) == 0
    assert client.post("/api/auth/logout", headers=headers).status_code == 200
    assert client.get("/api/auth/me", headers=headers).status_code == 401


@pytest.mark.parametrize("setting", ["disabled", "sunset"])
def test_legacy_cutover_does_not_disable_modern_sessions(client, monkeypatch, setting):
    legacy = create_access_token({"sub": "2"})
    modern = login(client)
    if setting == "disabled":
        monkeypatch.setattr(settings, "AUTH_ACCEPT_LEGACY_TOKENS", False)
    else:
        monkeypatch.setattr(settings, "AUTH_LEGACY_ACCEPT_UNTIL", utc_now() - timedelta(seconds=1))
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {legacy}"}).status_code == 401
    assert client.get("/api/auth/me", headers=bearer(modern)).status_code == 200


def test_validation_only_rollout_supports_old_workers_and_password_changes(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ISSUE_SESSION_TOKENS", False)
    data = login(client, refresh=False)
    # Mirrors the deployed decoder, which cannot yet accept an audience claim.
    jwt.decode(data["access_token"], settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    assert client.get("/api/auth/me", headers=bearer(data)).status_code == 200
    assert client.put("/api/auth/change-password", headers=bearer(data), json={
        "current_password": FIXTURE_PASSWORD, "new_password": NEW_PASSWORD,
    }).status_code == 200
    assert client.get("/api/auth/me", headers=bearer(data)).status_code == 401
    fresh = client.post("/api/auth/login", json={"email": "user2@example.com", "password": NEW_PASSWORD})
    assert fresh.status_code == 200
    assert client.get("/api/auth/me", headers=bearer(fresh.json()["data"])).status_code == 200


def test_refresh_opt_in_not_available_during_validation_only_rollout(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ISSUE_SESSION_TOKENS", False)
    response = client.post("/api/auth/register", json={
        "name": "No Partial Account", "email": "partial@example.com", "password": NEW_PASSWORD,
        "use_refresh_tokens": True,
    })
    assert response.status_code == 401
    with SessionLocal() as db:
        assert db.scalar(select(User).where(User.email == "partial@example.com")) is None


@pytest.mark.parametrize("user_id,endpoint,expected", [
    (2, "/api/users", 403), (4, "/api/users", 403), (1, "/api/users", 200),
    (2, "/api/seller/me", 403), (4, "/api/seller/me", 200),
])
def test_existing_roles_and_ownership_survive_refresh(client, user_id, endpoint, expected):
    data = login(client, user_id)
    rotated = rotate(client, data).json()["data"]
    assert client.get(endpoint, headers=bearer(rotated)).status_code == expected
    if user_id == 4:
        assert client.put("/api/products/2", headers=bearer(rotated), json={"name": "Wrong owner"}).status_code == 404


def test_current_database_role_and_active_flag_are_authoritative(client):
    data = login(client, 1)
    with SessionLocal() as db:
        db.get(User, 1).role = "customer"
        db.commit()
    rotated = rotate(client, data).json()["data"]
    assert client.get("/api/users", headers=bearer(rotated)).status_code == 403
    with SessionLocal() as db:
        db.get(User, 1).is_active = False
        db.commit()
    assert client.get("/api/auth/me", headers=bearer(rotated)).status_code == 403
    assert rotate(client, rotated).status_code == 401


def test_refresh_quota_shared_between_route_aliases(client):
    for index in range(settings.RATE_LIMIT_AUTH_REFRESH):
        prefix = "/api" if index % 2 else "/api/v1"
        assert client.post(f"{prefix}/auth/refresh", json={"refresh_token": "unknown"}).status_code == 401
    response = client.post("/api/auth/refresh", json={"refresh_token": "unknown"})
    assert response.status_code == 429
    assert response.json()["error_code"] == "RATE_LIMIT_EXCEEDED"
    assert int(response.headers["retry-after"]) > 0


@pytest.mark.parametrize("body", [{}, {"refresh_token": ""}, {"refresh_token": None}, {"refresh_token": 123}, {"refresh_token": "x" * 513}])
def test_refresh_validation_does_not_echo_input(client, body):
    response = client.post("/api/auth/refresh", json=body)
    assert response.status_code == 422
    assert all("input" not in error and "ctx" not in error for error in response.json()["detail"])
    assert response.headers["cache-control"] == "no-store"


def test_invalid_refresh_never_downgrades_to_access_or_cookie_auth(client):
    data = login(client)
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {data['refresh_token']}"}).status_code == 401
    assert rotate(client, {"refresh_token": data["access_token"]}).status_code == 401
    client.cookies.set("refresh_token", data["refresh_token"])
    assert client.post("/api/auth/refresh", json={}).status_code == 422
    client.cookies.clear()
    assert client.post("/api/auth/logout").status_code == 401


def test_sensitive_responses_are_not_cached_and_unknown_refresh_is_generic(client):
    response = client.post("/api/auth/login", json={"email": "user2@example.com", "password": FIXTURE_PASSWORD})
    assert response.headers["cache-control"] == "no-store"
    invalid = client.post("/api/auth/refresh", json={"refresh_token": "unrecognized-credential"})
    assert invalid.status_code == 401
    assert invalid.headers["cache-control"] == "no-store"
    assert "unrecognized-credential" not in invalid.text
    assert "token_hash" not in invalid.text


def test_logout_expiry_between_dependency_and_handler_is_401(client, monkeypatch):
    from app.api.v1.routes import auth

    data = login(client)
    monkeypatch.setattr(auth, "decode_access_token", lambda token: None)
    assert client.post("/api/auth/logout", headers=bearer(data)).status_code == 401


def test_issued_credentials_are_not_exposed_in_object_repr():
    issued = IssuedTokens("private-access-value", "private-refresh-value", 900)
    assert "private-access-value" not in repr(issued)
    assert "private-refresh-value" not in repr(issued)


def test_zero_lifetime_token_does_not_fall_back_to_default_lifetime(client):
    token = create_access_token({"sub": "2"}, timedelta(0))
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
