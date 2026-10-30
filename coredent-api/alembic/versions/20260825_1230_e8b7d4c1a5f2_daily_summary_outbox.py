"""daily summary delivery outbox

Revision ID: e8b7d4c1a5f2
Revises: c9f2a6d8e104
Create Date: 2026-08-25 12:30:00

B7-9: makes practice daily-summary emails durable. One row per
(practice, local summary date, recipient user) with a claim/lease state
machine; the unique constraint is the race guard between concurrent
schedulers. Purely additive: no existing rows are read or modified.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "e8b7d4c1a5f2"
down_revision: str | None = "c9f2a6d8e104"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "daily_summary_outbox",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "practice_id",
            UUID(as_uuid=True),
            sa.ForeignKey("practices.id"),
            nullable=False,
        ),
        sa.Column(
            "user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("summary_date", sa.Date(), nullable=False),
        sa.Column("recipient_email", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "SENDING",
                "SENT",
                "FAILED",
                name="dailysummarystatus",
            ),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.UniqueConstraint(
            "practice_id",
            "summary_date",
            "user_id",
            name="uq_daily_summary_practice_date_user",
        ),
    )
    op.create_index(
        "ix_daily_summary_delivery_due",
        "daily_summary_outbox",
        ["status", "next_attempt_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_daily_summary_delivery_due", table_name="daily_summary_outbox"
    )
    op.drop_table("daily_summary_outbox")
    op.execute("DROP TYPE IF EXISTS dailysummarystatus")
