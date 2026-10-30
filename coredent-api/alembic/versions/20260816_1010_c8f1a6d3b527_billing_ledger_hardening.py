"""billing ledger hardening: invoice tax_rate, payment refunds, unique txn

Revision ID: c8f1a6d3b527
Revises: b7d2e9c1a410
Create Date: 2026-08-16 10:10:00

- invoices.tax_rate: persist the fractional rate so line-item edits can
  recompute tax instead of silently zeroing it.
- payments.refunded_amount: partial-refund bookkeeping; only full refunds
  flip status to REFUNDED.
- payments.transaction_id becomes unique: one ledger row per gateway
  transaction, enforced by the database as the race guard for concurrent
  webhook deliveries.

DATA SAFETY (C-02): an earlier revision of this migration executed
``DELETE FROM payments`` to force uniqueness by discarding every duplicate
except the lowest id. That is irreversible destruction of money records --
it does not reconcile invoice totals, refunds, payment status, or audit
rows, and ``downgrade()`` cannot restore it. The migration now *refuses to
run* when duplicates exist and reports the offending transaction ids so an
operator can reconcile them deliberately. See
``scripts/reconcile_duplicate_payments.py`` for the assisted path.

OFFLINE (``--sql``) MODE: there is no live connection, so the duplicate check
cannot run during rendering. The generated script carries an explicit
``DO ... RAISE WARNING`` block telling the operator to reconcile duplicates
before applying it to any database with payment history; on a fresh database
(no payments) the unique index simply builds.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "c8f1a6d3b527"
down_revision: str | None = "b7d2e9c1a410"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _inspect_safe(bind):
    try:
        return sa.inspect(bind)
    except sa.exc.NoInspectionAvailable:
        return None


def upgrade() -> None:
    bind = op.get_bind()
    if _inspect_safe(bind) is None:
        # Offline (--sql): no live connection, so the duplicate check below
        # cannot run. Emit the DDL statically and embed the warning in the
        # script itself (batch mode needs reflection, so use plain ops).
        op.add_column(
            "invoices", sa.Column("tax_rate", sa.Numeric(8, 6), nullable=True)
        )
        op.execute(
            "UPDATE invoices SET tax_rate = gst_rate / 100.0 "
            "WHERE tax_rate IS NULL AND gst_rate IS NOT NULL"
        )
        op.add_column(
            "payments",
            sa.Column("refunded_amount", sa.Numeric(10, 2), nullable=True),
        )
        op.execute(
            "DO $$ BEGIN RAISE WARNING 'c8f1a6d3b527: this script was "
            "rendered offline, so the duplicate payments.transaction_id "
            "check did NOT run. If this database has payment history, run "
            "scripts/reconcile_duplicate_payments.py --report BEFORE "
            "applying this script; the unique index below will fail on "
            "duplicated transaction_ids.'; END $$"
        )
        op.create_index(
            "uq_payments_transaction_id",
            "payments",
            ["transaction_id"],
            unique=True,
        )
        return

    with op.batch_alter_table("invoices", schema=None) as batch_op:
        batch_op.add_column(sa.Column("tax_rate", sa.Numeric(8, 6), nullable=True))
    # Backfill from the GST percent where present (18.00 -> 0.18); invoices
    # without GST data keep a NULL rate (treated as 0 on next recompute).
    op.execute(
        "UPDATE invoices SET tax_rate = gst_rate / 100.0 "
        "WHERE tax_rate IS NULL AND gst_rate IS NOT NULL"
    )

    with op.batch_alter_table("payments", schema=None) as batch_op:
        batch_op.add_column(sa.Column("refunded_amount", sa.Numeric(10, 2), nullable=True))

    # C-02 FIX: never delete payment rows. Detect duplicates and abort with
    # an actionable report so an operator reconciles the money trail first.
    _abort_if_duplicate_transaction_ids()

    op.create_index(
        "uq_payments_transaction_id",
        "payments",
        ["transaction_id"],
        unique=True,
    )


def _abort_if_duplicate_transaction_ids() -> None:
    """Fail the migration when ``payments.transaction_id`` is not unique.

    Raising here leaves the transaction to roll back, so the added columns
    are discarded too and the database is left exactly as it was. The
    alternative (deleting rows) destroys financial history irreversibly.
    """
    conn = op.get_bind()
    duplicates = conn.execute(
        sa.text(
            """
            SELECT transaction_id, COUNT(*) AS row_count
            FROM payments
            WHERE transaction_id IS NOT NULL
            GROUP BY transaction_id
            HAVING COUNT(*) > 1
            ORDER BY row_count DESC, transaction_id
            """
        )
    ).fetchall()

    if not duplicates:
        return

    total_extra = sum(row.row_count - 1 for row in duplicates)
    sample = ", ".join(
        f"{row.transaction_id} (x{row.row_count})" for row in duplicates[:20]
    )
    if len(duplicates) > 20:
        sample += f", ... and {len(duplicates) - 20} more"

    raise RuntimeError(
        "Refusing to apply migration c8f1a6d3b527: "
        f"{len(duplicates)} transaction_id value(s) are duplicated across "
        f"{total_extra} extra payment row(s). Enforcing uniqueness requires "
        "removing rows, which would destroy financial history and desynchronise "
        "invoice totals, refunds, and audit records.\n\n"
        f"Duplicated transaction_ids: {sample}\n\n"
        "Reconcile these rows before re-running the migration. "
        "`python scripts/reconcile_duplicate_payments.py --report` lists the "
        "affected invoices and proposed merges; `--apply` performs the merge "
        "inside a single transaction with invoice totals recomputed."
    )


def downgrade() -> None:
    op.drop_index("uq_payments_transaction_id", table_name="payments")
    with op.batch_alter_table("payments", schema=None) as batch_op:
        batch_op.drop_column("refunded_amount")
    with op.batch_alter_table("invoices", schema=None) as batch_op:
        batch_op.drop_column("tax_rate")
