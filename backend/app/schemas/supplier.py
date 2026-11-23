from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SupplierCreate(BaseModel):
    code: str | None = Field(default=None, max_length=40)
    name: str = Field(min_length=2, max_length=150)
    contact_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=50)
    address: str | None = None
    city: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    tax_id: str | None = Field(default=None, max_length=80)
    payment_terms: str = Field(default="Net 30", max_length=80)
    lead_time_days: int = Field(default=7, ge=0, le=365)
    status: str = Field(default="Active", max_length=20)
    notes: str | None = None


class SupplierUpdate(BaseModel):
    code: str | None = Field(default=None, max_length=40)
    name: str | None = Field(default=None, min_length=2, max_length=150)
    contact_name: str | None = Field(default=None, min_length=2, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    address: str | None = None
    city: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    tax_id: str | None = Field(default=None, max_length=80)
    payment_terms: str | None = Field(default=None, max_length=80)
    lead_time_days: int | None = Field(default=None, ge=0, le=365)
    status: str | None = Field(default=None, max_length=20)
    notes: str | None = None


class SupplierPurchaseOrderSummary(BaseModel):
    id: int
    po_number: str
    warehouse_id: int
    warehouse_name: str | None = None
    status: str
    total_cost: Decimal
    expected_at: datetime | None = None
    ordered_at: datetime | None = None
    received_at: datetime | None = None
    created_at: datetime


class SupplierResponse(BaseModel):
    id: int
    code: str
    name: str
    contact_name: str
    email: str
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    country: str | None = None
    tax_id: str | None = None
    payment_terms: str
    lead_time_days: int
    status: str
    notes: str | None = None
    purchase_orders_count: int = 0
    open_purchase_orders_count: int = 0
    total_procured_amount: Decimal = Decimal("0.00")
    recent_purchase_orders: list[SupplierPurchaseOrderSummary] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
