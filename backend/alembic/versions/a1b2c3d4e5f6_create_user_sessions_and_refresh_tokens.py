"""create_user_sessions_and_refresh_tokens

Revision ID: a1b2c3d4e5f6
Revises: c4b8d91a2e3f
Create Date: 2026-11-04 07:30:00.000000

Adds user_sessions and refresh_tokens tables to support stateful session management,
atomic single-use refresh token rotation, and replay breach detection.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'c4b8d91a2e3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    # =========================================================================
    # 1. Table: user_sessions (Parent session entity)
    # =========================================================================
    if 'user_sessions' not in existing_tables:
        op.create_table(
            'user_sessions',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('session_id', sa.String(length=36), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('token_family', sa.String(length=36), nullable=False),
            sa.Column('ip_address', sa.String(length=45), nullable=True),
            sa.Column('user_agent', sa.String(length=255), nullable=True),
            sa.Column('device_name', sa.String(length=100), nullable=True),
            sa.Column('is_revoked', sa.Boolean(), nullable=False, server_default=sa.text('false')),
            sa.Column('revoked_reason', sa.String(length=50), nullable=True),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('last_activity_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_user_sessions_user_id_users'), ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_user_sessions')),
        )
        op.create_index(op.f('ix_user_sessions_session_id'), 'user_sessions', ['session_id'], unique=True)
        op.create_index(op.f('ix_user_sessions_user_id'), 'user_sessions', ['user_id'], unique=False)
        op.create_index(op.f('ix_user_sessions_token_family'), 'user_sessions', ['token_family'], unique=False)
        op.create_index(op.f('ix_user_sessions_expires_at'), 'user_sessions', ['expires_at'], unique=False)
    else:
        # Table exists: verify indexes & constraints
        session_indexes = {idx['name'] for idx in inspector.get_indexes('user_sessions')}
        if 'ix_user_sessions_session_id' not in session_indexes:
            op.create_index(op.f('ix_user_sessions_session_id'), 'user_sessions', ['session_id'], unique=True)
        if 'ix_user_sessions_user_id' not in session_indexes:
            op.create_index(op.f('ix_user_sessions_user_id'), 'user_sessions', ['user_id'], unique=False)
        if 'ix_user_sessions_token_family' not in session_indexes:
            op.create_index(op.f('ix_user_sessions_token_family'), 'user_sessions', ['token_family'], unique=False)
        if 'ix_user_sessions_expires_at' not in session_indexes:
            op.create_index(op.f('ix_user_sessions_expires_at'), 'user_sessions', ['expires_at'], unique=False)

    # =========================================================================
    # 2. Table: refresh_tokens (Child rotation & history records)
    # =========================================================================
    if 'refresh_tokens' not in existing_tables:
        op.create_table(
            'refresh_tokens',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('session_id', sa.String(length=36), nullable=False),
            sa.Column('token_hash', sa.String(length=64), nullable=False),
            sa.Column('parent_token_hash', sa.String(length=64), nullable=True),
            sa.Column('is_revoked', sa.Boolean(), nullable=False, server_default=sa.text('false')),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['session_id'], ['user_sessions.session_id'], name=op.f('fk_refresh_tokens_session_id_user_sessions'), ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_refresh_tokens')),
        )
        op.create_index(op.f('ix_refresh_tokens_session_id'), 'refresh_tokens', ['session_id'], unique=False)
        op.create_index(op.f('ix_refresh_tokens_token_hash'), 'refresh_tokens', ['token_hash'], unique=True)
        op.create_index(op.f('ix_refresh_tokens_expires_at'), 'refresh_tokens', ['expires_at'], unique=False)
    else:
        # Table exists: verify indexes
        token_indexes = {idx['name'] for idx in inspector.get_indexes('refresh_tokens')}
        if 'ix_refresh_tokens_session_id' not in token_indexes:
            op.create_index(op.f('ix_refresh_tokens_session_id'), 'refresh_tokens', ['session_id'], unique=False)
        if 'ix_refresh_tokens_token_hash' not in token_indexes:
            op.create_index(op.f('ix_refresh_tokens_token_hash'), 'refresh_tokens', ['token_hash'], unique=True)
        if 'ix_refresh_tokens_expires_at' not in token_indexes:
            op.create_index(op.f('ix_refresh_tokens_expires_at'), 'refresh_tokens', ['expires_at'], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    # =========================================================================
    # Drop tables in reverse foreign key order: child first, then parent
    # WARNING: Dropping these tables will delete all active user sessions and
    # refresh tokens, forcing all connected clients to re-authenticate on their
    # next request.
    # =========================================================================
    if 'refresh_tokens' in existing_tables:
        token_indexes = {idx['name'] for idx in inspector.get_indexes('refresh_tokens')}
        if 'ix_refresh_tokens_expires_at' in token_indexes:
            op.drop_index(op.f('ix_refresh_tokens_expires_at'), table_name='refresh_tokens')
        if 'ix_refresh_tokens_token_hash' in token_indexes:
            op.drop_index(op.f('ix_refresh_tokens_token_hash'), table_name='refresh_tokens')
        if 'ix_refresh_tokens_session_id' in token_indexes:
            op.drop_index(op.f('ix_refresh_tokens_session_id'), table_name='refresh_tokens')
        op.drop_table('refresh_tokens')

    if 'user_sessions' in existing_tables:
        session_indexes = {idx['name'] for idx in inspector.get_indexes('user_sessions')}
        if 'ix_user_sessions_expires_at' in session_indexes:
            op.drop_index(op.f('ix_user_sessions_expires_at'), table_name='user_sessions')
        if 'ix_user_sessions_token_family' in session_indexes:
            op.drop_index(op.f('ix_user_sessions_token_family'), table_name='user_sessions')
        if 'ix_user_sessions_user_id' in session_indexes:
            op.drop_index(op.f('ix_user_sessions_user_id'), table_name='user_sessions')
        if 'ix_user_sessions_session_id' in session_indexes:
            op.drop_index(op.f('ix_user_sessions_session_id'), table_name='user_sessions')
        op.drop_table('user_sessions')
