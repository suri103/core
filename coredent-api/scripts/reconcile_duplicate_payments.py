"""Reconcile duplicate ``payments.transaction_id`` rows before enforcing uniqueness.

Alembic revision ``c8f1a6d3b527`` adds a unique index on
``payments.transaction_id``. It deliberately refuses to run while duplicates
exist rather than deleting rows, because deleting payment rows destroys
financial history and desynchronises invoice totals, refunds, and audit
records (audit finding C-02).

This script performs the reconciliation explicitly and reversibly-by-review:

``--report``
    Print every duplicated transaction_id, the rows involved, the invoices
    they belong to, and the invoice total that would result after merging.
    Read-only. Run this first and have it reviewed by whoever owns billing.

``--apply``
    Merge each duplicate group into the earliest row inside a single
    transaction. Extra rows are *not* deleted: they are voided by setting
    ``status='failed'``, clearing ``transaction_id`` (so uniqueness can be
    enforced) and appending a note that records the surviving row's id. The
    money trail stays in the table and stays auditable.

Merge rule: the earliest row per transaction_id survives and keeps its
amount. Duplicate rows are gateway re-deliveries of the *same* transaction,
so their amounts are not additive; collapsing them is what makes
``Invoice.amount_paid`` correct again. If a group contains rows with
*differing* amounts, that is not a re-delivery and the script refuses to
merge it automatically -- those groups are reported and left untouched.

Examples:
    python scripts/reconcile_duplicate_payments.py --report
    python scripts/reconcile_duplicate_payments.py --apply
    python scripts/reconcile_duplicate_payments.py --apply --yes
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select, text


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.database import AsyncSessionLocal, engine  # noqa: E402
from app.models.billing import Invoice, Payment, PaymentStatus  # noqa: E402

VOID_NOTE = "voided by reconcile_duplicate_payments: duplicate of payment {survivor}"


async def _duplicate_groups(session) -> list[dict]:
    """Return one entry per duplicated transaction_id, ordered deterministically."""
    rows = (
        await session.execute(
            text(
                """
                SELECT transaction_id
                FROM payments
                WHERE transaction_id IS NOT NULL
                GROUP BY transaction_id
                HAVING COUNT(*) > 1
                ORDER BY transaction_id
                """
            )
        )
    ).fetchall()

    groups: list[dict] = []
    for row in rows:
        txn_id = row.transaction_id
        payments = (
            (
                await session.execute(
                    select(Payment)
                    .where(Payment.transaction_id == txn_id)
                    .order_by(Payment.created_at.asc(), Payment.id.asc())
                )
            )
            .scalars()
            .all()
        )
        amounts = {Decimal(str(p.amount)) for p in payments}
        groups.append(
            {
                "transaction_id": txn_id,
                "payments": payments,
                "survivor": payments[0],
                "duplicates": payments[1:],
                "amounts_differ": len(amounts) > 1,
            }
        )
    return groups


async def _invoice_snapshot(session, invoice_id) -> tuple[Invoice | None, Decimal, Decimal]:
    """Return (invoice, current amount_paid, total) with payments loaded."""
    if invoice_id is None:
        return None, Decimal("0"), Decimal("0")
    invoice = (
        await session.execute(select(Invoice).where(Invoice.id == invoice_id))
    ).scalar_one_or_none()
    if invoice is None:
        return None, Decimal("0"), Decimal("0")
    await session.refresh(invoice, ["payments"])
    return invoice, invoice.amount_paid, Decimal(str(invoice.total))


async def report() -> int:
    """Print the reconciliation plan. Read-only. Returns a process exit code."""
    async with AsyncSessionLocal() as session:
        groups = await _duplicate_groups(session)

        if not groups:
            print("No duplicate payments.transaction_id values found.")
            print("Migration c8f1a6d3b527 can be applied safely.")
            return 0

        blocked = [g for g in groups if g["amounts_differ"]]
        mergeable = [g for g in groups if not g["amounts_differ"]]

        print(f"Duplicate transaction_id groups: {len(groups)}")
        print(f"  auto-mergeable (identical amounts): {len(mergeable)}")
        print(f"  needs manual review (differing amounts): {len(blocked)}")
        print()

        for group in groups:
            tag = "MANUAL REVIEW" if group["amounts_differ"] else "MERGEABLE"
            print(f"[{tag}] transaction_id={group['transaction_id']}")
            for payment in group["payments"]:
                marker = "keep" if payment is group["survivor"] else "void"
                print(
                    f"    {marker}  payment={payment.id}"
                    f"  invoice={payment.invoice_id}"
                    f"  amount={payment.amount}"
                    f"  refunded={payment.refunded_amount or 0}"
                    f"  status={getattr(payment.status, 'value', payment.status)}"
                    f"  created={payment.created_at}"
                )

            invoice_ids = {p.invoice_id for p in group["payments"] if p.invoice_id}
            for invoice_id in sorted(invoice_ids, key=str):
                invoice, current_paid, total = await _invoice_snapshot(session, invoice_id)
                if invoice is None:
                    print(f"    invoice {invoice_id}: MISSING (orphaned payment row)")
                    continue
                removed = sum(
                    Decimal(str(p.amount)) - Decimal(str(p.refunded_amount or 0))
                    for p in group["duplicates"]
                    if p.invoice_id == invoice_id
                    and p.status in (PaymentStatus.COMPLETED, PaymentStatus.REFUNDED)
                )
                projected = current_paid - removed
                print(
                    f"    invoice {invoice.invoice_number}: total={total}"
                    f" paid_now={current_paid} paid_after_merge={projected}"
                    f" balance_after_merge={total - projected}"
                )
            print()

        if blocked:
            print(
                "Groups marked MANUAL REVIEW contain differing amounts and are not "
                "gateway re-deliveries. Resolve them by hand before --apply; "
                "--apply will refuse to run while any remain."
            )
        return 1


async def apply(assume_yes: bool) -> int:
    """Merge auto-mergeable duplicate groups in one transaction."""
    async with AsyncSessionLocal() as session:
        groups = await _duplicate_groups(session)

        if not groups:
            print("No duplicate payments.transaction_id values found. Nothing to do.")
            return 0

        blocked = [g for g in groups if g["amounts_differ"]]
        if blocked:
            print(
                f"Refusing to apply: {len(blocked)} duplicate group(s) have differing "
                "amounts and cannot be merged automatically."
            )
            for group in blocked:
                print(f"  transaction_id={group['transaction_id']}")
            print("Run --report for detail and resolve these by hand first.")
            return 2

        total_voids = sum(len(g["duplicates"]) for g in groups)
        print(
            f"About to void {total_voids} duplicate payment row(s) across "
            f"{len(groups)} transaction(s). No rows will be deleted."
        )
        if not assume_yes:
            answer = input("Proceed? [y/N] ").strip().lower()
            if answer not in {"y", "yes"}:
                print("Aborted. No changes made.")
                return 1

        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        touched_invoices: set = set()

        for group in groups:
            survivor = group["survivor"]
            for duplicate in group["duplicates"]:
                note = VOID_NOTE.format(survivor=survivor.id)
                duplicate.status = PaymentStatus.FAILED
                # Freeing transaction_id is what allows the unique index to be
                # created; the surviving row retains the gateway reference.
                duplicate.transaction_id = None
                duplicate.notes = (
                    f"{duplicate.notes}\n{stamp} {note}"
                    if duplicate.notes
                    else f"{stamp} {note}"
                )
                if duplicate.invoice_id:
                    touched_invoices.add(duplicate.invoice_id)
            if survivor.invoice_id:
                touched_invoices.add(survivor.invoice_id)

        await session.flush()

        # Recompute derived invoice status from the corrected ledger.
        from app.services.invoice_status import derive_invoice_status

        for invoice_id in touched_invoices:
            invoice, _, _ = await _invoice_snapshot(session, invoice_id)
            if invoice is None:
                continue
            invoice.status = derive_invoice_status(invoice)

        await session.commit()

        print(
            f"Done. Voided {total_voids} duplicate row(s); recomputed "
            f"{len(touched_invoices)} invoice status value(s)."
        )
        print("Migration c8f1a6d3b527 can now be applied.")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reconcile duplicate payments.transaction_id rows (no deletions).",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--report", action="store_true", help="read-only reconciliation plan")
    mode.add_argument("--apply", action="store_true", help="merge duplicate groups")
    parser.add_argument(
        "--yes", action="store_true", help="skip the interactive confirmation for --apply"
    )
    args = parser.parse_args()

    try:
        if args.report:
            return asyncio.run(report())
        return asyncio.run(apply(assume_yes=args.yes))
    finally:
        asyncio.run(engine.dispose())


if __name__ == "__main__":
    raise SystemExit(main())
