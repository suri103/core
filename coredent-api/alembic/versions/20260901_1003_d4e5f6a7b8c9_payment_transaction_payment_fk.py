"""link payment_transactions to the invoice-ledger payments

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-01 10:03:00

M5: ``PaymentTransaction`` (processor ledger) and ``Payment`` (invoice
ledger) previously shared no foreign key or other explicit link. This adds a
nullable ``payment_id`` FK — nullable so manual ledger entries (which never
touch a gateway) and legacy rows remain valid — and backfills the link
deterministically: a transaction whose ``processor_transaction_id`` equals a
``Payment.transaction_id`` in the same practice is that payment's processor
row. Rows without a match keep NULL.

Schema-drift repair folded in (caught by the SQLite test suite): the model
``Payment.practice_id`` (NOT NULL, tenant scoping) existed only in the
model — the baseline ``payments`` table never had the column and no later
migration added it, so the M5 backfill crashed with ``no such column:
p.practice_id``. This revision adds the column, backfills it from the
parent invoice (``payments.invoice_id -> invoices.practice_id``), then
enforces NOT NULL + FK + index.
"""

from collections.abc import Sequence

import logging

import sqlalchemy as sa
from alembic import op

logger = logging.getLogger(__name__)

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    has_inspection = True
    try:
        sa.inspect(bind)
    except sa.exc.NoInspectionAvailable:  # offline (--sql) rendering
        has_inspection = False

    if has_inspection:
        # The FKs/columns are added inside batch blocks on SQLite (table
        # recreation) and as plain DDL on PostgreSQL.
        with op.batch_alter_table("payments") as batch_op:
            batch_op.add_column(
                sa.Column("practice_id", sa.UUID(), nullable=True)
            )
        # Deterministic backfill: every payment belongs to exactly one
        # invoice, and invoices are practice-scoped.
        op.execute(
            sa.text(
                "UPDATE payments SET practice_id = ("
                "  SELECT i.practice_id FROM invoices i"
                "  WHERE i.id = payments.invoice_id"
                ") WHERE practice_id IS NULL"
            )
        )
        with op.batch_alter_table("payments") as batch_op:
            batch_op.alter_column(
                "practice_id",
                existing_type=sa.UUID(),
                nullable=False,
            )
            batch_op.create_foreign_key(
                "fk_payments_practice_id", "practices", ["practice_id"], ["id"]
            )
            batch_op.create_index(
                "ix_payments_practice_id", ["practice_id"], unique=False
            )

        # The FK is added inside a batch block on SQLite (table recreation)
        # and as plain DDL on PostgreSQL.
        with op.batch_alter_table("payment_transactions") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "payment_id",
                    sa.UUID(),
                    sa.ForeignKey(
                        "payments.id", name="fk_payment_transactions_payment_id"
                    ),
                    nullable=True,
                )
            )
    else:
        # Offline (--sql): emit the static form (M-04 convention).
        op.add_column(
            "payments",
            sa.Column("practice_id", sa.UUID(), nullable=True),
        )
        op.execute(
            "UPDATE payments SET practice_id = ("
            "  SELECT i.practice_id FROM invoices i"
            "  WHERE i.id = payments.invoice_id"
            ") WHERE practice_id IS NULL"
        )
        op.alter_column("payments", "practice_id", nullable=False)
        op.create_foreign_key(
            "fk_payments_practice_id", "payments", "practices",
            ["practice_id"], ["id"],
        )
        op.create_index("ix_payments_practice_id", "payments", ["practice_id"])

        op.add_column(
            "payment_transactions",
            sa.Column("payment_id", sa.UUID(), nullable=True),
        )
        op.create_foreign_key(
            "fk_payment_transactions_payment_id",
            "payment_transactions",
            "payments",
            ["payment_id"],
            ["id"],
        )

    # Deterministic backfill: the two ledgers carry the same external id
    # (Payment.transaction_id == PaymentTransaction.processor_transaction_id).
    # This is a plain correlated UPDATE, valid on both PostgreSQL and SQLite.
    backfill = sa.text(
        "UPDATE payment_transactions SET payment_id = ("
        "  SELECT p.id FROM payments p"
        "  WHERE p.transaction_id = payment_transactions.processor_transaction_id"
        "    AND p.practice_id = payment_transactions.practice_id"
        "  LIMIT 1"
        ") WHERE payment_id IS NULL"
    )
    op.execute(backfill)
    if has_inspection:
        logger.info(
            "%s: added payments.practice_id (backfilled from invoices) and "
            "backfilled payment_transactions.payment_id",
            revision,
        )


def downgrade() -> None:
    bind = op.get_bind()
    try:
        sa.inspect(bind)
    except sa.exc.NoInspectionAvailable:  # offline (--sql) rendering
        op.drop_constraint(
            "fk_payment_transactions_payment_id",
            "payment_transactions",
            type_="foreignkey",
        )
        op.drop_column("payment_transactions", "payment_id")
        op.drop_index("ix_payments_practice_id", table_name="payments")
        op.drop_constraint(
            "fk_payments_practice_id", "payments", type_="foreignkey"
        )
        op.drop_column("payments", "practice_id")
        return

    with op.batch_alter_table("payment_transactions") as batch_op:
        batch_op.drop_constraint("fk_payment_transactions_payment_id", type_="foreignkey")
        batch_op.drop_column("payment_id")
    with op.batch_alter_table("payments") as batch_op:
        batch_op.drop_index("ix_payments_practice_id")
        batch_op.drop_constraint("fk_payments_practice_id", type_="foreignkey")
        batch_op.drop_column("practice_id")
