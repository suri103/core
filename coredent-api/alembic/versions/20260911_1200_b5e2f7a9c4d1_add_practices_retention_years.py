"""add practices.retention_years for per-practice retention override

Revision ID: b5e2f7a9c4d1
Revises: f8d1c3a5e729
Create Date: 2026-09-11 12:00:00

Nullable Integer on practices. NULL = platform default (7y). The purge
eligibility takes max(practice, platform) so a practice can only extend
retention, never shorten below the floor (docs/DATA_RETENTION_POLICY.md § 6).
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "b5e2f7a9c4d1"
down_revision: str | None = "f8d1c3a5e729"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("practices", schema=None) as batch_op:
        batch_op.add_column(sa.Column("retention_years", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("practices", schema=None) as batch_op:
        batch_op.drop_column("retention_years")
