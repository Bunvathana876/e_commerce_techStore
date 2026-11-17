"""Create idempotency_records table for robust duplicate-order protection.

Revision ID: e1f2a3b4c5d6
Revises: d7e8f9012abc
Create Date: 2026-11-16 19:15:00.000000

Adds idempotency_records table to enforce atomic request idempotency across
multiple production worker processes and withstand server restarts/crashes.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, Sequence[str], None] = 'd7e8f9012abc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'idempotency_records' not in existing_tables:
        op.create_table(
            'idempotency_records',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('key', sa.String(length=255), nullable=False),
            sa.Column('status', sa.String(length=30), server_default='processing', nullable=False),
            sa.Column('order_id', sa.Integer(), nullable=True),
            sa.Column('response_data', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_idempotency_records_user_id_users'), ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['order_id'], ['orders.id'], name=op.f('fk_idempotency_records_order_id_orders'), ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_idempotency_records')),
            sa.UniqueConstraint('user_id', 'key', name='uq_idempotency_records_user_key'),
        )
        op.create_index(op.f('ix_idempotency_records_user_id'), 'idempotency_records', ['user_id'], unique=False)
        op.create_index(op.f('ix_idempotency_records_key'), 'idempotency_records', ['key'], unique=False)
        op.create_index(op.f('ix_idempotency_records_order_id'), 'idempotency_records', ['order_id'], unique=False)
    else:
        indexes = {idx['name'] for idx in inspector.get_indexes('idempotency_records')}
        if 'ix_idempotency_records_user_id' not in indexes:
            op.create_index(op.f('ix_idempotency_records_user_id'), 'idempotency_records', ['user_id'], unique=False)
        if 'ix_idempotency_records_key' not in indexes:
            op.create_index(op.f('ix_idempotency_records_key'), 'idempotency_records', ['key'], unique=False)
        if 'ix_idempotency_records_order_id' not in indexes:
            op.create_index(op.f('ix_idempotency_records_order_id'), 'idempotency_records', ['order_id'], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'idempotency_records' in existing_tables:
        indexes = {idx['name'] for idx in inspector.get_indexes('idempotency_records')}
        if 'ix_idempotency_records_order_id' in indexes:
            op.drop_index(op.f('ix_idempotency_records_order_id'), table_name='idempotency_records')
        if 'ix_idempotency_records_key' in indexes:
            op.drop_index(op.f('ix_idempotency_records_key'), table_name='idempotency_records')
        if 'ix_idempotency_records_user_id' in indexes:
            op.drop_index(op.f('ix_idempotency_records_user_id'), table_name='idempotency_records')
        op.drop_table('idempotency_records')
