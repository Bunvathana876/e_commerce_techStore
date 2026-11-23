from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


class CouponValidateRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=50, description="Promo/Coupon code")
    subtotal: Decimal = Field(..., ge=0, description="Current cart subtotal")


class CouponValidateResponse(BaseModel):
    valid: bool
    code: str
    discount_type: str
    discount_value: Decimal
    discount_amount: Decimal
    new_subtotal: Decimal
    message: str


class CouponResponse(BaseModel):
    id: int
    code: str
    description: str | None = None
    discount_type: str
    discount_value: Decimal
    min_order_amount: Decimal
    max_discount_amount: Decimal | None = None
    is_active: bool
    expires_at: datetime | None = None
    usage_limit: int | None = None
    per_user_limit: int | None = None
    used_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class CouponCreateRequest(BaseModel):
    code: str = Field(..., min_length=2, max_length=50, description="Unique promo code")
    description: str | None = Field(default=None, max_length=255)
    discount_type: str = Field(default="percent", pattern="^(percent|fixed)$")
    discount_value: Decimal = Field(..., gt=0, description="Discount amount or percentage")
    min_order_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    max_discount_amount: Decimal | None = Field(default=None, ge=0)
    is_active: bool = True
    expires_at: datetime | None = None
    usage_limit: int | None = Field(default=None, ge=1)
    per_user_limit: int | None = Field(default=None, ge=1)


class CouponUpdateRequest(BaseModel):
    description: str | None = Field(default=None, max_length=255)
    discount_type: str | None = Field(default=None, pattern="^(percent|fixed)$")
    discount_value: Decimal | None = Field(default=None, gt=0)
    min_order_amount: Decimal | None = Field(default=None, ge=0)
    max_discount_amount: Decimal | None = Field(default=None, ge=0)
    is_active: bool | None = None
    expires_at: datetime | None = None
    usage_limit: int | None = Field(default=None, ge=1)
    per_user_limit: int | None = Field(default=None, ge=1)
