"""add bounded refresh-token overlap fields

Revision ID: b7e3a1d9c842
Revises: f4a9c2d7e631
Create Date: 2026-08-26 10:30:00

Allows one immediately previous refresh-token hash to remain valid briefly so
concurrent tabs do not revoke an otherwise healthy session family.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7e3a1d9c842"
down_revision: str | None = "f4a9c2d7e631"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("previous_token_hash", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "sessions",
        sa.Column(
            "previous_token_valid_until",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_sessions_previous_token_hash",
        "sessions",
        ["previous_token_hash"],
    )


def downgrade() -> None:
    op.drop_index("ix_sessions_previous_token_hash", table_name="sessions")
    op.drop_column("sessions", "previous_token_valid_until")
    op.drop_column("sessions", "previous_token_hash")
