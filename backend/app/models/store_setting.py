from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class StoreSetting(Base):
    """Singleton persisted store configuration managed from the admin portal."""

    __tablename__ = "store_settings"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    key: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        default="default",
        index=True,
    )

    # General store identity
    store_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        default="Blue Panda",
    )

    store_email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="support@bluepanda.com",
    )

    store_phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    store_address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    store_logo_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    currency: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="USD",
    )

    language: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="en",
    )

    timezone: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        default="Asia/Phnom_Penh",
    )

    # Appearance
    theme: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="light",
    )

    primary_color: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="#245BE7",
    )

    sidebar_style: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="default",
    )

    # Shipping rules
    free_shipping_min: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("100.00"),
    )

    standard_shipping_fee: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("2.00"),
    )

    express_shipping_fee: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("12.00"),
    )

    estimated_delivery_days: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="1-3",
    )

    # Supported payment methods
    enable_card_payment: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    enable_cod_payment: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Operational notification preferences
    notify_new_order: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    notify_low_stock: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    notify_customer_message: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    notify_weekly_report: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    updated_by_user_id: Mapped[int | None] = mapped_column(
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
        CheckConstraint("free_shipping_min >= 0", name="ck_store_settings_free_shipping_min_non_negative"),
        CheckConstraint("standard_shipping_fee >= 0", name="ck_store_settings_standard_fee_non_negative"),
        CheckConstraint("express_shipping_fee >= 0", name="ck_store_settings_express_fee_non_negative"),
    )
