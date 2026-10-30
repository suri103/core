"""add fenced daily-summary delivery claims

Revision ID: d3c8f1a6b529
Revises: b7e3a1d9c842
Create Date: 2026-08-26 12:00:00

Adds explicit lease ownership to daily-summary outbox rows so concurrent or
stale workers cannot both deliver or finalize the same summary.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d3c8f1a6b529"
down_revision: str | None = "b7e3a1d9c842"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "daily_summary_outbox",
        sa.Column("claim_token", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "daily_summary_outbox",
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "daily_summary_outbox",
        sa.Column("claim_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_daily_summary_claim_expiry",
        "daily_summary_outbox",
        ["status", "claim_expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_daily_summary_claim_expiry", table_name="daily_summary_outbox"
    )
    op.drop_column("daily_summary_outbox", "claim_expires_at")
    op.drop_column("daily_summary_outbox", "claimed_at")
    op.drop_column("daily_summary_outbox", "claim_token")
