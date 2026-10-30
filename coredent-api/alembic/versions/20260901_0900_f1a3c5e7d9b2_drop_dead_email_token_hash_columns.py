"""drop dead email_verification_token_hash columns

Revision ID: f1a3c5e7d9b2
Revises: a7f3e2c1d854
Create Date: 2026-09-01 09:00:00

WHY
---
The baseline created ``email_verification_token_hash`` on both ``users`` and
``online_bookings`` (each with its own index), but no model ever mapped the
column: the user flow verifies via plaintext ``email_verification_token``
(with expiry added by b7d2e9c1a410), and OnlineBooking likewise. The columns
and indexes are dead weight in every migrated database (Phase-1 finding
H-03). The online_bookings twin is the identical defect and is removed in the
same pass.

Safety: both columns are nullable, indexed-only, and never read or written by
any code path (verified by full-tree grep of app/ and tests/).

Offline (``--sql``) rendering emits the drops statically, per the M-04
convention; the online path is reflection-guarded and idempotent.
"""

from collections.abc import Sequence

import logging

import sqlalchemy as sa
from alembic import op

logger = logging.getLogger(__name__)

revision: str = "f1a3c5e7d9b2"
down_revision: str | None = "a7f3e2c1d854"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# (table, dead column, index on that column)
_DEAD_COLUMNS = [
    ("users", "email_verification_token_hash", "ix_users_email_verification_token_hash"),
    (
        "online_bookings",
        "email_verification_token_hash",
        "ix_online_bookings_email_verification_token_hash",
    ),
]


def _inspect_safe(bind):
    try:
        return sa.inspect(bind)
    except sa.exc.NoInspectionAvailable:
        return None


def upgrade() -> None:
    bind = op.get_bind()
    insp = _inspect_safe(bind)
    if insp is None:
        # Offline (--sql): the chain-built database always has both columns,
        # so emit the drops statically (M-04 convention).
        for table_name, column_name, index_name in _DEAD_COLUMNS:
            op.drop_index(index_name, table_name=table_name)
            op.drop_column(table_name, column_name)
        return

    for table_name, column_name, index_name in _DEAD_COLUMNS:
        if not insp.has_table(table_name):
            continue
        columns = {c["name"] for c in insp.get_columns(table_name)}
        if column_name not in columns:
            continue  # already cleaned up (idempotent re-run)
        index_names = {ix["name"] for ix in insp.get_indexes(table_name)}
        if index_name in index_names:
            op.drop_index(index_name, table_name=table_name)
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.drop_column(column_name)
        logger.info("%s: dropped dead column %s.%s", revision, table_name, column_name)


def downgrade() -> None:
    bind = op.get_bind()
    insp = _inspect_safe(bind)
    if insp is None:
        # Offline (--sql): restore the baseline shape statically.
        for table_name, column_name, index_name in _DEAD_COLUMNS:
            op.add_column(
                table_name,
                sa.Column(column_name, sa.String(length=255), nullable=True),
            )
            op.create_index(index_name, table_name, [column_name], unique=False)
        return

    for table_name, column_name, index_name in _DEAD_COLUMNS:
        if not insp.has_table(table_name):
            continue
        if column_name in {c["name"] for c in insp.get_columns(table_name)}:
            continue
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(column_name, sa.String(length=255), nullable=True)
            )
        op.create_index(index_name, table_name, [column_name], unique=False)
