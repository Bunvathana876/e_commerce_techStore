import base64
from datetime import datetime, timedelta, timezone
import hashlib
import math
import secrets
from typing import Any
from uuid import uuid4

import bcrypt
import jwt

from app.core.config import settings

SHA256_BCRYPT_PREFIX = "sha256$"


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt, pre-hashing secrets over 72 UTF-8 bytes."""
    salt = bcrypt.gensalt()
    raw = password.encode("utf-8")
    if len(raw) <= 72:
        return bcrypt.hashpw(raw, salt).decode("utf-8")
    # Pre-hash long passphrases so bcrypt's 72-byte limit never raises or truncates entropy.
    digest = base64.b64encode(hashlib.sha256(raw).digest())
    return f"{SHA256_BCRYPT_PREFIX}{bcrypt.hashpw(digest, salt).decode('utf-8')}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored bcrypt (or SHA-256 pre-hashed) digest."""
    try:
        raw = plain_password.encode("utf-8")
        if hashed_password.startswith(SHA256_BCRYPT_PREFIX):
            digest = base64.b64encode(hashlib.sha256(raw).digest())
            stored_hash = hashed_password[len(SHA256_BCRYPT_PREFIX):].encode("utf-8")
            return bcrypt.checkpw(digest, stored_hash)
        if len(raw) > 72:
            return False
        return bcrypt.checkpw(raw, hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
    *,
    session_id: str | None = None,
) -> str:
    """Generate a signed JWT access token."""
    to_encode = data.copy()
    
    if expires_delta is not None:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    if session_id is not None:
        to_encode.update({
            "type": "access",
            "session_id": session_id,
            "jti": str(uuid4()),
            "iat": datetime.now(timezone.utc),
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
        })
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Validate modern claims strictly; accept signed legacy JWTs during rollout."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["exp", "sub"], "verify_aud": False},
        )
        expiry = payload.get("exp")
        if type(expiry) not in (int, float) or not math.isfinite(expiry):
            return None
        if not isinstance(payload["sub"], str) or not payload["sub"].isdigit():
            return None

        modern_claims = {"type", "session_id", "jti", "iss", "aud"}
        if modern_claims.intersection(payload):
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
                issuer=settings.JWT_ISSUER,
                audience=settings.JWT_AUDIENCE,
                options={"require": ["exp", "sub", "iat", "jti", "session_id", "type", "iss", "aud"]},
            )
            if (
                payload["type"] != "access"
                or not isinstance(payload["session_id"], str)
                or not payload["session_id"]
                or not isinstance(payload["jti"], str)
                or not payload["jti"]
                or type(payload["iat"]) not in (int, float)
                or not math.isfinite(payload["iat"])
                or payload["iat"] >= expiry
            ):
                return None
        elif not settings.AUTH_ACCEPT_LEGACY_TOKENS:
            return None
        elif settings.AUTH_LEGACY_ACCEPT_UNTIL is not None:
            cutoff = settings.AUTH_LEGACY_ACCEPT_UNTIL
            if cutoff.tzinfo is None:
                cutoff = cutoff.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) >= cutoff:
                return None
        return payload
    except (jwt.PyJWTError, ValueError, TypeError, OverflowError):
        return None


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

