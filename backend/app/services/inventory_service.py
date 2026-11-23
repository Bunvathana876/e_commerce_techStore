from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from decimal import Decimal
import math
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.inventory import (
    InventoryJournalEntry,
    InventoryLedgerLine,
    PurchaseOrder,
    PurchaseOrderItem,
    Warehouse,
    WarehouseStock,
    WarehouseTransfer,
    WarehouseTransferItem,
)
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.user import User
from app.schemas.inventory import (
    InventoryJournalEntryResponse,
    InventoryLedgerLineResponse,
    InventoryLedgerListResponse,
    InventoryLedgerTrialBalance,
    PurchaseOrderCreate,
    PurchaseOrderItemResponse,
    PurchaseOrderReceiveRequest,
    PurchaseOrderResponse,
    StockAdjustmentRequest,
    WarehouseCreate,
    WarehouseResponse,
    WarehouseStockResponse,
    WarehouseTransferCreate,
    WarehouseTransferItemResponse,
    WarehouseTransferResponse,
    WarehouseUpdate,
)

DEFAULT_WAREHOUSE_CODE = "WH-MAIN"
DEFAULT_WAREHOUSE_NAME = "Main Fulfillment Warehouse"


class InventoryService:
    """Shared atomic inventory, multi-warehouse, PO, transfer, and double-entry ledger operations."""

    @staticmethod
    def aggregate_quantities(items: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
        totals: dict[int, int] = {}
        for product_id, quantity in items:
            if quantity < 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Item quantity must be at least 1.",
                )
            totals[product_id] = totals.get(product_id, 0) + quantity
        return sorted(totals.items(), key=lambda pair: pair[0])

    @staticmethod
    def _new_ref(prefix: str) -> str:
        return f"{prefix}-{uuid4().hex[:12].upper()}"

    @staticmethod
    def ensure_default_warehouse(db: Session) -> Warehouse:
        warehouse = db.scalar(
            select(Warehouse)
            .where(Warehouse.is_default.is_(True), Warehouse.is_active.is_(True))
            .order_by(Warehouse.id.asc())
        )
        if warehouse is not None:
            return warehouse

        warehouse = db.scalar(
            select(Warehouse).where(Warehouse.code == DEFAULT_WAREHOUSE_CODE)
        )
        if warehouse is not None:
            warehouse.is_default = True
            warehouse.is_active = True
            db.flush()
            return warehouse

        try:
            with db.begin_nested():
                warehouse = Warehouse(
                    code=DEFAULT_WAREHOUSE_CODE,
                    name=DEFAULT_WAREHOUSE_NAME,
                    location="Phnom Penh Hub",
                    is_default=True,
                    is_active=True,
                )
                db.add(warehouse)
                db.flush()
                return warehouse
        except IntegrityError:
            existing = db.scalar(
                select(Warehouse).where(
                    (Warehouse.is_default.is_(True)) | (Warehouse.code == DEFAULT_WAREHOUSE_CODE)
                )
            )
            if existing is not None:
                return existing
            raise

    @staticmethod
    def _get_or_create_warehouse_stock(
        db: Session,
        warehouse_id: int,
        product_id: int,
        initial_quantity: int = 0,
    ) -> WarehouseStock:
        ws = db.scalar(
            select(WarehouseStock).where(
                WarehouseStock.warehouse_id == warehouse_id,
                WarehouseStock.product_id == product_id,
            )
        )
        if ws is not None:
            return ws

        try:
            with db.begin_nested():
                ws = WarehouseStock(
                    warehouse_id=warehouse_id,
                    product_id=product_id,
                    quantity=max(0, initial_quantity),
                    reserved_quantity=0,
                    reorder_point=10,
                )
                db.add(ws)
                db.flush()
                return ws
        except IntegrityError:
            ws = db.scalar(
                select(WarehouseStock).where(
                    WarehouseStock.warehouse_id == warehouse_id,
                    WarehouseStock.product_id == product_id,
                )
            )
            if ws is not None:
                return ws
            raise

    @staticmethod
    def post_journal_entry(
        db: Session,
        *,
        entry_type: str,
        lines_spec: list[dict],
        reference_type: str | None = None,
        reference_id: int | None = None,
        reason: str | None = None,
        actor_user_id: int | None = None,
    ) -> InventoryJournalEntry:
        if len(lines_spec) < 2:
            raise ValueError("Double-entry inventory journal requires at least two lines.")

        total_debit = sum(int(line.get("debit_qty", 0)) for line in lines_spec)
        total_credit = sum(int(line.get("credit_qty", 0)) for line in lines_spec)
        if total_debit <= 0 or total_debit != total_credit:
            raise ValueError(
                f"Unbalanced inventory journal entry: debits={total_debit}, credits={total_credit}."
            )

        entry = InventoryJournalEntry(
            entry_number=InventoryService._new_ref("INV"),
            entry_type=entry_type,
            reference_type=reference_type,
            reference_id=reference_id,
            reason=reason[:500] if reason else None,
            created_by_user_id=actor_user_id,
        )
        db.add(entry)
        db.flush()

        for line in lines_spec:
            debit = int(line.get("debit_qty", 0))
            credit = int(line.get("credit_qty", 0))
            if not ((debit > 0 and credit == 0) or (credit > 0 and debit == 0)):
                raise ValueError("Each inventory ledger line must carry exactly one non-zero side.")
            db.add(
                InventoryLedgerLine(
                    journal_entry_id=entry.id,
                    product_id=int(line["product_id"]),
                    product_name=str(line["product_name"])[:200],
                    warehouse_id=line.get("warehouse_id"),
                    account_type=str(line["account_type"]),
                    debit_qty=debit,
                    credit_qty=credit,
                    unit_cost=Decimal(str(line.get("unit_cost", "0.00"))),
                    balance_after=line.get("balance_after"),
                )
            )
        db.flush()
        return entry

    @staticmethod
    def record_deduction_journal(
        db: Session,
        deduction_lines: list[dict],
        *,
        entry_type: str = "order_sale",
        reference_type: str | None = None,
        reference_id: int | None = None,
        reason: str | None = None,
        actor_user_id: int | None = None,
    ) -> InventoryJournalEntry | None:
        if not deduction_lines:
            return None
        return InventoryService.post_journal_entry(
            db,
            entry_type=entry_type,
            lines_spec=deduction_lines,
            reference_type=reference_type,
            reference_id=reference_id,
            reason=reason,
            actor_user_id=actor_user_id,
        )

    @staticmethod
    def _sync_pre_deduction_warehouse_stocks(
        db: Session,
        product: Product,
        pre_deduction_total: int,
        default_wh: Warehouse,
    ) -> list[WarehouseStock]:
        stocks = list(
            db.scalars(
                select(WarehouseStock)
                .where(WarehouseStock.product_id == product.id)
                .order_by(WarehouseStock.warehouse_id.asc())
            ).all()
        )
        if not stocks:
            ws = InventoryService._get_or_create_warehouse_stock(
                db,
                default_wh.id,
                product.id,
                initial_quantity=pre_deduction_total,
            )
            return [ws]

        current_wh_total = sum(s.quantity for s in stocks)
        if current_wh_total != pre_deduction_total:
            # Reconcile default warehouse row when tests/legacy updates touched Product.stock directly.
            default_ws = next((s for s in stocks if s.warehouse_id == default_wh.id), None)
            if default_ws is None:
                default_ws = InventoryService._get_or_create_warehouse_stock(
                    db, default_wh.id, product.id, initial_quantity=0
                )
                stocks.append(default_ws)
            diff = pre_deduction_total - current_wh_total
            default_ws.quantity = max(0, default_ws.quantity + diff)
            db.flush()
        return stocks

    @staticmethod
    def deduct_stock(
        db: Session,
        items: Iterable[tuple[int, int]],
        *,
        inactive_detail_fn: Callable[[int, Product | None], str] | None = None,
        ledger_out: list[dict] | None = None,
        entry_type: str = "order_sale",
        reference_type: str | None = None,
        reference_id: int | None = None,
        reason: str | None = None,
        actor_user_id: int | None = None,
    ) -> dict[int, Product]:
        ordered_requirements = InventoryService.aggregate_quantities(items)
        updated_products: dict[int, Product] = {}
        collected_lines: list[dict] = []
        default_wh: Warehouse | None = None

        for product_id, required_qty in ordered_requirements:
            result = db.execute(
                update(Product)
                .where(
                    Product.id == product_id,
                    Product.is_active.is_(True),
                    Product.stock >= required_qty,
                )
                .values(stock=Product.stock - required_qty)
                .execution_options(synchronize_session=False)
            )

            current = db.scalar(
                select(Product)
                .where(Product.id == product_id)
                .execution_options(populate_existing=True)
            )

            if result.rowcount != 1:
                if current is None or not current.is_active:
                    detail = (
                        inactive_detail_fn(product_id, current)
                        if inactive_detail_fn is not None
                        else f"Product #{product_id} is inactive or not found."
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=detail,
                    )

                if current.stock < required_qty:
                    conflict_detail = (
                        f"Insufficient stock for '{current.name}'. "
                        f"Available: {current.stock}, requested: {required_qty}."
                    )
                else:
                    conflict_detail = (
                        f"Inventory changed concurrently for '{current.name}'. "
                        "Please retry your checkout."
                    )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=conflict_detail,
                )

            assert current is not None
            updated_products[product_id] = current

            # Synchronize multi-warehouse stock & collect double-entry ledger lines
            if default_wh is None:
                default_wh = InventoryService.ensure_default_warehouse(db)

            pre_deduction_total = current.stock + required_qty
            stocks = InventoryService._sync_pre_deduction_warehouse_stocks(
                db, current, pre_deduction_total, default_wh
            )

            # Prioritize default warehouse first, then other warehouses by id
            stocks_ordered = sorted(
                stocks,
                key=lambda s: (0 if s.warehouse_id == default_wh.id else 1, s.warehouse_id),
            )
            remaining = required_qty
            unit_cost = (
                current.discount_price
                if current.discount_price is not None and Decimal(current.discount_price) > Decimal("0.00")
                else current.price
            )

            for ws in stocks_ordered:
                if remaining <= 0:
                    break
                take = min(ws.quantity, remaining)
                if take <= 0:
                    continue
                ws.quantity -= take
                remaining -= take
                collected_lines.append(
                    {
                        "product_id": current.id,
                        "product_name": current.name,
                        "warehouse_id": ws.warehouse_id,
                        "account_type": "warehouse_on_hand",
                        "debit_qty": 0,
                        "credit_qty": take,
                        "unit_cost": unit_cost,
                        "balance_after": ws.quantity,
                    }
                )
                collected_lines.append(
                    {
                        "product_id": current.id,
                        "product_name": current.name,
                        "warehouse_id": None,
                        "account_type": "customer_fulfillment",
                        "debit_qty": take,
                        "credit_qty": 0,
                        "unit_cost": unit_cost,
                        "balance_after": None,
                    }
                )

            # Fallback balance line if external stock was below aggregate
            if remaining > 0:
                default_ws = next(
                    (s for s in stocks_ordered if s.warehouse_id == default_wh.id),
                    stocks_ordered[0],
                )
                collected_lines.append(
                    {
                        "product_id": current.id,
                        "product_name": current.name,
                        "warehouse_id": default_ws.warehouse_id,
                        "account_type": "warehouse_on_hand",
                        "debit_qty": 0,
                        "credit_qty": remaining,
                        "unit_cost": unit_cost,
                        "balance_after": default_ws.quantity,
                    }
                )
                collected_lines.append(
                    {
                        "product_id": current.id,
                        "product_name": current.name,
                        "warehouse_id": None,
                        "account_type": "customer_fulfillment",
                        "debit_qty": remaining,
                        "credit_qty": 0,
                        "unit_cost": unit_cost,
                        "balance_after": None,
                    }
                )

        if ledger_out is not None:
            ledger_out.extend(collected_lines)
        elif collected_lines:
            InventoryService.record_deduction_journal(
                db,
                collected_lines,
                entry_type=entry_type,
                reference_type=reference_type,
                reference_id=reference_id,
                reason=reason or "Stock deduction",
                actor_user_id=actor_user_id,
            )

        return updated_products

    @staticmethod
    def restore_stock(
        db: Session,
        items: Iterable[tuple[int, int]],
        *,
        warehouse_id: int | None = None,
        entry_type: str = "order_cancellation",
        reference_type: str | None = None,
        reference_id: int | None = None,
        reason: str | None = None,
        actor_user_id: int | None = None,
    ) -> None:
        ordered_restorations = InventoryService.aggregate_quantities(items)
        if not ordered_restorations:
            return

        target_wh = (
            db.scalar(select(Warehouse).where(Warehouse.id == warehouse_id))
            if warehouse_id is not None
            else InventoryService.ensure_default_warehouse(db)
        )
        if target_wh is None:
            target_wh = InventoryService.ensure_default_warehouse(db)

        ledger_lines: list[dict] = []
        for product_id, restore_qty in ordered_restorations:
            db.execute(
                update(Product)
                .where(Product.id == product_id)
                .values(stock=Product.stock + restore_qty)
                .execution_options(synchronize_session=False)
            )
            product = db.scalar(
                select(Product)
                .where(Product.id == product_id)
                .execution_options(populate_existing=True)
            )
            if product is None:
                continue

            ws = InventoryService._get_or_create_warehouse_stock(
                db, target_wh.id, product.id, initial_quantity=max(0, product.stock - restore_qty)
            )
            ws.quantity += restore_qty
            db.flush()

            unit_cost = (
                product.discount_price
                if product.discount_price is not None and Decimal(product.discount_price) > Decimal("0.00")
                else product.price
            )
            ledger_lines.append(
                {
                    "product_id": product.id,
                    "product_name": product.name,
                    "warehouse_id": target_wh.id,
                    "account_type": "warehouse_on_hand",
                    "debit_qty": restore_qty,
                    "credit_qty": 0,
                    "unit_cost": unit_cost,
                    "balance_after": ws.quantity,
                }
            )
            ledger_lines.append(
                {
                    "product_id": product.id,
                    "product_name": product.name,
                    "warehouse_id": None,
                    "account_type": "customer_fulfillment",
                    "debit_qty": 0,
                    "credit_qty": restore_qty,
                    "unit_cost": unit_cost,
                    "balance_after": None,
                }
            )

        if ledger_lines:
            InventoryService.post_journal_entry(
                db,
                entry_type=entry_type,
                lines_spec=ledger_lines,
                reference_type=reference_type,
                reference_id=reference_id,
                reason=reason or "Stock restoration",
                actor_user_id=actor_user_id,
            )

    @staticmethod
    def record_product_opening_stock(
        db: Session,
        product: Product,
        *,
        actor_user_id: int | None = None,
    ) -> None:
        if product.stock <= 0:
            return
        default_wh = InventoryService.ensure_default_warehouse(db)
        ws = InventoryService._get_or_create_warehouse_stock(
            db, default_wh.id, product.id, initial_quantity=0
        )
        ws.quantity += product.stock
        db.flush()
        InventoryService.post_journal_entry(
            db,
            entry_type="opening_balance",
            reference_type="product",
            reference_id=product.id,
            reason=f"Initial catalog stock for '{product.name}'",
            actor_user_id=actor_user_id,
            lines_spec=[
                {
                    "product_id": product.id,
                    "product_name": product.name,
                    "warehouse_id": default_wh.id,
                    "account_type": "warehouse_on_hand",
                    "debit_qty": product.stock,
                    "credit_qty": 0,
                    "unit_cost": product.price,
                    "balance_after": ws.quantity,
                },
                {
                    "product_id": product.id,
                    "product_name": product.name,
                    "warehouse_id": None,
                    "account_type": "inventory_adjustment",
                    "debit_qty": 0,
                    "credit_qty": product.stock,
                    "unit_cost": product.price,
                    "balance_after": None,
                },
            ],
        )

    @staticmethod
    def record_product_stock_delta(
        db: Session,
        product: Product,
        old_stock: int,
        new_stock: int,
        *,
        actor_user_id: int | None = None,
    ) -> None:
        delta = new_stock - old_stock
        if delta == 0:
            return
        default_wh = InventoryService.ensure_default_warehouse(db)
        ws = InventoryService._get_or_create_warehouse_stock(
            db, default_wh.id, product.id, initial_quantity=max(0, old_stock)
        )
        if delta > 0:
            ws.quantity += delta
            lines = [
                {
                    "product_id": product.id,
                    "product_name": product.name,
                    "warehouse_id": default_wh.id,
                    "account_type": "warehouse_on_hand",
                    "debit_qty": delta,
                    "credit_qty": 0,
                    "unit_cost": product.price,
                    "balance_after": ws.quantity,
                },
                {
                    "product_id": product.id,
                    "product_name": product.name,
                    "warehouse_id": None,
                    "account_type": "inventory_adjustment",
                    "debit_qty": 0,
                    "credit_qty": delta,
                    "unit_cost": product.price,
                    "balance_after": None,
                },
            ]
        else:
            qty = abs(delta)
            ws.quantity = max(0, ws.quantity - qty)
            lines = [
                {
                    "product_id": product.id,
                    "product_name": product.name,
                    "warehouse_id": None,
                    "account_type": "inventory_adjustment",
                    "debit_qty": qty,
                    "credit_qty": 0,
                    "unit_cost": product.price,
                    "balance_after": None,
                },
                {
                    "product_id": product.id,
                    "product_name": product.name,
                    "warehouse_id": default_wh.id,
                    "account_type": "warehouse_on_hand",
                    "debit_qty": 0,
                    "credit_qty": qty,
                    "unit_cost": product.price,
                    "balance_after": ws.quantity,
                },
            ]
        db.flush()
        InventoryService.post_journal_entry(
            db,
            entry_type="adjustment",
            reference_type="product",
            reference_id=product.id,
            reason=f"Catalog product stock updated ({old_stock} -> {new_stock})",
            actor_user_id=actor_user_id,
            lines_spec=lines,
        )

    # ==============================
    # WAREHOUSES
    # ==============================
    @staticmethod
    def _build_warehouse_response(db: Session, wh: Warehouse) -> WarehouseResponse:
        agg = db.execute(
            select(
                func.coalesce(func.sum(WarehouseStock.quantity), 0),
                func.count(WarehouseStock.id),
            ).where(WarehouseStock.warehouse_id == wh.id)
        ).one()
        return WarehouseResponse(
            id=wh.id,
            code=wh.code,
            name=wh.name,
            location=wh.location,
            address=wh.address,
            contact_name=wh.contact_name,
            contact_phone=wh.contact_phone,
            is_default=wh.is_default,
            is_active=wh.is_active,
            total_units=int(agg[0] or 0),
            sku_count=int(agg[1] or 0),
            created_at=wh.created_at,
            updated_at=wh.updated_at,
        )

    @staticmethod
    def list_warehouses(db: Session) -> list[WarehouseResponse]:
        InventoryService.ensure_default_warehouse(db)
        db.commit()
        warehouses = list(db.scalars(select(Warehouse).order_by(Warehouse.is_default.desc(), Warehouse.id.asc())).all())
        return [InventoryService._build_warehouse_response(db, wh) for wh in warehouses]

    @staticmethod
    def create_warehouse(db: Session, data: WarehouseCreate) -> WarehouseResponse:
        code = data.code.strip().upper()
        name = data.name.strip()
        if db.scalar(select(Warehouse).where((Warehouse.code == code) | (Warehouse.name == name))):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A warehouse with this code or name already exists.",
            )

        if data.is_default:
            db.execute(update(Warehouse).values(is_default=False))

        wh = Warehouse(
            code=code,
            name=name,
            location=data.location.strip() if data.location else None,
            address=data.address.strip() if data.address else None,
            contact_name=data.contact_name.strip() if data.contact_name else None,
            contact_phone=data.contact_phone.strip() if data.contact_phone else None,
            is_default=data.is_default,
            is_active=data.is_active,
        )
        db.add(wh)
        db.commit()
        db.refresh(wh)
        return InventoryService._build_warehouse_response(db, wh)

    @staticmethod
    def update_warehouse(db: Session, warehouse_id: int, data: WarehouseUpdate) -> WarehouseResponse:
        wh = db.scalar(select(Warehouse).where(Warehouse.id == warehouse_id))
        if not wh:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Warehouse #{warehouse_id} not found.",
            )

        updates = data.model_dump(exclude_unset=True)
        if "code" in updates and updates["code"] is not None:
            new_code = updates.pop("code").strip().upper()
            if db.scalar(select(Warehouse).where(Warehouse.code == new_code, Warehouse.id != wh.id)):
                raise HTTPException(status_code=409, detail=f"Warehouse code '{new_code}' already exists.")
            wh.code = new_code

        if "name" in updates and updates["name"] is not None:
            new_name = updates.pop("name").strip()
            if db.scalar(select(Warehouse).where(Warehouse.name == new_name, Warehouse.id != wh.id)):
                raise HTTPException(status_code=409, detail=f"Warehouse name '{new_name}' already exists.")
            wh.name = new_name

        if updates.get("is_default") is True:
            db.execute(update(Warehouse).where(Warehouse.id != wh.id).values(is_default=False))
            wh.is_default = True
            wh.is_active = True
            updates.pop("is_default", None)
        elif updates.get("is_default") is False and wh.is_default:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Assign another default warehouse before unsetting the current default.",
            )

        if updates.get("is_active") is False and wh.is_default:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate the default warehouse.",
            )

        for field, value in updates.items():
            if isinstance(value, str):
                setattr(wh, field, value.strip() or None)
            else:
                setattr(wh, field, value)

        db.commit()
        db.refresh(wh)
        return InventoryService._build_warehouse_response(db, wh)

    # ==============================
    # STOCK QUERIES & MANUAL ADJUSTMENTS
    # ==============================
    @staticmethod
    def list_warehouse_stocks(
        db: Session,
        *,
        warehouse_id: int | None = None,
        product_id: int | None = None,
    ) -> list[WarehouseStockResponse]:
        default_wh = InventoryService.ensure_default_warehouse(db)
        # Ensure all existing catalog products have a default warehouse baseline row if uninitialized
        products = list(db.scalars(select(Product).order_by(Product.id.asc())).all())
        for prod in products:
            has_any = db.scalar(
                select(WarehouseStock.id).where(WarehouseStock.product_id == prod.id).limit(1)
            )
            if has_any is None:
                InventoryService._get_or_create_warehouse_stock(
                    db, default_wh.id, prod.id, initial_quantity=prod.stock
                )
        db.commit()

        query = (
            select(WarehouseStock, Warehouse, Product)
            .join(Warehouse, Warehouse.id == WarehouseStock.warehouse_id)
            .join(Product, Product.id == WarehouseStock.product_id)
        )
        if warehouse_id is not None:
            query = query.where(WarehouseStock.warehouse_id == warehouse_id)
        if product_id is not None:
            query = query.where(WarehouseStock.product_id == product_id)
        query = query.order_by(Warehouse.is_default.desc(), Warehouse.id.asc(), Product.id.asc())

        rows = db.execute(query).all()
        return [
            WarehouseStockResponse(
                id=ws.id,
                warehouse_id=wh.id,
                warehouse_code=wh.code,
                warehouse_name=wh.name,
                product_id=prod.id,
                product_name=prod.name,
                product_price=prod.price,
                product_is_active=prod.is_active,
                quantity=ws.quantity,
                reserved_quantity=ws.reserved_quantity,
                reorder_point=ws.reorder_point,
                updated_at=ws.updated_at,
            )
            for ws, wh, prod in rows
        ]

    @staticmethod
    def create_adjustment(
        db: Session,
        data: StockAdjustmentRequest,
        *,
        actor_user_id: int,
    ) -> InventoryJournalEntryResponse:
        product = db.scalar(
            select(Product).where(Product.id == data.product_id).with_for_update()
        )
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product #{data.product_id} not found.",
            )

        if data.warehouse_id is not None:
            wh = db.scalar(
                select(Warehouse).where(Warehouse.id == data.warehouse_id, Warehouse.is_active.is_(True))
            )
            if not wh:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Active warehouse #{data.warehouse_id} not found.",
                )
        else:
            wh = InventoryService.ensure_default_warehouse(db)

        # Ensure baseline warehouse row exists before applying adjustment
        has_any = db.scalar(
            select(WarehouseStock.id).where(WarehouseStock.product_id == product.id).limit(1)
        )
        default_wh = InventoryService.ensure_default_warehouse(db)
        if has_any is None:
            InventoryService._get_or_create_warehouse_stock(
                db, default_wh.id, product.id, initial_quantity=product.stock
            )

        ws = InventoryService._get_or_create_warehouse_stock(db, wh.id, product.id, initial_quantity=0)
        new_wh_qty = ws.quantity + data.quantity_delta
        new_total_qty = product.stock + data.quantity_delta
        if new_wh_qty < 0 or new_total_qty < 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Insufficient stock in warehouse '{wh.name}' for '{product.name}'. "
                    f"Available: {ws.quantity}, requested delta: {data.quantity_delta}."
                ),
            )

        ws.quantity = new_wh_qty
        product.stock = new_total_qty
        unit_cost = data.unit_cost if data.unit_cost > Decimal("0.00") else product.price

        abs_qty = abs(data.quantity_delta)
        if data.quantity_delta > 0:
            lines = [
                {
                    "product_id": product.id,
                    "product_name": product.name,
                    "warehouse_id": wh.id,
                    "account_type": "warehouse_on_hand",
                    "debit_qty": abs_qty,
                    "credit_qty": 0,
                    "unit_cost": unit_cost,
                    "balance_after": ws.quantity,
                },
                {
                    "product_id": product.id,
                    "product_name": product.name,
                    "warehouse_id": None,
                    "account_type": "inventory_adjustment",
                    "debit_qty": 0,
                    "credit_qty": abs_qty,
                    "unit_cost": unit_cost,
                    "balance_after": None,
                },
            ]
        else:
            lines = [
                {
                    "product_id": product.id,
                    "product_name": product.name,
                    "warehouse_id": None,
                    "account_type": "inventory_adjustment",
                    "debit_qty": abs_qty,
                    "credit_qty": 0,
                    "unit_cost": unit_cost,
                    "balance_after": None,
                },
                {
                    "product_id": product.id,
                    "product_name": product.name,
                    "warehouse_id": wh.id,
                    "account_type": "warehouse_on_hand",
                    "debit_qty": 0,
                    "credit_qty": abs_qty,
                    "unit_cost": unit_cost,
                    "balance_after": ws.quantity,
                },
            ]

        entry = InventoryService.post_journal_entry(
            db,
            entry_type="adjustment",
            reference_type="warehouse_adjustment",
            reference_id=wh.id,
            reason=data.reason.strip(),
            actor_user_id=actor_user_id,
            lines_spec=lines,
        )
        db.commit()
        return InventoryService._serialize_journal_entry(db, entry.id)

    # ==============================
    # LEDGER QUERY
    # ==============================
    @staticmethod
    def _serialize_journal_entry(db: Session, entry_id: int) -> InventoryJournalEntryResponse:
        entry = db.scalar(
            select(InventoryJournalEntry)
            .options(selectinload(InventoryJournalEntry.lines))
            .where(InventoryJournalEntry.id == entry_id)
        )
        assert entry is not None
        wh_ids = {line.warehouse_id for line in entry.lines if line.warehouse_id is not None}
        wh_map = (
            {wh.id: wh.name for wh in db.scalars(select(Warehouse).where(Warehouse.id.in_(wh_ids))).all()}
            if wh_ids
            else {}
        )
        return InventoryJournalEntryResponse(
            id=entry.id,
            entry_number=entry.entry_number,
            entry_type=entry.entry_type,
            reference_type=entry.reference_type,
            reference_id=entry.reference_id,
            reason=entry.reason,
            created_by_user_id=entry.created_by_user_id,
            created_at=entry.created_at,
            lines=[
                InventoryLedgerLineResponse(
                    id=line.id,
                    journal_entry_id=line.journal_entry_id,
                    product_id=line.product_id,
                    product_name=line.product_name,
                    warehouse_id=line.warehouse_id,
                    warehouse_name=wh_map.get(line.warehouse_id) if line.warehouse_id else None,
                    account_type=line.account_type,
                    debit_qty=line.debit_qty,
                    credit_qty=line.credit_qty,
                    unit_cost=line.unit_cost,
                    balance_after=line.balance_after,
                    created_at=line.created_at,
                )
                for line in sorted(entry.lines, key=lambda item: item.id)
            ],
        )

    @staticmethod
    def list_ledger(
        db: Session,
        *,
        product_id: int | None = None,
        warehouse_id: int | None = None,
        entry_type: str | None = None,
        page: int = 1,
        limit: int = 25,
    ) -> InventoryLedgerListResponse:
        page = max(1, page)
        limit = max(1, min(100, limit))

        query = select(InventoryJournalEntry)
        if entry_type and entry_type.strip().lower() != "all":
            query = query.where(InventoryJournalEntry.entry_type == entry_type.strip())
        if product_id is not None or warehouse_id is not None:
            line_subq = select(InventoryLedgerLine.journal_entry_id)
            if product_id is not None:
                line_subq = line_subq.where(InventoryLedgerLine.product_id == product_id)
            if warehouse_id is not None:
                line_subq = line_subq.where(InventoryLedgerLine.warehouse_id == warehouse_id)
            query = query.where(InventoryJournalEntry.id.in_(line_subq))

        total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
        offset = (page - 1) * limit
        entries = list(
            db.scalars(
                query.options(selectinload(InventoryJournalEntry.lines))
                .order_by(InventoryJournalEntry.created_at.desc(), InventoryJournalEntry.id.desc())
                .offset(offset)
                .limit(limit)
            ).all()
        )

        all_wh_ids = {
            line.warehouse_id
            for entry in entries
            for line in entry.lines
            if line.warehouse_id is not None
        }
        wh_map = (
            {wh.id: wh.name for wh in db.scalars(select(Warehouse).where(Warehouse.id.in_(all_wh_ids))).all()}
            if all_wh_ids
            else {}
        )

        serialized = [
            InventoryJournalEntryResponse(
                id=entry.id,
                entry_number=entry.entry_number,
                entry_type=entry.entry_type,
                reference_type=entry.reference_type,
                reference_id=entry.reference_id,
                reason=entry.reason,
                created_by_user_id=entry.created_by_user_id,
                created_at=entry.created_at,
                lines=[
                    InventoryLedgerLineResponse(
                        id=line.id,
                        journal_entry_id=line.journal_entry_id,
                        product_id=line.product_id,
                        product_name=line.product_name,
                        warehouse_id=line.warehouse_id,
                        warehouse_name=wh_map.get(line.warehouse_id) if line.warehouse_id else None,
                        account_type=line.account_type,
                        debit_qty=line.debit_qty,
                        credit_qty=line.credit_qty,
                        unit_cost=line.unit_cost,
                        balance_after=line.balance_after,
                        created_at=line.created_at,
                    )
                    for line in sorted(entry.lines, key=lambda item: item.id)
                ],
            )
            for entry in entries
        ]

        tb_row = db.execute(
            select(
                func.coalesce(func.sum(InventoryLedgerLine.debit_qty), 0),
                func.coalesce(func.sum(InventoryLedgerLine.credit_qty), 0),
            )
        ).one()
        total_debits = int(tb_row[0] or 0)
        total_credits = int(tb_row[1] or 0)
        total_entries = db.scalar(select(func.count(InventoryJournalEntry.id))) or 0

        return InventoryLedgerListResponse(
            entries=serialized,
            trial_balance=InventoryLedgerTrialBalance(
                total_debits=total_debits,
                total_credits=total_credits,
                balanced=(total_debits == total_credits),
                total_entries=int(total_entries),
            ),
            total=int(total),
            page=page,
            limit=limit,
        )

    # ==============================
    # PURCHASE ORDERS
    # ==============================
    @staticmethod
    def _serialize_po(db: Session, po_id: int) -> PurchaseOrderResponse:
        po = db.scalar(
            select(PurchaseOrder)
            .options(
                selectinload(PurchaseOrder.items),
                selectinload(PurchaseOrder.supplier),
                selectinload(PurchaseOrder.warehouse),
            )
            .where(PurchaseOrder.id == po_id)
        )
        if not po:
            raise HTTPException(status_code=404, detail=f"Purchase order #{po_id} not found.")

        return PurchaseOrderResponse(
            id=po.id,
            po_number=po.po_number,
            supplier_id=po.supplier_id,
            supplier_name=po.supplier.name if po.supplier else None,
            warehouse_id=po.warehouse_id,
            warehouse_name=po.warehouse.name if po.warehouse else None,
            status=po.status,
            total_cost=po.total_cost,
            expected_at=po.expected_at,
            ordered_at=po.ordered_at,
            received_at=po.received_at,
            notes=po.notes,
            created_by_user_id=po.created_by_user_id,
            created_at=po.created_at,
            updated_at=po.updated_at,
            items=[
                PurchaseOrderItemResponse(
                    id=item.id,
                    purchase_order_id=item.purchase_order_id,
                    product_id=item.product_id,
                    product_name=item.product_name,
                    quantity_ordered=item.quantity_ordered,
                    quantity_received=item.quantity_received,
                    unit_cost=item.unit_cost,
                    line_total=item.line_total,
                )
                for item in po.items
            ],
        )

    @staticmethod
    def list_purchase_orders(db: Session, status_filter: str | None = None) -> list[PurchaseOrderResponse]:
        query = select(PurchaseOrder).order_by(PurchaseOrder.created_at.desc(), PurchaseOrder.id.desc())
        if status_filter and status_filter.strip().lower() != "all":
            query = query.where(PurchaseOrder.status == status_filter.strip().lower())
        pos = list(db.scalars(query).all())
        return [InventoryService._serialize_po(db, po.id) for po in pos]

    @staticmethod
    def create_purchase_order(
        db: Session,
        data: PurchaseOrderCreate,
        *,
        actor_user_id: int,
    ) -> PurchaseOrderResponse:
        supplier = db.scalar(select(Supplier).where(Supplier.id == data.supplier_id))
        if not supplier:
            raise HTTPException(status_code=404, detail=f"Supplier #{data.supplier_id} not found.")
        if supplier.status != "Active":
            raise HTTPException(status_code=409, detail="Cannot create purchase order for an inactive supplier.")

        warehouse = db.scalar(
            select(Warehouse).where(Warehouse.id == data.warehouse_id, Warehouse.is_active.is_(True))
        )
        if not warehouse:
            raise HTTPException(status_code=404, detail=f"Active warehouse #{data.warehouse_id} not found.")

        total_cost = Decimal("0.00")
        items_to_add: list[PurchaseOrderItem] = []
        for item_in in data.items:
            product = db.scalar(select(Product).where(Product.id == item_in.product_id))
            if not product:
                raise HTTPException(status_code=404, detail=f"Product #{item_in.product_id} not found.")
            line_total = (item_in.unit_cost * item_in.quantity_ordered).quantize(Decimal("0.01"))
            total_cost += line_total
            items_to_add.append(
                PurchaseOrderItem(
                    product_id=product.id,
                    product_name=product.name,
                    quantity_ordered=item_in.quantity_ordered,
                    quantity_received=0,
                    unit_cost=item_in.unit_cost.quantize(Decimal("0.01")),
                    line_total=line_total,
                )
            )

        po = PurchaseOrder(
            po_number=InventoryService._new_ref("PO"),
            supplier_id=supplier.id,
            warehouse_id=warehouse.id,
            status="draft",
            total_cost=total_cost.quantize(Decimal("0.01")),
            expected_at=data.expected_at,
            notes=data.notes.strip() if data.notes else None,
            created_by_user_id=actor_user_id,
        )
        db.add(po)
        db.flush()
        for item in items_to_add:
            item.purchase_order_id = po.id
            db.add(item)
        db.commit()
        return InventoryService._serialize_po(db, po.id)

    @staticmethod
    def mark_purchase_order_ordered(db: Session, po_id: int) -> PurchaseOrderResponse:
        po = db.scalar(select(PurchaseOrder).where(PurchaseOrder.id == po_id).with_for_update())
        if not po:
            raise HTTPException(status_code=404, detail=f"Purchase order #{po_id} not found.")
        if po.status != "draft":
            raise HTTPException(
                status_code=409,
                detail=f"Purchase order #{po.po_number} cannot move from '{po.status}' to 'ordered'.",
            )
        po.status = "ordered"
        po.ordered_at = datetime.now(timezone.utc)
        db.commit()
        return InventoryService._serialize_po(db, po.id)

    @staticmethod
    def receive_purchase_order(
        db: Session,
        po_id: int,
        data: PurchaseOrderReceiveRequest,
        *,
        actor_user_id: int,
    ) -> PurchaseOrderResponse:
        po = db.scalar(
            select(PurchaseOrder)
            .options(selectinload(PurchaseOrder.items))
            .where(PurchaseOrder.id == po_id)
            .with_for_update()
        )
        if not po:
            raise HTTPException(status_code=404, detail=f"Purchase order #{po_id} not found.")
        if po.status not in {"draft", "ordered", "partially_received"}:
            raise HTTPException(
                status_code=409,
                detail=f"Purchase order #{po.po_number} in '{po.status}' state cannot receive stock.",
            )

        items_by_id = {item.id: item for item in po.items}
        receive_map: dict[int, int] = {}
        if data.items:
            for req_item in data.items:
                if req_item.item_id not in items_by_id:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Purchase order item #{req_item.item_id} does not belong to PO {po.po_number}.",
                    )
                receive_map[req_item.item_id] = receive_map.get(req_item.item_id, 0) + req_item.quantity_received
        else:
            for item in po.items:
                remaining = item.quantity_ordered - item.quantity_received
                if remaining > 0:
                    receive_map[item.id] = remaining

        if not receive_map:
            raise HTTPException(status_code=400, detail="No remaining quantities to receive.")

        default_wh = InventoryService.ensure_default_warehouse(db)
        ledger_lines: list[dict] = []
        now = datetime.now(timezone.utc)

        for item_id, qty_to_receive in sorted(receive_map.items()):
            po_item = items_by_id[item_id]
            remaining = po_item.quantity_ordered - po_item.quantity_received
            if qty_to_receive > remaining:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Cannot receive {qty_to_receive} units of '{po_item.product_name}'; "
                        f"only {remaining} remaining on {po.po_number}."
                    ),
                )
            if po_item.product_id is None:
                raise HTTPException(
                    status_code=409,
                    detail=f"Product for PO item '{po_item.product_name}' no longer exists.",
                )

            product = db.scalar(
                select(Product).where(Product.id == po_item.product_id).with_for_update()
            )
            if not product:
                raise HTTPException(status_code=404, detail=f"Product #{po_item.product_id} not found.")

            has_any = db.scalar(
                select(WarehouseStock.id).where(WarehouseStock.product_id == product.id).limit(1)
            )
            if has_any is None:
                InventoryService._get_or_create_warehouse_stock(
                    db, default_wh.id, product.id, initial_quantity=product.stock
                )

            ws = InventoryService._get_or_create_warehouse_stock(
                db, po.warehouse_id, product.id, initial_quantity=0
            )
            ws.quantity += qty_to_receive
            product.stock += qty_to_receive
            po_item.quantity_received += qty_to_receive
            db.flush()

            ledger_lines.append(
                {
                    "product_id": product.id,
                    "product_name": product.name,
                    "warehouse_id": po.warehouse_id,
                    "account_type": "warehouse_on_hand",
                    "debit_qty": qty_to_receive,
                    "credit_qty": 0,
                    "unit_cost": po_item.unit_cost,
                    "balance_after": ws.quantity,
                }
            )
            ledger_lines.append(
                {
                    "product_id": product.id,
                    "product_name": product.name,
                    "warehouse_id": None,
                    "account_type": "supplier_clearing",
                    "debit_qty": 0,
                    "credit_qty": qty_to_receive,
                    "unit_cost": po_item.unit_cost,
                    "balance_after": None,
                }
            )

        all_received = all(item.quantity_received >= item.quantity_ordered for item in po.items)
        po.status = "received" if all_received else "partially_received"
        if po.ordered_at is None:
            po.ordered_at = now
        if all_received:
            po.received_at = now
        if data.notes:
            po.notes = f"{po.notes} | {data.notes.strip()}".strip(" |") if po.notes else data.notes.strip()

        InventoryService.post_journal_entry(
            db,
            entry_type="purchase_receipt",
            reference_type="purchase_order",
            reference_id=po.id,
            reason=f"Goods receipt for {po.po_number}",
            actor_user_id=actor_user_id,
            lines_spec=ledger_lines,
        )
        db.commit()
        return InventoryService._serialize_po(db, po.id)

    @staticmethod
    def cancel_purchase_order(db: Session, po_id: int) -> PurchaseOrderResponse:
        po = db.scalar(
            select(PurchaseOrder)
            .options(selectinload(PurchaseOrder.items))
            .where(PurchaseOrder.id == po_id)
            .with_for_update()
        )
        if not po:
            raise HTTPException(status_code=404, detail=f"Purchase order #{po_id} not found.")
        if po.status not in {"draft", "ordered"}:
            raise HTTPException(
                status_code=409,
                detail=f"Purchase order {po.po_number} in '{po.status}' status cannot be cancelled.",
            )
        if any(item.quantity_received > 0 for item in po.items):
            raise HTTPException(
                status_code=409,
                detail=f"Purchase order {po.po_number} already has received items and cannot be cancelled.",
            )
        po.status = "cancelled"
        db.commit()
        return InventoryService._serialize_po(db, po.id)

    # ==============================
    # WAREHOUSE TRANSFERS
    # ==============================
    @staticmethod
    def _serialize_transfer(db: Session, transfer_id: int) -> WarehouseTransferResponse:
        transfer = db.scalar(
            select(WarehouseTransfer)
            .options(
                selectinload(WarehouseTransfer.items),
                selectinload(WarehouseTransfer.source_warehouse),
                selectinload(WarehouseTransfer.destination_warehouse),
            )
            .where(WarehouseTransfer.id == transfer_id)
        )
        if not transfer:
            raise HTTPException(status_code=404, detail=f"Warehouse transfer #{transfer_id} not found.")

        return WarehouseTransferResponse(
            id=transfer.id,
            transfer_number=transfer.transfer_number,
            source_warehouse_id=transfer.source_warehouse_id,
            source_warehouse_name=transfer.source_warehouse.name if transfer.source_warehouse else None,
            destination_warehouse_id=transfer.destination_warehouse_id,
            destination_warehouse_name=transfer.destination_warehouse.name if transfer.destination_warehouse else None,
            status=transfer.status,
            notes=transfer.notes,
            created_by_user_id=transfer.created_by_user_id,
            dispatched_at=transfer.dispatched_at,
            completed_at=transfer.completed_at,
            created_at=transfer.created_at,
            updated_at=transfer.updated_at,
            items=[
                WarehouseTransferItemResponse(
                    id=item.id,
                    transfer_id=item.transfer_id,
                    product_id=item.product_id,
                    product_name=item.product_name,
                    quantity=item.quantity,
                )
                for item in transfer.items
            ],
        )

    @staticmethod
    def list_transfers(db: Session, status_filter: str | None = None) -> list[WarehouseTransferResponse]:
        query = select(WarehouseTransfer).order_by(WarehouseTransfer.created_at.desc(), WarehouseTransfer.id.desc())
        if status_filter and status_filter.strip().lower() != "all":
            query = query.where(WarehouseTransfer.status == status_filter.strip().lower())
        rows = list(db.scalars(query).all())
        return [InventoryService._serialize_transfer(db, t.id) for t in rows]

    @staticmethod
    def create_transfer(
        db: Session,
        data: WarehouseTransferCreate,
        *,
        actor_user_id: int,
    ) -> WarehouseTransferResponse:
        if data.source_warehouse_id == data.destination_warehouse_id:
            raise HTTPException(
                status_code=400,
                detail="Source and destination warehouses must be different.",
            )

        src = db.scalar(
            select(Warehouse).where(Warehouse.id == data.source_warehouse_id, Warehouse.is_active.is_(True))
        )
        dst = db.scalar(
            select(Warehouse).where(Warehouse.id == data.destination_warehouse_id, Warehouse.is_active.is_(True))
        )
        if not src or not dst:
            raise HTTPException(status_code=404, detail="Both source and destination warehouses must exist and be active.")

        aggregated = InventoryService.aggregate_quantities(
            [(item.product_id, item.quantity) for item in data.items]
        )
        items_to_add: list[WarehouseTransferItem] = []
        for product_id, qty in aggregated:
            product = db.scalar(select(Product).where(Product.id == product_id))
            if not product:
                raise HTTPException(status_code=404, detail=f"Product #{product_id} not found.")
            items_to_add.append(
                WarehouseTransferItem(
                    product_id=product.id,
                    product_name=product.name,
                    quantity=qty,
                )
            )

        transfer = WarehouseTransfer(
            transfer_number=InventoryService._new_ref("TRF"),
            source_warehouse_id=src.id,
            destination_warehouse_id=dst.id,
            status="draft",
            notes=data.notes.strip() if data.notes else None,
            created_by_user_id=actor_user_id,
        )
        db.add(transfer)
        db.flush()
        for item in items_to_add:
            item.transfer_id = transfer.id
            db.add(item)
        db.commit()
        return InventoryService._serialize_transfer(db, transfer.id)

    @staticmethod
    def dispatch_transfer(
        db: Session,
        transfer_id: int,
        *,
        actor_user_id: int,
    ) -> WarehouseTransferResponse:
        transfer = db.scalar(
            select(WarehouseTransfer)
            .options(selectinload(WarehouseTransfer.items))
            .where(WarehouseTransfer.id == transfer_id)
            .with_for_update()
        )
        if not transfer:
            raise HTTPException(status_code=404, detail=f"Warehouse transfer #{transfer_id} not found.")
        if transfer.status != "draft":
            raise HTTPException(
                status_code=409,
                detail=f"Transfer {transfer.transfer_number} is in '{transfer.status}' status and cannot be dispatched.",
            )

        default_wh = InventoryService.ensure_default_warehouse(db)
        ledger_lines: list[dict] = []
        for item in sorted(transfer.items, key=lambda i: i.product_id or 0):
            if item.product_id is None:
                raise HTTPException(status_code=409, detail=f"Product '{item.product_name}' no longer exists.")
            product = db.scalar(select(Product).where(Product.id == item.product_id).with_for_update())
            if not product:
                raise HTTPException(status_code=404, detail=f"Product #{item.product_id} not found.")

            has_any = db.scalar(
                select(WarehouseStock.id).where(WarehouseStock.product_id == product.id).limit(1)
            )
            if has_any is None:
                InventoryService._get_or_create_warehouse_stock(
                    db, default_wh.id, product.id, initial_quantity=product.stock
                )

            src_ws = InventoryService._get_or_create_warehouse_stock(
                db, transfer.source_warehouse_id, product.id, initial_quantity=0
            )
            if src_ws.quantity < item.quantity or product.stock < item.quantity:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Insufficient stock in source warehouse for '{product.name}'. "
                        f"Available: {src_ws.quantity}, requested: {item.quantity}."
                    ),
                )

            src_ws.quantity -= item.quantity
            # In-transit stock is temporarily non-sellable until destination receipt completes.
            product.stock -= item.quantity
            db.flush()

            ledger_lines.append(
                {
                    "product_id": product.id,
                    "product_name": product.name,
                    "warehouse_id": None,
                    "account_type": "in_transit",
                    "debit_qty": item.quantity,
                    "credit_qty": 0,
                    "unit_cost": product.price,
                    "balance_after": None,
                }
            )
            ledger_lines.append(
                {
                    "product_id": product.id,
                    "product_name": product.name,
                    "warehouse_id": transfer.source_warehouse_id,
                    "account_type": "warehouse_on_hand",
                    "debit_qty": 0,
                    "credit_qty": item.quantity,
                    "unit_cost": product.price,
                    "balance_after": src_ws.quantity,
                }
            )

        transfer.status = "in_transit"
        transfer.dispatched_at = datetime.now(timezone.utc)
        InventoryService.post_journal_entry(
            db,
            entry_type="transfer_out",
            reference_type="warehouse_transfer",
            reference_id=transfer.id,
            reason=f"Dispatched {transfer.transfer_number}",
            actor_user_id=actor_user_id,
            lines_spec=ledger_lines,
        )
        db.commit()
        return InventoryService._serialize_transfer(db, transfer.id)

    @staticmethod
    def complete_transfer(
        db: Session,
        transfer_id: int,
        *,
        actor_user_id: int,
    ) -> WarehouseTransferResponse:
        transfer = db.scalar(
            select(WarehouseTransfer)
            .options(selectinload(WarehouseTransfer.items))
            .where(WarehouseTransfer.id == transfer_id)
            .with_for_update()
        )
        if not transfer:
            raise HTTPException(status_code=404, detail=f"Warehouse transfer #{transfer_id} not found.")
        if transfer.status != "in_transit":
            raise HTTPException(
                status_code=409,
                detail=f"Transfer {transfer.transfer_number} must be 'in_transit' before completion.",
            )

        ledger_lines: list[dict] = []
        for item in sorted(transfer.items, key=lambda i: i.product_id or 0):
            if item.product_id is None:
                raise HTTPException(status_code=409, detail=f"Product '{item.product_name}' no longer exists.")
            product = db.scalar(select(Product).where(Product.id == item.product_id).with_for_update())
            if not product:
                raise HTTPException(status_code=404, detail=f"Product #{item.product_id} not found.")

            dst_ws = InventoryService._get_or_create_warehouse_stock(
                db, transfer.destination_warehouse_id, product.id, initial_quantity=0
            )
            dst_ws.quantity += item.quantity
            product.stock += item.quantity
            db.flush()

            ledger_lines.append(
                {
                    "product_id": product.id,
                    "product_name": product.name,
                    "warehouse_id": transfer.destination_warehouse_id,
                    "account_type": "warehouse_on_hand",
                    "debit_qty": item.quantity,
                    "credit_qty": 0,
                    "unit_cost": product.price,
                    "balance_after": dst_ws.quantity,
                }
            )
            ledger_lines.append(
                {
                    "product_id": product.id,
                    "product_name": product.name,
                    "warehouse_id": None,
                    "account_type": "in_transit",
                    "debit_qty": 0,
                    "credit_qty": item.quantity,
                    "unit_cost": product.price,
                    "balance_after": None,
                }
            )

        transfer.status = "completed"
        transfer.completed_at = datetime.now(timezone.utc)
        InventoryService.post_journal_entry(
            db,
            entry_type="transfer_in",
            reference_type="warehouse_transfer",
            reference_id=transfer.id,
            reason=f"Completed {transfer.transfer_number}",
            actor_user_id=actor_user_id,
            lines_spec=ledger_lines,
        )
        db.commit()
        return InventoryService._serialize_transfer(db, transfer.id)

    @staticmethod
    def cancel_transfer(
        db: Session,
        transfer_id: int,
        *,
        actor_user_id: int,
    ) -> WarehouseTransferResponse:
        transfer = db.scalar(
            select(WarehouseTransfer)
            .options(selectinload(WarehouseTransfer.items))
            .where(WarehouseTransfer.id == transfer_id)
            .with_for_update()
        )
        if not transfer:
            raise HTTPException(status_code=404, detail=f"Warehouse transfer #{transfer_id} not found.")
        if transfer.status in {"completed", "cancelled"}:
            raise HTTPException(
                status_code=409,
                detail=f"Transfer {transfer.transfer_number} is already '{transfer.status}'.",
            )

        if transfer.status == "in_transit":
            ledger_lines: list[dict] = []
            for item in sorted(transfer.items, key=lambda i: i.product_id or 0):
                if item.product_id is None:
                    continue
                product = db.scalar(select(Product).where(Product.id == item.product_id).with_for_update())
                if not product:
                    continue
                src_ws = InventoryService._get_or_create_warehouse_stock(
                    db, transfer.source_warehouse_id, product.id, initial_quantity=0
                )
                src_ws.quantity += item.quantity
                product.stock += item.quantity
                db.flush()

                ledger_lines.append(
                    {
                        "product_id": product.id,
                        "product_name": product.name,
                        "warehouse_id": transfer.source_warehouse_id,
                        "account_type": "warehouse_on_hand",
                        "debit_qty": item.quantity,
                        "credit_qty": 0,
                        "unit_cost": product.price,
                        "balance_after": src_ws.quantity,
                    }
                )
                ledger_lines.append(
                    {
                        "product_id": product.id,
                        "product_name": product.name,
                        "warehouse_id": None,
                        "account_type": "in_transit",
                        "debit_qty": 0,
                        "credit_qty": item.quantity,
                        "unit_cost": product.price,
                        "balance_after": None,
                    }
                )

            if ledger_lines:
                InventoryService.post_journal_entry(
                    db,
                    entry_type="transfer_cancel",
                    reference_type="warehouse_transfer",
                    reference_id=transfer.id,
                    reason=f"Cancelled in-transit transfer {transfer.transfer_number}",
                    actor_user_id=actor_user_id,
                    lines_spec=ledger_lines,
                )

        transfer.status = "cancelled"
        db.commit()
        return InventoryService._serialize_transfer(db, transfer.id)
