"""Recording and reconciliation of payment-processor webhook events.

Audit finding C-01. Two invariants live here:

1. **Never acknowledge money we did not record.** Every processor event that
   reports a monetary outcome either produces a ``PaymentTransaction`` or is
   persisted as ``UNRECONCILED`` in ``processor_webhook_events``. Only then
   may the endpoint answer 200.

2. **Never guess the tenant.** ``PaymentTransaction.practice_id`` and
   ``patient_id`` are NOT NULL, and inventing them would attach one
   practice's money to another. When processor metadata is insufficient, the
   event is quarantined for an operator instead.

PHI: only allowlisted routing fields are persisted from the payload.

M5: ``PaymentTransaction.payment_id`` links the processor ledger row to its
invoice-ledger ``Payment`` (resolved from ``Payment.transaction_id ==
PaymentTransaction.processor_transaction_id`` within the same practice).
The link is nullable by design: manual ledger entries (cash/check/UPI) have
no processor transaction, and legacy rows predate the link.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.patient import Patient
from app.models.payment import (
    PaymentMethod,
    PaymentStatus,
    PaymentTransaction,
)
from app.models.processor_event import ProcessorEventStatus, ProcessorWebhookEvent

logger = logging.getLogger(__name__)

# Fields copied out of a processor payload into ProcessorWebhookEvent.summary.
# Deliberately excludes anything free-text or patient-identifying:
# `description`, `receipt_email`, `shipping`, `billing_details` and the raw
# metadata blob are all omitted (audit finding M-22).
_SUMMARY_ALLOWLIST = (
    "id",
    "object",
    "amount",
    "amount_received",
    "amount_refunded",
    "currency",
    "status",
    "created",
    "livemode",
    "payment_method_types",
)

# Metadata keys we trust for tenant routing. These are set by our own
# create-payment path, never by the customer.
_METADATA_PRACTICE_KEYS = ("practice_id",)
_METADATA_PATIENT_KEYS = ("patient_id",)
_METADATA_INVOICE_KEYS = ("invoice_id",)


def summarize_event(payload: Mapping[str, Any]) -> dict:
    """Extract the non-PHI subset of a processor object for storage."""
    summary = {k: payload.get(k) for k in _SUMMARY_ALLOWLIST if k in payload}
    # Keep only our own routing metadata, not arbitrary customer-supplied keys.
    metadata = payload.get("metadata") or {}
    routing = {
        k: metadata.get(k)
        for k in (*_METADATA_PRACTICE_KEYS, *_METADATA_PATIENT_KEYS, *_METADATA_INVOICE_KEYS)
        if metadata.get(k)
    }
    if routing:
        summary["routing_metadata"] = routing
    return summary


def _first_uuid(metadata: Mapping[str, Any], keys: tuple[str, ...]) -> Optional[UUID]:
    for key in keys:
        raw = metadata.get(key)
        if not raw:
            continue
        try:
            return UUID(str(raw))
        except (ValueError, TypeError, AttributeError):
            logger.warning("Processor metadata %s is not a valid UUID; ignoring", key)
    return None


def minor_units_to_decimal(amount_minor: Optional[int], currency: Optional[str]) -> Decimal:
    """Convert processor minor units to a Decimal amount.

    Most currencies use 2 decimal places. Zero-decimal currencies (JPY, KRW,
    VND, ...) are reported by Stripe in whole units, so dividing by 100 would
    under-record by 100x. The zero-decimal set is from Stripe's documented
    list.
    """
    if amount_minor is None:
        return Decimal("0.00")
    zero_decimal = {
        "bif", "clp", "djf", "gnf", "jpy", "kmf", "krw", "mga",
        "pyg", "rwf", "ugx", "vnd", "vuv", "xaf", "xof", "xpf",
    }
    code = (currency or "usd").lower()
    if code in zero_decimal:
        return Decimal(amount_minor)
    return (Decimal(amount_minor) / Decimal(100)).quantize(Decimal("0.01"))


async def record_event(
    db: AsyncSession,
    *,
    processor: str,
    event_id: Optional[str],
    event_type: str,
    payload: Mapping[str, Any],
    status: ProcessorEventStatus,
    practice_id: Optional[UUID] = None,
    payment_transaction_id: Optional[UUID] = None,
    error_message: Optional[str] = None,
) -> Optional[ProcessorWebhookEvent]:
    """Upsert the durable record for a processor event.

    Returns the row, or ``None`` when ``event_id`` is absent (nothing to key
    idempotency on). Never raises on a duplicate ``event_id``: the existing
    row is updated instead, which is what a Redis-flush replay looks like.
    """
    if not event_id:
        logger.warning(
            "Processor event of type %s arrived without an id; cannot record "
            "durably", event_type
        )
        return None

    existing = (
        await db.execute(
            select(ProcessorWebhookEvent).where(
                ProcessorWebhookEvent.event_id == event_id
            )
        )
    ).scalar_one_or_none()

    amount_minor = payload.get("amount_received") or payload.get("amount")
    currency = payload.get("currency")
    resolved_at = (
        datetime.now(timezone.utc)
        if status in (ProcessorEventStatus.PROCESSED, ProcessorEventStatus.IGNORED)
        else None
    )

    if existing is not None:
        existing.status = status
        existing.practice_id = practice_id or existing.practice_id
        existing.payment_transaction_id = (
            payment_transaction_id or existing.payment_transaction_id
        )
        existing.error_message = error_message
        existing.summary = summarize_event(payload)
        existing.resolved_at = resolved_at or existing.resolved_at
        return existing

    row = ProcessorWebhookEvent(
        processor=processor,
        event_id=event_id,
        event_type=event_type,
        status=status,
        practice_id=practice_id,
        processor_object_id=payload.get("id"),
        amount_minor=int(amount_minor) if amount_minor is not None else None,
        currency=currency,
        payment_transaction_id=payment_transaction_id,
        summary=summarize_event(payload),
        error_message=error_message,
    )
    row.resolved_at = resolved_at
    db.add(row)
    try:
        # H1 FIX: flush inside a SAVEPOINT so a concurrent duplicate event_id
        # rolls back only this insert — a full rollback() would discard the
        # caller's pending Payment.status/refunded_amount mutations and the
        # webhook would return 200 having lost the money update.
        async with db.begin_nested():
            await db.flush()
    except IntegrityError:
        # Concurrent delivery inserted it first; treat as already recorded.
        # The savepoint rollback above preserved the caller's pending changes.
        return (
            await db.execute(
                select(ProcessorWebhookEvent).where(
                    ProcessorWebhookEvent.event_id == event_id
                )
            )
        ).scalar_one_or_none()
    return row


async def link_invoice_ledger_payment(
    db: AsyncSession, transaction: PaymentTransaction
) -> None:
    """Attach the invoice-ledger ``Payment`` matching this processor row.

    M5: both ledgers record the same gateway charge — ``Payment`` with
    ``transaction_id`` (invoice ledger) and ``PaymentTransaction`` with
    ``processor_transaction_id`` (processor ledger) carry the same external
    id. Linking them makes the dual-ledger relationship explicit instead of
    implicit. No-op when the invoice-ledger row does not exist (manual
    entries, reconstructed rows) or is already linked.
    """
    if transaction.payment_id is not None:
        return
    if not transaction.processor_transaction_id:
        return
    from app.models.billing import Payment

    match = (
        await db.execute(
            select(Payment.id).where(
                Payment.transaction_id == transaction.processor_transaction_id,
                Payment.practice_id == transaction.practice_id,
            )
        )
    ).scalar_one_or_none()
    if match is not None:
        transaction.payment_id = match


async def resolve_payment_transaction(
    db: AsyncSession,
    payment_intent: Mapping[str, Any],
) -> tuple[Optional[PaymentTransaction], Optional[str]]:
    """Find or reconstruct the ledger row for a processor payment intent.

    Returns ``(transaction, reason_unresolvable)``. Exactly one is non-None.

    Lookup order:
      1. existing row by ``processor_transaction_id`` (the normal case);
      2. reconstruct from our own routing metadata when the row is missing
         because the pre-webhook insert never happened.

    Reconstruction requires a practice and a patient that actually belong
    together. It never invents them.
    """
    processor_id = payment_intent.get("id")
    if not processor_id:
        return None, "processor payment object has no id"

    existing = (
        await db.execute(
            select(PaymentTransaction).where(
                PaymentTransaction.processor_transaction_id == processor_id
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        await link_invoice_ledger_payment(db, existing)
        return existing, None

    metadata = payment_intent.get("metadata") or {}
    practice_id = _first_uuid(metadata, _METADATA_PRACTICE_KEYS)
    patient_id = _first_uuid(metadata, _METADATA_PATIENT_KEYS)

    if practice_id is None or patient_id is None:
        return None, (
            "no local ledger row and processor metadata lacks practice_id/"
            "patient_id, so the payment cannot be attributed to a tenant"
        )

    # The patient must belong to the claimed practice. Without this a
    # spoofable metadata pair would post money across tenants.
    patient = (
        await db.execute(
            select(Patient).where(
                Patient.id == patient_id,
                Patient.practice_id == practice_id,
            )
        )
    ).scalar_one_or_none()
    if patient is None:
        return None, (
            f"metadata patient {patient_id} does not belong to practice "
            f"{practice_id}"
        )

    invoice_id = _first_uuid(metadata, _METADATA_INVOICE_KEYS)
    if invoice_id is not None:
        from app.models.billing import Invoice

        invoice = (
            await db.execute(
                select(Invoice).where(
                    Invoice.id == invoice_id,
                    Invoice.practice_id == practice_id,
                    Invoice.patient_id == patient_id,
                )
            )
        ).scalar_one_or_none()
        if invoice is None:
            # Better to record the payment without the invoice link than to
            # attach it to a foreign invoice.
            logger.warning(
                "Processor metadata invoice %s does not match practice/patient; "
                "recording payment without invoice link",
                invoice_id,
            )
            invoice_id = None

    amount = minor_units_to_decimal(
        payment_intent.get("amount_received") or payment_intent.get("amount"),
        payment_intent.get("currency"),
    )

    transaction = PaymentTransaction(
        practice_id=practice_id,
        patient_id=patient_id,
        invoice_id=invoice_id,
        transaction_type="charge",
        payment_method=PaymentMethod.CREDIT_CARD,
        amount=amount,
        total_amount=amount,
        currency=(payment_intent.get("currency") or "usd").upper()[:3],
        status=PaymentStatus.PENDING,
        processor_transaction_id=processor_id,
        notes=(
            "Ledger row reconstructed from processor webhook; no local record "
            "existed at the time the payment succeeded."
        ),
    )
    db.add(transaction)
    try:
        await db.flush()
    except IntegrityError:
        # A concurrent delivery created it. Re-read and use that row.
        await db.rollback()
        winner = (
            await db.execute(
                select(PaymentTransaction).where(
                    PaymentTransaction.processor_transaction_id == processor_id
                )
            )
        ).scalar_one_or_none()
        if winner is None:
            return None, "concurrent insert conflict could not be resolved"
        return winner, None

    logger.warning(
        "Reconstructed missing PaymentTransaction %s for processor payment %s "
        "(practice=%s)",
        transaction.id,
        processor_id,
        practice_id,
    )
    await link_invoice_ledger_payment(db, transaction)
    return transaction, None
