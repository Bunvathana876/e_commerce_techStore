from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class RefundCreateRequest(BaseModel):
    order_id: int = Field(gt=0)
    amount: Decimal | None = Field(default=None, gt=0)
    refund_method: str | None = Field(default=None, max_length=50)
    reason: str = Field(min_length=3, max_length=500)
    notes: str | None = Field(default=None, max_length=1000)
    restock_items: bool = False
    warehouse_id: int | None = Field(default=None, gt=0)


class RefundApproveRequest(BaseModel):
    notes: str | None = Field(default=None, max_length=500)


class RefundProcessRequest(BaseModel):
    external_reference: str | None = Field(default=None, max_length=120)
    restock_items: bool | None = None
    warehouse_id: int | None = Field(default=None, gt=0)
    notes: str | None = Field(default=None, max_length=500)


class RefundRejectRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class RefundLedgerEntryResponse(BaseModel):
    id: int
    journal_ref: str
    refund_id: int
    order_id: int
    entry_type: str
    account_code: str
    account_name: str
    debit_amount: Decimal
    credit_amount: Decimal
    currency: str
    memo: str | None = None
    created_by_user_id: int | None = None
    created_at: datetime


class RefundResponse(BaseModel):
    id: int
    refund_number: str
    order_id: int
    customer_id: int | None = None
    customer_name: str | None = None
    customer_email: str | None = None
    order_total: Decimal | None = None
    order_status: str | None = None
    order_payment_status: str | None = None
    amount: Decimal
    currency: str
    refund_method: str
    status: str
    reason: str
    notes: str | None = None
    restock_items: bool
    restocked: bool
    warehouse_id: int | None = None
    external_reference: str | None = None
    requested_at: datetime
    approved_at: datetime | None = None
    processed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    ledger_entries: list[RefundLedgerEntryResponse] = []


class RefundAccountBalance(BaseModel):
    account_code: str
    account_name: str
    total_debits: Decimal
    total_credits: Decimal
    net_balance: Decimal


class RefundLedgerTrialBalance(BaseModel):
    total_debits: Decimal
    total_credits: Decimal
    balanced: bool
    accounts: list[RefundAccountBalance] = []


class RefundLedgerListResponse(BaseModel):
    entries: list[RefundLedgerEntryResponse]
    trial_balance: RefundLedgerTrialBalance
    total: int
    page: int
    limit: int
