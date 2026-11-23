from decimal import Decimal
from pydantic import BaseModel


class PaymentMethodBreakdown(BaseModel):
    payment_method: str
    orders_count: int
    gross_amount: Decimal


class DailyTrendPoint(BaseModel):
    date: str
    orders_count: int
    gross_revenue: Decimal
    refunds_total: Decimal
    net_revenue: Decimal


class ExecutiveReportResponse(BaseModel):
    days: int
    gross_paid_revenue: Decimal
    settled_refunds_total: Decimal
    pending_refund_liability: Decimal
    net_revenue: Decimal
    total_orders: int
    paid_orders_count: int
    cancelled_orders_count: int
    average_order_value: Decimal
    payment_method_breakdown: list[PaymentMethodBreakdown]
    daily_trend: list[DailyTrendPoint]


class WarehouseInventorySummary(BaseModel):
    warehouse_id: int
    warehouse_code: str
    warehouse_name: str
    is_default: bool
    sku_count: int
    total_units: int
    low_stock_skus: int
    out_of_stock_skus: int
    retail_valuation: Decimal


class InventoryReportResponse(BaseModel):
    total_products: int
    total_warehouses: int
    total_on_hand_units: int
    total_retail_valuation: Decimal
    total_po_cost_committed: Decimal
    open_purchase_orders_count: int
    in_transit_transfers_count: int
    ledger_total_debits: int
    ledger_total_credits: int
    ledger_balanced: bool
    warehouses: list[WarehouseInventorySummary]
