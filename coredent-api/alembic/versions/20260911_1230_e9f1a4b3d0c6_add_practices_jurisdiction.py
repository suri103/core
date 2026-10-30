"""add practices.jurisdiction for the retention preset picker

Revision ID: e9f1a4b3d0c6
Revises: b5e2f7a9c4d1
Create Date: 2026-09-11 12:30:00

Nullable String(16) on practices storing the jurisdiction code picked in
Settings → General (e.g. 'CA', 'USA'). Purely a UI convenience for the
retention preset picker; purge enforcement only reads retention_years.
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "e9f1a4b3d0c6"
down_revision: str | None = "b5e2f7a9c4d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("practices", schema=None) as batch_op:
        batch_op.add_column(sa.Column("jurisdiction", sa.String(length=16), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("practices", schema=None) as batch_op:
        batch_op.drop_column("jurisdiction")
