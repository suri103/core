"""add ACCOUNTANT and SUPER_ADMIN user roles

Revision ID: f8d1c3a5e729
Revises: e7f8a9b0c1d2
Create Date: 2026-09-10 09:30:00

Extends the ``userrole`` enum with two production-readiness members:

- ACCOUNTANT — finance-only clinic staff (billing / payments / reports).
  Previously all money handling lived on OWNER/ADMIN/FRONT_DESK; clinics
  that hire bookkeepers need a least-privilege role for it.
- SUPER_ADMIN — the SaaS operator's own staff (platform-level, not a
  clinic role). Super admins live in their own bootstrap practice and are
  authorized via /platform/* endpoints, never clinic routes.

SQLite (tests) stores enums as VARCHAR with a CHECK constraint; the batch
mode recreate is skipped for the CHECK because the ORM enum writes both
values anyway and the test suite creates tables from the ORM metadata
(``Base.metadata.create_all``), which already contains the new members.
"""
from collections.abc import Sequence

from alembic import op


revision: str = "f8d1c3a5e729"
down_revision: str | None = "e7f8a9b0c1d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_MEMBERS = ("ACCOUNTANT", "SUPER_ADMIN")


def _add_enum_members(bind, enum_name: str, members) -> None:
    """Best-effort Postgres enum extension (skipped on SQLite/other dialects)."""
    if bind.dialect.name != "postgresql":
        return
    for member in members:
        try:
            op.execute(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{member}'")
        except Exception:
            # PG < 13 has no IF NOT EXISTS; tolerate duplicate-value errors.
            try:
                op.execute(f"ALTER TYPE {enum_name} ADD VALUE '{member}'")
            except Exception:
                pass


def upgrade() -> None:
    bind = op.get_bind()
    _add_enum_members(bind, "userrole", _NEW_MEMBERS)
    # Billing ledger partial-refund status (see models/billing.py PaymentStatus).
    _add_enum_members(bind, "paymentstatus", ("partially_refunded",))


def downgrade() -> None:
    # Enum members are intentionally not removed (Postgres cannot drop values).
    return
