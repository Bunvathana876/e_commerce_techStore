from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, computed_field


class UserBase(BaseModel):
    name: str
    email: EmailStr
    phone: str | None = None
    avatar: str | None = None


UserRole = Literal["admin", "seller", "customer", "staff", "employee"]


class UserCreate(UserBase):
    password: str
    role: UserRole = "customer"
    is_active: bool = True


class UserUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    avatar: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    password: str | None = None


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    phone: str | None = None
    avatar: str | None = None
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def full_name(self) -> str:
        return self.name

    @computed_field
    @property
    def avatar_url(self) -> str | None:
        return self.avatar

    model_config = ConfigDict(from_attributes=True)


