from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


class PosItemInput(BaseModel):
    product_id: int
    quantity: int = Field(default=1, ge=1, le=10000)
    price: Decimal | None = Field(default=None, allow_inf_nan=False)


class PosCheckoutRequest(BaseModel):
    items: list[PosItemInput]
    customer_id: int | None = None
    customer_name: str | None = Field(default="Walk-in Customer", max_length=120)
    customer_phone: str | None = Field(default=None, max_length=40)
    payment_method: str = Field(default="Cash", max_length=50)
    amount_paid: Decimal = Field(default=Decimal("0.00"), ge=0, allow_inf_nan=False)
    change_due: Decimal = Field(default=Decimal("0.00"), ge=0, allow_inf_nan=False)
    discount_amount: Decimal = Field(default=Decimal("0.00"), ge=0, allow_inf_nan=False)
    tax_amount: Decimal = Field(default=Decimal("0.00"), ge=0, allow_inf_nan=False)
    notes: str | None = Field(default=None, max_length=500)


class PosReceiptItem(BaseModel):
    product_id: int | None = None
    product_name: str
    price: Decimal
    quantity: int
    subtotal: Decimal


class PosReceiptResponse(BaseModel):
    order_id: int
    order_number: str
    subtotal: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    shipping_fee: Decimal = Decimal("0.00")
    total: Decimal
    payment_method: str
    payment_status: str
    amount_paid: Decimal
    change_due: Decimal
    customer_name: str
    customer_phone: str | None = None
    cashier_name: str
    notes: str | None = None
    created_at: datetime
    items: list[PosReceiptItem]

    model_config = ConfigDict(from_attributes=True)


class PosSummaryResponse(BaseModel):
    date: str
    today_orders_count: int
    today_total_sales: Decimal
    today_cash_sales: Decimal
    today_card_sales: Decimal
    today_qr_sales: Decimal

