from fastapi import APIRouter, Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.auth_errors import AuthSessionError, SensitiveAuthRoute
from app.core.dependencies import get_current_user, security_scheme
from app.core.security import decode_access_token
from app.core.rate_limit import RateLimiter, get_rate_limiter_manager
from app.db.database import get_db
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RefreshTokenRequest,
    RefreshTokenResponse,
    RegisterRequest,
    ResetPasswordRequest,
    ResetPasswordValidateRequest,
)
from app.schemas.user import UserResponse, UserUpdate
from app.services.auth_service import AuthService
from app.services.auth_session_service import AuthSessionService

router = APIRouter(prefix="/auth", tags=["Authentication"], route_class=SensitiveAuthRoute)


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RateLimiter(times=settings.RATE_LIMIT_AUTH_REGISTER, seconds=60, scope="auth:register"))],
)
def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
):
    token_response = AuthService.register(db, request)
    return {
        "success": True,
        "message": "User registered successfully.",
        "data": token_response.model_dump(),
    }


@router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RateLimiter(times=settings.RATE_LIMIT_AUTH_LOGIN, seconds=60, scope="auth:login"))],
)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
):
    token_response = AuthService.login(db, request)
    return {
        "success": True,
        "message": "Login successful.",
        "data": token_response.model_dump(),
    }


@router.get("/me", status_code=status.HTTP_200_OK)
def get_me(
    current_user: User = Depends(get_current_user),
):
    return {
        "success": True,
        "message": "Current user profile retrieved successfully.",
        "data": UserResponse.model_validate(current_user).model_dump(),
    }


@router.put(
    "/me",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RateLimiter(times=settings.RATE_LIMIT_SENSITIVE_MUTATIONS, seconds=60, scope="auth:update_me", user_scoped=True))],
)
def update_me(
    request: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    updated_user = AuthService.update_profile(db, current_user, request)
    return {
        "success": True,
        "message": "Profile updated successfully.",
        "data": UserResponse.model_validate(updated_user).model_dump(),
    }


@router.put(
    "/change-password",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RateLimiter(times=settings.RATE_LIMIT_SENSITIVE_MUTATIONS, seconds=60, scope="auth:change_password", user_scoped=True))],
)
def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    AuthService.change_password(db, current_user, request)
    return {
        "success": True,
        "message": "Password changed successfully.",
    }


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_db),
):
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise AuthSessionError("Invalid or expired token.")
    session_id = payload.get("session_id") or AuthSessionService.legacy_session_id(credentials.credentials)
    AuthSessionService.logout(db, current_user.id, session_id)
    return {
        "success": True,
        "message": "Logged out successfully.",
    }


@router.post(
    "/refresh",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RateLimiter(times=settings.RATE_LIMIT_AUTH_REFRESH, seconds=60, scope="auth:refresh"))],
)
def refresh_session(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    issued = AuthSessionService.refresh(db, request.refresh_token.get_secret_value())
    return {
        "success": True,
        "message": "Session refreshed successfully.",
        "data": RefreshTokenResponse(
            access_token=issued.access_token,
            refresh_token=issued.refresh_token,
            expires_in=issued.expires_in,
        ).model_dump(),
    }


@router.post(
    "/logout-all",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RateLimiter(times=settings.RATE_LIMIT_SENSITIVE_MUTATIONS, seconds=60, scope="auth:logout_all", user_scoped=True))],
)
def logout_all(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user = AuthSessionService.lock_user(db, current_user.id)
    AuthSessionService.revoke_all(db, user, "logout_all")
    db.commit()
    return {"success": True, "message": "All sessions logged out successfully."}


@router.post(
    "/forgot-password",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RateLimiter(times=settings.RATE_LIMIT_AUTH_PASSWORD_RESET, seconds=60, scope="auth:forgot_password"))],
)
def forgot_password(
    payload: ForgotPasswordRequest,
    http_request: Request,
    db: Session = Depends(get_db),
):
    client_ip = get_rate_limiter_manager().ip_resolver.resolve_client_ip(http_request)
    ttl_minutes = AuthService.request_password_reset(
        db,
        payload.email,
        client=payload.client,
        requested_ip=client_ip,
    )
    return {
        "success": True,
        "message": "If an active account exists for that email, password reset instructions have been sent.",
        "data": {"expires_in_minutes": ttl_minutes},
    }


@router.post(
    "/reset-password/validate",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RateLimiter(times=settings.RATE_LIMIT_AUTH_PASSWORD_RESET, seconds=60, scope="auth:reset_validate"))],
)
def validate_reset_token(
    payload: ResetPasswordValidateRequest,
    db: Session = Depends(get_db),
):
    is_valid = AuthService.validate_password_reset_token(db, payload.token)
    return {
        "success": True,
        "message": "Reset token checked.",
        "data": {"valid": is_valid},
    }


@router.post(
    "/reset-password",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RateLimiter(times=settings.RATE_LIMIT_AUTH_PASSWORD_RESET, seconds=60, scope="auth:reset_password"))],
)
def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    AuthService.reset_password(db, payload.token, payload.new_password)
    return {
        "success": True,
        "message": "Password has been reset successfully. Please sign in with your new password.",
    }


