"""Concurrency tests that genuinely require real PostgreSQL.

The billing module's two production race protections only take effect on
PostgreSQL:

1. ``_next_invoice_number`` serializes same-practice/same-day invoice
   creation with ``pg_advisory_xact_lock`` so concurrent requests cannot
   mint duplicate invoice numbers.
2. ``create_payment`` locks the invoice row with ``SELECT ... FOR UPDATE``
   so two concurrent payments cannot both observe a positive balance and
   over-pay a single invoice.

SQLite (the default local test engine) has neither row locks nor advisory
locks, so these tests are skipped unless the suite is pointed at a real
PostgreSQL via ``TEST_DATABASE_URL``. CI does exactly that
(``.github/workflows/ci.yml``), so this file is the real migration +
concurrency validation for those paths on every push.
"""

import asyncio
import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine_url
from app.main import app as fastapi_app
from app.models.billing import Invoice, InvoiceStatus, Payment
from app.services.payment_service import PaymentService

pytestmark = pytest.mark.asyncio

_REQUIRES_POSTGRES = engine_url.startswith("postgresql")


def _new_client() -> AsyncClient:
    """A dedicated client per concurrent request to avoid sharing an
    in-flight ASGI transport between simultaneous requests."""
    return AsyncClient(
        transport=ASGITransport(app=fastapi_app, client=(f"c-{uuid.uuid4().hex}", 0)),
        base_url="http://test",
        follow_redirects=True,
    )


async def test_concurrent_invoice_creation_produces_unique_numbers(
    auth_headers: dict,
    test_patient,
):
    """Advisory-locked invoice numbering is unique under concurrency."""
    if not _REQUIRES_POSTGRES:
        pytest.skip("Requires real PostgreSQL for pg_advisory_xact_lock")

    async def create(i: int):
        async with _new_client() as ac:
            return await ac.post(
                "/api/v1/billing/invoices/",
                headers=auth_headers,
                json={
                    "patient_id": str(test_patient.id),
                    "status": "pending",
                    "line_items": [
                        {
                            "description": f"Concurrent {i}",
                            "quantity": 1,
                            "unit_price": 10.0,
                            "total": 10.0,
                        }
                    ],
                },
            )

    results = await asyncio.gather(*(create(i) for i in range(8)))
    for r in results:
        assert r.status_code == 200, r.text
    numbers = [r.json()["invoice_number"] for r in results]
    # Under the advisory lock every request gets a distinct number.
    assert len(numbers) == len(set(numbers)), numbers


async def test_concurrent_payments_cannot_overpay(
    auth_headers: dict,
    db_session: AsyncSession,
    test_patient,
):
    """FOR UPDATE prevents two concurrent payments from both clearing."""
    if not _REQUIRES_POSTGRES:
        pytest.skip("Requires real PostgreSQL for SELECT ... FOR UPDATE")

    invoice = Invoice(
        practice_id=test_patient.practice_id,
        patient_id=test_patient.id,
        invoice_number="INV-CONC-PAY-001",
        status=InvoiceStatus.PENDING,
        subtotal=Decimal("100.00"),
        tax=Decimal("0.00"),
        total=Decimal("100.00"),
        line_items=[
            {"description": "Service", "quantity": 1, "unit_price": "100.00", "total": "100.00"}
        ],
    )
    db_session.add(invoice)
    await db_session.commit()
    await db_session.refresh(invoice)

    payload = {
        "invoice_id": str(invoice.id),
        "patient_id": str(test_patient.id),
        "amount": "100.00",
        "payment_method": "cash",
    }

    async def pay():
        async with _new_client() as ac:
            return await ac.post(
                "/api/v1/billing/payments/", headers=auth_headers, json=payload
            )

    results = await asyncio.gather(pay(), pay())
    # Exactly one payment settles; the loser is rejected (409 if it sees the
    # freshly PAID invoice, 400/422 if it observes a zero balance first).
    codes = sorted(r.status_code for r in results)
    assert codes[0] == 200, results
    assert codes[1] in (400, 409, 422), results

    # The invoice is fully paid but never over-paid, and only one payment row
    # exists for the transaction.
    await db_session.refresh(invoice)
    assert invoice.status == InvoiceStatus.PAID
    completed = await PaymentService.completed_total(db_session, invoice.id)
    assert completed == Decimal("100.00")

    count = await db_session.execute(
        select(func.count(Payment.id)).where(Payment.invoice_id == invoice.id)
    )
    assert count.scalar() == 1