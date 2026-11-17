"""Tests for Phase 1C Task 1: Backend Session & Token Models and Password Policy."""
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy.exc import IntegrityError

from app.core.password_policy import (
    COMMON_PASSWORDS,
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    normalize_password,
    validate_password_strength,
)
from app.db.database import SessionLocal
from app.models.session import RefreshToken, UserSession
from app.models.user import User
from app.schemas.auth import (
    RefreshTokenRequest,
    RefreshTokenResponse,
    SessionListResponse,
    SessionResponse,
    TokenResponse,
)
from app.schemas.user import UserResponse


# -----------------------------------------------------------------------------
# SQLAlchemy Session & Refresh Token Model Tests
# -----------------------------------------------------------------------------


def test_user_session_creation_and_defaults():
    """Verify UserSession persists correctly with expected defaults."""
    with SessionLocal() as db:
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=7)
        session = UserSession(
            session_id="test-session-uuid-1",
            user_id=1,
            token_family="family-uuid-1",
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0 TestBrowser",
            device_name="Chrome on macOS",
            expires_at=expires,
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        assert session.id is not None
        assert session.session_id == "test-session-uuid-1"
        assert session.user_id == 1
        assert session.token_family == "family-uuid-1"
        assert session.ip_address == "192.168.1.100"
        assert session.device_name == "Chrome on macOS"
        assert session.is_revoked is False
        assert session.revoked_reason is None
        assert session.created_at is not None
        assert session.last_activity_at is not None


def test_refresh_token_creation_and_defaults():
    """Verify RefreshToken persists correctly with expected defaults."""
    with SessionLocal() as db:
        now = datetime.now(timezone.utc)
        session = UserSession(
            session_id="test-session-uuid-2",
            user_id=1,
            token_family="family-uuid-2",
            expires_at=now + timedelta(days=7),
        )
        db.add(session)
        db.commit()

        refresh_token = RefreshToken(
            session_id="test-session-uuid-2",
            token_hash="a" * 64,
            parent_token_hash=None,
            expires_at=now + timedelta(days=7),
        )
        db.add(refresh_token)
        db.commit()
        db.refresh(refresh_token)

        assert refresh_token.id is not None
        assert refresh_token.session_id == "test-session-uuid-2"
        assert refresh_token.token_hash == "a" * 64
        assert refresh_token.parent_token_hash is None
        assert refresh_token.is_revoked is False
        assert refresh_token.used_at is None
        assert refresh_token.created_at is not None


def test_relationship_traversal():
    """Verify bidirectional navigation between User, UserSession, and RefreshToken."""
    with SessionLocal() as db:
        now = datetime.now(timezone.utc)
        session = UserSession(
            session_id="test-session-uuid-3",
            user_id=2,
            token_family="family-uuid-3",
            device_name="Flutter on iOS",
            expires_at=now + timedelta(days=7),
        )
        token1 = RefreshToken(
            session_id="test-session-uuid-3",
            token_hash="b" * 64,
            expires_at=now + timedelta(days=7),
        )
        token2 = RefreshToken(
            session_id="test-session-uuid-3",
            token_hash="c" * 64,
            parent_token_hash="b" * 64,
            expires_at=now + timedelta(days=7),
        )
        session.refresh_tokens.extend([token1, token2])
        db.add(session)
        db.commit()

        # Fetch user and traverse to sessions and refresh tokens
        user = db.query(User).filter_by(id=2).first()
        assert user is not None
        user_session_ids = [s.session_id for s in user.sessions]
        assert "test-session-uuid-3" in user_session_ids

        matched_session = next(s for s in user.sessions if s.session_id == "test-session-uuid-3")
        assert matched_session.user.id == 2
        assert len(matched_session.refresh_tokens) == 2

        # Verify child token points back to session and user
        child_token = matched_session.refresh_tokens[0]
        assert child_token.session.session_id == "test-session-uuid-3"
        assert child_token.session.user.id == 2


def test_cascade_delete_user_removes_sessions_and_tokens():
    """Deleting a user must cascade delete all sessions and refresh tokens."""
    with SessionLocal() as db:
        temp_user = User(
            name="Temporary User",
            email="temp.cascade@example.com",
            role="customer",
            password_hash="hashed-pw",
            is_active=True,
        )
        db.add(temp_user)
        db.commit()
        db.refresh(temp_user)
        user_id = temp_user.id

        now = datetime.now(timezone.utc)
        session = UserSession(
            session_id="cascade-session-uuid",
            user_id=user_id,
            token_family="cascade-family",
            expires_at=now + timedelta(days=7),
        )
        token = RefreshToken(
            session_id="cascade-session-uuid",
            token_hash="d" * 64,
            expires_at=now + timedelta(days=7),
        )
        session.refresh_tokens.append(token)
        db.add(session)
        db.commit()

        # Confirm existence
        assert db.query(UserSession).filter_by(session_id="cascade-session-uuid").first() is not None
        assert db.query(RefreshToken).filter_by(token_hash="d" * 64).first() is not None

        # Delete user
        db.delete(temp_user)
        db.commit()

        # Verify cascade
        assert db.query(UserSession).filter_by(session_id="cascade-session-uuid").first() is None
        assert db.query(RefreshToken).filter_by(token_hash="d" * 64).first() is None


def test_cascade_delete_session_removes_refresh_tokens():
    """Deleting a session must cascade delete child refresh tokens but keep user."""
    with SessionLocal() as db:
        now = datetime.now(timezone.utc)
        session = UserSession(
            session_id="session-cascade-only",
            user_id=1,
            token_family="family-isolated",
            expires_at=now + timedelta(days=7),
        )
        token = RefreshToken(
            session_id="session-cascade-only",
            token_hash="e" * 64,
            expires_at=now + timedelta(days=7),
        )
        session.refresh_tokens.append(token)
        db.add(session)
        db.commit()

        # Delete session
        db.delete(session)
        db.commit()

        # Child token must be gone
        assert db.query(RefreshToken).filter_by(token_hash="e" * 64).first() is None
        # User 1 must still exist
        assert db.query(User).filter_by(id=1).first() is not None


def test_unique_constraints_on_session_and_token():
    """Enforce unique session_id and token_hash constraints."""
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        s1 = UserSession(
            session_id="unique-sess-id",
            user_id=1,
            token_family="fam-1",
            expires_at=now + timedelta(days=1),
        )
        db.add(s1)
        db.commit()

    with SessionLocal() as db:
        s2 = UserSession(
            session_id="unique-sess-id",
            user_id=2,
            token_family="fam-2",
            expires_at=now + timedelta(days=1),
        )
        db.add(s2)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    with SessionLocal() as db:
        t1 = RefreshToken(
            session_id="unique-sess-id",
            token_hash="f" * 64,
            expires_at=now + timedelta(days=1),
        )
        db.add(t1)
        db.commit()

    with SessionLocal() as db:
        t2 = RefreshToken(
            session_id="unique-sess-id",
            token_hash="f" * 64,
            expires_at=now + timedelta(days=1),
        )
        db.add(t2)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


# -----------------------------------------------------------------------------
# Password Policy Validation & Normalization Tests
# -----------------------------------------------------------------------------


def test_password_policy_length_bounds():
    """Validate boundary conditions for password length."""
    # Under minimum
    valid, msg = validate_password_strength("short")
    assert valid is False
    assert f"at least {MIN_PASSWORD_LENGTH}" in msg

    valid, msg = validate_password_strength("1234567")
    assert valid is False
    assert f"at least {MIN_PASSWORD_LENGTH}" in msg

    # Over maximum
    too_long = "a" * (MAX_PASSWORD_LENGTH + 1)
    valid, msg = validate_password_strength(too_long)
    assert valid is False
    assert f"cannot exceed {MAX_PASSWORD_LENGTH}" in msg

    # Exact max length (with diverse characters)
    exact_max = ("SuperSecurePassphrase!" * 6)[:MAX_PASSWORD_LENGTH]
    assert len(exact_max) == MAX_PASSWORD_LENGTH
    valid, msg = validate_password_strength(exact_max)
    assert valid is True
    assert msg is None


def test_password_policy_whitespace_and_invalid_types():
    """Reject empty strings, pure whitespace, and non-string inputs."""
    for invalid in ["", "        ", "\t\t\n\r  ", "   "]:
        valid, msg = validate_password_strength(invalid)
        assert valid is False
        assert "whitespace" in msg or f"at least {MIN_PASSWORD_LENGTH}" in msg

    valid, msg = validate_password_strength(None)  # type: ignore[arg-type]
    assert valid is False
    assert "valid text string" in msg


def test_password_policy_repeated_character():
    """Reject single repeated character passwords."""
    for repeated in ["aaaaaaaa", "11111111", "!!!!!!!!", "ZZZZZZZZZZ"]:
        valid, msg = validate_password_strength(repeated)
        assert valid is False
        assert "single repeated character" in msg


def test_password_policy_common_trivial_passwords():
    """Reject known trivial and easily guessed passwords."""
    for trivial in ["password", "Password123", "12345678", "qwertyuiop", "admin123", "letmein123"]:
        valid, msg = validate_password_strength(trivial)
        assert valid is False
        assert "too common or easily guessed" in msg


def test_password_policy_valid_passphrases():
    """Accept multi-word passphrases and strong passwords without composition penalties."""
    valid_passwords = [
        "correct horse battery staple",
        "blue panda marketplace 2026",
        "C0mpl3x-P@ssw0rd!#99",
        "this is a very long and memorable passphrase that satisfies nist guidelines",
        "Khmer-Kampot-Pepper-2026",
    ]
    for pwd in valid_passwords:
        valid, msg = validate_password_strength(pwd)
        assert valid is True, f"Failed for {pwd}: {msg}"
        assert msg is None


def test_password_policy_unicode_nfkc_normalization():
    """Verify Unicode NFKC normalization processes decomposed characters correctly."""
    # Decomposed: 'e' + combining acute accent (\u0301) vs Precomposed: '\u00e9'
    decomposed = "caf\u0065\u030112345"
    precomposed = "caf\u00e912345"
    normalized_decomposed = normalize_password(decomposed)
    normalized_precomposed = normalize_password(precomposed)

    assert normalized_decomposed == normalized_precomposed
    valid, msg = validate_password_strength(decomposed)
    assert valid is True


# -----------------------------------------------------------------------------
# Pydantic Schemas Tests
# -----------------------------------------------------------------------------


def test_pydantic_refresh_token_request_and_response():
    """Verify RefreshTokenRequest and RefreshTokenResponse contracts."""
    req = RefreshTokenRequest(refresh_token="sample-refresh-token")
    assert req.refresh_token.get_secret_value() == "sample-refresh-token"
    assert "sample-refresh-token" not in repr(req)

    res = RefreshTokenResponse(
        access_token="new-access-token",
        expires_in=900,
        refresh_token="rotated-refresh-token",
    )
    dumped = res.model_dump()
    assert dumped["access_token"] == "new-access-token"
    assert dumped["token"] == "new-access-token"  # Alias validator
    assert dumped["token_type"] == "bearer"
    assert dumped["expires_in"] == 900
    assert dumped["refresh_token"] == "rotated-refresh-token"
    assert "token_hash" not in dumped


def test_pydantic_session_responses_and_no_token_hash_exposure():
    """Verify SessionResponse and SessionListResponse do not leak token_hash."""
    now = datetime.now(timezone.utc)
    sess_res = SessionResponse(
        session_id="sess-uuid-4",
        device_name="Safari on iPhone",
        ip_address="10.0.0.1",
        created_at=now,
        last_activity_at=now,
        is_current=True,
    )
    dumped = sess_res.model_dump()
    assert dumped["session_id"] == "sess-uuid-4"
    assert dumped["device_name"] == "Safari on iPhone"
    assert dumped["ip_address"] == "10.0.0.1"
    assert dumped["is_current"] is True
    assert "token_hash" not in dumped
    assert "token_hash" not in SessionResponse.model_fields

    list_res = SessionListResponse(sessions=[sess_res], total=1)
    list_dumped = list_res.model_dump()
    assert list_dumped["total"] == 1
    assert len(list_dumped["sessions"]) == 1
    assert "token_hash" not in list_dumped["sessions"][0]
    assert "token_hash" not in SessionListResponse.model_fields


def test_pydantic_token_response_backward_compatibility():
    """Ensure TokenResponse maintains full backward compatibility with legacy consumers."""
    legacy_data = {
        "access_token": "legacy-access-token",
        "user": {
            "id": 1,
            "name": "Fixture User",
            "email": "user@example.com",
            "role": "customer",
            "is_active": True,
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        },
    }
    tok_res = TokenResponse(**legacy_data)
    dumped = tok_res.model_dump()

    # Legacy fields
    assert dumped["access_token"] == "legacy-access-token"
    assert dumped["token"] == "legacy-access-token"
    assert dumped["token_type"] == "bearer"
    assert dumped["user"]["email"] == "user@example.com"

    # New optional/default fields
    assert dumped["expires_in"] == 900
    assert dumped["refresh_token"] is None
    assert "token_hash" not in dumped
