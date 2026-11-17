"""Verify the shipping defaults separately from opt-in modern session tests."""
import pytest
from sqlalchemy import func, select

from app.core.config import Settings, settings
from app.core.security import decode_access_token
from app.db.database import SessionLocal
from app.models.session import RefreshToken


def test_modern_issuance_is_opt_in_by_default():
    assert Settings.model_fields["AUTH_ISSUE_SESSION_TOKENS"].default is False
    assert Settings.model_fields["AUTH_ACCEPT_LEGACY_TOKENS"].default is True


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
@pytest.mark.parametrize("user_id,role", [(1, "admin"), (2, "customer"), (4, "seller")])
def test_default_rollout_login_and_logout_are_backward_compatible(client, monkeypatch, prefix, user_id, role):
    monkeypatch.setattr(settings, "AUTH_ISSUE_SESSION_TOKENS", Settings.model_fields["AUTH_ISSUE_SESSION_TOKENS"].default)
    response = client.post(f"{prefix}/auth/login", json={
        "email": f"user{user_id}@example.com", "password": "Fixture-password-123",
    })
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["token"] == data["access_token"]
    assert data["user"]["role"] == role
    assert data["expires_in"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    assert data["refresh_token"] is None
    claims = decode_access_token(data["access_token"])
    assert "session_id" not in claims and "aud" not in claims
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    assert client.get(f"{prefix}/auth/me", headers=headers).status_code == 200
    assert client.post(f"{prefix}/auth/logout", headers=headers).status_code == 200
    assert client.get(f"{prefix}/auth/me", headers=headers).status_code == 401
    with SessionLocal() as db:
        assert db.scalar(select(func.count(RefreshToken.id))) == 0
