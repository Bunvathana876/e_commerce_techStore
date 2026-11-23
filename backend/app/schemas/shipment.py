from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class OrderShipmentSummary(BaseModel):
    id: int
    order_id: int
    carrier: str
    tracking_number: str | None = None
    tracking_url: str | None = None
    status: str
    estimated_delivery_at: datetime | None = None
    shipped_at: datetime | None = None
    delivered_at: datetime | None = None
    notes: str | None = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderTrackingEventResponse(BaseModel):
    id: int | None = None
    status: str
    title: str
    description: str | None = None
    location: str | None = None
    occurred_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderTrackingResponse(BaseModel):
    order_id: int
    order_status: str
    payment_status: str
    shipping_address: str
    has_shipment_record: bool = False
    shipment: OrderShipmentSummary | None = None
    events: list[OrderTrackingEventResponse] = []


class OrderTrackingUpdateRequest(BaseModel):
    carrier: str = Field(..., min_length=2, max_length=100)
    tracking_number: str | None = Field(default=None, max_length=120)
    tracking_url: str | None = Field(default=None, max_length=500)
    status: str = Field(default="in_transit", max_length=40)
    estimated_delivery_at: datetime | None = None
    event_title: str | None = Field(default=None, max_length=160)
    event_description: str | None = Field(default=None, max_length=1000)
    location: str | None = Field(default=None, max_length=160)
    notes: str | None = Field(default=None, max_length=1000)
