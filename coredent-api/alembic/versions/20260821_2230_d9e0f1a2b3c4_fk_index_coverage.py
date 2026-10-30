"""index coverage: add missing FK indexes

Revision ID: d9e0f1a2b3c4
Revises: c7d8e9f0a1b2
Create Date: 2026-08-21 22:30:00

WHY
---
scripts/check_index_coverage.py found ~55 foreign-key columns with no index.
Every tenant-scoped query filters or joins on these (practice_id above all),
so each was a potential full scan as data grows. Notably:
  - eligibility.patient_id / insurance_pre_authorizations.patient_id /
    explanations_of_benefits.claim_id back the M1 tenant-scoped joins
  - payment_plan_installments.plan_id backs the installment selectinload
  - reminders.appointment_id is indexed by b8e4f6a2c9d7 already

OPERATIONS NOTE (PostgreSQL)
----------------------------
Plain CREATE INDEX takes a brief ACCESS EXCLUSIVE-ish lock while building.
For a young SaaS dataset this is seconds; if a table has grown large,
create that one index manually with CONCURRENTLY BEFORE running this
migration (it will skip existing indexes), or run during low traffic.

Idempotent: reflection-guarded, skips indexes that already exist.

Offline (``--sql``) rendering emits CREATE INDEX for every target statically
(M-04 fix); it previously emitted nothing. None of the target index names
collide with any index created elsewhere in the chain, so the emitted script
is safe to run against a chain-built database.
"""

from collections.abc import Sequence

import logging

import sqlalchemy as sa
from alembic import op

logger = logging.getLogger(__name__)

revision: str = "d9e0f1a2b3c4"
down_revision: str | None = "c7d8e9f0a1b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# (table, column) pairs needing an index. Generated from
# scripts/check_index_coverage.py against the migrated schema.
_INDEX_TARGETS = [
    ("practices", "group_id"),
    ("appointment_types", "practice_id"),
    ("booking_pages", "practice_id"),
    ("chairs", "practice_id"),
    ("document_templates", "practice_id"),
    ("document_templates", "related_template_id"),
    ("fee_schedules", "practice_id"),
    ("image_templates", "practice_id"),
    ("labs", "practice_id"),
    ("marketing_campaigns", "practice_id"),
    ("marketing_templates", "practice_id"),
    ("message_templates", "practice_id"),
    ("payment_terminals", "practice_id"),
    ("referral_reports", "practice_id"),
    ("lab_cases", "lab_id"),
    ("lab_cases", "patient_id"),
    ("lab_cases", "provider_id"),
    ("lab_invoices", "lab_id"),
    ("lab_communications", "lab_case_id"),
    ("purchase_orders", "supplier_id"),
    ("purchase_order_items", "order_id"),
    ("purchase_order_items", "item_id"),
    ("recurring_billing", "patient_id"),
    ("recurring_billing", "practice_id"),
    ("recurring_billing", "payment_card_id"),
    ("referral_communications", "referral_id"),
    ("treatment_phases", "treatment_plan_id"),
    ("treatment_plan_notes", "treatment_plan_id"),
    ("treatment_plan_notes", "author_id"),
    ("booking_notifications", "booking_id"),
    ("document_signatures", "signed_by_user_id"),
    ("document_signatures", "document_id"),
    ("document_signatures", "signer_id"),
    ("signature_fields", "document_id"),
    ("eligibility", "patient_insurance_id"),
    ("eligibility", "patient_id"),
    ("eligibility", "carrier_id"),
    ("insurance_claims", "patient_insurance_id"),
    ("insurance_claims", "carrier_id"),
    ("insurance_claims", "patient_id"),
    ("insurance_pre_authorizations", "patient_id"),
    ("insurance_pre_authorizations", "patient_insurance_id"),
    ("payment_plan_installments", "plan_id"),
    ("payment_transactions", "recurring_billing_id"),
    ("payment_transactions", "payment_card_id"),
    ("payment_transactions", "patient_id"),
    ("payment_transactions", "practice_id"),
    ("payment_transactions", "invoice_id"),
    ("waitlist_entries", "booking_id"),
    ("waitlist_entries", "booking_page_id"),
    ("waitlist_entries", "appointment_type_id"),
    ("waitlist_entries", "practice_id"),
    ("waitlist_entries", "patient_id"),
    ("explanations_of_benefits", "claim_id"),
    ("treatment_procedures", "appointment_id"),
    ("treatment_procedures", "pre_auth_id"),
    ("treatment_procedures", "treatment_plan_id"),
    ("treatment_procedures", "phase_id"),
    # --- remainder surfaced by the full check run -----------------------
    ("referral_sources", "practice_id"),
    ("suppliers", "practice_id"),
    ("treatment_plan_templates", "practice_id"),
    ("audit_logs", "user_id"),
    ("booking_availability", "practice_id"),
    ("booking_availability", "provider_id"),
    ("conversations", "auto_response_template_id"),
    ("conversations", "practice_id"),
    ("conversations", "patient_id"),
    ("conversations", "assigned_user_id"),
    ("image_series", "patient_id"),
    ("image_series", "practice_id"),
    ("image_series", "provider_id"),
    ("insurance_carriers", "practice_id"),
    ("insurance_carriers", "fee_schedule_id"),
    ("inventory_alerts", "practice_id"),
    ("inventory_alerts", "item_id"),
    ("inventory_alerts", "resolved_by"),
    ("inventory_transactions", "item_id"),
    ("inventory_transactions", "user_id"),
    ("inventory_transactions", "practice_id"),
    ("invoices", "patient_id"),
    ("marketing_campaign_segments", "campaign_id"),
    ("marketing_emails", "campaign_id"),
    ("marketing_emails", "patient_id"),
    ("newsletter_subscriptions", "patient_id"),
    ("newsletter_subscriptions", "practice_id"),
    ("patient_images", "practice_id"),
    ("patient_images", "patient_id"),
    ("patient_images", "provider_id"),
    ("payment_cards", "practice_id"),
    ("payment_cards", "patient_id"),
    ("payment_settings", "default_payment_terminal_id"),
    ("perio_charts", "provider_id"),
    ("perio_charts", "patient_id"),
    ("purchase_orders", "practice_id"),
    ("purchase_orders", "ordered_by"),
    ("referrals", "referral_source_id"),
    ("referrals", "referring_provider_id"),
    ("referrals", "target_practice_id"),
    ("referrals", "patient_id"),
    ("reminder_schedules", "practice_id"),
    ("reminder_schedules", "template_id"),
    ("reminder_schedules", "appointment_type_id"),
    ("sessions", "user_id"),
    ("staff_invitations", "invited_by"),
    ("treatment_plans", "practice_id"),
    ("treatment_plans", "provider_id"),
    ("treatment_plans", "patient_id"),
    ("clinical_notes", "patient_id"),
    ("clinical_notes", "appointment_id"),
    ("clinical_notes", "provider_id"),
    ("conversation_messages", "sender_id"),
    ("conversation_messages", "conversation_id"),
    ("documents", "appointment_id"),
    ("documents", "practice_id"),
    ("documents", "created_by"),
    ("documents", "patient_id"),
    ("documents", "template_id"),
    ("documents", "treatment_plan_id"),
    ("lab_communications", "user_id"),
    ("lab_invoices", "practice_id"),
    ("lab_invoices", "lab_case_id"),
    ("online_bookings", "appointment_id"),
    ("online_bookings", "practice_id"),
    ("online_bookings", "patient_id"),
    ("online_bookings", "booking_page_id"),
    ("online_bookings", "provider_id"),
    ("online_bookings", "appointment_type_id"),
    ("patient_insurances", "verified_by"),
    ("patient_insurances", "carrier_id"),
    ("patient_insurances", "patient_id"),
    ("patient_messages", "appointment_id"),
    ("patient_messages", "patient_id"),
    ("patient_messages", "template_id"),
    ("patient_messages", "user_id"),
    ("patient_messages", "practice_id"),
    ("patient_messages", "parent_message_id"),
    ("payment_plans", "practice_id"),
    ("payment_plans", "invoice_id"),
    ("payment_plans", "patient_id"),
    ("payments", "invoice_id"),
    ("payments", "patient_id"),
    ("perio_chart_entries", "perio_chart_id"),
    ("referral_communications", "user_id"),
]


def _inspect_safe(bind):
    try:
        return sa.inspect(bind)
    except sa.exc.NoInspectionAvailable:
        return None


def upgrade() -> None:
    bind = op.get_bind()
    insp = _inspect_safe(bind)
    if insp is None:
        # Offline (--sql) rendering: emit every target statically (M-04).
        for table_name, column_name in _INDEX_TARGETS:
            op.create_index(
                f"ix_{table_name}_{column_name}", table_name, [column_name]
            )
        return

    existing_tables = set(insp.get_table_names())
    created = 0
    for table_name, column_name in _INDEX_TARGETS:
        if table_name not in existing_tables:
            continue
        index_name = f"ix_{table_name}_{column_name}"
        existing_indexes = {ix["name"] for ix in insp.get_indexes(table_name)}
        if index_name in existing_indexes:
            continue
        op.create_index(index_name, table_name, [column_name])
        created += 1
    logger.info("d9e0f1a2b3c4: created %d FK indexes", created)


def downgrade() -> None:
    bind = op.get_bind()
    insp = _inspect_safe(bind)
    if insp is None:
        return

    existing_tables = set(insp.get_table_names())
    for table_name, column_name in reversed(_INDEX_TARGETS):
        if table_name not in existing_tables:
            continue
        index_name = f"ix_{table_name}_{column_name}"
        existing_indexes = {ix["name"] for ix in insp.get_indexes(table_name)}
        if index_name in existing_indexes:
            op.drop_index(index_name, table_name=table_name)
