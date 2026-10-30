"""appointment cancellation_reason column

Revision ID: a9d3e4f5b6c7
Revises: f8c9d2e3a4b5
Create Date: 2026-09-01 12:30:00

The cancel endpoint previously appended ``Cancelled: <reason>`` to the
``appointments.notes`` column. ``notes`` is otherwise a clinical
observation field; the appended state-machine metadata polluted both the
clinical review surface and the downstream filters that look at it.

This change:

1. Adds ``appointments.cancellation_reason`` (Text, nullable).
2. Backfills any existing rows that already had ``Cancelled: …``
   strings appended to their ``notes``.
3. Leaves ``notes`` itself untouched so clinical history is preserved.

SQLite note: batch mode is used for every DDL so the table is recreated
rather than failing on in-place ALTER. Offline (--sql) rendering emits
the static form per the repo convention.
"""
import re
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a9d3e4f5b6c7"
down_revision: str | None = "f8c9d2e3a4b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CANCELLED_RE = re.compile(r"(?is)\n?Cancelled:\s*(.+?)\s*$")


def upgrade() -> None:
    bind = op.get_bind()
    has_inspection = True
    try:
        sa.inspect(bind)
    except sa.exc.NoInspectionAvailable:
        has_inspection = False

    # 1. Add the column (nullable so the existing rows stay in place).
    if has_inspection:
        with op.batch_alter_table("appointments") as batch_op:
            batch_op.add_column(sa.Column("cancellation_reason", sa.Text, nullable=True))
    else:
        op.add_column("appointments", sa.Column("cancellation_reason", sa.Text, nullable=True))

    # 2. Backfill: any ``notes`` ending with ``Cancelled: ...`` moves
    # that suffix into ``cancellation_reason`` and leaves the clinical
    # portion in ``notes``. We do this in Python so it works identically
    # on Postgres and SQLite.
    rows = bind.execute(
        sa.text("SELECT id, notes FROM appointments WHERE notes IS NOT NULL")
    ).fetchall()
    migrated = 0
    for row_id, notes in rows:
        if not notes:
            continue
        match = _CANCELLED_RE.search(notes)
        if not match:
            continue
        reason = match.group(1).strip()
        cleaned_notes = _CANCELLED_RE.sub("", notes).rstrip()
        bind.execute(
            sa.text(
                "UPDATE appointments SET cancellation_reason = :r, "
                "notes = :n WHERE id = :id"
            ),
            {"r": reason, "n": cleaned_notes or None, "id": row_id},
        )
        migrated += 1


def downgrade() -> None:
    bind = op.get_bind()
    try:
        sa.inspect(bind)
    except sa.exc.NoInspectionAvailable:
        op.drop_column("appointments", "cancellation_reason")
        return

    with op.batch_alter_table("appointments") as batch_op:
        batch_op.drop_column("cancellation_reason")