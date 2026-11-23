"""Account recovery tests: hashed reset tokens, SMTP/SendGrid dispatch, validation, single-use, session revocation."""

from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.db.database import SessionLocal
from app.models.password_reset import PasswordResetToken
from app.models.user import User
from app.services.email_service import EmailService


def test_forgot_password_does_not_enumerate_emails_and_hashes_token(
    client, monkeypatch
):
    sent_payloads: list[dict] = []

    def fake_send_email(*, to_email, user_name, raw_token, client="storefront", expire_minutes=None, cfg=None):
        sent_payloads.append(
            {
                "to_email": to_email,
                "user_name": user_name,
                "raw_token": raw_token,
                "client": client,
            }
        )
        return "smtp"

    monkeypatch.setattr(EmailService, "ensure_configured", staticmethod(lambda cfg=None: "smtp"))
    monkeypatch.setattr(EmailService, "send_password_reset_email", staticmethod(fake_send_email))

    # Unknown email returns generic 200 without sending email
    unknown_res = client.post(
        "/api/auth/forgot-password",
        json={"email": "nobody-here@example.com", "client": "storefront"},
    )
    assert unknown_res.status_code == 200
    assert unknown_res.json()["success"] is True
    assert len(sent_payloads) == 0

    # Existing user triggers reset email and stores hashed token (never raw token)
    known_res = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "user2@example.com", "client": "management"},
    )
    assert known_res.status_code == 200
    assert known_res.json()["success"] is True
    assert len(sent_payloads) == 1
    issued_token = sent_payloads[0]["raw_token"]
    assert sent_payloads[0]["client"] == "management"
    assert len(issued_token) >= 32

    with SessionLocal() as db:
        rows = list(db.scalars(select(PasswordResetToken).where(PasswordResetToken.user_id == 2)).all())
        assert len(rows) == 1
        assert rows[0].token_hash != issued_token
        assert len(rows[0].token_hash) == 64


def test_email_service_smtp_sendgrid_and_prod_guard(monkeypatch):
    # 1. Production with unconfigured email fails closed with 503
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "auto")
    monkeypatch.setattr(settings, "SENDGRID_API_KEY", None)
    monkeypatch.setattr(settings, "SMTP_HOST", None)

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        EmailService.ensure_configured()
    assert exc_info.value.status_code == 503

    # 2. SMTP transport path invokes smtplib.SMTP and sends message
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "smtp")
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.test")
    monkeypatch.setattr(settings, "SMTP_PORT", 587)
    monkeypatch.setattr(settings, "SMTP_USE_TLS", True)
    monkeypatch.setattr(settings, "SMTP_USERNAME", "mailer")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "app-pass")

    smtp_events: list[str] = []

    class FakeSMTP:
        def __init__(self, host, port, timeout=15):
            smtp_events.append(f"connect:{host}:{port}")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def ehlo(self):
            smtp_events.append("ehlo")

        def starttls(self, context=None):
            smtp_events.append("starttls")

        def login(self, user, pwd):
            smtp_events.append(f"login:{user}")

        def send_message(self, msg):
            smtp_events.append(f"send:{msg['To']}")

    monkeypatch.setattr("app.services.email_service.smtplib.SMTP", FakeSMTP)
    provider = EmailService.send_password_reset_email(
        to_email="user2@example.com",
        user_name="Fixture 2",
        raw_token="raw_tok_123",
    )
    assert provider == "smtp"
    assert "send:user2@example.com" in smtp_events

    # 3. SendGrid HTTP API path
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "sendgrid")
    monkeypatch.setattr(settings, "SENDGRID_API_KEY", "SG.fake_key_123")
    sendgrid_calls: list[dict] = []

    class FakeResp:
        status_code = 202

    def fake_httpx_post(url, headers=None, json=None, timeout=10.0):
        sendgrid_calls.append({"url": url, "headers": headers, "json": json})
        return FakeResp()

    monkeypatch.setattr("app.services.email_service.httpx.post", fake_httpx_post)
    sg_provider = EmailService.send_password_reset_email(
        to_email="user2@example.com",
        user_name="Fixture 2",
        raw_token="raw_tok_456",
    )
    assert sg_provider == "sendgrid"
    assert sendgrid_calls[0]["url"] == "https://api.sendgrid.com/v3/mail/send"
    assert sendgrid_calls[0]["json"]["personalizations"][0]["to"][0]["email"] == "user2@example.com"


def test_reset_password_full_lifecycle_revokes_sessions_and_is_single_use(
    client, monkeypatch
):
    captured_tokens: list[str] = []

    monkeypatch.setattr(EmailService, "ensure_configured", staticmethod(lambda cfg=None: "console"))
    monkeypatch.setattr(
        EmailService,
        "send_password_reset_email",
        staticmethod(lambda **kwargs: captured_tokens.append(kwargs["raw_token"]) or "console"),
    )

    # Log in first to obtain a live bearer session
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "user2@example.com", "password": "Fixture-password-123"},
    )
    assert login_res.status_code == 200
    old_token = login_res.json()["data"]["access_token"]
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {old_token}"}).status_code
        == 200
    )

    # Trigger forgot password
    client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "user2@example.com", "client": "storefront"},
    )
    assert len(captured_tokens) == 1
    reset_token = captured_tokens[0]

    # Validate valid & invalid tokens
    val_ok = client.post("/api/auth/reset-password/validate", json={"token": reset_token})
    assert val_ok.status_code == 200
    assert val_ok.json()["data"]["valid"] is True

    val_bad = client.post(
        "/api/auth/reset-password/validate",
        json={"token": "nonexistent-reset-token-123456"},
    )
    assert val_bad.status_code == 200
    assert val_bad.json()["data"]["valid"] is False

    # Weak password rejected
    weak_res = client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "short"},
    )
    assert weak_res.status_code in (400, 422)

    # Valid reset succeeds
    reset_res = client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "BrandNewSecurePassword!99"},
    )
    assert reset_res.status_code == 200

    # Prior bearer session is revoked immediately
    stale_me = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {old_token}"}
    )
    assert stale_me.status_code == 401

    # Single-use: second reuse of same token is rejected
    reuse_res = client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "AnotherPassword!123"},
    )
    assert reuse_res.status_code == 400

    # Old password fails; new password logs in cleanly
    old_login = client.post(
        "/api/v1/auth/login",
        json={"email": "user2@example.com", "password": "Fixture-password-123"},
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/api/v1/auth/login",
        json={"email": "user2@example.com", "password": "BrandNewSecurePassword!99"},
    )
    assert new_login.status_code == 200


def test_expired_reset_token_is_rejected(client, monkeypatch):
    captured: list[str] = []
    monkeypatch.setattr(EmailService, "ensure_configured", staticmethod(lambda cfg=None: "console"))
    monkeypatch.setattr(
        EmailService,
        "send_password_reset_email",
        staticmethod(lambda **kwargs: captured.append(kwargs["raw_token"]) or "console"),
    )

    client.post(
        "/api/auth/forgot-password",
        json={"email": "user2@example.com"},
    )
    token = captured[0]

    with SessionLocal() as db:
        row = db.scalar(select(PasswordResetToken).where(PasswordResetToken.user_id == 2))
        row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        db.commit()

    val_res = client.post("/api/auth/reset-password/validate", json={"token": token})
    assert val_res.status_code == 200
    assert val_res.json()["data"]["valid"] is False

    reset_res = client.post(
        "/api/auth/reset-password",
        json={"token": token, "new_password": "AnotherValidPassword!77"},
    )
    assert reset_res.status_code == 400
