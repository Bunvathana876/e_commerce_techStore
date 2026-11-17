from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


class ReviewCreateRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="Star rating from 1 to 5")
    comment: str = Field(..., min_length=1, max_length=2000, description="Customer review text")
    order_id: int | None = Field(default=None, description="Optional associated order ID")


class ReviewStatusUpdateRequest(BaseModel):
    status: str = Field(..., description="Review status: pending, approved, rejected")


class ReviewReplyRequest(BaseModel):
    admin_reply: str = Field(..., min_length=1, max_length=2000, description="Admin/Seller response to review")


class ReviewUserSummary(BaseModel):
    id: int
    name: str
    email: str
    avatar: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ReviewProductSummary(BaseModel):
    id: int
    name: str
    image_url: str | None = None
    price: Decimal

    model_config = ConfigDict(from_attributes=True)


class ReviewResponse(BaseModel):
    id: int
    product_id: int
    user_id: int
    order_id: int | None = None
    rating: int
    comment: str
    status: str
    admin_reply: str | None = None
    admin_replied_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    user: ReviewUserSummary | None = None
    product: ReviewProductSummary | None = None

    model_config = ConfigDict(from_attributes=True)
