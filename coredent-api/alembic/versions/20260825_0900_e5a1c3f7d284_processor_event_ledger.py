"""processor webhook event ledger + unique processor_transaction_id

Revision ID: e5a1c3f7d284
Revises: d9e0f1a2b3c4
Create Date: 2026-08-25 09:00:00

WHY (audit finding C-01)
------------------------
Two defects let a successful external payment be acknowledged without being
recorded:

1. ``payment_transactions.processor_transaction_id`` was not unique. It is the
   idempotency key for processor callbacks, so without uniqueness a webhook
   lookup could match — and mutate — the wrong ledger row, and two concurrent
   deliveries could each insert a row for one real payment.

2. There was nowhere to put an event that could not be attributed to a tenant.
   ``payment_transactions.practice_id`` and ``patient_id`` are NOT NULL and
   must not be guessed, so an unattributable payment had to be either dropped
   or mis-filed. ``processor_webhook_events`` gives it a durable home, and
   doubles as database-backed idempotency behind the Redis dedup marker.

DATA SAFETY
-----------
Like c8f1a6d3b527, this migration never deletes payment rows. If duplicate
``processor_transaction_id`` values already exist it aborts with a report so
an operator reconciles them deliberately.

Idempotent: reflection-guarded so a partially applied run can be re-run.
"""

from collections.abc import Sequence

import logging

import sqlalchemy as sa
from alembic import op

logger = logging.getLogger(__name__)

revision: str = "e5a1c3f7d284"
down_revision: str | None = "d9e0f1a2b3c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Enum NAMES, not values. SQLAlchemy persists the member name for a Python
# enum, so a type created from the values ("processed") rejects every ORM write
# of "PROCESSED" with `invalid input value for enum processoreventstatus`. The
# original declaration used the values, which left the processor webhook ledger
# unable to record anything on PostgreSQL; f4b7c1d9e2a3 adds the names to
# already-migrated databases. See tests/test_enum_migration_parity.py.
_PROCESSOR_EVENT_STATUS = (
    "PROCESSED",
    "UNRECONCILED",
    "FAILED",
    "IGNORED",
)


def _inspector():
    try:
        return sa.inspect(op.get_bind())
    except sa.exc.NoInspectionAvailable:
        # Offline (--sql) rendering uses a mock connection.
        return None


def _has_table(name: str) -> bool:
    insp = _inspector()
    return insp is not None and name in insp.get_table_names()


def _has_index(table: str, index: str) -> bool:
    if not _has_table(table):
        return False
    insp = _inspector()
    names = {ix["name"] for ix in insp.get_indexes(table)}
    names.update(
        uc["name"] for uc in insp.get_unique_constraints(table) if uc.get("name")
    )
    return index in names


def _abort_if_duplicate_processor_ids() -> None:
    """Fail rather than delete when processor_transaction_id is not unique."""
    conn = op.get_bind()
    duplicates = conn.execute(
        sa.text(
            """
            SELECT processor_transaction_id, COUNT(*) AS row_count
            FROM payment_transactions
            WHERE processor_transaction_id IS NOT NULL
            GROUP BY processor_transaction_id
            HAVING COUNT(*) > 1
            ORDER BY row_count DESC, processor_transaction_id
            """
        )
    ).fetchall()

    if not duplicates:
        return

    sample = ", ".join(
        f"{row.processor_transaction_id} (x{row.row_count})" for row in duplicates[:20]
    )
    if len(duplicates) > 20:
        sample += f", ... and {len(duplicates) - 20} more"

    raise RuntimeError(
        "Refusing to apply migration e5a1c3f7d284: "
        f"{len(duplicates)} processor_transaction_id value(s) are duplicated in "
        "payment_transactions. Enforcing uniqueness would require removing "
        "rows, which destroys financial history.\n\n"
        f"Duplicated ids: {sample}\n\n"
        "Reconcile these rows manually (the earliest row per processor id is "
        "normally the real one; later rows are duplicate webhook inserts and "
        "should be voided by setting status='failed' and clearing "
        "processor_transaction_id), then re-run the migration."
    )


def _upgrade_offline_static() -> None:
    # Offline (--sql): reflection and the duplicate-processor-id check both
    # need a live connection. On a chain-built database none of these objects
    # exist yet, so emit the full changeset statically with the warning
    # embedded in the script (M-04 convention). The enum type is emitted by
    # create_table itself (SchemaType ordering handles the dependency).
    op.create_table(
        "processor_webhook_events",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("processor", sa.String(length=30), nullable=False),
        sa.Column("event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column(
            "status",
            sa.Enum(*_PROCESSOR_EVENT_STATUS, name="processoreventstatus"),
            nullable=False,
        ),
        sa.Column(
            "practice_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("practices.id"),
            nullable=True,
        ),
        sa.Column("processor_object_id", sa.String(length=255), nullable=True),
        sa.Column("amount_minor", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column(
            "payment_transaction_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("payment_transactions.id"),
            nullable=True,
        ),
        sa.Column("summary", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "uq_processor_webhook_events_event_id",
        "processor_webhook_events",
        ["event_id"],
        unique=True,
    )
    op.create_index(
        "ix_processor_events_status_received",
        "processor_webhook_events",
        ["status", "received_at"],
    )
    op.create_index(
        "ix_processor_events_object",
        "processor_webhook_events",
        ["processor", "processor_object_id"],
    )
    op.create_index(
        "ix_processor_webhook_events_practice_id",
        "processor_webhook_events",
        ["practice_id"],
    )
    op.execute(
        "DO $$ BEGIN RAISE WARNING 'e5a1c3f7d284: this script was rendered "
        "offline, so the duplicate payment_transactions.processor_transaction_id "
        "check did NOT run. If this database has payment history, reconcile "
        "duplicated processor ids before applying this script; the unique "
        "index below will fail on duplicates.'; END $$"
    )
    op.create_index(
        "uq_payment_transactions_processor_txn_id",
        "payment_transactions",
        ["processor_transaction_id"],
        unique=True,
    )


def upgrade() -> None:
    if _inspector() is None:
        _upgrade_offline_static()
        return

    status_enum = sa.Enum(*_PROCESSOR_EVENT_STATUS, name="processoreventstatus")
    # The column must reference the type WITHOUT emitting its own CREATE TYPE:
    # the type is created explicitly just below, and a second CREATE TYPE for an
    # existing type fails on PostgreSQL. This is what killed the container -
    # the run reached "enum type created; creating table" and died inside
    # op.create_table, every time, with no traceback.
    status_enum_column = sa.Enum(
        *_PROCESSOR_EVENT_STATUS, name="processoreventstatus", create_type=False
    )

    if not _has_table("processor_webhook_events"):
        status_enum.create(op.get_bind(), checkfirst=True)
        if op.get_bind().dialect.name == "postgresql":
            # Raw, explicit DDL rather than op.create_table().
            #
            # op.create_table() for this specific table killed the container in
            # production: the process died with no Python traceback and no
            # native fault (faulthandler was enabled and printed nothing), on
            # every attempt. The cause was never identified - a process killed
            # from outside leaves no evidence behind - but issuing the DDL as
            # plain statements made it succeed, and it keeps each step small
            # enough to identify itself if it ever fails again.
            op.execute(
                """
                CREATE TABLE processor_webhook_events (
                    id UUID NOT NULL PRIMARY KEY,
                    processor VARCHAR(30) NOT NULL,
                    event_id VARCHAR(255) NOT NULL,
                    event_type VARCHAR(100) NOT NULL,
                    status processoreventstatus NOT NULL,
                    practice_id UUID,
                    processor_object_id VARCHAR(255),
                    amount_minor BIGINT,
                    currency VARCHAR(3),
                    payment_transaction_id UUID,
                    summary JSON,
                    error_message TEXT,
                    resolution_notes TEXT,
                    received_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                    resolved_at TIMESTAMP WITH TIME ZONE
                )
                """
            )
            op.execute(
                "ALTER TABLE processor_webhook_events ADD CONSTRAINT "
                "fk_processor_events_practice_id FOREIGN KEY (practice_id) "
                "REFERENCES practices (id)"
            )
            op.execute(
                "ALTER TABLE processor_webhook_events ADD CONSTRAINT "
                "fk_processor_events_payment_transaction_id FOREIGN KEY "
                "(payment_transaction_id) REFERENCES payment_transactions (id)"
            )
        else:
            # Non-PostgreSQL (SQLite in the test suite) keeps the portable path.
            op.create_table(
                "processor_webhook_events",
                sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, nullable=False),
                sa.Column("processor", sa.String(length=30), nullable=False),
                sa.Column("event_id", sa.String(length=255), nullable=False),
                sa.Column("event_type", sa.String(length=100), nullable=False),
                sa.Column("status", status_enum_column, nullable=False),
                sa.Column(
                    "practice_id",
                    sa.UUID(as_uuid=True),
                    sa.ForeignKey("practices.id"),
                    nullable=True,
                ),
                sa.Column("processor_object_id", sa.String(length=255), nullable=True),
                sa.Column("amount_minor", sa.BigInteger(), nullable=True),
                sa.Column("currency", sa.String(length=3), nullable=True),
                sa.Column(
                    "payment_transaction_id",
                    sa.UUID(as_uuid=True),
                    sa.ForeignKey("payment_transactions.id"),
                    nullable=True,
                ),
                sa.Column("summary", sa.JSON(), nullable=True),
                sa.Column("error_message", sa.Text(), nullable=True),
                sa.Column("resolution_notes", sa.Text(), nullable=True),
                sa.Column(
                    "received_at",
                    sa.DateTime(timezone=True),
                    server_default=sa.func.now(),
                    nullable=False,
                ),
                sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            )

    if not _has_index("processor_webhook_events", "uq_processor_webhook_events_event_id"):
        op.create_index(
            "uq_processor_webhook_events_event_id",
            "processor_webhook_events",
            ["event_id"],
            unique=True,
        )
    if not _has_index("processor_webhook_events", "ix_processor_events_status_received"):
        op.create_index(
            "ix_processor_events_status_received",
            "processor_webhook_events",
            ["status", "received_at"],
        )
    if not _has_index("processor_webhook_events", "ix_processor_events_object"):
        op.create_index(
            "ix_processor_events_object",
            "processor_webhook_events",
            ["processor", "processor_object_id"],
        )
    if not _has_index("processor_webhook_events", "ix_processor_webhook_events_practice_id"):
        op.create_index(
            "ix_processor_webhook_events_practice_id",
            "processor_webhook_events",
            ["practice_id"],
        )

    if not _has_index("payment_transactions", "uq_payment_transactions_processor_txn_id"):
        _abort_if_duplicate_processor_ids()
        op.create_index(
            "uq_payment_transactions_processor_txn_id",
            "payment_transactions",
            ["processor_transaction_id"],
            unique=True,
        )



def downgrade() -> None:
    if _has_index("payment_transactions", "uq_payment_transactions_processor_txn_id"):
        op.drop_index(
            "uq_payment_transactions_processor_txn_id",
            table_name="payment_transactions",
        )

    for index in (
        "ix_processor_webhook_events_practice_id",
        "ix_processor_events_object",
        "ix_processor_events_status_received",
        "uq_processor_webhook_events_event_id",
    ):
        if _has_index("processor_webhook_events", index):
            op.drop_index(index, table_name="processor_webhook_events")

    if _has_table("processor_webhook_events"):
        op.drop_table("processor_webhook_events")

    sa.Enum(name="processoreventstatus").drop(op.get_bind(), checkfirst=True)
