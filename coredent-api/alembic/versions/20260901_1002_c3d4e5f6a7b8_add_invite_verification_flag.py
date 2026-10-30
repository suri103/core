"""add immediate email-verification requirement flag

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-01 10:02:00

M1: ``users.email_verification_required`` marks accounts (created through
the staff-invitation accept flow) that must confirm their inbox before they
can sign in — the 72h invite token is not proof of email ownership.
Self-registered accounts keep the documented seven-day grace period; this
flag makes the verification gate immediate for invite-accepted accounts.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "email_verification_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "email_verification_required")
