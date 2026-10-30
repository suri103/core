"""make reminder and patient-message delivery claims durable

Revision ID: c9f2a6d8e104
Revises: b7d4f8c2e901
Create Date: 2026-08-25 12:00:00

B5 hardening: the scheduler and Celery workers previously selected a PENDING
row, performed provider I/O, then changed its status. Overlapping Beat runs,
redelivery, or concurrent workers could therefore send the same reminder or
patient message more than once. This migration adds a durable lease/attempt
state to the existing delivery records and an optional business idempotency
key for patient messages.

No live delivery history is deleted or guessed. Existing PENDING rows become
immediately dispatchable; duplicate non-null idempotency keys abort the
migration for explicit reconciliation.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c9f2a6d8e104"
down_revision: str | None = "b7d4f8c2e901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_REMINDER_DUE_INDEX = "ix_reminders_delivery_due"
_MESSAGE_DUE_INDEX = "ix_patient_messages_delivery_due"
_MESSAGE_DEDUPE_INDEX = "uq_patient_messages_practice_dedupe_key"


def _inspector():
    try:
        return sa.inspect(op.get_bind())
    except sa.exc.NoInspectionAvailable:
        # Offline (--sql) rendering uses a mock connection.
        return None


def _has_table(name: str) -> bool:
    insp = _inspector()
    return insp is not None and name in insp.get_table_names()


def _columns(table: str) -> set[str]:
    if not _has_table(table):
        return set()
    return {column["name"] for column in _inspector().get_columns(table)}


def _has_index(table: str, name: str) -> bool:
    if not _has_table(table):
        return False
    inspector = _inspector()
    names = {index["name"] for index in inspector.get_indexes(table)}
    names.update(
        constraint["name"]
        for constraint in inspector.get_unique_constraints(table)
        if constraint.get("name")
    )
    return name in names


def _add_reminder_statuses(bind) -> None:
    """Add state-machine values on PostgreSQL; SQLite stores strings."""
    if bind.dialect.name != "postgresql":
        return
    for value in ("PROCESSING", "SKIPPED"):
        try:
            op.execute(f"ALTER TYPE reminderstatus ADD VALUE IF NOT EXISTS '{value}'")
        except Exception:
            # PostgreSQL versions before IF NOT EXISTS report a duplicate value
            # error. Retrying without the clause preserves the existing house
            # style and only suppresses an already-present member.
            try:
                op.execute(f"ALTER TYPE reminderstatus ADD VALUE '{value}'")
            except Exception:
                pass


def _abort_on_duplicate_message_keys() -> None:
    bind = op.get_bind()
    duplicates = bind.execute(
        sa.text(
            "SELECT practice_id, dedupe_key, COUNT(*) AS row_count "
            "FROM patient_messages "
            "WHERE dedupe_key IS NOT NULL "
            "GROUP BY practice_id, dedupe_key "
            "HAVING COUNT(*) > 1"
        )
    ).fetchall()
    if duplicates:
        sample = ", ".join(
            f"{row[0]}:{row[1]} ({row[2]} rows)" for row in duplicates[:20]
        )
        raise RuntimeError(
            "Refusing to create the patient-message idempotency index because "
            "duplicate non-null delivery keys already exist: "
            f"{sample}. Reconcile the affected messages explicitly, then rerun Alembic."
        )


def _add_delivery_columns(table: str) -> None:
    columns = _columns(table)
    additions = []
    if "attempt_count" not in columns:
        additions.append(
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0")
        )
    if "next_attempt_at" not in columns:
        additions.append(sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True))
    if "claimed_at" not in columns:
        additions.append(sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))
    if "claim_token" not in columns:
        additions.append(sa.Column("claim_token", sa.String(length=64), nullable=True))
    if "claim_expires_at" not in columns:
        additions.append(
            sa.Column("claim_expires_at", sa.DateTime(timezone=True), nullable=True)
        )
    if additions:
        with op.batch_alter_table(table, schema=None) as batch_op:
            for column in additions:
                batch_op.add_column(column)


def _upgrade_offline_static() -> None:
    # Offline (--sql): both tables exist in any chain-built database. Emit the
    # full changeset statically; the dedupe_key duplicate check needs a live
    # connection, so it becomes an embedded warning (M-04 convention).
    for value in ("PROCESSING", "SKIPPED"):
        op.execute(f"ALTER TYPE reminderstatus ADD VALUE IF NOT EXISTS '{value}'")

    for table in ("reminders", "patient_messages"):
        if table == "patient_messages":
            op.add_column(
                table, sa.Column("dedupe_key", sa.String(length=255), nullable=True)
            )
        op.add_column(
            table,
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        )
        op.add_column(
            table, sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True)
        )
        op.add_column(
            table, sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True)
        )
        op.add_column(
            table, sa.Column("claim_token", sa.String(length=64), nullable=True)
        )
        op.add_column(
            table, sa.Column("claim_expires_at", sa.DateTime(timezone=True), nullable=True)
        )

    op.execute(
        "UPDATE reminders SET next_attempt_at = scheduled_at "
        "WHERE status = 'PENDING' AND next_attempt_at IS NULL"
    )
    op.create_index(
        _REMINDER_DUE_INDEX, "reminders", ["status", "next_attempt_at"], unique=False
    )

    op.execute(
        "UPDATE patient_messages "
        "SET next_attempt_at = COALESCE(scheduled_at, created_at, CURRENT_TIMESTAMP) "
        "WHERE status = 'PENDING' AND next_attempt_at IS NULL"
    )
    op.execute(
        "DO $$ BEGIN RAISE WARNING 'c9f2a6d8e104: this script was rendered "
        "offline, so the duplicate patient_messages.dedupe_key check did NOT "
        "run. If this database has message history, reconcile duplicated "
        "non-null dedupe keys before applying this script; the unique index "
        "below will fail on duplicates.'; END $$"
    )
    op.create_index(
        _MESSAGE_DEDUPE_INDEX,
        "patient_messages",
        ["practice_id", "dedupe_key"],
        unique=True,
        postgresql_where=sa.text("dedupe_key IS NOT NULL"),
    )
    op.create_index(
        _MESSAGE_DUE_INDEX,
        "patient_messages",
        ["status", "next_attempt_at"],
        unique=False,
    )


def upgrade() -> None:
    bind = op.get_bind()
    if _inspector() is None:
        _upgrade_offline_static()
        return

    if _has_table("reminders"):
        _add_reminder_statuses(bind)
        _add_delivery_columns("reminders")
        bind.execute(
            sa.text(
                "UPDATE reminders "
                "SET next_attempt_at = scheduled_at "
                "WHERE status = 'PENDING' AND next_attempt_at IS NULL"
            )
        )
        if not _has_index("reminders", _REMINDER_DUE_INDEX):
            op.create_index(
                _REMINDER_DUE_INDEX,
                "reminders",
                ["status", "next_attempt_at"],
                unique=False,
            )

    if _has_table("patient_messages"):
        columns = _columns("patient_messages")
        if "dedupe_key" not in columns:
            with op.batch_alter_table("patient_messages", schema=None) as batch_op:
                batch_op.add_column(sa.Column("dedupe_key", sa.String(length=255), nullable=True))
        _add_delivery_columns("patient_messages")
        bind.execute(
            sa.text(
                "UPDATE patient_messages "
                "SET next_attempt_at = COALESCE(scheduled_at, created_at, CURRENT_TIMESTAMP) "
                "WHERE status = 'PENDING' AND next_attempt_at IS NULL"
            )
        )
        _abort_on_duplicate_message_keys()
        if not _has_index("patient_messages", _MESSAGE_DEDUPE_INDEX):
            kwargs = {}
            predicate = sa.text("dedupe_key IS NOT NULL")
            if bind.dialect.name == "postgresql":
                kwargs["postgresql_where"] = predicate
            elif bind.dialect.name == "sqlite":
                kwargs["sqlite_where"] = predicate
            op.create_index(
                _MESSAGE_DEDUPE_INDEX,
                "patient_messages",
                ["practice_id", "dedupe_key"],
                unique=True,
                **kwargs,
            )
        if not _has_index("patient_messages", _MESSAGE_DUE_INDEX):
            op.create_index(
                _MESSAGE_DUE_INDEX,
                "patient_messages",
                ["status", "next_attempt_at"],
                unique=False,
            )


def downgrade() -> None:
    if _has_table("patient_messages"):
        if _has_index("patient_messages", _MESSAGE_DUE_INDEX):
            op.drop_index(_MESSAGE_DUE_INDEX, table_name="patient_messages")
        if _has_index("patient_messages", _MESSAGE_DEDUPE_INDEX):
            op.drop_index(_MESSAGE_DEDUPE_INDEX, table_name="patient_messages")
        with op.batch_alter_table("patient_messages", schema=None) as batch_op:
            for column in (
                "claim_expires_at",
                "claim_token",
                "claimed_at",
                "next_attempt_at",
                "attempt_count",
                "dedupe_key",
            ):
                if column in _columns("patient_messages"):
                    batch_op.drop_column(column)

    if _has_table("reminders"):
        if _has_index("reminders", _REMINDER_DUE_INDEX):
            op.drop_index(_REMINDER_DUE_INDEX, table_name="reminders")
        with op.batch_alter_table("reminders", schema=None) as batch_op:
            for column in (
                "claim_expires_at",
                "claim_token",
                "claimed_at",
                "next_attempt_at",
                "attempt_count",
            ):
                if column in _columns("reminders"):
                    batch_op.drop_column(column)
    # PostgreSQL cannot remove enum values; PROCESSING and SKIPPED remain
    # harmless if this revision is downgraded.
