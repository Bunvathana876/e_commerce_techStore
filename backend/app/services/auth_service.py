from datetime import timedelta
import hashlib
import secrets

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.password_policy import validate_password_strength
from app.core.security import hash_password, verify_password
from app.models.password_reset import PasswordResetToken
from app.models.user import User
from app.schemas.auth import ChangePasswordRequest, LoginRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserResponse, UserUpdate
from app.services.auth_session_service import AuthSessionService, as_utc, utc_now
from app.services.email_service import EmailService


class AuthService:
    @staticmethod
    def register(db: Session, data: RegisterRequest) -> TokenResponse:
        # Check if email is already taken
        existing_user = db.scalar(
            select(User).where(User.email == data.email.lower().strip())
        )
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email already exists.",
            )

        # Validate password strength according to NIST SP 800-63B guidelines
        is_valid, error_msg = validate_password_strength(data.password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg or "Password does not meet security policy requirements.",
            )

        # Hash password and create user
        password_hash = hash_password(data.password)
        new_user = User(
            name=data.name.strip(),
            email=data.email.lower().strip(),
            password_hash=password_hash,
            phone=data.phone.strip() if data.phone else None,
            role="customer",
            is_active=True,
        )

        db.add(new_user)
        db.flush()
        issued = AuthSessionService.issue(db, new_user, data.use_refresh_tokens)
        db.commit()

        return TokenResponse(
            access_token=issued.access_token,
            refresh_token=issued.refresh_token,
            expires_in=issued.expires_in,
            token_type="bearer",
            user=UserResponse.model_validate(new_user),
        )

    @staticmethod
    def login(db: Session, data: LoginRequest) -> TokenResponse:
        user = db.scalar(
            select(User).where(User.email == data.email.lower().strip())
        )

        if not user or not verify_password(data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account is disabled. Please contact support.",
            )

        locked_user = db.scalar(
            select(User)
            .where(User.id == user.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if not locked_user or not locked_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account is disabled. Please contact support.",
            )

        issued = AuthSessionService.issue(db, locked_user, data.use_refresh_tokens)
        db.commit()

        return TokenResponse(
            access_token=issued.access_token,
            refresh_token=issued.refresh_token,
            expires_in=issued.expires_in,
            token_type="bearer",
            user=UserResponse.model_validate(locked_user),
        )

    @staticmethod
    def update_profile(db: Session, user: User, data: UserUpdate) -> User:
        if data.name is not None:
            user.name = data.name.strip()
        if data.phone is not None:
            user.phone = data.phone.strip() if data.phone.strip() else None
        if data.avatar is not None:
            user.avatar = data.avatar.strip() if data.avatar.strip() else None

        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def change_password(db: Session, user: User, data: ChangePasswordRequest) -> None:
        user = AuthSessionService.lock_user(db, user.id)
        if not verify_password(data.current_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password does not match.",
            )

        is_valid, error_msg = validate_password_strength(data.new_password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg or "New password does not meet security policy requirements.",
            )

        user.password_hash = hash_password(data.new_password)
        AuthSessionService.revoke_all(db, user, "password_changed")
        db.commit()

    @staticmethod
    def _hash_reset_token(raw_token: str) -> str:
        return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()

    @staticmethod
    def request_password_reset(
        db: Session,
        email: str,
        *,
        client: str = "storefront",
        requested_ip: str | None = None,
    ) -> int:
        # Enforce email provider configuration before processing so unconfigured
        # production deployments fail closed without revealing account existence.
        EmailService.ensure_configured()

        normalized_email = email.lower().strip()
        user = db.scalar(select(User).where(User.email == normalized_email))
        ttl_minutes = settings.PASSWORD_RESET_EXPIRE_MINUTES

        if user and user.is_active:
            now = utc_now()
            raw_token = secrets.token_urlsafe(32)
            token_hash = AuthService._hash_reset_token(raw_token)

            # Invalidate any unconsumed reset tokens for this user.
            db.execute(
                update(PasswordResetToken)
                .where(
                    PasswordResetToken.user_id == user.id,
                    PasswordResetToken.is_revoked.is_(False),
                    PasswordResetToken.used_at.is_(None),
                )
                .values(is_revoked=True)
            )
            db.add(
                PasswordResetToken(
                    user_id=user.id,
                    token_hash=token_hash,
                    expires_at=now + timedelta(minutes=ttl_minutes),
                    is_revoked=False,
                    requested_ip=requested_ip[:64] if requested_ip else None,
                )
            )
            db.commit()

            EmailService.send_password_reset_email(
                to_email=user.email,
                user_name=user.name,
                raw_token=raw_token,
                client=client,
                expire_minutes=ttl_minutes,
            )

        return ttl_minutes

    @staticmethod
    def validate_password_reset_token(db: Session, raw_token: str) -> bool:
        cleaned = (raw_token or "").strip()
        if not cleaned:
            return False
        token_hash = AuthService._hash_reset_token(cleaned)
        token_row = db.scalar(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
        )
        if token_row is None or token_row.is_revoked or token_row.used_at is not None:
            return False
        if as_utc(token_row.expires_at) <= utc_now():
            return False
        user = db.get(User, token_row.user_id)
        return user is not None and user.is_active

    @staticmethod
    def reset_password(db: Session, raw_token: str, new_password: str) -> None:
        is_valid, error_msg = validate_password_strength(new_password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg or "Password does not meet security policy requirements.",
            )

        token_hash = AuthService._hash_reset_token(raw_token)
        token_row = db.scalar(
            select(PasswordResetToken)
            .where(PasswordResetToken.token_hash == token_hash)
            .with_for_update()
        )
        now = utc_now()
        if (
            token_row is None
            or token_row.is_revoked
            or token_row.used_at is not None
            or as_utc(token_row.expires_at) <= now
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password reset link is invalid or has expired.",
            )

        user = AuthSessionService.lock_user(db, token_row.user_id)
        user.password_hash = hash_password(new_password)
        token_row.used_at = now
        token_row.is_revoked = True

        db.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.id != token_row.id,
                PasswordResetToken.is_revoked.is_(False),
            )
            .values(is_revoked=True)
        )
        AuthSessionService.revoke_all(db, user, "password_reset")
        db.commit()


