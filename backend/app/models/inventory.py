from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.supplier import Supplier
    from app.models.user import User


class Warehouse(Base):
    __tablename__ = "warehouses"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    code: Mapped[str] = mapped_column(
        String(40),
        unique=True,
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        nullable=False,
    )

    location: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    contact_name: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    contact_phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    stocks: Mapped[list["WarehouseStock"]] = relationship(
        "WarehouseStock",
        back_populates="warehouse",
    )


class WarehouseStock(Base):
    __tablename__ = "warehouse_stocks"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    reserved_quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    reorder_point: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("warehouse_id", "product_id", name="uq_warehouse_stocks_warehouse_product"),
        CheckConstraint("quantity >= 0", name="ck_warehouse_stocks_quantity_non_negative"),
        CheckConstraint("reserved_quantity >= 0", name="ck_warehouse_stocks_reserved_non_negative"),
        CheckConstraint("reorder_point >= 0", name="ck_warehouse_stocks_reorder_non_negative"),
    )

    warehouse: Mapped["Warehouse"] = relationship("Warehouse", back_populates="stocks")
    product: Mapped["Product"] = relationship("Product")


class InventoryJournalEntry(Base):
    __tablename__ = "inventory_journal_entries"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    entry_number: Mapped[str] = mapped_column(
        String(60),
        unique=True,
        nullable=False,
        index=True,
    )

    entry_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )  # opening_balance | purchase_receipt | order_sale | order_cancellation | refund_restock | transfer_out | transfer_in | transfer_cancel | adjustment

    reference_type: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
    )

    reference_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )

    reason: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # Plain snapshot ID (never ON DELETE SET NULL FK on immutable tables).
    created_by_user_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    lines: Mapped[list["InventoryLedgerLine"]] = relationship(
        "InventoryLedgerLine",
        back_populates="journal_entry",
    )


class InventoryLedgerLine(Base):
    __tablename__ = "inventory_ledger_lines"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    journal_entry_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_journal_entries.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Plain snapshot ID so product deletions never mutate immutable ledger history.
    product_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )

    product_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    warehouse_id: Mapped[int | None] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    account_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )  # warehouse_on_hand | supplier_clearing | customer_fulfillment | in_transit | inventory_adjustment

    debit_qty: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    credit_qty: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    balance_after: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint("debit_qty >= 0", name="ck_inventory_ledger_lines_debit_non_negative"),
        CheckConstraint("credit_qty >= 0", name="ck_inventory_ledger_lines_credit_non_negative"),
        CheckConstraint(
            "(debit_qty > 0 AND credit_qty = 0) OR (credit_qty > 0 AND debit_qty = 0)",
            name="ck_inventory_ledger_lines_single_side",
        ),
    )

    journal_entry: Mapped["InventoryJournalEntry"] = relationship(
        "InventoryJournalEntry",
        back_populates="lines",
    )
    warehouse: Mapped["Warehouse | None"] = relationship("Warehouse")


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    po_number: Mapped[str] = mapped_column(
        String(60),
        unique=True,
        nullable=False,
        index=True,
    )

    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="draft",  # draft | ordered | partially_received | received | cancelled
    )

    total_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    expected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    ordered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint("total_cost >= 0", name="ck_purchase_orders_total_cost_non_negative"),
    )

    supplier: Mapped["Supplier"] = relationship("Supplier", back_populates="purchase_orders")
    warehouse: Mapped["Warehouse"] = relationship("Warehouse")
    created_by: Mapped["User | None"] = relationship("User")
    items: Mapped[list["PurchaseOrderItem"]] = relationship(
        "PurchaseOrderItem",
        back_populates="purchase_order",
        cascade="all, delete-orphan",
    )


class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    purchase_order_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    product_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    quantity_ordered: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    quantity_received: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    line_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint("quantity_ordered > 0", name="ck_po_items_qty_ordered_positive"),
        CheckConstraint(
            "quantity_received >= 0 AND quantity_received <= quantity_ordered",
            name="ck_po_items_qty_received_valid",
        ),
        CheckConstraint("unit_cost >= 0", name="ck_po_items_unit_cost_non_negative"),
        CheckConstraint("line_total >= 0", name="ck_po_items_line_total_non_negative"),
    )

    purchase_order: Mapped["PurchaseOrder"] = relationship("PurchaseOrder", back_populates="items")
    product: Mapped["Product | None"] = relationship("Product")


class WarehouseTransfer(Base):
    __tablename__ = "warehouse_transfers"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    transfer_number: Mapped[str] = mapped_column(
        String(60),
        unique=True,
        nullable=False,
        index=True,
    )

    source_warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    destination_warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="draft",  # draft | in_transit | completed | cancelled
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    dispatched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "source_warehouse_id != destination_warehouse_id",
            name="ck_warehouse_transfers_distinct_warehouses",
        ),
    )

    source_warehouse: Mapped["Warehouse"] = relationship(
        "Warehouse",
        foreign_keys=[source_warehouse_id],
    )
    destination_warehouse: Mapped["Warehouse"] = relationship(
        "Warehouse",
        foreign_keys=[destination_warehouse_id],
    )
    created_by: Mapped["User | None"] = relationship("User")
    items: Mapped[list["WarehouseTransferItem"]] = relationship(
        "WarehouseTransferItem",
        back_populates="transfer",
        cascade="all, delete-orphan",
    )


class WarehouseTransferItem(Base):
    __tablename__ = "warehouse_transfer_items"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    transfer_id: Mapped[int] = mapped_column(
        ForeignKey("warehouse_transfers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    product_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_transfer_items_qty_positive"),
    )

    transfer: Mapped["WarehouseTransfer"] = relationship(
        "WarehouseTransfer",
        back_populates="items",
    )
    product: Mapped["Product | None"] = relationship("Product")


def _reject_immutable_inventory_mutation(*_args, **_kwargs) -> None:
    raise ValueError("Inventory ledger entries are immutable and cannot be modified or deleted.")


for _immutable_cls in (InventoryJournalEntry, InventoryLedgerLine):
    event.listen(_immutable_cls, "before_update", _reject_immutable_inventory_mutation)
    event.listen(_immutable_cls, "before_delete", _reject_immutable_inventory_mutation)
