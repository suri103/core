"""
End-to-end test for the critical practice funnel:
register -> book -> treat -> invoice -> pay
"""
import datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment, AppointmentStatus
from app.models.treatment import TreatmentPlan, TreatmentPlanStatus

pytestmark = pytest.mark.asyncio


class TestCriticalFunnel:
    """E2E test exercising the full patient journey through the system."""

    async def test_full_funnel(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_patient,
        test_user,
        test_practice,
    ):
        """
        1. Register: Practice and patient already exist via fixtures.
        2. Book: Create an appointment directly in DB.
        3. Treat: Create a treatment plan directly in DB.
        4. Invoice: Create an invoice for the treatment via API.
        5. Pay: Create a payment against the invoice via API.
        """
        # ------------------------------------------------------------------
        # 2. BOOK — Create an appointment
        # ------------------------------------------------------------------
        appt = Appointment(
            practice_id=test_practice.id,
            patient_id=test_patient.id,
            provider_id=test_user.id,
            appointment_type="cleaning",
            status=AppointmentStatus.SCHEDULED,
            start_time=datetime.datetime(2026, 4, 1, 9, 0, 0),
            end_time=datetime.datetime(2026, 4, 1, 10, 0, 0),
            duration=60,
            notes="Routine cleaning",
        )
        db_session.add(appt)
        await db_session.commit()

        # Verify via API
        get_appt = await client.get(
            f"/api/v1/appointments/{appt.id}", headers=auth_headers
        )
        assert get_appt.status_code == 200
        assert get_appt.json()["status"] == "scheduled"

        # ------------------------------------------------------------------
        # 3. TREAT — Create a treatment plan
        # ------------------------------------------------------------------
        plan = TreatmentPlan(
            practice_id=test_practice.id,
            patient_id=test_patient.id,
            provider_id=test_user.id,
            plan_name="Routine Cleaning Plan",
            status=TreatmentPlanStatus.IN_PROGRESS,
        )
        db_session.add(plan)
        await db_session.commit()

        # Verify via API
        get_plan = await client.get(
            f"/api/v1/treatment/plans/{plan.id}", headers=auth_headers
        )
        assert get_plan.status_code == 200
        assert get_plan.json()["status"] == "in_progress"

        # ------------------------------------------------------------------
        # 4. INVOICE — Create an invoice for the treatment via API
        # ------------------------------------------------------------------
        invoice_response = await client.post(
            "/api/v1/billing/invoices/",
            headers=auth_headers,
            json={
                "patient_id": str(test_patient.id),
                "line_items": [
                    {
                        "description": "Prophylaxis + Exam",
                        "quantity": 1,
                        "unit_price": "120.00",
                        "total": "120.00",
                    }
                ],
                "tax_rate": "0.0",
                "notes": "Invoice for routine cleaning",
            },
        )
        assert invoice_response.status_code == 200
        invoice_data = invoice_response.json()
        invoice_id = invoice_data["id"]
        assert invoice_data["total"] == "120.00"
        assert invoice_data["status"] == "pending"

        # ------------------------------------------------------------------
        # 5. PAY — Create a payment against the invoice via API
        # ------------------------------------------------------------------
        payment_response = await client.post(
            "/api/v1/billing/payments/",
            headers=auth_headers,
            json={
                "invoice_id": invoice_id,
                "patient_id": str(test_patient.id),
                "amount": "120.00",
                "payment_method": "card",
                # M7 contract: completed manual payments carry an external
                # reference (receipt number here).
                "transaction_id": "RCPT-E2E-001",
            },
        )
        assert payment_response.status_code == 200
        payment_data = payment_response.json()
        assert payment_data["amount"] == "120.00"
        assert payment_data["status"] == "completed"

        # ------------------------------------------------------------------
        # Verify invoice is marked paid
        # ------------------------------------------------------------------
        get_invoice_response = await client.get(
            f"/api/v1/billing/invoices/{invoice_id}", headers=auth_headers
        )
        assert get_invoice_response.status_code == 200
        final_invoice = get_invoice_response.json()
        assert final_invoice["status"] == "paid"
        assert float(final_invoice["balance_due"]) == 0.0
