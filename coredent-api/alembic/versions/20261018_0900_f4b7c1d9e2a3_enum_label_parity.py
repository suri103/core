"""enum label parity: labels the ORM writes that the migrated types lack

Revision ID: f4b7c1d9e2a3
Revises: e3f4a5b6c7d8
Create Date: 2026-10-18 09:00:00

The baseline migration declared three Postgres enum types more than once with
different member sets. SQLAlchemy emits one ``CREATE TYPE`` per name per run and
memoizes it, so a fresh database keeps only the **first** declaration's labels
for the whole type — the later, wider declaration is silently ignored. Each
label declared anywhere in the model must therefore exist on the type, or the
first INSERT carrying it fails with

  invalid input value for enum <type>: "<LABEL>"

which is what this revision repairs, non-destructively and idempotently:

- ``messagestatus``  + SENDING   (app/models/communication.py MessageStatus).
  ``send_message_task`` and ``process_scheduled_messages_task`` set it as the
  first statement of the task, so every PatientMessage delivery failed on a
  migration-built database.
- ``paymentstatus``  + PROCESSING, PARTIALLY_REFUNDED, VOIDED, CANCELLED
  (both app/models/billing.py and app/models/payment.py PaymentStatus).
- ``paymentmethod``  + CARD, UPI, CREDIT_CARD, DEBIT_CARD, BANK_TRANSFER
  (billing.PaymentMethod and payment.PaymentMethod; the union is added because
  which declaration "won" depends on table creation order).
- ``processoreventstatus`` + PROCESSED, UNRECONCILED, FAILED, IGNORED
  (e5a1c3f7d284 created the type from the enum *values*, lowercase, while
  SQLAlchemy persists member *names* — so the durable processor-webhook ledger
  could not record a row on PostgreSQL.)

Labels are added, never removed: Postgres cannot drop an enum value, and other
rows still reference the existing ones. Already-present values are left alone,
so this is a no-op on a database created from the corrected baseline. A missing
type raises loudly rather than being skipped — the statements are bare so the
database reports the real problem.

The earlier migration f8d1c3a5e729 added the *lowercase* value
'partially_refunded', which the ORM never emits (SQLAlchemy persists enum
**names**). That stray label is inert and cannot be removed; the labels this
revision adds are the names the ORM actually writes.

``tests/test_enum_migration_parity.py`` prevents this class from returning, and
``scripts/check_schema_drift.py`` now compares enum labels against the live
database in CI.
"""
from collections.abc import Sequence

from alembic import op


revision: str = "f4b7c1d9e2a3"
down_revision: str | None = "e3f4a5b6c7d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Every statement is literal on purpose: the parity test greps this file, and an
# operator can read exactly what the deploy will do to the shared types.
_ADD_VALUE_STATEMENTS: tuple[str, ...] = (
    "ALTER TYPE messagestatus ADD VALUE IF NOT EXISTS 'SENDING'",
    "ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS 'PROCESSING'",
    "ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS 'PARTIALLY_REFUNDED'",
    "ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS 'VOIDED'",
    "ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS 'CANCELLED'",
    "ALTER TYPE paymentmethod ADD VALUE IF NOT EXISTS 'CARD'",
    "ALTER TYPE paymentmethod ADD VALUE IF NOT EXISTS 'UPI'",
    "ALTER TYPE paymentmethod ADD VALUE IF NOT EXISTS 'CREDIT_CARD'",
    "ALTER TYPE paymentmethod ADD VALUE IF NOT EXISTS 'DEBIT_CARD'",
    "ALTER TYPE paymentmethod ADD VALUE IF NOT EXISTS 'BANK_TRANSFER'",
    # processoreventstatus was created from the enum VALUES ("processed") by
    # e5a1c3f7d284 while the ORM writes the NAMES ("PROCESSED"), so the durable
    # webhook ledger could not record a single row on PostgreSQL.
    "ALTER TYPE processoreventstatus ADD VALUE IF NOT EXISTS 'PROCESSED'",
    "ALTER TYPE processoreventstatus ADD VALUE IF NOT EXISTS 'UNRECONCILED'",
    "ALTER TYPE processoreventstatus ADD VALUE IF NOT EXISTS 'FAILED'",
    "ALTER TYPE processoreventstatus ADD VALUE IF NOT EXISTS 'IGNORED'",
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite (and any other dialect) stores these as VARCHAR plus a CHECK
        # constraint generated per column from the model metadata; there is no
        # shared type object to extend.
        return

    for statement in _ADD_VALUE_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    # Enum values cannot be dropped in Postgres, and rows may already use the
    # labels this revision added. Downgrade is intentionally a no-op.
    return
