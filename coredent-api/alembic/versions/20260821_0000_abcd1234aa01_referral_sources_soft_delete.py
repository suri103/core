"""referral_sources soft-delete columns

Revision ID: abcd1234aa01
Revises: f2c5d7e8b930
Create Date: 2026-08-21
"""

from alembic import op
import sqlalchemy as sa


revision: str = "abcd1234aa01"
down_revision: str | None = "f2c5d7e8b930"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("referral_sources", sa.Column("is_deleted", sa.Boolean(), nullable=True))
    op.add_column("referral_sources", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("referral_sources", "deleted_at")
    op.drop_column("referral_sources", "is_deleted")
