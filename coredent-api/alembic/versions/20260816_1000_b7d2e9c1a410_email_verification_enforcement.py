"""email verification expiry + enforcement grandfathering

Revision ID: b7d2e9c1a410
Revises: a3c4e5f60718
Create Date: 2026-08-16 10:00:00

Adds `email_verification_token_expires_at` so verification links actually
expire (the emails already promised 24 hours), and grandfathers every
existing unverified account to verified. Login/refresh now enforce
verification after a 7-day grace period for accounts created after this
migration; marking pre-existing accounts as verified preserves the access
they already had instead of locking out entire tenants on deploy.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "b7d2e9c1a410"
down_revision: str | None = "a3c4e5f60718"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "email_verification_token_expires_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )
    # Grandfather: these accounts have had full system access all along.
    op.execute(
        "UPDATE users SET is_email_verified = TRUE WHERE is_email_verified = FALSE"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE users SET is_email_verified = FALSE "
        "WHERE is_email_verified = TRUE AND email_verification_token IS NOT NULL"
    )
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("email_verification_token_expires_at")
