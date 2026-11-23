from collections import defaultdict
import csv
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import io

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.inventory import (
    InventoryJournalEntry,
    InventoryLedgerLine,
    PurchaseOrder,
    Warehouse,
    WarehouseStock,
    WarehouseTransfer,
)
from app.models.order import Order
from app.models.product import Product
from app.models.refund import Refund, RefundLedgerEntry
from app.schemas.report import (
    DailyTrendPoint,
    ExecutiveReportResponse,
    InventoryReportResponse,
    PaymentMethodBreakdown,
    WarehouseInventorySummary,
)
from app.services.inventory_service import InventoryService


class ReportingService:
    """Authoritative executive financial and multi-warehouse inventory reporting service."""

    @staticmethod
    def get_executive_report(db: Session, *, days: int = 30) -> ExecutiveReportResponse:
        days = max(1, min(3650, days))
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_naive = cutoff.replace(tzinfo=None)

        orders = list(
            db.scalars(
                select(Order).where(Order.created_at >= cutoff_naive).order_by(Order.created_at.asc())
            ).all()
        )

        # Include orders refunded even if created within window or settled within window
        refunds = list(
            db.scalars(
                select(Refund).where(Refund.created_at >= cutoff).order_by(Refund.created_at.asc())
            ).all()
        )

        gross_paid = Decimal("0.00")
        paid_orders_count = 0
        cancelled_orders_count = 0
        method_buckets: dict[str, dict] = {}
        daily_buckets: dict[str, dict] = defaultdict(
            lambda: {
                "orders_count": 0,
                "gross_revenue": Decimal("0.00"),
                "refunds_total": Decimal("0.00"),
            }
        )

        for o in orders:
            day_key = o.created_at.date().isoformat()
            daily_buckets[day_key]["orders_count"] += 1
            if (o.status or "").lower() == "cancelled":
                cancelled_orders_count += 1
            if (o.payment_status or "").lower() in {"paid", "refunded"} and (o.status or "").lower() != "cancelled":
                amt = Decimal(o.total)
                gross_paid += amt
                paid_orders_count += 1
                daily_buckets[day_key]["gross_revenue"] += amt

                method = o.payment_method or "Cash on Delivery"
                bucket = method_buckets.setdefault(
                    method, {"orders_count": 0, "gross_amount": Decimal("0.00")}
                )
                bucket["orders_count"] += 1
                bucket["gross_amount"] += amt

        settled_refunds = Decimal("0.00")
        pending_refund_liability = Decimal("0.00")
        for r in refunds:
            amt = Decimal(r.amount)
            if r.status == "processed":
                settled_refunds += amt
                r_day = (r.processed_at or r.created_at).date().isoformat()
                daily_buckets[r_day]["refunds_total"] += amt
            elif r.status == "approved":
                pending_refund_liability += amt

        net_revenue = (gross_paid - settled_refunds).quantize(Decimal("0.01"))
        avg_order_value = (
            (gross_paid / paid_orders_count).quantize(Decimal("0.01"))
            if paid_orders_count > 0
            else Decimal("0.00")
        )

        return ExecutiveReportResponse(
            days=days,
            gross_paid_revenue=gross_paid.quantize(Decimal("0.01")),
            settled_refunds_total=settled_refunds.quantize(Decimal("0.01")),
            pending_refund_liability=pending_refund_liability.quantize(Decimal("0.01")),
            net_revenue=net_revenue,
            total_orders=len(orders),
            paid_orders_count=paid_orders_count,
            cancelled_orders_count=cancelled_orders_count,
            average_order_value=avg_order_value,
            payment_method_breakdown=[
                PaymentMethodBreakdown(
                    payment_method=m,
                    orders_count=v["orders_count"],
                    gross_amount=v["gross_amount"].quantize(Decimal("0.01")),
                )
                for m, v in sorted(method_buckets.items())
            ],
            daily_trend=[
                DailyTrendPoint(
                    date=day,
                    orders_count=vals["orders_count"],
                    gross_revenue=vals["gross_revenue"].quantize(Decimal("0.01")),
                    refunds_total=vals["refunds_total"].quantize(Decimal("0.01")),
                    net_revenue=(vals["gross_revenue"] - vals["refunds_total"]).quantize(Decimal("0.01")),
                )
                for day, vals in sorted(daily_buckets.items())
            ],
        )

    @staticmethod
    def get_inventory_report(db: Session) -> InventoryReportResponse:
        # Ensure baseline warehouse stocks are synced for all products
        stocks = InventoryService.list_warehouse_stocks(db)
        warehouses = list(
            db.scalars(select(Warehouse).order_by(Warehouse.is_default.desc(), Warehouse.id.asc())).all()
        )
        total_products = db.scalar(select(func.count(Product.id))) or 0

        by_wh: dict[int, list] = defaultdict(list)
        for s in stocks:
            by_wh[s.warehouse_id].append(s)

        wh_summaries: list[WarehouseInventorySummary] = []
        total_units = 0
        total_valuation = Decimal("0.00")
        for wh in warehouses:
            wh_rows = by_wh.get(wh.id, [])
            units = sum(r.quantity for r in wh_rows)
            val = sum((Decimal(r.product_price) * r.quantity for r in wh_rows), Decimal("0.00"))
            low_skus = sum(1 for r in wh_rows if 0 < r.quantity <= r.reorder_point)
            oos_skus = sum(1 for r in wh_rows if r.quantity == 0)
            total_units += units
            total_valuation += val
            wh_summaries.append(
                WarehouseInventorySummary(
                    warehouse_id=wh.id,
                    warehouse_code=wh.code,
                    warehouse_name=wh.name,
                    is_default=wh.is_default,
                    sku_count=len(wh_rows),
                    total_units=units,
                    low_stock_skus=low_skus,
                    out_of_stock_skus=oos_skus,
                    retail_valuation=val.quantize(Decimal("0.01")),
                )
            )

        open_pos = list(
            db.scalars(
                select(PurchaseOrder).where(
                    PurchaseOrder.status.in_(["draft", "ordered", "partially_received"])
                )
            ).all()
        )
        total_po_committed = sum((Decimal(po.total_cost) for po in open_pos), Decimal("0.00"))
        in_transit_count = (
            db.scalar(
                select(func.count(WarehouseTransfer.id)).where(
                    WarehouseTransfer.status == "in_transit"
                )
            )
            or 0
        )
        tb = db.execute(
            select(
                func.coalesce(func.sum(InventoryLedgerLine.debit_qty), 0),
                func.coalesce(func.sum(InventoryLedgerLine.credit_qty), 0),
            )
        ).one()
        total_debits = int(tb[0] or 0)
        total_credits = int(tb[1] or 0)

        return InventoryReportResponse(
            total_products=int(total_products),
            total_warehouses=len(warehouses),
            total_on_hand_units=total_units,
            total_retail_valuation=total_valuation.quantize(Decimal("0.01")),
            total_po_cost_committed=total_po_committed.quantize(Decimal("0.01")),
            open_purchase_orders_count=len(open_pos),
            in_transit_transfers_count=int(in_transit_count),
            ledger_total_debits=total_debits,
            ledger_total_credits=total_credits,
            ledger_balanced=(total_debits == total_credits),
            warehouses=wh_summaries,
        )

    @staticmethod
    def export_ledger_csv(db: Session, ledger_type: str) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        normalized = (ledger_type or "").strip().lower()

        if normalized == "inventory":
            writer.writerow([
                "entry_number",
                "entry_type",
                "reference_type",
                "reference_id",
                "product_id",
                "product_name",
                "warehouse_id",
                "account_type",
                "debit_qty",
                "credit_qty",
                "unit_cost",
                "balance_after",
                "reason",
                "created_at",
            ])
            rows = db.execute(
                select(InventoryLedgerLine, InventoryJournalEntry)
                .join(
                    InventoryJournalEntry,
                    InventoryJournalEntry.id == InventoryLedgerLine.journal_entry_id,
                )
                .order_by(InventoryLedgerLine.id.asc())
            ).all()
            for line, entry in rows:
                writer.writerow([
                    entry.entry_number,
                    entry.entry_type,
                    entry.reference_type or "",
                    entry.reference_id or "",
                    line.product_id,
                    line.product_name,
                    line.warehouse_id or "",
                    line.account_type,
                    line.debit_qty,
                    line.credit_qty,
                    f"{Decimal(line.unit_cost):.2f}",
                    line.balance_after if line.balance_after is not None else "",
                    entry.reason or "",
                    line.created_at.isoformat(),
                ])
        elif normalized == "refunds":
            writer.writerow([
                "journal_ref",
                "refund_id",
                "order_id",
                "entry_type",
                "account_code",
                "account_name",
                "debit_amount",
                "credit_amount",
                "currency",
                "memo",
                "created_at",
            ])
            rows = list(
                db.scalars(select(RefundLedgerEntry).order_by(RefundLedgerEntry.id.asc())).all()
            )
            for le in rows:
                writer.writerow([
                    le.journal_ref,
                    le.refund_id,
                    le.order_id,
                    le.entry_type,
                    le.account_code,
                    le.account_name,
                    f"{Decimal(le.debit_amount):.2f}",
                    f"{Decimal(le.credit_amount):.2f}",
                    le.currency,
                    le.memo or "",
                    le.created_at.isoformat(),
                ])
        else:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=400,
                detail="Invalid ledger parameter. Allowed values: 'inventory', 'refunds'.",
            )

        return output.getvalue()
