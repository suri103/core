"""scope financial uniques per practice (L-1/L-2)

Revision ID: f3a4b5c6d7e8
Revises: c8d4f7e2a6b1
Create Date: 2026-09-03 10:00:00

L-1 FIX: ``payments.transaction_id`` was globally unique
(``uq_payments_transaction_id``). A scoped pre-check missed foreign-practice
rows, so the insert hit the global unique and the 409-vs-200 difference
leaked cross-tenant existence for guessable references (check/receipt
numbers). Replace with composite ``(practice_id, transaction_id)``
(``uq_payment_practice_transaction``) matching the endpoint replay lookup.

L-2 FIX: ``lab_invoices.invoice_number`` and ``purchase_orders.order_number``
were globally unique, letting one tenant squat/probe another's numbers and
forcing a global advisory lock for lab invoices. Replace with per-practice
composites (``uq_lab_invoice_practice_number``,
``uq_purchase_order_practice_number``) like invoices/cases.

Relaxing direction: global uniqueness implies per-practice uniqueness, so
existing rows already satisfy the new constraints — no backfill or
conflict resolution needed. Deploying never locks out existing users.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f3a4b5c6d7e8"
down_revision: str | None = "c8d4f7e2a6b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_index(table: str, name: str) -> bool:
    bind = op.get_bind()
    try:
        insp = sa.inspect(bind)
    except sa.exc.NoInspectionAvailable:
        return False
    try:
        return any(ix["name"] == name for ix in insp.get_indexes(table))
    except Exception:
        return False


def _has_constraint(table: str, name: str) -> bool:
    bind = op.get_bind()
    try:
        insp = sa.inspect(bind)
    except sa.exc.NoInspectionAvailable:
        return False
    try:
        return any(c["name"] == name for c in insp.get_unique_constraints(table))
    except Exception:
        return False


def upgrade() -> None:
    bind = op.get_bind()
    has_inspection = True
    try:
        sa.inspect(bind)
    except sa.exc.NoInspectionAvailable:  # offline (--sql) rendering
        has_inspection = False

    if not has_inspection:
        # Offline: emit static DDL (repo convention for --sql rendering).
        op.execute("DROP INDEX IF EXISTS uq_payments_transaction_id;")
        op.execute(
            "ALTER TABLE payments ADD CONSTRAINT uq_payment_practice_transaction "
            "UNIQUE (practice_id, transaction_id);"
        )
        op.execute(
            "ALTER TABLE lab_invoices ADD CONSTRAINT uq_lab_invoice_practice_number "
            "UNIQUE (practice_id, invoice_number);"
        )
        op.execute(
            "ALTER TABLE purchase_orders ADD CONSTRAINT uq_purchase_order_practice_number "
            "UNIQUE (practice_id, order_number);"
        )
        return

    # --- payments.transaction_id: global -> per-practice ---
    # Created as a unique index named uq_payments_transaction_id.
    if _has_index("payments", "uq_payments_transaction_id"):
        with op.batch_alter_table("payments") as batch_op:
            batch_op.drop_index("uq_payments_transaction_id")
    if not _has_constraint("payments", "uq_payment_practice_transaction"):
        with op.batch_alter_table("payments") as batch_op:
            batch_op.create_unique_constraint(
                "uq_payment_practice_transaction",
                ["practice_id", "transaction_id"],
            )

    # --- lab_invoices.invoice_number: global -> per-practice ---
    # Baseline used an unnamed UniqueConstraint('invoice_number'); find and
    # drop any single-column unique on invoice_number, then add composite.
    try:
        insp = sa.inspect(bind)
        for c in insp.get_unique_constraints("lab_invoices"):
            cols = list(c.get("column_names") or [])
            if cols == ["invoice_number"] and c["name"]:
                with op.batch_alter_table("lab_invoices") as batch_op:
                    batch_op.drop_constraint(c["name"], type_="unique")
        for ix in insp.get_indexes("lab_invoices"):
            if ix.get("unique") and ix.get("column_names") == ["invoice_number"]:
                with op.batch_alter_table("lab_invoices") as batch_op:
                    batch_op.drop_index(ix["name"])
    except Exception:
        pass
    if not _has_constraint("lab_invoices", "uq_lab_invoice_practice_number"):
        with op.batch_alter_table("lab_invoices") as batch_op:
            batch_op.create_unique_constraint(
                "uq_lab_invoice_practice_number",
                ["practice_id", "invoice_number"],
            )

    # --- purchase_orders.order_number: global -> per-practice ---
    try:
        insp = sa.inspect(bind)
        for c in insp.get_unique_constraints("purchase_orders"):
            cols = list(c.get("column_names") or [])
            if cols == ["order_number"] and c["name"]:
                with op.batch_alter_table("purchase_orders") as batch_op:
                    batch_op.drop_constraint(c["name"], type_="unique")
        for ix in insp.get_indexes("purchase_orders"):
            if ix.get("unique") and ix.get("column_names") == ["order_number"]:
                with op.batch_alter_table("purchase_orders") as batch_op:
                    batch_op.drop_index(ix["name"])
    except Exception:
        pass
    if not _has_constraint("purchase_orders", "uq_purchase_order_practice_number"):
        with op.batch_alter_table("purchase_orders") as batch_op:
            batch_op.create_unique_constraint(
                "uq_purchase_order_practice_number",
                ["practice_id", "order_number"],
            )


def downgrade() -> None:
    bind = op.get_bind()
    try:
        sa.inspect(bind)
        has_inspection = True
    except sa.exc.NoInspectionAvailable:
        has_inspection = False

    if not has_inspection:
        op.execute("ALTER TABLE payments DROP CONSTRAINT IF EXISTS uq_payment_practice_transaction;")
        op.execute("CREATE UNIQUE INDEX uq_payments_transaction_id ON payments (transaction_id);")
        op.execute("ALTER TABLE lab_invoices DROP CONSTRAINT IF EXISTS uq_lab_invoice_practice_number;")
        op.execute("ALTER TABLE purchase_orders DROP CONSTRAINT IF EXISTS uq_purchase_order_practice_number;")
        return

    with op.batch_alter_table("payments") as batch_op:
        try:
            batch_op.drop_constraint("uq_payment_practice_transaction", type_="unique")
        except Exception:
            pass
        try:
            batch_op.create_index("uq_payments_transaction_id", ["transaction_id"], unique=True)
        except Exception:
            pass
    with op.batch_alter_table("lab_invoices") as batch_op:
        try:
            batch_op.drop_constraint("uq_lab_invoice_practice_number", type_="unique")
        except Exception:
            pass
    with op.batch_alter_table("purchase_orders") as batch_op:
        try:
            batch_op.drop_constraint("uq_purchase_order_practice_number", type_="unique")
        except Exception:
            pass
