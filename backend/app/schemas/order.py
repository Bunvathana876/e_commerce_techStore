from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.shipment import OrderShipmentSummary


class OrderUserSummary(BaseModel):
    id: int
    name: str
    email: str
    phone: str | None = None
    avatar: str | None = None

    model_config = ConfigDict(from_attributes=True)


class OrderItemResponse(BaseModel):
    id: int
    order_id: int
    product_id: int | None = None
    product_name: str
    price: Decimal
    quantity: int
    subtotal: Decimal
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderItemCreate(BaseModel):
    product_id: int = Field(gt=0, description="Product ID")
    quantity: int = Field(gt=0, description="Item quantity (positive integer)")


class OrderCreateRequest(BaseModel):
    shipping_address: str | None = Field(default=None, description="Full delivery address text")
    shipping_address_id: int | None = Field(default=None, description="Optional Address ID")
    payment_method: str = Field(default="Cash on Delivery", max_length=50)
    phone: str | None = None
    full_name: str | None = None
    coupon_code: str | None = Field(default=None, description="Optional promo/coupon code")
    items: list[OrderItemCreate] | None = Field(
        default=None,
        description="Optional explicit order items for atomic checkout. If omitted, uses server cart.",
    )
    idempotency_key: str | None = Field(
        default=None,
        max_length=255,
        description="Optional client-generated idempotency key to prevent duplicate orders from retries.",
    )


class OrderResponse(BaseModel):
    id: int
    user_id: int
    user: OrderUserSummary | None = None
    status: str
    subtotal: Decimal
    discount_amount: Decimal = Decimal("0.00")
    coupon_code: str | None = None
    shipping_fee: Decimal
    total: Decimal
    payment_method: str
    payment_status: str
    shipping_address: str
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemResponse] = []
    shipment: OrderShipmentSummary | None = None

    model_config = ConfigDict(from_attributes=True)


class OrderStatusUpdateRequest(BaseModel):
    status: str | None = None
    payment_status: str | None = None
    reason: str | None = Field(
        default=None,
        max_length=500,
        description="Audit reason or receipt reference for manual cash settlement or refund.",
    )


class SellerOrderResponse(OrderResponse):
    seller_items: list[OrderItemResponse] = []
    seller_subtotal: Decimal = Decimal("0.00")
    can_update_status: bool = False


class SellerOrderPaginationResponse(BaseModel):
    items: list[SellerOrderResponse]
    total: int
    page: int
    limit: int
    total_pages: int


class SellerDashboardLowStockProduct(BaseModel):
    id: int
    name: str
    price: Decimal
    stock: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class SellerDashboardResponse(BaseModel):
    seller_id: int
    store_name: str
    store_status: str
    rating: Decimal
    total_products: int
    active_products: int
    low_stock_products_count: int
    out_of_stock_products_count: int
    total_orders: int
    pending_orders: int
    processing_orders: int
    shipped_orders: int
    delivered_orders: int
    cancelled_orders: int
    gross_revenue: Decimal
    recent_orders: list[SellerOrderResponse] = []
    low_stock_items: list[SellerDashboardLowStockProduct] = []



