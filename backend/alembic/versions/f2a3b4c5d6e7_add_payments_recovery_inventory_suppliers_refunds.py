"""Add digital payments, account recovery, multi-warehouse inventory ledger, suppliers, and refund ledger tables.

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-11-23 11:05:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2a3b4c5d6e7'
down_revision: Union[str, Sequence[str], None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


IMMUTABLE_TABLES = (
    'inventory_journal_entries',
    'inventory_ledger_lines',
    'refund_ledger_entries',
)


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    # 1. password_reset_tokens
    if 'password_reset_tokens' not in existing_tables:
        op.create_table(
            'password_reset_tokens',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('token_hash', sa.String(length=64), nullable=False),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('is_revoked', sa.Boolean(), server_default=sa.text('false'), nullable=False),
            sa.Column('requested_ip', sa.String(length=64), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_password_reset_tokens_user_id_users'), ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_password_reset_tokens')),
        )
        op.create_index(op.f('ix_password_reset_tokens_user_id'), 'password_reset_tokens', ['user_id'], unique=False)
        op.create_index(op.f('ix_password_reset_tokens_token_hash'), 'password_reset_tokens', ['token_hash'], unique=True)
        op.create_index(op.f('ix_password_reset_tokens_expires_at'), 'password_reset_tokens', ['expires_at'], unique=False)

    # 2. payment_transactions
    if 'payment_transactions' not in existing_tables:
        op.create_table(
            'payment_transactions',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('transaction_ref', sa.String(length=60), nullable=False),
            sa.Column('order_id', sa.Integer(), nullable=False),
            sa.Column('provider', sa.String(length=40), server_default='cod', nullable=False),
            sa.Column('payment_method', sa.String(length=50), nullable=False),
            sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
            sa.Column('currency', sa.String(length=10), server_default='USD', nullable=False),
            sa.Column('status', sa.String(length=30), server_default='pending', nullable=False),
            sa.Column('provider_reference', sa.String(length=120), nullable=True),
            sa.Column('card_brand', sa.String(length=30), nullable=True),
            sa.Column('card_last4', sa.String(length=4), nullable=True),
            sa.Column('failure_reason', sa.String(length=500), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.CheckConstraint('amount >= 0', name='ck_payment_transactions_amount_non_negative'),
            sa.ForeignKeyConstraint(['order_id'], ['orders.id'], name=op.f('fk_payment_transactions_order_id_orders'), ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_payment_transactions')),
        )
        op.create_index(op.f('ix_payment_transactions_transaction_ref'), 'payment_transactions', ['transaction_ref'], unique=True)
        op.create_index(op.f('ix_payment_transactions_order_id'), 'payment_transactions', ['order_id'], unique=False)
        op.create_index(op.f('ix_payment_transactions_provider_reference'), 'payment_transactions', ['provider_reference'], unique=False)

    # 3. suppliers
    if 'suppliers' not in existing_tables:
        op.create_table(
            'suppliers',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('code', sa.String(length=40), nullable=False),
            sa.Column('name', sa.String(length=150), nullable=False),
            sa.Column('contact_name', sa.String(length=120), nullable=False),
            sa.Column('email', sa.String(length=255), nullable=False),
            sa.Column('phone', sa.String(length=50), nullable=True),
            sa.Column('address', sa.Text(), nullable=True),
            sa.Column('city', sa.String(length=100), nullable=True),
            sa.Column('country', sa.String(length=100), nullable=True),
            sa.Column('tax_id', sa.String(length=80), nullable=True),
            sa.Column('payment_terms', sa.String(length=80), server_default='Net 30', nullable=False),
            sa.Column('lead_time_days', sa.Integer(), server_default='7', nullable=False),
            sa.Column('status', sa.String(length=20), server_default='Active', nullable=False),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.CheckConstraint('lead_time_days >= 0', name='ck_suppliers_lead_time_non_negative'),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_suppliers')),
        )
        op.create_index(op.f('ix_suppliers_code'), 'suppliers', ['code'], unique=True)
        op.create_index(op.f('ix_suppliers_name'), 'suppliers', ['name'], unique=False)
        op.create_index(op.f('ix_suppliers_email'), 'suppliers', ['email'], unique=False)

    # 4. warehouses
    if 'warehouses' not in existing_tables:
        op.create_table(
            'warehouses',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('code', sa.String(length=40), nullable=False),
            sa.Column('name', sa.String(length=150), nullable=False),
            sa.Column('location', sa.String(length=255), nullable=True),
            sa.Column('address', sa.Text(), nullable=True),
            sa.Column('contact_name', sa.String(length=120), nullable=True),
            sa.Column('contact_phone', sa.String(length=50), nullable=True),
            sa.Column('is_default', sa.Boolean(), server_default=sa.text('false'), nullable=False),
            sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_warehouses')),
            sa.UniqueConstraint('name', name=op.f('uq_warehouses_name')),
        )
        op.create_index(op.f('ix_warehouses_code'), 'warehouses', ['code'], unique=True)

    # 5. warehouse_stocks
    if 'warehouse_stocks' not in existing_tables:
        op.create_table(
            'warehouse_stocks',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('warehouse_id', sa.Integer(), nullable=False),
            sa.Column('product_id', sa.Integer(), nullable=False),
            sa.Column('quantity', sa.Integer(), server_default='0', nullable=False),
            sa.Column('reserved_quantity', sa.Integer(), server_default='0', nullable=False),
            sa.Column('reorder_point', sa.Integer(), server_default='10', nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.CheckConstraint('quantity >= 0', name='ck_warehouse_stocks_quantity_non_negative'),
            sa.CheckConstraint('reserved_quantity >= 0', name='ck_warehouse_stocks_reserved_non_negative'),
            sa.CheckConstraint('reorder_point >= 0', name='ck_warehouse_stocks_reorder_non_negative'),
            sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.id'], name=op.f('fk_warehouse_stocks_warehouse_id_warehouses'), ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('fk_warehouse_stocks_product_id_products'), ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_warehouse_stocks')),
            sa.UniqueConstraint('warehouse_id', 'product_id', name='uq_warehouse_stocks_warehouse_product'),
        )
        op.create_index(op.f('ix_warehouse_stocks_warehouse_id'), 'warehouse_stocks', ['warehouse_id'], unique=False)
        op.create_index(op.f('ix_warehouse_stocks_product_id'), 'warehouse_stocks', ['product_id'], unique=False)

    # 6. inventory_journal_entries
    if 'inventory_journal_entries' not in existing_tables:
        op.create_table(
            'inventory_journal_entries',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('entry_number', sa.String(length=60), nullable=False),
            sa.Column('entry_type', sa.String(length=40), nullable=False),
            sa.Column('reference_type', sa.String(length=40), nullable=True),
            sa.Column('reference_id', sa.Integer(), nullable=True),
            sa.Column('reason', sa.String(length=500), nullable=True),
            sa.Column('created_by_user_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_inventory_journal_entries')),
        )
        op.create_index(op.f('ix_inventory_journal_entries_entry_number'), 'inventory_journal_entries', ['entry_number'], unique=True)
        op.create_index(op.f('ix_inventory_journal_entries_reference_id'), 'inventory_journal_entries', ['reference_id'], unique=False)

    # 7. inventory_ledger_lines
    if 'inventory_ledger_lines' not in existing_tables:
        op.create_table(
            'inventory_ledger_lines',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('journal_entry_id', sa.Integer(), nullable=False),
            sa.Column('product_id', sa.Integer(), nullable=False),
            sa.Column('product_name', sa.String(length=200), nullable=False),
            sa.Column('warehouse_id', sa.Integer(), nullable=True),
            sa.Column('account_type', sa.String(length=40), nullable=False),
            sa.Column('debit_qty', sa.Integer(), server_default='0', nullable=False),
            sa.Column('credit_qty', sa.Integer(), server_default='0', nullable=False),
            sa.Column('unit_cost', sa.Numeric(precision=10, scale=2), server_default='0.00', nullable=False),
            sa.Column('balance_after', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.CheckConstraint('debit_qty >= 0', name='ck_inventory_ledger_lines_debit_non_negative'),
            sa.CheckConstraint('credit_qty >= 0', name='ck_inventory_ledger_lines_credit_non_negative'),
            sa.CheckConstraint(
                '(debit_qty > 0 AND credit_qty = 0) OR (credit_qty > 0 AND debit_qty = 0)',
                name='ck_inventory_ledger_lines_single_side',
            ),
            sa.ForeignKeyConstraint(['journal_entry_id'], ['inventory_journal_entries.id'], name=op.f('fk_inventory_ledger_lines_journal_entry_id_inventory_journal_entries'), ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.id'], name=op.f('fk_inventory_ledger_lines_warehouse_id_warehouses'), ondelete='RESTRICT'),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_inventory_ledger_lines')),
        )
        op.create_index(op.f('ix_inventory_ledger_lines_journal_entry_id'), 'inventory_ledger_lines', ['journal_entry_id'], unique=False)
        op.create_index(op.f('ix_inventory_ledger_lines_product_id'), 'inventory_ledger_lines', ['product_id'], unique=False)
        op.create_index(op.f('ix_inventory_ledger_lines_warehouse_id'), 'inventory_ledger_lines', ['warehouse_id'], unique=False)

    # 8. purchase_orders
    if 'purchase_orders' not in existing_tables:
        op.create_table(
            'purchase_orders',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('po_number', sa.String(length=60), nullable=False),
            sa.Column('supplier_id', sa.Integer(), nullable=False),
            sa.Column('warehouse_id', sa.Integer(), nullable=False),
            sa.Column('status', sa.String(length=30), server_default='draft', nullable=False),
            sa.Column('total_cost', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False),
            sa.Column('expected_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('ordered_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('received_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('created_by_user_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.CheckConstraint('total_cost >= 0', name='ck_purchase_orders_total_cost_non_negative'),
            sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id'], name=op.f('fk_purchase_orders_supplier_id_suppliers'), ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.id'], name=op.f('fk_purchase_orders_warehouse_id_warehouses'), ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], name=op.f('fk_purchase_orders_created_by_user_id_users'), ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_purchase_orders')),
        )
        op.create_index(op.f('ix_purchase_orders_po_number'), 'purchase_orders', ['po_number'], unique=True)
        op.create_index(op.f('ix_purchase_orders_supplier_id'), 'purchase_orders', ['supplier_id'], unique=False)
        op.create_index(op.f('ix_purchase_orders_warehouse_id'), 'purchase_orders', ['warehouse_id'], unique=False)

    # 9. purchase_order_items
    if 'purchase_order_items' not in existing_tables:
        op.create_table(
            'purchase_order_items',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('purchase_order_id', sa.Integer(), nullable=False),
            sa.Column('product_id', sa.Integer(), nullable=True),
            sa.Column('product_name', sa.String(length=200), nullable=False),
            sa.Column('quantity_ordered', sa.Integer(), nullable=False),
            sa.Column('quantity_received', sa.Integer(), server_default='0', nullable=False),
            sa.Column('unit_cost', sa.Numeric(precision=10, scale=2), nullable=False),
            sa.Column('line_total', sa.Numeric(precision=12, scale=2), nullable=False),
            sa.CheckConstraint('quantity_ordered > 0', name='ck_po_items_qty_ordered_positive'),
            sa.CheckConstraint('quantity_received >= 0 AND quantity_received <= quantity_ordered', name='ck_po_items_qty_received_valid'),
            sa.CheckConstraint('unit_cost >= 0', name='ck_po_items_unit_cost_non_negative'),
            sa.CheckConstraint('line_total >= 0', name='ck_po_items_line_total_non_negative'),
            sa.ForeignKeyConstraint(['purchase_order_id'], ['purchase_orders.id'], name=op.f('fk_purchase_order_items_purchase_order_id_purchase_orders'), ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('fk_purchase_order_items_product_id_products'), ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_purchase_order_items')),
        )
        op.create_index(op.f('ix_purchase_order_items_purchase_order_id'), 'purchase_order_items', ['purchase_order_id'], unique=False)
        op.create_index(op.f('ix_purchase_order_items_product_id'), 'purchase_order_items', ['product_id'], unique=False)

    # 10. warehouse_transfers
    if 'warehouse_transfers' not in existing_tables:
        op.create_table(
            'warehouse_transfers',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('transfer_number', sa.String(length=60), nullable=False),
            sa.Column('source_warehouse_id', sa.Integer(), nullable=False),
            sa.Column('destination_warehouse_id', sa.Integer(), nullable=False),
            sa.Column('status', sa.String(length=30), server_default='draft', nullable=False),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('created_by_user_id', sa.Integer(), nullable=True),
            sa.Column('dispatched_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.CheckConstraint('source_warehouse_id != destination_warehouse_id', name='ck_warehouse_transfers_distinct_warehouses'),
            sa.ForeignKeyConstraint(['source_warehouse_id'], ['warehouses.id'], name=op.f('fk_warehouse_transfers_source_warehouse_id_warehouses'), ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(['destination_warehouse_id'], ['warehouses.id'], name=op.f('fk_warehouse_transfers_destination_warehouse_id_warehouses'), ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], name=op.f('fk_warehouse_transfers_created_by_user_id_users'), ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_warehouse_transfers')),
        )
        op.create_index(op.f('ix_warehouse_transfers_transfer_number'), 'warehouse_transfers', ['transfer_number'], unique=True)
        op.create_index(op.f('ix_warehouse_transfers_source_warehouse_id'), 'warehouse_transfers', ['source_warehouse_id'], unique=False)
        op.create_index(op.f('ix_warehouse_transfers_destination_warehouse_id'), 'warehouse_transfers', ['destination_warehouse_id'], unique=False)

    # 11. warehouse_transfer_items
    if 'warehouse_transfer_items' not in existing_tables:
        op.create_table(
            'warehouse_transfer_items',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('transfer_id', sa.Integer(), nullable=False),
            sa.Column('product_id', sa.Integer(), nullable=True),
            sa.Column('product_name', sa.String(length=200), nullable=False),
            sa.Column('quantity', sa.Integer(), nullable=False),
            sa.CheckConstraint('quantity > 0', name='ck_transfer_items_qty_positive'),
            sa.ForeignKeyConstraint(['transfer_id'], ['warehouse_transfers.id'], name=op.f('fk_warehouse_transfer_items_transfer_id_warehouse_transfers'), ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('fk_warehouse_transfer_items_product_id_products'), ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_warehouse_transfer_items')),
        )
        op.create_index(op.f('ix_warehouse_transfer_items_transfer_id'), 'warehouse_transfer_items', ['transfer_id'], unique=False)
        op.create_index(op.f('ix_warehouse_transfer_items_product_id'), 'warehouse_transfer_items', ['product_id'], unique=False)

    # 12. refunds
    if 'refunds' not in existing_tables:
        op.create_table(
            'refunds',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('refund_number', sa.String(length=60), nullable=False),
            sa.Column('order_id', sa.Integer(), nullable=False),
            sa.Column('customer_id', sa.Integer(), nullable=True),
            sa.Column('requested_by_user_id', sa.Integer(), nullable=True),
            sa.Column('processed_by_user_id', sa.Integer(), nullable=True),
            sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
            sa.Column('currency', sa.String(length=10), server_default='USD', nullable=False),
            sa.Column('refund_method', sa.String(length=50), nullable=False),
            sa.Column('status', sa.String(length=30), server_default='requested', nullable=False),
            sa.Column('reason', sa.String(length=500), nullable=False),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('restock_items', sa.Boolean(), server_default=sa.text('false'), nullable=False),
            sa.Column('restocked', sa.Boolean(), server_default=sa.text('false'), nullable=False),
            sa.Column('warehouse_id', sa.Integer(), nullable=True),
            sa.Column('external_reference', sa.String(length=120), nullable=True),
            sa.Column('requested_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.CheckConstraint('amount > 0', name='ck_refunds_amount_positive'),
            sa.ForeignKeyConstraint(['order_id'], ['orders.id'], name=op.f('fk_refunds_order_id_orders'), ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(['customer_id'], ['users.id'], name=op.f('fk_refunds_customer_id_users'), ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['requested_by_user_id'], ['users.id'], name=op.f('fk_refunds_requested_by_user_id_users'), ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['processed_by_user_id'], ['users.id'], name=op.f('fk_refunds_processed_by_user_id_users'), ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.id'], name=op.f('fk_refunds_warehouse_id_warehouses'), ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_refunds')),
        )
        op.create_index(op.f('ix_refunds_refund_number'), 'refunds', ['refund_number'], unique=True)
        op.create_index(op.f('ix_refunds_order_id'), 'refunds', ['order_id'], unique=False)
        op.create_index(op.f('ix_refunds_customer_id'), 'refunds', ['customer_id'], unique=False)

    # 13. refund_ledger_entries
    if 'refund_ledger_entries' not in existing_tables:
        op.create_table(
            'refund_ledger_entries',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('journal_ref', sa.String(length=60), nullable=False),
            sa.Column('refund_id', sa.Integer(), nullable=False),
            sa.Column('order_id', sa.Integer(), nullable=False),
            sa.Column('entry_type', sa.String(length=40), nullable=False),
            sa.Column('account_code', sa.String(length=20), nullable=False),
            sa.Column('account_name', sa.String(length=100), nullable=False),
            sa.Column('debit_amount', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False),
            sa.Column('credit_amount', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False),
            sa.Column('currency', sa.String(length=10), server_default='USD', nullable=False),
            sa.Column('memo', sa.String(length=500), nullable=True),
            sa.Column('created_by_user_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.CheckConstraint('debit_amount >= 0', name='ck_refund_ledger_entries_debit_non_negative'),
            sa.CheckConstraint('credit_amount >= 0', name='ck_refund_ledger_entries_credit_non_negative'),
            sa.CheckConstraint(
                '(debit_amount > 0 AND credit_amount = 0) OR (credit_amount > 0 AND debit_amount = 0)',
                name='ck_refund_ledger_entries_single_side',
            ),
            sa.ForeignKeyConstraint(['refund_id'], ['refunds.id'], name=op.f('fk_refund_ledger_entries_refund_id_refunds'), ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(['order_id'], ['orders.id'], name=op.f('fk_refund_ledger_entries_order_id_orders'), ondelete='RESTRICT'),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_refund_ledger_entries')),
        )
        op.create_index(op.f('ix_refund_ledger_entries_journal_ref'), 'refund_ledger_entries', ['journal_ref'], unique=False)
        op.create_index(op.f('ix_refund_ledger_entries_refund_id'), 'refund_ledger_entries', ['refund_id'], unique=False)
        op.create_index(op.f('ix_refund_ledger_entries_order_id'), 'refund_ledger_entries', ['order_id'], unique=False)

    # PostgreSQL-level immutability triggers for double-entry inventory and refund ledgers
    if conn.dialect.name == 'postgresql':
        op.execute(sa.text("""
            CREATE OR REPLACE FUNCTION prevent_immutable_ledger_mutation()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'Ledger table % is immutable and cannot be modified or deleted.', TG_TABLE_NAME;
            END;
            $$ LANGUAGE plpgsql;
        """))
        for table_name in IMMUTABLE_TABLES:
            trigger_name = f"trg_immutable_{table_name}"
            op.execute(sa.text(f"DROP TRIGGER IF EXISTS {trigger_name} ON {table_name};"))
            op.execute(sa.text(f"""
                CREATE TRIGGER {trigger_name}
                BEFORE UPDATE OR DELETE ON {table_name}
                FOR EACH ROW
                EXECUTE FUNCTION prevent_immutable_ledger_mutation();
            """))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if conn.dialect.name == 'postgresql':
        for table_name in IMMUTABLE_TABLES:
            if table_name in existing_tables:
                op.execute(sa.text(f"DROP TRIGGER IF EXISTS trg_immutable_{table_name} ON {table_name};"))
        op.execute(sa.text("DROP FUNCTION IF EXISTS prevent_immutable_ledger_mutation();"))

    drop_order = [
        'refund_ledger_entries',
        'refunds',
        'warehouse_transfer_items',
        'warehouse_transfers',
        'purchase_order_items',
        'purchase_orders',
        'inventory_ledger_lines',
        'inventory_journal_entries',
        'warehouse_stocks',
        'warehouses',
        'suppliers',
        'payment_transactions',
        'password_reset_tokens',
    ]
    for table_name in drop_order:
        if table_name in existing_tables:
            op.drop_table(table_name)
