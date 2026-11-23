from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class WarehouseCreate(BaseModel):
    code: str = Field(min_length=2, max_length=40)
    name: str = Field(min_length=2, max_length=150)
    location: str | None = Field(default=None, max_length=255)
    address: str | None = None
    contact_name: str | None = Field(default=None, max_length=120)
    contact_phone: str | None = Field(default=None, max_length=50)
    is_default: bool = False
    is_active: bool = True


class WarehouseUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=2, max_length=40)
    name: str | None = Field(default=None, min_length=2, max_length=150)
    location: str | None = Field(default=None, max_length=255)
    address: str | None = None
    contact_name: str | None = Field(default=None, max_length=120)
    contact_phone: str | None = Field(default=None, max_length=50)
    is_default: bool | None = None
    is_active: bool | None = None


class WarehouseResponse(BaseModel):
    id: int
    code: str
    name: str
    location: str | None = None
    address: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    is_default: bool
    is_active: bool
    total_units: int = 0
    sku_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WarehouseStockResponse(BaseModel):
    id: int
    warehouse_id: int
    warehouse_code: str
    warehouse_name: str
    product_id: int
    product_name: str
    product_price: Decimal
    product_is_active: bool
    quantity: int
    reserved_quantity: int
    reorder_point: int
    updated_at: datetime


class StockAdjustmentRequest(BaseModel):
    product_id: int = Field(gt=0)
    warehouse_id: int | None = Field(default=None, gt=0)
    quantity_delta: int
    reason: str = Field(min_length=3, max_length=500)
    unit_cost: Decimal = Field(default=Decimal("0.00"), ge=0)

    @field_validator("quantity_delta")
    @classmethod
    def _non_zero_delta(cls, value: int) -> int:
        if value == 0:
            raise ValueError("quantity_delta cannot be zero")
        return value


class InventoryLedgerLineResponse(BaseModel):
    id: int
    journal_entry_id: int
    product_id: int
    product_name: str
    warehouse_id: int | None = None
    warehouse_name: str | None = None
    account_type: str
    debit_qty: int
    credit_qty: int
    unit_cost: Decimal
    balance_after: int | None = None
    created_at: datetime


class InventoryJournalEntryResponse(BaseModel):
    id: int
    entry_number: str
    entry_type: str
    reference_type: str | None = None
    reference_id: int | None = None
    reason: str | None = None
    created_by_user_id: int | None = None
    created_at: datetime
    lines: list[InventoryLedgerLineResponse] = []


class InventoryLedgerTrialBalance(BaseModel):
    total_debits: int
    total_credits: int
    balanced: bool
    total_entries: int


class InventoryLedgerListResponse(BaseModel):
    entries: list[InventoryJournalEntryResponse]
    trial_balance: InventoryLedgerTrialBalance
    total: int
    page: int
    limit: int


class PurchaseOrderItemCreate(BaseModel):
    product_id: int = Field(gt=0)
    quantity_ordered: int = Field(gt=0, le=100000)
    unit_cost: Decimal = Field(ge=0)


class PurchaseOrderCreate(BaseModel):
    supplier_id: int = Field(gt=0)
    warehouse_id: int = Field(gt=0)
    expected_at: datetime | None = None
    notes: str | None = None
    items: list[PurchaseOrderItemCreate] = Field(min_length=1)


class PurchaseOrderReceiveItem(BaseModel):
    item_id: int = Field(gt=0)
    quantity_received: int = Field(gt=0, le=100000)


class PurchaseOrderReceiveRequest(BaseModel):
    items: list[PurchaseOrderReceiveItem] | None = None
    notes: str | None = Field(default=None, max_length=500)


class PurchaseOrderItemResponse(BaseModel):
    id: int
    purchase_order_id: int
    product_id: int | None = None
    product_name: str
    quantity_ordered: int
    quantity_received: int
    unit_cost: Decimal
    line_total: Decimal


class PurchaseOrderResponse(BaseModel):
    id: int
    po_number: str
    supplier_id: int
    supplier_name: str | None = None
    warehouse_id: int
    warehouse_name: str | None = None
    status: str
    total_cost: Decimal
    expected_at: datetime | None = None
    ordered_at: datetime | None = None
    received_at: datetime | None = None
    notes: str | None = None
    created_by_user_id: int | None = None
    created_at: datetime
    updated_at: datetime
    items: list[PurchaseOrderItemResponse] = []


class WarehouseTransferItemCreate(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=100000)


class WarehouseTransferCreate(BaseModel):
    source_warehouse_id: int = Field(gt=0)
    destination_warehouse_id: int = Field(gt=0)
    notes: str | None = None
    items: list[WarehouseTransferItemCreate] = Field(min_length=1)


class WarehouseTransferItemResponse(BaseModel):
    id: int
    transfer_id: int
    product_id: int | None = None
    product_name: str
    quantity: int


class WarehouseTransferResponse(BaseModel):
    id: int
    transfer_number: str
    source_warehouse_id: int
    source_warehouse_name: str | None = None
    destination_warehouse_id: int
    destination_warehouse_name: str | None = None
    status: str
    notes: str | None = None
    created_by_user_id: int | None = None
    dispatched_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    items: list[WarehouseTransferItemResponse] = []
