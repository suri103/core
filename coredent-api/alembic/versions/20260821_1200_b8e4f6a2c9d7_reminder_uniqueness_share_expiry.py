"""reminder uniqueness + image share expiry

Revision ID: b8e4f6a2c9d7
Revises: abcd1234aa01
Create Date: 2026-08-21 12:00:00

- reminders: enforce one reminder per appointment (M12). The scheduler used a
  check-then-insert pattern with no DB guard, so overlapping runs could create
  duplicate reminders and double-email patients. Existing duplicates are
  collapsed first (keeping the oldest row per appointment) so the unique index
  can be created on live data without failing.
- patient_images: add share_expires_at (L1). Share emails promise a 30-day
  expiry but no column existed to enforce it. Legacy rows keep NULL, which the
  application treats as "no expiry" (grandfathered shares created before this
  change); new shares always set it.

Written defensively per house style: reflection-guarded, idempotent, works on
PostgreSQL and SQLite (batch mode).

OFFLINE (``--sql``) MODE: emits the same changeset statically (M-04 fix). The
online duplicate-collapse loop becomes one equivalent ``DELETE`` that keeps
the oldest reminder per appointment.
"""

from collections.abc import Sequence

import logging

import sqlalchemy as sa
from alembic import op

logger = logging.getLogger(__name__)

revision: str = "b8e4f6a2c9d7"
down_revision: str | None = "abcd1234aa01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _inspect_safe(bind):
    try:
        return sa.inspect(bind)
    except sa.exc.NoInspectionAvailable:
        return None


def _table_exists(bind, table: str) -> bool:
    insp = _inspect_safe(bind)
    return insp is not None and insp.has_table(table)


def _columns(bind, table: str) -> set[str]:
    insp = _inspect_safe(bind)
    return set() if insp is None else {c["name"] for c in insp.get_columns(table)}


def _upgrade_offline_static() -> None:
    # Offline (--sql): both tables exist in any chain-built database. The
    # online duplicate-collapse loop becomes one equivalent DELETE that keeps
    # the oldest reminder per appointment (created_at ASC, id ASC).
    op.execute(
        """
        DELETE FROM reminders
        WHERE EXISTS (
            SELECT 1 FROM reminders keeper
            WHERE keeper.appointment_id = reminders.appointment_id
              AND (keeper.created_at, keeper.id)
                  < (reminders.created_at, reminders.id)
        )
        """
    )
    op.create_index(
        "uq_reminders_appointment_id", "reminders", ["appointment_id"], unique=True
    )
    op.add_column(
        "patient_images",
        sa.Column("share_expires_at", sa.DateTime(timezone=True), nullable=True),
    )


def upgrade() -> None:
    bind = op.get_bind()
    if _inspect_safe(bind) is None:
        _upgrade_offline_static()
        return

    # --- reminders: collapse duplicates, then unique index -------------
    if _table_exists(bind, "reminders"):
        dup_rows = bind.execute(sa.text(
            """
            SELECT appointment_id, COUNT(*) AS n
            FROM reminders
            GROUP BY appointment_id
            HAVING COUNT(*) > 1
            """
        )).fetchall()

        for row in dup_rows:
            appointment_id = row[0]
            keep = bind.execute(sa.text(
                """
                SELECT id FROM reminders
                WHERE appointment_id = :aid
                ORDER BY created_at ASC, id ASC
                LIMIT 1
                """
            ), {"aid": appointment_id}).scalar()
            if keep is None:
                continue
            result = bind.execute(sa.text(
                """
                DELETE FROM reminders
                WHERE appointment_id = :aid AND id != :keep
                """
            ), {"aid": appointment_id, "keep": keep})
            logger.info(
                "b8e4f6a2c9d7: removed %d duplicate reminder(s) for "
                "appointment %s", result.rowcount, appointment_id,
            )

        existing_indexes = {ix["name"] for ix in sa.inspect(bind).get_indexes("reminders")}
        if "uq_reminders_appointment_id" not in existing_indexes:
            op.create_index(
                "uq_reminders_appointment_id",
                "reminders",
                ["appointment_id"],
                unique=True,
            )

    # --- patient_images: share_expires_at ------------------------------
    if _table_exists(bind, "patient_images") and (
        "share_expires_at" not in _columns(bind, "patient_images")
    ):
        with op.batch_alter_table("patient_images", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("share_expires_at", sa.DateTime(timezone=True), nullable=True)
            )

    # NOTE: broader schema drift (referrals.completed_at, conversations.*,
    # document_signatures.*, marketing tables, ...) is repaired by the
    # dedicated additive sync migration that follows this revision.


def downgrade() -> None:
    bind = op.get_bind()
    if _inspect_safe(bind) is None:
        logger.warning(
            "b8e4f6a2c9d7 downgrade: reflection unavailable; emitting no DDL"
        )
        return

    if _table_exists(bind, "patient_images") and (
        "share_expires_at" in _columns(bind, "patient_images")
    ):
        with op.batch_alter_table("patient_images", schema=None) as batch_op:
            batch_op.drop_column("share_expires_at")

    if _table_exists(bind, "reminders"):
        existing_indexes = {ix["name"] for ix in sa.inspect(bind).get_indexes("reminders")}
        if "uq_reminders_appointment_id" in existing_indexes:
            op.drop_index("uq_reminders_appointment_id", table_name="reminders")
