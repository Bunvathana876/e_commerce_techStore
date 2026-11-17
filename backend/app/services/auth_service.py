from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.password_policy import validate_password_strength
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.auth import ChangePasswordRequest, LoginRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserResponse, UserUpdate
from app.services.auth_session_service import AuthSessionService


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
            select(User).where(User.email == data.email.lower().strip()).with_for_update()
            .execution_options(populate_existing=True)
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

        issued = AuthSessionService.issue(db, user, data.use_refresh_tokens)
        db.commit()

        return TokenResponse(
            access_token=issued.access_token,
            refresh_token=issued.refresh_token,
            expires_in=issued.expires_in,
            token_type="bearer",
            user=UserResponse.model_validate(user),
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


