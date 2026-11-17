from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class NotificationBase(BaseModel):
    type: str = Field(default="system", description="Notification category (order, promo, delivery, stock, review, system)")
    title: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1)
    link: str | None = None


class NotificationCreate(NotificationBase):
    user_id: int | None = Field(default=None, description="Target user ID or None for a read-only shared admin notice")


class NotificationUpdate(BaseModel):
    read: bool | None = None
    title: str | None = None
    message: str | None = None


class NotificationResponse(NotificationBase):
    id: int
    user_id: int | None = None
    read: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UnreadCountResponse(BaseModel):
    unread_count: int

