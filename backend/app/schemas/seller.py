from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SellerBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=150, description="Store name")
    owner_name: str = Field(..., min_length=2, max_length=100, description="Owner full name")
    email: str = Field(..., description="Store or owner contact email")
    phone: str | None = Field(None, max_length=50)
    address: str | None = Field(None, max_length=255)
    description: str | None = None
    logo: str | None = None
    status: str = Field("Active", description="Store status: Active, Pending, Suspended")


class SellerCreate(SellerBase):
    password: str | None = Field(None, min_length=6, description="Optional account password for seller login")


class SellerUpdate(BaseModel):
    name: str | None = None
    owner_name: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    description: str | None = None
    logo: str | None = None
    status: str | None = None
    rating: Decimal | float | None = None
    products_count: int | None = None
    orders_count: int | None = None
    total_revenue: Decimal | float | None = None


class SellerProfileUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=150, description="Store name")
    description: str | None = Field(None, max_length=2000, description="Store description")
    phone: str | None = Field(None, max_length=50, description="Contact phone")
    address: str | None = Field(None, max_length=255, description="Physical address")
    logo: str | None = Field(None, max_length=500, description="Store logo URL")

    # Privileged fields that sellers cannot modify:
    status: str | None = Field(None, description="Privileged: cannot be changed by seller")
    rating: Decimal | float | None = Field(None, description="Privileged: cannot be changed by seller")
    products_count: int | None = Field(None, description="Privileged: cannot be changed by seller")
    orders_count: int | None = Field(None, description="Privileged: cannot be changed by seller")
    total_revenue: Decimal | float | None = Field(None, description="Privileged: cannot be changed by seller")
    user_id: int | None = Field(None, description="Privileged: cannot be changed by seller")
    email: str | None = Field(None, description="Privileged: cannot be changed by seller")


class SellerResponse(SellerBase):
    id: int
    user_id: int | None = None
    rating: float
    products_count: int
    orders_count: int
    total_revenue: float
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
