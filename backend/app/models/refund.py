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
    event,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.models.inventory import Warehouse
    from app.models.order import Order
    from app.models.user import User


class Refund(Base):
    __tablename__ = "refunds"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    refund_number: Mapped[str] = mapped_column(
        String(60),
        unique=True,
        nullable=False,
        index=True,
    )

    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    requested_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    processed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="USD",
    )

    refund_method: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="requested",  # requested | approved | processed | rejected
    )

    reason: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    restock_items: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    restocked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    warehouse_id: Mapped[int | None] = mapped_column(
        ForeignKey("warehouses.id", ondelete="SET NULL"),
        nullable=True,
    )

    external_reference: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    processed_at: Mapped[datetime | None] = mapped_column(
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
        CheckConstraint("amount > 0", name="ck_refunds_amount_positive"),
    )

    order: Mapped["Order"] = relationship("Order")
    customer: Mapped["User | None"] = relationship("User", foreign_keys=[customer_id])
    requested_by: Mapped["User | None"] = relationship("User", foreign_keys=[requested_by_user_id])
    processed_by: Mapped["User | None"] = relationship("User", foreign_keys=[processed_by_user_id])
    warehouse: Mapped["Warehouse | None"] = relationship("Warehouse")
    ledger_entries: Mapped[list["RefundLedgerEntry"]] = relationship(
        "RefundLedgerEntry",
        back_populates="refund",
    )


class RefundLedgerEntry(Base):
    __tablename__ = "refund_ledger_entries"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    journal_ref: Mapped[str] = mapped_column(
        String(60),
        nullable=False,
        index=True,
    )

    refund_id: Mapped[int] = mapped_column(
        ForeignKey("refunds.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    entry_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )  # refund_accrual | refund_settlement | refund_reversal

    account_code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )  # 4100 | 2100 | 1010 | 1020

    account_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    debit_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    credit_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    currency: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="USD",
    )

    memo: Mapped[str | None] = mapped_column(
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

    __table_args__ = (
        CheckConstraint("debit_amount >= 0", name="ck_refund_ledger_entries_debit_non_negative"),
        CheckConstraint("credit_amount >= 0", name="ck_refund_ledger_entries_credit_non_negative"),
        CheckConstraint(
            "(debit_amount > 0 AND credit_amount = 0) OR (credit_amount > 0 AND debit_amount = 0)",
            name="ck_refund_ledger_entries_single_side",
        ),
    )

    refund: Mapped["Refund"] = relationship("Refund", back_populates="ledger_entries")
    order: Mapped["Order"] = relationship("Order")


def _reject_immutable_refund_ledger_mutation(*_args, **_kwargs) -> None:
    raise ValueError("Refund accounting ledger entries are immutable and cannot be modified or deleted.")


event.listen(RefundLedgerEntry, "before_update", _reject_immutable_refund_ledger_mutation)
event.listen(RefundLedgerEntry, "before_delete", _reject_immutable_refund_ledger_mutation)
