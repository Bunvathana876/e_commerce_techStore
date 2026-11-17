from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import logging
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth_errors import AuthSessionError
from app.core.config import settings
from app.core.security import create_access_token, generate_refresh_token, hash_refresh_token
from app.models.session import RefreshToken, UserSession
from app.models.user import User

logger = logging.getLogger("uvicorn.error")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    # SQLite drops tzinfo; PostgreSQL preserves it.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


@dataclass(frozen=True)
class IssuedTokens:
    access_token: str = field(repr=False)
    refresh_token: str | None = field(repr=False)
    expires_in: int


class AuthSessionService:
    @staticmethod
    def lock_user(db: Session, user_id: int) -> User:
        user = db.scalar(select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True))
        if user is None or not user.is_active:
            raise AuthSessionError("Account is unavailable.")
        return user

    @staticmethod
    def legacy_session_id(token: str) -> str:
        # Deterministic across workers, without persisting the bearer credential.
        return str(uuid5(NAMESPACE_URL, "blue-panda:legacy:" + hash_refresh_token(token)))

    @staticmethod
    def issue(db: Session, user: User, use_refresh_tokens: bool) -> IssuedTokens:
        if use_refresh_tokens and not settings.AUTH_ISSUE_SESSION_TOKENS:
            raise AuthSessionError("Refresh sessions are not enabled yet.", "REFRESH_NOT_ENABLED")
        minutes = (
            settings.SESSION_ACCESS_TOKEN_EXPIRE_MINUTES
            if use_refresh_tokens else settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
        now = utc_now()
        access_lifetime = timedelta(minutes=minutes)
        if not settings.AUTH_ISSUE_SESSION_TOKENS:
            # Validation-only rollout: old API workers must still accept these JWTs.
            # Nonce avoids issuing the same legacy JWT twice within one second.
            token = create_access_token({"sub": str(user.id), "legacy_nonce": str(uuid4())}, access_lifetime)
            # Pre-register this freshly password-authenticated credential even if
            # unregistered legacy credentials were blocked after a password change.
            session_id = AuthSessionService.legacy_session_id(token)
            db.add(UserSession(
                session_id=session_id, user_id=user.id, token_family=str(uuid4()),
                expires_at=now + access_lifetime,
            ))
            db.flush()
            return IssuedTokens(token, None, minutes * 60)

        session_id = str(uuid4())
        expires_at = now + (
            timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS) if use_refresh_tokens else access_lifetime
        )
        db.add(UserSession(
            session_id=session_id, user_id=user.id, token_family=str(uuid4()), expires_at=expires_at,
        ))
        db.flush()
        raw_refresh = None
        if use_refresh_tokens:
            raw_refresh = generate_refresh_token()
            db.add(RefreshToken(
                session_id=session_id, token_hash=hash_refresh_token(raw_refresh), expires_at=expires_at,
            ))
        access_lifetime = min(access_lifetime, expires_at - now)
        token = create_access_token({"sub": str(user.id)}, access_lifetime, session_id=session_id)
        return IssuedTokens(token, raw_refresh, int(access_lifetime.total_seconds()))

    @staticmethod
    def validate_access(db: Session, user: User, token: str, payload: dict[str, Any]) -> UserSession:
        session_id = payload.get("session_id")
        if session_id is not None:
            session = db.scalar(select(UserSession).where(
                UserSession.session_id == session_id, UserSession.user_id == user.id,
            ))
        else:
            session_id = AuthSessionService.legacy_session_id(token)
            session = db.scalar(select(UserSession).where(
                UserSession.session_id == session_id, UserSession.user_id == user.id,
            ))
            if session is None:
                user = AuthSessionService.lock_user(db, user.id)
                if user.legacy_tokens_revoked_at is not None:
                    raise AuthSessionError("Please sign in again.")
                # Recheck after the user lock: another worker may have adopted it.
                session = db.scalar(select(UserSession).where(UserSession.session_id == session_id))
                if session is None:
                    session = UserSession(
                        session_id=session_id, user_id=user.id, token_family=str(uuid4()),
                        expires_at=datetime.fromtimestamp(payload["exp"], timezone.utc),
                    )
                    try:
                        with db.begin_nested():
                            db.add(session)
                            db.flush()
                    except IntegrityError:
                        session = db.scalar(select(UserSession).where(UserSession.session_id == session_id))
                # Adoption is persisted before the endpoint runs, even for reads.
                db.commit()
        if session is None or session.user_id != user.id or session.is_revoked or as_utc(session.expires_at) <= utc_now():
            raise AuthSessionError("Session is expired or revoked.")
        return session

    @staticmethod
    def revoke_all(db: Session, user: User, reason: str) -> None:
        """Caller holds the user lock; credential change and revocation commit together."""
        user.legacy_tokens_revoked_at = utc_now()
        db.execute(update(UserSession).where(UserSession.user_id == user.id).values(
            is_revoked=True, revoked_reason=reason,
        ))
        session_ids = select(UserSession.session_id).where(UserSession.user_id == user.id)
        db.execute(update(RefreshToken).where(RefreshToken.session_id.in_(session_ids)).values(is_revoked=True))

    @staticmethod
    def logout(db: Session, user_id: int, session_id: str) -> None:
        AuthSessionService.lock_user(db, user_id)
        db.execute(update(UserSession).where(
            UserSession.session_id == session_id, UserSession.user_id == user_id,
        ).values(is_revoked=True, revoked_reason="logout"))
        owned_sessions = select(UserSession.session_id).where(
            UserSession.session_id == session_id, UserSession.user_id == user_id,
        )
        db.execute(update(RefreshToken).where(RefreshToken.session_id.in_(owned_sessions)).values(is_revoked=True))
        db.commit()

    @staticmethod
    def refresh(db: Session, raw_token: str) -> IssuedTokens:
        token_hash = hash_refresh_token(raw_token)
        owner = db.execute(select(UserSession.user_id, UserSession.session_id).join(
            RefreshToken, RefreshToken.session_id == UserSession.session_id,
        ).where(RefreshToken.token_hash == token_hash)).first()
        if owner is None:
            raise AuthSessionError("Invalid refresh token.", "INVALID_REFRESH_TOKEN")

        # All session mutations take locks in user -> session -> token order.
        AuthSessionService.lock_user(db, owner.user_id)
        session = db.scalar(select(UserSession).where(
            UserSession.session_id == owner.session_id,
        ).with_for_update().execution_options(populate_existing=True))
        token = db.scalar(select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
        ).with_for_update().execution_options(populate_existing=True))
        if session is None or token is None:
            raise AuthSessionError("Invalid refresh token.", "INVALID_REFRESH_TOKEN")

        now = utc_now()
        if token.used_at is not None:
            # Persist the breach response BEFORE raising; request rollback must not undo it.
            AuthSessionService._revoke_family(db, session.token_family)
            db.commit()
            logger.warning("Authentication refresh replay detected; token family revoked.")
            raise AuthSessionError("Refresh token reuse detected. Please sign in again.", "TOKEN_REUSE_DETECTED")
        if session.is_revoked or token.is_revoked or as_utc(session.expires_at) <= now or as_utc(token.expires_at) <= now:
            raise AuthSessionError("Refresh session is expired or revoked.", "INVALID_REFRESH_TOKEN")

        consumed = db.execute(update(RefreshToken).where(
            RefreshToken.id == token.id, RefreshToken.used_at.is_(None), RefreshToken.is_revoked.is_(False),
        ).values(used_at=now))
        if consumed.rowcount != 1:
            AuthSessionService._revoke_family(db, session.token_family)
            db.commit()
            raise AuthSessionError("Refresh token reuse detected. Please sign in again.", "TOKEN_REUSE_DETECTED")

        raw_refresh = generate_refresh_token()
        db.add(RefreshToken(
            session_id=session.session_id, token_hash=hash_refresh_token(raw_refresh),
            parent_token_hash=token_hash, expires_at=session.expires_at,
        ))
        session.last_activity_at = now
        lifetime = min(timedelta(minutes=settings.SESSION_ACCESS_TOKEN_EXPIRE_MINUTES), as_utc(session.expires_at) - now)
        access_token = create_access_token({"sub": str(owner.user_id)}, lifetime, session_id=session.session_id)
        result = IssuedTokens(access_token, raw_refresh, int(lifetime.total_seconds()))
        db.commit()
        return result

    @staticmethod
    def _revoke_family(db: Session, family: str) -> None:
        session_ids = select(UserSession.session_id).where(UserSession.token_family == family)
        db.execute(update(RefreshToken).where(RefreshToken.session_id.in_(session_ids)).values(is_revoked=True))
        db.execute(update(UserSession).where(UserSession.token_family == family).values(
            is_revoked=True, revoked_reason="token_reuse",
        ))
