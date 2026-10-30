"""add npi columns to users and practices

Revision ID: a7f3e2c1d854
Revises: d3c8f1a6b529
Create Date: 2026-08-31 13:00:00

Adds the optional NPI fields the EDI claim endpoints read
(``endpoints/edi.py`` accesses ``current_user.npi`` and the practice's
service-facility NPI when building X12 837P segments).  Before the model
columns existed, claim generation raised ``AttributeError`` at runtime;
``endpoints/insurance.py`` masked the same gap with a ``getattr`` fallback.

Written defensively (column-existence guards + batch mode) so it is
idempotent on both PostgreSQL and SQLite, consistent with the rest of the
chain.  Unlike older defensive migrations, offline ``--sql`` mode emits
static DDL instead of silently returning, so rendered deployment scripts
actually contain the change.
"""

from collections.abc import Sequence

import logging

import sqlalchemy as sa
from alembic import op

logger = logging.getLogger(__name__)

revision: str = "a7f3e2c1d854"
down_revision: str | None = "d3c8f1a6b529"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Naming convention required by batch mode on SQLite (unnamed constraints
# cannot be re-emitted otherwise).
_NAMING_CONVENTION = {
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s",
}


def _inspect_safe(bind):
    """Return the live inspector, or None when inspection is unavailable
    (offline ``--sql`` rendering uses a mock connection)."""
    try:
        return sa.inspect(bind)
    except sa.exc.NoInspectionAvailable:
        return None


def _table_exists(bind, table: str) -> bool:
    insp = _inspect_safe(bind)
    return insp is not None and insp.has_table(table)


def _columns(bind, table: str) -> set[str]:
    insp = _inspect_safe(bind)
    return set() if insp is None else {c['name'] for c in insp.get_columns(table)}


def _add_npi_column(table: str) -> None:
    bind = op.get_bind()
    insp = _inspect_safe(bind)
    if insp is None:
        # Offline (--sql) mode: no reflection, emit static DDL.
        op.add_column(table, sa.Column("npi", sa.String(length=20), nullable=True))
        return
    if not _table_exists(bind, table) or "npi" in _columns(bind, table):
        return
    with op.batch_alter_table(
        table, schema=None, naming_convention=_NAMING_CONVENTION
    ) as batch_op:
        batch_op.add_column(sa.Column("npi", sa.String(length=20), nullable=True))


def _drop_npi_column(table: str) -> None:
    bind = op.get_bind()
    insp = _inspect_safe(bind)
    if insp is None:
        op.drop_column(table, "npi")
        return
    if not _table_exists(bind, table) or "npi" not in _columns(bind, table):
        return
    with op.batch_alter_table(
        table, schema=None, naming_convention=_NAMING_CONVENTION
    ) as batch_op:
        batch_op.drop_column("npi")


def upgrade() -> None:
    _add_npi_column("users")
    _add_npi_column("practices")


def downgrade() -> None:
    _drop_npi_column("practices")
    _drop_npi_column("users")
