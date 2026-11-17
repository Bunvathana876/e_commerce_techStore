"""Add a revocation barrier for pre-session JWTs without issued-at claims.

Revision ID: d7e8f9012abc
Revises: a1b2c3d4e5f6

Nullable and without backfill: existing users, passwords, roles and seller links
remain intact. Prepare for review; apply only through the approved migration job.
"""
from alembic import op
import sqlalchemy as sa

revision = "d7e8f9012abc"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("users")}
    if "legacy_tokens_revoked_at" not in columns:
        op.add_column("users", sa.Column("legacy_tokens_revoked_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    # Operational rollback should retain this barrier, not revive revoked legacy JWTs.
    op.drop_column("users", "legacy_tokens_revoked_at")
