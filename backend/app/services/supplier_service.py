from decimal import Decimal
import re
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.inventory import PurchaseOrder, Warehouse
from app.models.supplier import Supplier
from app.schemas.supplier import (
    SupplierCreate,
    SupplierPurchaseOrderSummary,
    SupplierResponse,
    SupplierUpdate,
)

ALLOWED_SUPPLIER_STATUSES = {"Active", "Inactive"}


class SupplierService:
    @staticmethod
    def _normalize_status(raw_status: str | None) -> str:
        cleaned = (raw_status or "Active").strip().lower()
        if cleaned == "active":
            return "Active"
        if cleaned == "inactive":
            return "Inactive"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid supplier status. Allowed values: Active, Inactive.",
        )

    @staticmethod
    def _generate_code(db: Session, name: str) -> str:
        prefix = re.sub(r"[^A-Z0-9]+", "", name.upper())[:4] or "SUP"
        candidate = f"SUP-{prefix}-{uuid4().hex[:4].upper()}"
        while db.scalar(select(Supplier.id).where(Supplier.code == candidate)) is not None:
            candidate = f"SUP-{prefix}-{uuid4().hex[:4].upper()}"
        return candidate

    @staticmethod
    def _build_response(
        db: Session,
        supplier: Supplier,
        *,
        include_recent_pos: bool = False,
    ) -> SupplierResponse:
        stats_row = db.execute(
            select(
                func.count(PurchaseOrder.id),
                func.coalesce(func.sum(PurchaseOrder.total_cost), Decimal("0.00")),
            ).where(PurchaseOrder.supplier_id == supplier.id)
        ).one()
        po_count = int(stats_row[0] or 0)
        total_procured = Decimal(stats_row[1] or 0)

        open_po_count = (
            db.scalar(
                select(func.count(PurchaseOrder.id)).where(
                    PurchaseOrder.supplier_id == supplier.id,
                    PurchaseOrder.status.in_(["draft", "ordered", "partially_received"]),
                )
            )
            or 0
        )

        recent_pos: list[SupplierPurchaseOrderSummary] = []
        if include_recent_pos:
            po_rows = db.scalars(
                select(PurchaseOrder)
                .where(PurchaseOrder.supplier_id == supplier.id)
                .order_by(PurchaseOrder.created_at.desc())
                .limit(20)
            ).all()
            wh_ids = {po.warehouse_id for po in po_rows}
            wh_names = (
                {
                    wh.id: wh.name
                    for wh in db.scalars(select(Warehouse).where(Warehouse.id.in_(wh_ids))).all()
                }
                if wh_ids
                else {}
            )
            recent_pos = [
                SupplierPurchaseOrderSummary(
                    id=po.id,
                    po_number=po.po_number,
                    warehouse_id=po.warehouse_id,
                    warehouse_name=wh_names.get(po.warehouse_id),
                    status=po.status,
                    total_cost=po.total_cost,
                    expected_at=po.expected_at,
                    ordered_at=po.ordered_at,
                    received_at=po.received_at,
                    created_at=po.created_at,
                )
                for po in po_rows
            ]

        return SupplierResponse(
            id=supplier.id,
            code=supplier.code,
            name=supplier.name,
            contact_name=supplier.contact_name,
            email=supplier.email,
            phone=supplier.phone,
            address=supplier.address,
            city=supplier.city,
            country=supplier.country,
            tax_id=supplier.tax_id,
            payment_terms=supplier.payment_terms,
            lead_time_days=supplier.lead_time_days,
            status=supplier.status,
            notes=supplier.notes,
            purchase_orders_count=po_count,
            open_purchase_orders_count=int(open_po_count),
            total_procured_amount=total_procured,
            recent_purchase_orders=recent_pos,
            created_at=supplier.created_at,
            updated_at=supplier.updated_at,
        )

    @staticmethod
    def list_suppliers(
        db: Session,
        *,
        status_filter: str | None = None,
        search: str | None = None,
    ) -> list[SupplierResponse]:
        query = select(Supplier)
        if status_filter and status_filter.strip().lower() != "all":
            query = query.where(Supplier.status.ilike(status_filter.strip()))
        if search and search.strip():
            term = f"%{search.strip()}%"
            query = query.where(
                or_(
                    Supplier.code.ilike(term),
                    Supplier.name.ilike(term),
                    Supplier.contact_name.ilike(term),
                    Supplier.email.ilike(term),
                )
            )
        suppliers = list(db.scalars(query.order_by(Supplier.id.desc())).all())
        return [SupplierService._build_response(db, s) for s in suppliers]

    @staticmethod
    def get_supplier(db: Session, supplier_id: int) -> SupplierResponse:
        supplier = db.scalar(select(Supplier).where(Supplier.id == supplier_id))
        if not supplier:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supplier #{supplier_id} not found.",
            )
        return SupplierService._build_response(db, supplier, include_recent_pos=True)

    @staticmethod
    def create_supplier(db: Session, data: SupplierCreate) -> SupplierResponse:
        code = (data.code or "").strip().upper() or SupplierService._generate_code(db, data.name)
        existing_code = db.scalar(select(Supplier).where(Supplier.code == code))
        if existing_code:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Supplier code '{code}' already exists.",
            )

        supplier = Supplier(
            code=code,
            name=data.name.strip(),
            contact_name=data.contact_name.strip(),
            email=data.email.lower().strip(),
            phone=data.phone.strip() if data.phone else None,
            address=data.address.strip() if data.address else None,
            city=data.city.strip() if data.city else None,
            country=data.country.strip() if data.country else None,
            tax_id=data.tax_id.strip() if data.tax_id else None,
            payment_terms=(data.payment_terms or "Net 30").strip(),
            lead_time_days=data.lead_time_days,
            status=SupplierService._normalize_status(data.status),
            notes=data.notes.strip() if data.notes else None,
        )
        db.add(supplier)
        db.commit()
        db.refresh(supplier)
        return SupplierService._build_response(db, supplier, include_recent_pos=True)

    @staticmethod
    def update_supplier(db: Session, supplier_id: int, data: SupplierUpdate) -> SupplierResponse:
        supplier = db.scalar(select(Supplier).where(Supplier.id == supplier_id))
        if not supplier:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supplier #{supplier_id} not found.",
            )

        updates = data.model_dump(exclude_unset=True)
        if "code" in updates and updates["code"] is not None:
            new_code = updates["code"].strip().upper()
            conflict = db.scalar(
                select(Supplier).where(Supplier.code == new_code, Supplier.id != supplier.id)
            )
            if conflict:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Supplier code '{new_code}' is already in use.",
                )
            supplier.code = new_code
            updates.pop("code")

        if "status" in updates and updates["status"] is not None:
            supplier.status = SupplierService._normalize_status(updates.pop("status"))

        if "email" in updates and updates["email"] is not None:
            supplier.email = updates.pop("email").lower().strip()

        for field, value in updates.items():
            if isinstance(value, str):
                setattr(supplier, field, value.strip() or None)
            else:
                setattr(supplier, field, value)

        db.commit()
        db.refresh(supplier)
        return SupplierService._build_response(db, supplier, include_recent_pos=True)

    @staticmethod
    def delete_supplier(db: Session, supplier_id: int) -> None:
        supplier = db.scalar(select(Supplier).where(Supplier.id == supplier_id))
        if not supplier:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supplier #{supplier_id} not found.",
            )

        linked_po_count = (
            db.scalar(
                select(func.count(PurchaseOrder.id)).where(PurchaseOrder.supplier_id == supplier.id)
            )
            or 0
        )
        if linked_po_count > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Cannot delete supplier '{supplier.name}' because {linked_po_count} purchase "
                    "order(s) reference it. Mark the supplier Inactive instead."
                ),
            )

        db.delete(supplier)
        db.commit()
