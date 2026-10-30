"""Single source of truth for derived invoice status.

Audit finding M-03: ``InvoiceStatus.OVERDUE`` was both derived by the
scheduled due-date sweep *and* settable by any client through
``PUT /billing/invoices/{id}``, so a caller could declare a financial state
that the sweep is supposed to own. PAID / PARTIALLY_PAID had the same
problem in reverse -- they are functions of the payment ledger, but the
transition matrix let them be reached by hand in some paths.

Status is now derived from two facts only: the payment ledger, and the due
date relative to the practice's business day. Clients may only move an
invoice between the states they legitimately own (DRAFT -> PENDING, and
either -> CANCELLED); everything else is computed here.
"""

from __future__ import annotations

from datetime import date, tzinfo
from decimal import Decimal
from typing import Optional

from app.models.billing import Invoice, InvoiceStatus

# States a client may set directly. Everything else is derived.
CLIENT_SETTABLE_STATUSES: frozenset[InvoiceStatus] = frozenset(
    {InvoiceStatus.DRAFT, InvoiceStatus.PENDING, InvoiceStatus.CANCELLED}
)

# States a brand-new invoice may be created in.
CREATABLE_STATUSES: frozenset[InvoiceStatus] = frozenset(
    {InvoiceStatus.DRAFT, InvoiceStatus.PENDING}
)

# Statuses that accept new money.
PAYABLE_STATUSES: frozenset[InvoiceStatus] = frozenset(
    {InvoiceStatus.PENDING, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE}
)

# Terminal / non-derivable statuses: never recomputed away.
_STICKY_STATUSES: frozenset[InvoiceStatus] = frozenset(
    {InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED}
)


def derive_invoice_status(
    invoice: Invoice,
    *,
    business_today: Optional[date] = None,
    tz: Optional[tzinfo] = None,
) -> InvoiceStatus:
    """Return the status implied by the invoice's ledger and due date.

    ``invoice.payments`` must already be loaded.

    ``business_today`` is the practice's current business date (see
    :mod:`app.core.business_time`). Pass it whenever overdue evaluation
    matters; omit it to skip overdue promotion, which is what payment-time
    recomputation wants -- posting a payment should never *newly* mark an
    invoice overdue as a side effect.
    """
    if invoice.status in _STICKY_STATUSES:
        return invoice.status

    if business_today is None and tz is not None:
        from app.core.business_time import business_date

        business_today = business_date(tz)

    total = Decimal(str(invoice.total or 0))
    paid = Decimal(str(invoice.amount_paid))

    if paid > total:
        raise ValueError("Completed payments exceed invoice total")
    if paid >= total:
        return InvoiceStatus.PAID
    if paid > 0:
        # A partly-paid invoice stays PARTIALLY_PAID even when past due; the
        # dunning path keys off balance_due and due_date, not this status,
        # and flipping it to OVERDUE would lose the "money arrived" signal.
        return InvoiceStatus.PARTIALLY_PAID

    if (
        business_today is not None
        and invoice.due_date is not None
        and invoice.due_date < business_today
    ):
        return InvoiceStatus.OVERDUE

    # No payments and not (yet) past due. Preserve an existing OVERDUE mark
    # rather than silently un-aging the invoice when no due date is set.
    if invoice.status == InvoiceStatus.OVERDUE:
        return InvoiceStatus.OVERDUE
    return InvoiceStatus.PENDING


def validate_client_status_change(
    current: InvoiceStatus, requested: InvoiceStatus
) -> Optional[str]:
    """Validate a client-requested status change.

    Returns an error message when the change is not permitted, or ``None``
    when it is. Derived states are rejected with an explanation rather than a
    bare "invalid transition" so API consumers understand *why*.
    """
    if requested == current:
        return None

    if requested in (InvoiceStatus.PAID, InvoiceStatus.PARTIALLY_PAID):
        return (
            f"Invoice status '{requested.value}' is derived from recorded "
            "payments and cannot be set directly. Record a payment instead."
        )
    if requested == InvoiceStatus.OVERDUE:
        return (
            "Invoice status 'overdue' is derived from the due date and is set "
            "by the scheduled billing sweep. Change the due date instead."
        )
    if current == InvoiceStatus.CANCELLED:
        return "A cancelled invoice is terminal and cannot change status."
    if current == InvoiceStatus.PAID and requested != InvoiceStatus.CANCELLED:
        return "A paid invoice cannot be reopened; issue a refund or credit note."
    if requested == InvoiceStatus.DRAFT:
        return "An invoice cannot return to draft once it has been issued."
    if requested == InvoiceStatus.PENDING and current != InvoiceStatus.DRAFT:
        return (
            f"Invoice status '{current.value}' is derived or already issued; "
            "only a draft invoice can be moved to pending."
        )
    if requested not in CLIENT_SETTABLE_STATUSES:
        return f"Invoice status '{requested.value}' cannot be set directly."
    return None
