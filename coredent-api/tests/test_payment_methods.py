"""Tests for accepted-payment-methods enforcement on manual payment creation.

The practice's ``accepted_payment_methods`` list was previously stored and
echoed by the settings API but never enforced on ``POST /billing/payments/``.
These tests verify a configured list now gates manual ledger entries while
keeping legacy behavior for unconfigured practices.
"""

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import Invoice, InvoiceStatus
from app.models.practice import Practice


async def _restrict_payment_methods(
    db: AsyncSession, practice_id, methods: list
) -> None:
    result = await db.execute(select(Practice).where(Practice.id == practice_id))
    practice = result.scalar_one()
    practice.accepted_payment_methods = methods
    await db.commit()


async def _pending_invoice(
    db: AsyncSession, practice_id, patient_id, invoice_number: str
) -> Invoice:
    invoice = Invoice(
        practice_id=practice_id,
        patient_id=patient_id,
        invoice_number=invoice_number,
        status=InvoiceStatus.PENDING,
        subtotal=Decimal("100.00"),
        tax=Decimal("0.00"),
        total=Decimal("100.00"),
        line_items=[
            {"description": "Service", "quantity": 1, "unit_price": "100.00", "total": "100.00"}
        ],
    )
    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)
    return invoice


class TestAcceptedPaymentMethods:
    @pytest.mark.asyncio
    async def test_rejects_payment_method_not_in_accepted_list(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_patient,
    ):
        await _restrict_payment_methods(db_session, test_patient.practice_id, ["card"])
        inv = await _pending_invoice(
            db_session, test_patient.practice_id, test_patient.id, "INV-PAYM-REJ-001"
        )

        response = await client.post(
            "/api/v1/billing/payments/",
            headers=auth_headers,
            json={
                "invoice_id": str(inv.id),
                "patient_id": str(test_patient.id),
                "amount": "100.00",
                "payment_method": "check",
                # M7 contract: a completed manual payment needs an external
                # reference. Send one so the assertion exercises the
                # accepted-methods gate, not the missing-reference gate.
                "transaction_id": "CHK-REJ-001",
            },
        )
        assert response.status_code == 422, response.text
        assert "not accepted" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_accepts_payment_method_in_accepted_list(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_patient,
    ):
        await _restrict_payment_methods(db_session, test_patient.practice_id, ["card"])
        inv = await _pending_invoice(
            db_session, test_patient.practice_id, test_patient.id, "INV-PAYM-OK-001"
        )

        response = await client.post(
            "/api/v1/billing/payments/",
            headers=auth_headers,
            json={
                "invoice_id": str(inv.id),
                "patient_id": str(test_patient.id),
                "amount": "100.00",
                "payment_method": "card",
                "transaction_id": "CD-OK-001",
            },
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["payment_method"] == "card"
        assert data["status"] == "completed"

    @pytest.mark.asyncio
    async def test_unconfigured_practice_keeps_default_methods(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_patient,
    ):
        """A practice with a null accepted list may still post the defaults."""
        inv = await _pending_invoice(
            db_session, test_patient.practice_id, test_patient.id, "INV-PAYM-DEF-001"
        )

        response = await client.post(
            "/api/v1/billing/payments/",
            headers=auth_headers,
            json={
                "invoice_id": str(inv.id),
                "patient_id": str(test_patient.id),
                "amount": "100.00",
                "payment_method": "cash",
                "transaction_id": "CSH-DEF-001",
            },
        )
        assert response.status_code == 200, response.text