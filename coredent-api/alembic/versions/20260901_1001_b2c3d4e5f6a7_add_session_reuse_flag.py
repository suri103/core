"""add single-use refresh-token overlap guard

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-01 10:01:00

H8: ``sessions.previous_token_consumed`` marks when the previous-token leg
of the refresh rotation has been used once. A replayed superseded token then
matches no session row and triggers the all-sessions revocation immediately
instead of silently rotating again inside the (5s) overlap window.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column(
            "previous_token_consumed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("sessions", "previous_token_consumed")
