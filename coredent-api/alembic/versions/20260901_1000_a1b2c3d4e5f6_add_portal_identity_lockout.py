"""add persistent portal identity lockout table

Revision ID: a1b2c3d4e5f6
Revises: f1a3c5e7d9b2
Create Date: 2026-09-01 10:00:00

M2: portal-access identity lockout state moves from a module-level dict
(into which it reset on every worker restart) to this durable table keyed by
(practice_slug, email), keeping the 15-minute window and its
window-extending semantics across restarts and replicas.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "f1a3c5e7d9b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "portal_identity_lockouts",
        sa.Column("practice_slug", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("practice_slug", "email"),
    )


def downgrade() -> None:
    op.drop_table("portal_identity_lockouts")
