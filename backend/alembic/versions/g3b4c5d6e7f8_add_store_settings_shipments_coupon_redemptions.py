"""Add store_settings, order_shipments, order_tracking_events, and coupon_redemptions.

Revision ID: g3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-11-23 12:05:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "g3b4c5d6e7f8"
down_revision: Union[str, Sequence[str], None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    # 1. coupons.per_user_limit column + constraint
    if "coupons" in existing_tables:
        coupon_cols = {c["name"] for c in inspector.get_columns("coupons")}
        if "per_user_limit" not in coupon_cols:
            op.add_column(
                "coupons",
                sa.Column("per_user_limit", sa.Integer(), nullable=True),
            )
        coupon_checks = {ck["name"] for ck in inspector.get_check_constraints("coupons")}
        if "ck_coupons_per_user_limit_positive" not in coupon_checks:
            if conn.dialect.name == "sqlite":
                with op.batch_alter_table("coupons") as batch_op:
                    batch_op.create_check_constraint(
                        "ck_coupons_per_user_limit_positive",
                        "per_user_limit IS NULL OR per_user_limit > 0",
                    )
            else:
                op.create_check_constraint(
                    "ck_coupons_per_user_limit_positive",
                    "coupons",
                    "per_user_limit IS NULL OR per_user_limit > 0",
                )

    # 2. coupon_redemptions
    if "coupon_redemptions" not in existing_tables:
        op.create_table(
            "coupon_redemptions",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("coupon_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("order_id", sa.Integer(), nullable=False),
            sa.Column(
                "redeemed_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()") if conn.dialect.name == "postgresql" else sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["coupon_id"],
                ["coupons.id"],
                name=op.f("fk_coupon_redemptions_coupon_id_coupons"),
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["users.id"],
                name=op.f("fk_coupon_redemptions_user_id_users"),
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["order_id"],
                ["orders.id"],
                name=op.f("fk_coupon_redemptions_order_id_orders"),
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_coupon_redemptions")),
        )
        op.create_index(op.f("ix_coupon_redemptions_coupon_id"), "coupon_redemptions", ["coupon_id"], unique=False)
        op.create_index(op.f("ix_coupon_redemptions_user_id"), "coupon_redemptions", ["user_id"], unique=False)
        op.create_index(op.f("ix_coupon_redemptions_order_id"), "coupon_redemptions", ["order_id"], unique=True)

    # 3. store_settings
    if "store_settings" not in existing_tables:
        now_default = (
            sa.text("now()") if conn.dialect.name == "postgresql" else sa.text("CURRENT_TIMESTAMP")
        )
        op.create_table(
            "store_settings",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("key", sa.String(length=50), server_default="default", nullable=False),
            sa.Column("store_name", sa.String(length=150), server_default="Blue Panda", nullable=False),
            sa.Column("store_email", sa.String(length=255), server_default="support@bluepanda.com", nullable=False),
            sa.Column("store_phone", sa.String(length=50), nullable=True),
            sa.Column("store_address", sa.Text(), nullable=True),
            sa.Column("store_logo_url", sa.String(length=500), nullable=True),
            sa.Column("currency", sa.String(length=10), server_default="USD", nullable=False),
            sa.Column("language", sa.String(length=20), server_default="en", nullable=False),
            sa.Column("timezone", sa.String(length=80), server_default="Asia/Phnom_Penh", nullable=False),
            sa.Column("theme", sa.String(length=30), server_default="light", nullable=False),
            sa.Column("primary_color", sa.String(length=20), server_default="#245BE7", nullable=False),
            sa.Column("sidebar_style", sa.String(length=30), server_default="default", nullable=False),
            sa.Column("free_shipping_min", sa.Numeric(precision=10, scale=2), server_default="100.00", nullable=False),
            sa.Column("standard_shipping_fee", sa.Numeric(precision=10, scale=2), server_default="2.00", nullable=False),
            sa.Column("express_shipping_fee", sa.Numeric(precision=10, scale=2), server_default="12.00", nullable=False),
            sa.Column("estimated_delivery_days", sa.String(length=50), server_default="1-3", nullable=False),
            sa.Column("enable_card_payment", sa.Boolean(), server_default=sa.text("true"), nullable=False),
            sa.Column("enable_cod_payment", sa.Boolean(), server_default=sa.text("true"), nullable=False),
            sa.Column("notify_new_order", sa.Boolean(), server_default=sa.text("true"), nullable=False),
            sa.Column("notify_low_stock", sa.Boolean(), server_default=sa.text("true"), nullable=False),
            sa.Column("notify_customer_message", sa.Boolean(), server_default=sa.text("true"), nullable=False),
            sa.Column("notify_weekly_report", sa.Boolean(), server_default=sa.text("false"), nullable=False),
            sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=now_default, nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=now_default, nullable=False),
            sa.CheckConstraint("free_shipping_min >= 0", name="ck_store_settings_free_shipping_min_non_negative"),
            sa.CheckConstraint("standard_shipping_fee >= 0", name="ck_store_settings_standard_fee_non_negative"),
            sa.CheckConstraint("express_shipping_fee >= 0", name="ck_store_settings_express_fee_non_negative"),
            sa.ForeignKeyConstraint(
                ["updated_by_user_id"],
                ["users.id"],
                name=op.f("fk_store_settings_updated_by_user_id_users"),
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_store_settings")),
        )
        op.create_index(op.f("ix_store_settings_key"), "store_settings", ["key"], unique=True)

    # 4. order_shipments
    if "order_shipments" not in existing_tables:
        now_default = (
            sa.text("now()") if conn.dialect.name == "postgresql" else sa.text("CURRENT_TIMESTAMP")
        )
        op.create_table(
            "order_shipments",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("order_id", sa.Integer(), nullable=False),
            sa.Column("carrier", sa.String(length=100), server_default="Blue Panda Express", nullable=False),
            sa.Column("tracking_number", sa.String(length=120), nullable=True),
            sa.Column("tracking_url", sa.String(length=500), nullable=True),
            sa.Column("status", sa.String(length=40), server_default="pending", nullable=False),
            sa.Column("estimated_delivery_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("shipped_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=now_default, nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=now_default, nullable=False),
            sa.ForeignKeyConstraint(
                ["order_id"],
                ["orders.id"],
                name=op.f("fk_order_shipments_order_id_orders"),
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["updated_by_user_id"],
                ["users.id"],
                name=op.f("fk_order_shipments_updated_by_user_id_users"),
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_order_shipments")),
        )
        op.create_index(op.f("ix_order_shipments_order_id"), "order_shipments", ["order_id"], unique=True)
        op.create_index(op.f("ix_order_shipments_tracking_number"), "order_shipments", ["tracking_number"], unique=False)

    # 5. order_tracking_events
    if "order_tracking_events" not in existing_tables:
        now_default = (
            sa.text("now()") if conn.dialect.name == "postgresql" else sa.text("CURRENT_TIMESTAMP")
        )
        op.create_table(
            "order_tracking_events",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("shipment_id", sa.Integer(), nullable=False),
            sa.Column("order_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=40), nullable=False),
            sa.Column("title", sa.String(length=160), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("location", sa.String(length=160), nullable=True),
            sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=now_default, nullable=False),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(
                ["shipment_id"],
                ["order_shipments.id"],
                name=op.f("fk_order_tracking_events_shipment_id_order_shipments"),
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["order_id"],
                ["orders.id"],
                name=op.f("fk_order_tracking_events_order_id_orders"),
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["created_by_user_id"],
                ["users.id"],
                name=op.f("fk_order_tracking_events_created_by_user_id_users"),
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_order_tracking_events")),
        )
        op.create_index(op.f("ix_order_tracking_events_shipment_id"), "order_tracking_events", ["shipment_id"], unique=False)
        op.create_index(op.f("ix_order_tracking_events_order_id"), "order_tracking_events", ["order_id"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    for table_name in (
        "order_tracking_events",
        "order_shipments",
        "store_settings",
        "coupon_redemptions",
    ):
        if table_name in existing_tables:
            op.drop_table(table_name)

    if "coupons" in existing_tables:
        coupon_checks = {ck["name"] for ck in inspector.get_check_constraints("coupons")}
        if "ck_coupons_per_user_limit_positive" in coupon_checks:
            if conn.dialect.name == "sqlite":
                with op.batch_alter_table("coupons") as batch_op:
                    batch_op.drop_constraint("ck_coupons_per_user_limit_positive", type_="check")
            else:
                op.drop_constraint("ck_coupons_per_user_limit_positive", "coupons", type_="check")
        coupon_cols = {c["name"] for c in inspector.get_columns("coupons")}
        if "per_user_limit" in coupon_cols:
            op.drop_column("coupons", "per_user_limit")
