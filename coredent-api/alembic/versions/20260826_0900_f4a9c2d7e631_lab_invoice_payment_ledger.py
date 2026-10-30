"""add idempotent lab invoice payment ledger

Revision ID: f4a9c2d7e631
Revises: e8b7d4c1a5f2
Create Date: 2026-08-26 09:00:00

Adds an immutable payment ledger while retaining LabInvoice.amount_paid as a
compatibility aggregate. Existing paid amounts become deterministic opening
ledger entries, so no historical financial state is discarded.

OFFLINE (``--sql``) MODE: the legacy backfill cannot run a read-modify loop
without a live connection. The generated script instead carries an
equivalent static ``INSERT ... SELECT``; the only divergence is that opening
entry ids come from ``gen_random_uuid()`` rather than the deterministic
UUIDv5 (uniqueness is preserved either way).
"""

from collections.abc import Sequence
from datetime import datetime, timezone
from decimal import Decimal
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "f4a9c2d7e631"
down_revision: str | None = "e8b7d4c1a5f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LEGACY_PAYMENT_NAMESPACE = uuid.UUID("86b2cdbc-57ad-45fb-9af5-d743beb472c8")


def _inspect_safe(bind):
    try:
        return sa.inspect(bind)
    except sa.exc.NoInspectionAvailable:
        return None


def upgrade() -> None:
    op.create_table(
        "lab_invoice_payments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "practice_id",
            UUID(as_uuid=True),
            sa.ForeignKey("practices.id"),
            nullable=False,
        ),
        sa.Column(
            "lab_invoice_id",
            UUID(as_uuid=True),
            sa.ForeignKey("lab_invoices.id"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("transaction_id", sa.String(length=255), nullable=False),
        sa.Column("payment_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "recorded_by_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "practice_id",
            "transaction_id",
            name="uq_lab_invoice_payment_practice_transaction",
        ),
    )
    op.create_index(
        "ix_lab_invoice_payments_lab_invoice_id",
        "lab_invoice_payments",
        ["lab_invoice_id"],
    )

    bind = op.get_bind()
    if _inspect_safe(bind) is None:
        # Offline (--sql): equivalent static backfill. gen_random_uuid()
        # stands in for the deterministic UUIDv5 of the online loop.
        op.execute(
            """
            INSERT INTO lab_invoice_payments (
                id, practice_id, lab_invoice_id, amount, transaction_id,
                payment_date, notes, recorded_by_id
            )
            SELECT
                gen_random_uuid(),
                li.practice_id,
                li.id,
                li.amount_paid,
                'LEGACY-LAB-' || li.id,
                COALESCE(li.payment_date, li.updated_at, li.created_at, CURRENT_TIMESTAMP),
                'Opening balance migrated from lab_invoices.amount_paid',
                NULL
            FROM lab_invoices li
            WHERE li.amount_paid > 0
            """
        )
        return

    invoices = sa.table(
        "lab_invoices",
        sa.column("id", UUID(as_uuid=True)),
        sa.column("practice_id", UUID(as_uuid=True)),
        sa.column("amount_paid", sa.Numeric(10, 2)),
        sa.column("payment_date", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    payments = sa.table(
        "lab_invoice_payments",
        sa.column("id", UUID(as_uuid=True)),
        sa.column("practice_id", UUID(as_uuid=True)),
        sa.column("lab_invoice_id", UUID(as_uuid=True)),
        sa.column("amount", sa.Numeric(10, 2)),
        sa.column("transaction_id", sa.String(length=255)),
        sa.column("payment_date", sa.DateTime(timezone=True)),
        sa.column("notes", sa.Text()),
        sa.column("recorded_by_id", UUID(as_uuid=True)),
    )

    historical = bind.execute(
        sa.select(
            invoices.c.id,
            invoices.c.practice_id,
            invoices.c.amount_paid,
            invoices.c.payment_date,
            invoices.c.updated_at,
            invoices.c.created_at,
        ).where(invoices.c.amount_paid > 0)
    ).mappings()
    now = datetime.now(timezone.utc)
    for invoice in historical:
        invoice_id = invoice["id"]
        bind.execute(
            payments.insert().values(
                id=uuid.uuid5(_LEGACY_PAYMENT_NAMESPACE, str(invoice_id)),
                practice_id=invoice["practice_id"],
                lab_invoice_id=invoice_id,
                amount=Decimal(str(invoice["amount_paid"])),
                transaction_id=f"LEGACY-LAB-{invoice_id}",
                payment_date=(
                    invoice["payment_date"]
                    or invoice["updated_at"]
                    or invoice["created_at"]
                    or now
                ),
                notes="Opening balance migrated from lab_invoices.amount_paid",
                recorded_by_id=None,
            )
        )


def downgrade() -> None:
    op.drop_index(
        "ix_lab_invoice_payments_lab_invoice_id",
        table_name="lab_invoice_payments",
    )
    op.drop_table("lab_invoice_payments")
