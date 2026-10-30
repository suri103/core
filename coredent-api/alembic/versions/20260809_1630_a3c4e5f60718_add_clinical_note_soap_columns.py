"""add clinical-note SOAP columns and note-type enum members

Revision ID: a3c4e5f60718
Revises: 7f3c8a1d2e4b
Create Date: 2026-08-09 16:30:00

The ClinicalNote model now stores the SOAP sections individually and may be
signed. The baseline migration only created `content` + `note_type`; this
revision adds the four SOAP text columns, the signing fields, relaxes
`content` to nullable (non-SOAP notes may omit the free-text body) and extends
the `notetype` enum with PROCEDURE and GENERAL for the frontend `type`
contract ('soap'|'procedure'|'general').
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "a3c4e5f60718"
down_revision: str | None = "7f3c8a1d2e4b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _add_enum_members(bind, members: Sequence[str]) -> None:
    """Best-effort Postgres enum extension (skipped on SQLite/other dialects)."""
    if bind.dialect.name != "postgresql":
        return
    for member in members:
        try:
            op.execute(f"ALTER TYPE notetype ADD VALUE IF NOT EXISTS '{member}'")
        except Exception:
            # PG < 13 has no IF NOT EXISTS; tolerate duplicate-value errors.
            try:
                op.execute(f"ALTER TYPE notetype ADD VALUE '{member}'")
            except Exception:
                pass


def upgrade() -> None:
    bind = op.get_bind()
    with op.batch_alter_table("clinical_notes", schema=None) as batch_op:
        batch_op.add_column(sa.Column("subjective", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("objective", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("assessment", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("plan", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(sa.Column("signed_by", sa.String(length=255), nullable=True))
        # Relax the free-text body: non-SOAP notes may omit `content`.
        batch_op.alter_column("content", existing_type=sa.Text(), nullable=True)
    _add_enum_members(bind, ("PROCEDURE", "GENERAL"))


def downgrade() -> None:
    # Enum members are intentionally not removed (Postgres cannot drop values).
    with op.batch_alter_table("clinical_notes", schema=None) as batch_op:
        batch_op.alter_column("content", existing_type=sa.Text(), nullable=False)
        batch_op.drop_column("signed_by")
        batch_op.drop_column("signed_at")
        batch_op.drop_column("plan")
        batch_op.drop_column("assessment")
        batch_op.drop_column("objective")
        batch_op.drop_column("subjective")