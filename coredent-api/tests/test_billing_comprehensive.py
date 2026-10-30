"""
Comprehensive billing endpoint tests covering invoice CRUD,
payment creation, and billing summary.
"""
import datetime
from decimal import Decimal
from uuid import uuid4
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.billing import Invoice, InvoiceStatus, Payment, PaymentStatus, PaymentMethod
from app.models.payment import (
    PaymentMethod as TxnPaymentMethod,
    PaymentStatus as TxnPaymentStatus,
    PaymentTransaction,
)

pytestmark = pytest.mark.asyncio


class TestInvoiceCRUD:
    """Authenticated invoice lifecycle tests."""

    async def test_create_invoice(self, client: AsyncClient, auth_headers, test_patient):
        """Create an invoice for a patient."""
        response = await client.post(
            "/api/v1/billing/invoices/",
            headers=auth_headers,
            json={
                "patient_id": str(test_patient.id),
                "line_items": [
                    {
                        "description": "Cleaning",
                        "quantity": 1,
                        "unit_price": "100.00",
                        "total": "100.00",
                    }
                ],
                "tax_rate": "0.0",
                "notes": "Test invoice",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["patient_id"] == str(test_patient.id)
        assert data["total"] == "100.00"
        assert data["status"] == "pending"
        assert "id" in data
        assert "invoice_number" in data
        assert data["patient_name"] == f"{test_patient.first_name} {test_patient.last_name}".strip()
        assert data["patient_email"] == test_patient.email
        assert data["patient_phone"] == test_patient.phone
        assert data["payments"] == []

    async def test_create_invoice_rejects_derived_status(
        self, client: AsyncClient, auth_headers, test_patient
    ):
        """A brand-new invoice cannot be minted directly as PAID (or other
        derived/terminal statuses) — PAID must come only from recorded payments."""
        response = await client.post(
            "/api/v1/billing/invoices/",
            headers=auth_headers,
            json={
                "patient_id": str(test_patient.id),
                "status": "paid",
                "line_items": [
                    {
                        "description": "Cleaning",
                        "quantity": 1,
                        "unit_price": "100.00",
                        "total": "100.00",
                    }
                ],
                "tax_rate": "0.0",
            },
        )
        assert response.status_code == 422, response.text

    async def test_create_invoice_rejects_cancelled_status(
        self, client: AsyncClient, auth_headers, test_patient
    ):
        """CANCELLED is terminal and cannot be set on creation."""
        response = await client.post(
            "/api/v1/billing/invoices/",
            headers=auth_headers,
            json={
                "patient_id": str(test_patient.id),
                "status": "cancelled",
                "line_items": [
                    {
                        "description": "Exam",
                        "quantity": 1,
                        "unit_price": "50.00",
                        "total": "50.00",
                    }
                ],
            },
        )
        assert response.status_code == 422, response.text

    async def test_create_invoice_allows_draft(
        self, client: AsyncClient, auth_headers, test_patient
    ):
        """DRAFT remains a legal starting state for a new invoice."""
        response = await client.post(
            "/api/v1/billing/invoices/",
            headers=auth_headers,
            json={
                "patient_id": str(test_patient.id),
                "status": "draft",
                "line_items": [
                    {
                        "description": "Exam",
                        "quantity": 1,
                        "unit_price": "50.00",
                        "total": "50.00",
                    }
                ],
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "draft"


    async def test_list_invoices(self, client: AsyncClient, auth_headers, db_session, test_patient):
        """List invoices should include practice invoices."""
        inv = Invoice(
            practice_id=test_patient.practice_id,
            patient_id=test_patient.id,
            invoice_number="INV-LIST-001",
            status=InvoiceStatus.PENDING,
            subtotal=Decimal("150.00"),
            tax=Decimal("0.00"),
            total=Decimal("150.00"),
            line_items=[{"description": "Filling", "quantity": 1, "unit_price": "150.00", "total": "150.00"}],
        )
        db_session.add(inv)
        await db_session.commit()

        response = await client.get("/api/v1/billing/invoices/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 1
        assert any(i["invoice_number"] == "INV-LIST-001" for i in data["invoices"])

    async def test_get_invoice_by_id(self, client: AsyncClient, auth_headers, db_session, test_patient):
        """Retrieve a single invoice by ID."""
        inv = Invoice(
            practice_id=test_patient.practice_id,
            patient_id=test_patient.id,
            invoice_number="INV-GET-001",
            status=InvoiceStatus.PENDING,
            subtotal=Decimal("200.00"),
            tax=Decimal("0.00"),
            total=Decimal("200.00"),
            line_items=[{"description": "Crown", "quantity": 1, "unit_price": "200.00", "total": "200.00"}],
        )
        db_session.add(inv)
        await db_session.commit()

        response = await client.get(
            f"/api/v1/billing/invoices/{inv.id}", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(inv.id)
        assert data["invoice_number"] == "INV-GET-001"

    async def test_update_invoice(self, client: AsyncClient, auth_headers, db_session, test_patient):
        """Update invoice status (validated transitions)."""
        inv = Invoice(
            practice_id=test_patient.practice_id,
            patient_id=test_patient.id,
            invoice_number="INV-UPD-001",
            status=InvoiceStatus.PENDING,
            subtotal=Decimal("50.00"),
            tax=Decimal("0.00"),
            total=Decimal("50.00"),
            line_items=[{"description": "Consultation", "quantity": 1, "unit_price": "50.00", "total": "50.00"}],
        )
        db_session.add(inv)
        await db_session.commit()

        # M-03: PAID is derived from the payment ledger and cannot be set by hand.
        response = await client.put(
            f"/api/v1/billing/invoices/{inv.id}",
            headers=auth_headers,
            json={"status": "paid"},
        )
        assert response.status_code == 409, response.text
        assert "derived from recorded payments" in response.json()["detail"]

        # M-03: OVERDUE is derived from the due date by the scheduled billing
        # sweep. A client used to be able to declare it directly, which let a
        # caller set a financial state the sweep is supposed to own.
        response = await client.put(
            f"/api/v1/billing/invoices/{inv.id}",
            headers=auth_headers,
            json={"status": "overdue"},
        )
        assert response.status_code == 409, response.text
        assert "derived from the due date" in response.json()["detail"]

        # A status a client legitimately owns still succeeds.
        response = await client.put(
            f"/api/v1/billing/invoices/{inv.id}",
            headers=auth_headers,
            json={"status": "cancelled"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["status"] == "cancelled"

    async def test_update_invoice_non_status_fields(
        self, client: AsyncClient, auth_headers, db_session, test_patient
    ):
        """Notes and due date remain editable without touching status."""
        inv = Invoice(
            practice_id=test_patient.practice_id,
            patient_id=test_patient.id,
            invoice_number="INV-UPD-002",
            status=InvoiceStatus.PENDING,
            subtotal=Decimal("50.00"),
            tax=Decimal("0.00"),
            total=Decimal("50.00"),
            line_items=[{"description": "Consultation", "quantity": 1, "unit_price": "50.00", "total": "50.00"}],
        )
        db_session.add(inv)
        await db_session.commit()

        response = await client.put(
            f"/api/v1/billing/invoices/{inv.id}",
            headers=auth_headers,
            json={"notes": "Insurance pending", "due_date": "2026-12-31"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["notes"] == "Insurance pending"
        assert data["status"] == "pending"


class TestPaymentCRUD:
    """Authenticated payment lifecycle tests."""

    async def test_create_payment(self, client: AsyncClient, auth_headers, db_session, test_patient):
        """Create a payment against an invoice."""
        inv = Invoice(
            practice_id=test_patient.practice_id,
            patient_id=test_patient.id,
            invoice_number="INV-PAY-001",
            status=InvoiceStatus.PENDING,
            subtotal=Decimal("120.00"),
            tax=Decimal("0.00"),
            total=Decimal("120.00"),
            line_items=[{"description": "Service", "quantity": 1, "unit_price": "120.00", "total": "120.00"}],
        )
        db_session.add(inv)
        await db_session.commit()

        response = await client.post(
            "/api/v1/billing/payments/",
            headers=auth_headers,
            json={
                "invoice_id": str(inv.id),
                "patient_id": str(test_patient.id),
                "amount": "120.00",
                "payment_method": "cash",
                "transaction_id": "CASH-DRAWER-0001",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["amount"] == "120.00"
        assert data["status"] == "completed"
        assert data["transaction_id"] == "CASH-DRAWER-0001"

    async def test_completed_manual_payment_requires_reference(
        self, client: AsyncClient, auth_headers, db_session, test_patient
    ):
        """A gateway-less COMPLETED entry without an external reference is
        unreconcilable and must be rejected (M7)."""
        inv = Invoice(
            practice_id=test_patient.practice_id,
            patient_id=test_patient.id,
            invoice_number="INV-PAY-NOREF-001",
            status=InvoiceStatus.PENDING,
            subtotal=Decimal("50.00"),
            tax=Decimal("0.00"),
            total=Decimal("50.00"),
            line_items=[],
        )
        db_session.add(inv)
        await db_session.commit()

        response = await client.post(
            "/api/v1/billing/payments/",
            headers=auth_headers,
            json={
                "invoice_id": str(inv.id),
                "patient_id": str(test_patient.id),
                "amount": "50.00",
                "payment_method": "cash",
            },
        )
        assert response.status_code == 422
        assert "reference" in response.json()["detail"].lower()

    async def test_list_payments(self, client: AsyncClient, auth_headers, db_session, test_patient):
        """List payments should return practice-scoped payments."""
        inv = Invoice(
            practice_id=test_patient.practice_id,
            patient_id=test_patient.id,
            invoice_number="INV-PAY-LIST-001",
            status=InvoiceStatus.PAID,
            subtotal=Decimal("80.00"),
            tax=Decimal("0.00"),
            total=Decimal("80.00"),
            line_items=[{"description": "X-Ray", "quantity": 1, "unit_price": "80.00", "total": "80.00"}],
        )
        db_session.add(inv)
        await db_session.flush()

        pay = Payment(
            invoice_id=inv.id,
            patient_id=test_patient.id,
            practice_id=test_patient.practice_id,
            amount=Decimal("80.00"),
            payment_method=PaymentMethod.CARD,
            status=PaymentStatus.COMPLETED,
        )
        db_session.add(pay)
        await db_session.commit()

        response = await client.get("/api/v1/billing/payments/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 1
        assert any(p["id"] == str(pay.id) for p in data["payments"])


class TestPaymentIntegrity:
    async def test_payment_rejects_patient_mismatch(self, client, auth_headers, db_session, test_patient, other_patient):
        inv = Invoice(
            practice_id=test_patient.practice_id,
            patient_id=test_patient.id,
            invoice_number="INV-PAY-MISMATCH-001",
            status=InvoiceStatus.PENDING,
            subtotal=Decimal("100.00"),
            tax=Decimal("0.00"),
            total=Decimal("100.00"),
            line_items=[],
        )
        db_session.add(inv)
        await db_session.commit()

        response = await client.post(
            "/api/v1/billing/payments/",
            headers=auth_headers,
            json={
                "invoice_id": str(inv.id),
                "patient_id": str(other_patient.id),
                "amount": "10.00",
                "payment_method": "cash",
            },
        )
        assert response.status_code == 400

    async def test_payment_rejects_overpayment(self, client, auth_headers, db_session, test_patient):
        inv = Invoice(
            practice_id=test_patient.practice_id,
            patient_id=test_patient.id,
            invoice_number="INV-PAY-OVER-001",
            status=InvoiceStatus.PENDING,
            subtotal=Decimal("100.00"),
            tax=Decimal("0.00"),
            total=Decimal("100.00"),
            line_items=[],
        )
        db_session.add(inv)
        await db_session.commit()

        response = await client.post(
            "/api/v1/billing/payments/",
            headers=auth_headers,
            json={
                "invoice_id": str(inv.id),
                "patient_id": str(test_patient.id),
                "amount": "100.01",
                "payment_method": "cash",
                "transaction_id": "REF-OVER-001",
            },
        )
        assert response.status_code == 400

    async def test_payment_plan_rejects_other_tenant_patient(self, client, auth_headers, other_patient):
        response = await client.post(
            "/api/v1/billing/payment-plans/",
            headers=auth_headers,
            json={
                "patient_id": str(other_patient.id),
                "invoice_id": str(uuid4()),
                "total_amount": "100.00",
                "months": 2,
            },
        )
        assert response.status_code == 404


class TestBillingSummary:
    """Billing summary endpoint tests."""

    async def test_get_billing_summary(self, client: AsyncClient, auth_headers, db_session, test_patient):
        """Billing summary should reflect practice invoices and payments."""
        inv = Invoice(
            practice_id=test_patient.practice_id,
            patient_id=test_patient.id,
            invoice_number="INV-SUM-001",
            status=InvoiceStatus.PAID,
            subtotal=Decimal("300.00"),
            tax=Decimal("0.00"),
            total=Decimal("300.00"),
            line_items=[{"description": "Root canal", "quantity": 1, "unit_price": "300.00", "total": "300.00"}],
        )
        db_session.add(inv)
        await db_session.commit()

        response = await client.get("/api/v1/billing/summary", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_invoices" in data
        assert "total_revenue" in data
        assert "outstanding_balance" in data
        assert isinstance(data["status_breakdown"], list)

    async def test_billing_summary_date_filter(self, client: AsyncClient, auth_headers):
        """Billing summary should accept date range filters without error."""
        today = datetime.date.today().isoformat()
        response = await client.get(
            f"/api/v1/billing/summary?start_date={today}&end_date={today}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_invoices" in data

    async def test_billing_summary_money_is_two_decimal_clean(
        self, client: AsyncClient, auth_headers, db_session, test_patient
    ):
        """Reported money figures must be proper currency amounts (M7)."""
        inv = Invoice(
            practice_id=test_patient.practice_id,
            patient_id=test_patient.id,
            invoice_number="INV-SUM-DEC-001",
            status=InvoiceStatus.PENDING,
            subtotal=Decimal("19.99"),
            tax=Decimal("0.00"),
            total=Decimal("19.99"),
            line_items=[{"description": "Exam", "quantity": 1, "unit_price": "19.99", "total": "19.99"}],
        )
        db_session.add(inv)
        await db_session.commit()

        response = await client.get("/api/v1/billing/summary", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total_revenue"] == 19.99
        assert data["outstanding_balance"] == 19.99
        amounts = [row["amount"] for row in data["status_breakdown"]]
        assert all(amount == round(amount, 2) for amount in amounts)


class TestLedgerReconciliation:
    """GET /billing/reconciliation surfaces processor money the invoice
    ledger has not absorbed."""

    async def _invoice(self, db_session, test_patient, number, total, status):
        inv = Invoice(
            practice_id=test_patient.practice_id,
            patient_id=test_patient.id,
            invoice_number=number,
            status=status,
            subtotal=total,
            tax=Decimal("0.00"),
            total=total,
            line_items=[],
        )
        db_session.add(inv)
        await db_session.flush()
        return inv

    async def _gateway_transaction(
        self, db_session, test_patient, invoice, processor_id, total, refunded=Decimal("0.00")
    ):
        txn = PaymentTransaction(
            practice_id=test_patient.practice_id,
            patient_id=test_patient.id,
            invoice_id=invoice.id if invoice else None,
            transaction_type="charge",
            payment_method=TxnPaymentMethod.CREDIT_CARD,
            amount=total,
            total_amount=total,
            refunded_amount=refunded,
            status=TxnPaymentStatus.COMPLETED,
            processor_transaction_id=processor_id,
        )
        db_session.add(txn)
        await db_session.commit()
        return txn

    async def test_reports_gateway_money_not_applied_to_invoice(
        self, client: AsyncClient, auth_headers, db_session, test_patient
    ):
        inv = await self._invoice(
            db_session, test_patient, "INV-RECON-001", Decimal("100.00"), InvoiceStatus.PENDING
        )
        await self._gateway_transaction(
            db_session, test_patient, inv, "pi_recon_unapplied", Decimal("100.00")
        )

        response = await client.get("/api/v1/billing/reconciliation", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        entries = [
            e for e in data["unapplied_gateway_transactions"]
            if e["processor_transaction_id"] == "pi_recon_unapplied"
        ]
        assert len(entries) == 1
        entry = entries[0]
        assert entry["net_amount"] == 100.0
        assert entry["invoice_number"] == "INV-RECON-001"
        assert entry["invoice_balance_due"] == 100.0

    async def test_settled_invoice_is_not_reported(
        self, client: AsyncClient, auth_headers, db_session, test_patient
    ):
        inv = await self._invoice(
            db_session, test_patient, "INV-RECON-002", Decimal("80.00"), InvoiceStatus.PAID
        )
        db_session.add(
            Payment(
                invoice_id=inv.id,
                patient_id=test_patient.id,
                practice_id=test_patient.practice_id,
                amount=Decimal("80.00"),
                payment_method=PaymentMethod.CARD,
                status=PaymentStatus.COMPLETED,
                transaction_id="pi_recon_settled",
            )
        )
        await db_session.flush()
        await self._gateway_transaction(
            db_session, test_patient, inv, "pi_recon_settled", Decimal("80.00")
        )

        response = await client.get("/api/v1/billing/reconciliation", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert all(
            e["processor_transaction_id"] != "pi_recon_settled"
            for e in data["unapplied_gateway_transactions"]
        )

    async def test_fully_refunded_gateway_row_is_not_reported(
        self, client: AsyncClient, auth_headers, db_session, test_patient
    ):
        inv = await self._invoice(
            db_session, test_patient, "INV-RECON-003", Decimal("60.00"), InvoiceStatus.PENDING
        )
        await self._gateway_transaction(
            db_session,
            test_patient,
            inv,
            "pi_recon_refunded",
            Decimal("60.00"),
            refunded=Decimal("60.00"),
        )

        response = await client.get("/api/v1/billing/reconciliation", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert all(
            e["processor_transaction_id"] != "pi_recon_refunded"
            for e in data["unapplied_gateway_transactions"]
        )

    async def _linked_refund_fixture(
        self, db_session, test_patient, number, txn_id
    ):
        """M-1 helper: a PAID invoice, its billing.Payment row, and the linked
        PaymentTransaction — the exact state a Stripe charge.refunded finds."""
        inv = await self._invoice(
            db_session, test_patient, number, Decimal("100.00"), InvoiceStatus.PAID
        )
        ledger = Payment(
            invoice_id=inv.id,
            patient_id=test_patient.id,
            practice_id=test_patient.practice_id,
            amount=Decimal("100.00"),
            payment_method=PaymentMethod.CARD,
            status=PaymentStatus.COMPLETED,
            transaction_id=txn_id,
        )
        db_session.add(ledger)
        await db_session.flush()
        txn = await self._gateway_transaction(
            db_session, test_patient, inv, txn_id, Decimal("100.00")
        )
        txn.payment_id = ledger.id
        await db_session.commit()
        return inv, ledger, txn

    async def _invoice_status(self, db_session, invoice_id) -> InvoiceStatus:
        """Re-read the status column without touching lazy relationships.

        ``Invoice.amount_paid`` lazy-loads ``Invoice.payments`` and would
        raise MissingGreenlet under AsyncSession, so these tests assert
        through the same SQL surfaces the money reports use.
        """
        result = await db_session.execute(
            select(Invoice.status).where(Invoice.id == invoice_id)
        )
        return result.scalar_one()

    async def _collected(self, db_session, invoice_id, practice_id) -> Decimal:
        """The exact refund-aware sum billing summary / reports compute."""
        from app.services.payment_service import PaymentService

        return await PaymentService.completed_total(db_session, invoice_id, practice_id)

    async def test_stripe_refund_propagates_to_invoice_ledger(
        self, client: AsyncClient, auth_headers, db_session, test_patient
    ):
        """M-1 regression: charge.refunded must reach the billing.Payment row.

        A Stripe refund that only updates the processor ledger leaves
        ``Invoice.amount_paid`` overstated: the invoice stays PAID and every
        money surface (billing summary, reports, portal balance) reports
        money the practice no longer has. The handler must set
        ``Payment.refunded_amount``, flip the status when fully refunded,
        and re-derive the invoice status via ``refresh_invoice_status``.
        """
        from app.api.v1.endpoints.stripe import handle_charge_refunded

        inv, ledger, _txn = await self._linked_refund_fixture(
            db_session, test_patient, "INV-REFUND-001", "pi_refund_full"
        )
        practice_id = test_patient.practice_id
        # Sanity: the invoice is fully paid by the linked ledger row.
        assert await self._collected(db_session, inv.id, practice_id) == Decimal("100.00")

        await handle_charge_refunded(
            db_session,
            {
                "id": "ch_refund_full",
                "payment_intent": "pi_refund_full",
                "amount_refunded": 10000,
                "currency": "usd",
            },
        )

        await db_session.refresh(ledger)
        assert ledger.refunded_amount == Decimal("100.00")
        assert ledger.status == PaymentStatus.REFUNDED
        # Fully refunded money no longer counts as collected on the invoice,
        # and the derived status demotes PAID -> PENDING.
        assert await self._collected(db_session, inv.id, practice_id) == Decimal("0")
        assert await self._invoice_status(db_session, inv.id) == InvoiceStatus.PENDING

    async def test_stripe_partial_refund_keeps_invoice_partially_paid(
        self, client: AsyncClient, auth_headers, db_session, test_patient
    ):
        """M-1 regression: a partial refund demotes PAID -> PARTIALLY_PAID.

        ``refresh_invoice_status`` derives status from the refund-aware
        ledger, so a 50-of-100 refund must show a half-paid invoice with
        the refunded amount subtracted from collections.
        """
        from app.api.v1.endpoints.stripe import handle_charge_refunded

        inv, ledger, _txn = await self._linked_refund_fixture(
            db_session, test_patient, "INV-REFUND-002", "pi_refund_partial"
        )
        practice_id = test_patient.practice_id

        await handle_charge_refunded(
            db_session,
            {
                "id": "ch_refund_partial",
                "payment_intent": "pi_refund_partial",
                "amount_refunded": 5000,
                "currency": "usd",
            },
        )

        await db_session.refresh(ledger)
        assert ledger.refunded_amount == Decimal("50.00")
        # A half-refunded ledger row is PARTIALLY_REFUNDED: the enum gained that
        # member for exactly this state (see models/billing.py PaymentStatus),
        # and the manual refund endpoint sets it too. Expecting COMPLETED here
        # encoded the pre-PARTIALLY_REFUNDED behaviour.
        assert ledger.status == PaymentStatus.PARTIALLY_REFUNDED
        assert await self._collected(db_session, inv.id, practice_id) == Decimal("50.00")
        assert (
            await self._invoice_status(db_session, inv.id)
            == InvoiceStatus.PARTIALLY_PAID
        )

    async def test_stripe_refund_larger_than_ledger_is_not_propagated(
        self, client: AsyncClient, auth_headers, db_session, test_patient
    ):
        """M-1 regression (safe default): an invalid refund amount must not
        corrupt the invoice ledger. A processor-reported refund exceeding the
        recorded billing.Payment amount is left to operator reconciliation —
        writing it would push amount_paid negative and corrupt balance_due.
        """
        from app.api.v1.endpoints.stripe import handle_charge_refunded

        inv, ledger, _txn = await self._linked_refund_fixture(
            db_session, test_patient, "INV-REFUND-003", "pi_refund_invalid"
        )
        practice_id = test_patient.practice_id

        await handle_charge_refunded(
            db_session,
            {
                "id": "ch_refund_invalid",
                "payment_intent": "pi_refund_invalid",
                # Processor claims MORE refund than was ever charged.
                "amount_refunded": 25000,
                "currency": "usd",
            },
        )

        await db_session.refresh(ledger)
        # Invoice ledger untouched: the safe default refused the write.
        assert ledger.refunded_amount is None or ledger.refunded_amount == Decimal("0")
        assert ledger.status == PaymentStatus.COMPLETED
        assert await self._collected(db_session, inv.id, practice_id) == Decimal("100.00")
        assert await self._invoice_status(db_session, inv.id) == InvoiceStatus.PAID
