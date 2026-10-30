"""add practices.inbound_phone_number and missing FK indexes

Revision ID: e3f4a5b6c7d8
Revises: c2d3e4f5a6b7
Create Date: 2026-10-15 14:00:00

1. Nullable VARCHAR(20) on practices. Stores dedicated inbound virtual phone number
   (e.g., Twilio/Telnyx DID in E.164 format) for multi-tenant webhook dispatch
   (communications_service.handle_inbound_sms). NULL for practices using shared
   system number or without SMS configured.
2. Missing foreign-key indexes flagged during Phase 3 verification:
   - patient_portal_access_codes.practice_id
   - patient_portal_sessions.practice_id
   - lab_invoice_payments.recorded_by_id
   - payment_transactions.payment_id
   - processor_webhook_events.payment_transaction_id
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "e3f4a5b6c7d8"
down_revision: str | None = "c2d3e4f5a6b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. practices.inbound_phone_number
    with op.batch_alter_table("practices", schema=None) as batch_op:
        batch_op.add_column(sa.Column("inbound_phone_number", sa.String(length=20), nullable=True))
        batch_op.create_index("ix_practices_inbound_phone_number", ["inbound_phone_number"], unique=False)

    # 2. Foreign-key indexes
    with op.batch_alter_table("patient_portal_access_codes", schema=None) as batch_op:
        batch_op.create_index("ix_patient_portal_access_codes_practice_id", ["practice_id"], unique=False)

    with op.batch_alter_table("patient_portal_sessions", schema=None) as batch_op:
        batch_op.create_index("ix_patient_portal_sessions_practice_id", ["practice_id"], unique=False)

    with op.batch_alter_table("lab_invoice_payments", schema=None) as batch_op:
        batch_op.create_index("ix_lab_invoice_payments_recorded_by_id", ["recorded_by_id"], unique=False)

    with op.batch_alter_table("payment_transactions", schema=None) as batch_op:
        batch_op.create_index("ix_payment_transactions_payment_id", ["payment_id"], unique=False)

    with op.batch_alter_table("processor_webhook_events", schema=None) as batch_op:
        batch_op.create_index("ix_processor_webhook_events_payment_transaction_id", ["payment_transaction_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("processor_webhook_events", schema=None) as batch_op:
        batch_op.drop_index("ix_processor_webhook_events_payment_transaction_id")

    with op.batch_alter_table("payment_transactions", schema=None) as batch_op:
        batch_op.drop_index("ix_payment_transactions_payment_id")

    with op.batch_alter_table("lab_invoice_payments", schema=None) as batch_op:
        batch_op.drop_index("ix_lab_invoice_payments_recorded_by_id")

    with op.batch_alter_table("patient_portal_sessions", schema=None) as batch_op:
        batch_op.drop_index("ix_patient_portal_sessions_practice_id")

    with op.batch_alter_table("patient_portal_access_codes", schema=None) as batch_op:
        batch_op.drop_index("ix_patient_portal_access_codes_practice_id")

    with op.batch_alter_table("practices", schema=None) as batch_op:
        batch_op.drop_index("ix_practices_inbound_phone_number")
        batch_op.drop_column("inbound_phone_number")
