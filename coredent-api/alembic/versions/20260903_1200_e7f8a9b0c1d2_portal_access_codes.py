"""portal magic-link access codes (Option A inbox proof)

Revision ID: e7f8a9b0c1d2
Revises: f3a4b5c6d7e8
Create Date: 2026-09-03 12:00:00

POST /portal/access no longer returns a bearer for email+DOB alone; it
creates a single-use hashed code and emails a link. POST /portal/access/verify
consumes the code and issues the bearer. No backfill: new table only.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e7f8a9b0c1d2"
down_revision: str | None = "f3a4b5c6d7e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "patient_portal_access_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("practice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("practices.id"), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
    )
    op.create_index(
        "ix_ppac_patient_active",
        "patient_portal_access_codes",
        ["patient_id", "used_at", "expires_at"],
    )
    op.create_index(
        op.f("ix_patient_portal_access_codes_token_hash"),
        "patient_portal_access_codes",
        ["token_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_patient_portal_access_codes_token_hash"),
        table_name="patient_portal_access_codes",
    )
    op.drop_index("ix_ppac_patient_active", table_name="patient_portal_access_codes")
    op.drop_table("patient_portal_access_codes")
