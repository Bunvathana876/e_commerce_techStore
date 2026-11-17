from datetime import datetime
from typing import Any
from pydantic import BaseModel, EmailStr, Field, SecretStr, model_validator

from app.schemas.user import UserResponse


class RegisterRequest(BaseModel):
    name: str | None = None
    full_name: str | None = None
    email: EmailStr
    password: str = Field(repr=False)
    phone: str | None = None
    use_refresh_tokens: bool = False

    @model_validator(mode="before")
    @classmethod
    def reconcile_name(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("name") and data.get("full_name"):
                data["name"] = data["full_name"]
            elif not data.get("full_name") and data.get("name"):
                data["full_name"] = data["name"]
        return data


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(repr=False)
    use_refresh_tokens: bool = False


class TokenResponse(BaseModel):
    access_token: str = Field(repr=False)
    token: str | None = Field(default=None, repr=False)
    token_type: str = "bearer"
    expires_in: int = 900
    refresh_token: str | None = Field(default=None, repr=False)
    user: UserResponse

    @model_validator(mode="before")
    @classmethod
    def populate_token(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "access_token" in data and not data.get("token"):
                data["token"] = data["access_token"]
        return data


class RefreshTokenRequest(BaseModel):
    refresh_token: SecretStr = Field(min_length=1, max_length=512)


class RefreshTokenResponse(BaseModel):
    access_token: str = Field(repr=False)
    token: str | None = Field(default=None, repr=False)
    token_type: str = "bearer"
    expires_in: int = 900
    refresh_token: str | None = Field(default=None, repr=False)

    @model_validator(mode="before")
    @classmethod
    def populate_token(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "access_token" in data and not data.get("token"):
                data["token"] = data["access_token"]
        return data


class SessionResponse(BaseModel):
    session_id: str
    device_name: str | None = None
    ip_address: str | None = None
    created_at: datetime
    last_activity_at: datetime
    is_current: bool = False


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]
    total: int


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(repr=False)
    new_password: str = Field(repr=False)


class AuthSuccessResponse(BaseModel):
    success: bool = True
    message: str
    data: TokenResponse
