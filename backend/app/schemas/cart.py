from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.product import ProductResponse


class CartItemAddRequest(BaseModel):
    product_id: int
    quantity: int = Field(default=1, ge=1)


class CartItemUpdateRequest(BaseModel):
    quantity: int = Field(..., ge=1)


class CartItemResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    product: ProductResponse
    item_total: Decimal
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CartResponse(BaseModel):
    items: list[CartItemResponse]
    total_items: int
    subtotal: Decimal


class CartReconcileRequest(BaseModel):
    items: list[CartItemAddRequest] = Field(
        default_factory=list,
        description="List of cart items to safely and non-destructively reconcile in a single transaction.",
    )

