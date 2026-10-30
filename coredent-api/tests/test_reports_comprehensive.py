"""
Comprehensive reports endpoint tests.
"""
import datetime

import pytest
from httpx import AsyncClient

from app.models.appointment import Appointment, AppointmentStatus
from app.models.billing import Invoice, Payment, PaymentStatus, PaymentMethod
from app.models.treatment import TreatmentPlan, TreatmentPlanStatus

pytestmark = pytest.mark.asyncio


class TestReportsDashboard:
    """Dashboard metrics aggregation tests."""

    async def test_dashboard_metrics(self, client: AsyncClient, auth_headers, db_session, test_patient, test_practice, test_user):
        # Create appointment
        appt = Appointment(
            practice_id=test_practice.id,
            patient_id=test_patient.id,
            provider_id=test_user.id,
            appointment_type="cleaning",
            status=AppointmentStatus.COMPLETED,
            start_time=datetime.datetime(2026, 5, 1, 9, 0, 0),
            end_time=datetime.datetime(2026, 5, 1, 10, 0, 0),
            duration=60,
        )
        db_session.add(appt)

        # Create invoice
        invoice = Invoice(
            practice_id=test_practice.id,
            patient_id=test_patient.id,
            invoice_number="INV-RPT-001",
            status="paid",
            subtotal=200,
            tax=0,
            total=200,
            line_items=[],
            created_at=datetime.datetime(2026, 5, 1, 12, 0, 0),
        )
        db_session.add(invoice)
        await db_session.flush()

        # Create payment
        payment = Payment(
            invoice_id=invoice.id,
            patient_id=test_patient.id,
            practice_id=test_practice.id,
            amount=200,
            payment_method=PaymentMethod.CARD,
            status=PaymentStatus.COMPLETED,
        )
        db_session.add(payment)

        # Create treatment plan
        plan = TreatmentPlan(
            practice_id=test_practice.id,
            patient_id=test_patient.id,
            provider_id=test_user.id,
            plan_name="Report Plan",
            status=TreatmentPlanStatus.ACCEPTED,
            created_date=datetime.date(2026, 5, 1),
        )
        db_session.add(plan)
        await db_session.commit()

        response = await client.get(
            "/api/v1/reports/dashboard?from=2026-05-01&to=2026-05-31",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["appointments"]["total"] >= 1
        assert data["revenue"]["totalRevenue"] >= 200.0
        assert data["treatmentAcceptance"]["proposedPlans"] >= 1
        assert "chairUtilization" in data

    async def test_dashboard_metrics_no_data(self, client: AsyncClient, auth_headers):
        response = await client.get(
            "/api/v1/reports/dashboard?from=2025-01-01&to=2025-01-31",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["appointments"]["total"] == 0
        assert data["revenue"]["totalRevenue"] == 0.0

    async def test_dashboard_missing_dates(self, client: AsyncClient, auth_headers):
        response = await client.get(
            "/api/v1/reports/dashboard", headers=auth_headers
        )
        assert response.status_code == 422
