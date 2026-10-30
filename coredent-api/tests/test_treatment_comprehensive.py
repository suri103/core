"""
Comprehensive treatment planning endpoint tests.
"""
import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.treatment import (
    ProcedureType,
    TreatmentPhase,
    TreatmentPlan,
    TreatmentPlanStatus,
    TreatmentProcedure,
)

pytestmark = pytest.mark.asyncio


class TestTreatmentPlanCRUD:
    """Authenticated treatment plan lifecycle tests."""

    async def test_list_treatment_plans(self, client: AsyncClient, auth_headers, db_session, test_patient, test_practice, test_user):
        plan = TreatmentPlan(
            practice_id=test_practice.id,
            patient_id=test_patient.id,
            provider_id=test_user.id,
            plan_name="Cleaning Plan",
            status=TreatmentPlanStatus.DRAFT,
            created_date=date(2020, 1, 1),
        )
        db_session.add(plan)
        await db_session.commit()

        response = await client.get("/api/v1/treatment/plans/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 1
        assert any(p["plan_name"] == "Cleaning Plan" for p in data["plans"])

    async def test_create_treatment_plan(self, client: AsyncClient, auth_headers, test_patient, test_user):
        response = await client.post(
            "/api/v1/treatment/plans/",
            headers=auth_headers,
            json={
                "patient_id": str(test_patient.id),
                "provider_id": str(test_user.id),
                "plan_name": "Comprehensive Restoration",
                "status": "draft",
                "chief_complaint": "Multiple cavities",
                "notes": "Patient anxious",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["plan_name"] == "Comprehensive Restoration"
        assert data["patient_id"] == str(test_patient.id)
        assert data["status"] == "draft"

    async def test_create_treatment_plan_patient_not_found(self, client: AsyncClient, auth_headers, test_user):
        response = await client.post(
            "/api/v1/treatment/plans/",
            headers=auth_headers,
            json={
                "patient_id": str(uuid.uuid4()),
                "provider_id": str(test_user.id),
                "plan_name": "Ghost Plan",
            },
        )
        assert response.status_code == 404

    async def test_get_treatment_plan(self, client: AsyncClient, auth_headers, db_session, test_patient, test_practice, test_user):
        plan = TreatmentPlan(
            practice_id=test_practice.id,
            patient_id=test_patient.id,
            provider_id=test_user.id,
            plan_name="Extraction Plan",
            status=TreatmentPlanStatus.DRAFT,
        )
        db_session.add(plan)
        await db_session.commit()

        response = await client.get(
            f"/api/v1/treatment/plans/{plan.id}", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(plan.id)
        assert data["plan_name"] == "Extraction Plan"

    async def test_update_treatment_plan(self, client: AsyncClient, auth_headers, db_session, test_patient, test_practice, test_user):
        plan = TreatmentPlan(
            practice_id=test_practice.id,
            patient_id=test_patient.id,
            provider_id=test_user.id,
            plan_name="Old Plan",
            status=TreatmentPlanStatus.DRAFT,
        )
        db_session.add(plan)
        await db_session.commit()

        # M-11: a DRAFT plan cannot jump straight to IN_PROGRESS. It must be
        # presented and accepted first — skipping those steps would record
        # treatment as under way that the patient never agreed to.
        response = await client.put(
            f"/api/v1/treatment/plans/{plan.id}",
            headers=auth_headers,
            json={"plan_name": "Updated Plan", "status": "in_progress"},
        )
        assert response.status_code == 409, response.text
        assert "Cannot change treatment plan status" in response.json()["detail"]

        # Walking the real lifecycle succeeds and renames the plan.
        response = await client.put(
            f"/api/v1/treatment/plans/{plan.id}",
            headers=auth_headers,
            json={"plan_name": "Updated Plan", "status": "presented"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["plan_name"] == "Updated Plan"

        response = await client.put(
            f"/api/v1/treatment/plans/{plan.id}",
            headers=auth_headers,
            json={"status": "accepted"},
        )
        assert response.status_code == 200, response.text

        response = await client.put(
            f"/api/v1/treatment/plans/{plan.id}",
            headers=auth_headers,
            json={"status": "in_progress"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["plan_name"] == "Updated Plan"
        assert data["status"] == "in_progress"

        # And a terminal plan stays terminal.
        response = await client.put(
            f"/api/v1/treatment/plans/{plan.id}",
            headers=auth_headers,
            json={"status": "completed"},
        )
        assert response.status_code == 200, response.text
        response = await client.put(
            f"/api/v1/treatment/plans/{plan.id}",
            headers=auth_headers,
            json={"status": "in_progress"},
        )
        assert response.status_code == 409, response.text

    async def test_delete_treatment_plan(self, client: AsyncClient, auth_headers, db_session, test_patient, test_practice, test_user):
        plan = TreatmentPlan(
            practice_id=test_practice.id,
            patient_id=test_patient.id,
            provider_id=test_user.id,
            plan_name="Delete Plan",
            status=TreatmentPlanStatus.DRAFT,
        )
        db_session.add(plan)
        await db_session.commit()

        response = await client.delete(
            f"/api/v1/treatment/plans/{plan.id}", headers=auth_headers
        )
        assert response.status_code == 200
        assert "cancelled" in response.json()["message"].lower()


class TestTreatmentPlanPhases:
    """Treatment phase endpoint tests."""

    async def test_list_phases(self, client: AsyncClient, auth_headers, db_session, test_patient, test_practice, test_user):
        plan = TreatmentPlan(
            practice_id=test_practice.id,
            patient_id=test_patient.id,
            provider_id=test_user.id,
            plan_name="Phase Plan",
            status=TreatmentPlanStatus.DRAFT,
        )
        db_session.add(plan)
        await db_session.flush()

        phase = TreatmentPhase(
            treatment_plan_id=plan.id,
            phase_name="Phase 1",
            phase_number=1,
            status="active",
        )
        db_session.add(phase)
        await db_session.commit()

        response = await client.get(
            f"/api/v1/treatment/plans/{plan.id}/phases", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 1
        assert any(p["phase_name"] == "Phase 1" for p in data["phases"])

    async def test_create_phase(self, client: AsyncClient, auth_headers, db_session, test_patient, test_practice, test_user):
        plan = TreatmentPlan(
            practice_id=test_practice.id,
            patient_id=test_patient.id,
            provider_id=test_user.id,
            plan_name="Phase Create Plan",
            status=TreatmentPlanStatus.DRAFT,
        )
        db_session.add(plan)
        await db_session.commit()

        response = await client.post(
            f"/api/v1/treatment/plans/{plan.id}/phases",
            headers=auth_headers,
            json={
                "phase_name": "Initial Phase",
                "phase_number": 1,
                "description": "First phase of treatment",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["phase_name"] == "Initial Phase"
        assert data["treatment_plan_id"] == str(plan.id)


class TestTreatmentProcedures:
    """Procedure endpoints use the schema fields and UUID routes end to end."""

    async def test_create_procedure_with_real_phase_updates_plan_totals(
        self,
        client: AsyncClient,
        auth_headers,
        db_session,
        test_patient,
        test_practice,
        test_user,
    ):
        plan = TreatmentPlan(
            practice_id=test_practice.id,
            patient_id=test_patient.id,
            provider_id=test_user.id,
            plan_name="Restorative Plan",
            status=TreatmentPlanStatus.DRAFT,
        )
        db_session.add(plan)
        await db_session.flush()
        phase = TreatmentPhase(
            treatment_plan_id=plan.id,
            phase_name="Restorative Phase",
            phase_number=1,
        )
        db_session.add(phase)
        await db_session.commit()

        response = await client.post(
            f"/api/v1/treatment/plans/{plan.id}/procedures",
            headers=auth_headers,
            json={
                "procedure_type": "restorative",
                "ada_code": "D2740",
                "description": "Crown - porcelain/ceramic",
                "fee": 425.50,
                "phase_id": str(phase.id),
                "insurance_estimate": 100,
                "patient_responsibility": 325.50,
            },
        )

        assert response.status_code == 200, response.text
        data = response.json()
        # Money is quantized to a decimal string on the wire (L-3: never a
        # binary float) — compare on the exact decimal, not Python floats.
        from decimal import Decimal

        assert data["treatment_plan_id"] == str(plan.id)
        assert data["phase_id"] == str(phase.id)
        assert data["procedure_type"] == "restorative"
        assert data["ada_code"] == "D2740"
        assert Decimal(str(data["fee"])) == Decimal("425.50")
        assert data["appointment_id"] is None
        assert data["pre_auth_id"] is None

        plan_response = await client.get(
            f"/api/v1/treatment/plans/{plan.id}", headers=auth_headers
        )
        assert plan_response.status_code == 200, plan_response.text
        plan_data = plan_response.json()
        assert Decimal(str(plan_data["total_estimated_cost"])) == Decimal("425.50")
        assert Decimal(str(plan_data["total_insurance_estimate"])) == Decimal("100")
        assert Decimal(str(plan_data["total_patient_responsibility"])) == Decimal("325.50")


class TestProcedureTenantScoping:
    """M-2 FIX: PUT/DELETE /procedures/{id} scope by tenant inside the fetch.

    Cross-tenant procedure ids must 404 (not 403), and a foreign-tenant row
    must never be loaded or mutated by the deferred-check pattern.
    """

    async def _create_plan_with_procedure(
        self, db_session, practice, provider_id, description
    ):
        from app.models.patient import Patient

        patient = Patient(
            practice_id=practice.id,
            first_name="Scope",
            last_name="Check",
            date_of_birth=date(1985, 5, 5),
        )
        db_session.add(patient)
        await db_session.flush()
        plan = TreatmentPlan(
            practice_id=practice.id,
            patient_id=patient.id,
            provider_id=provider_id,
            plan_name=f"Scoped Plan {uuid.uuid4().hex[:6]}",
            status=TreatmentPlanStatus.DRAFT,
        )
        db_session.add(plan)
        await db_session.flush()
        procedure = TreatmentProcedure(
            treatment_plan_id=plan.id,
            procedure_type=ProcedureType.RESTORATIVE,
            ada_code="D2750",
            description=description,
            fee=950.00,
        )
        db_session.add(procedure)
        await db_session.commit()
        return procedure

    async def test_update_rejects_cross_tenant_procedure_with_404(
        self, client, auth_headers, db_session, other_practice, test_user
    ):
        foreign = await self._create_plan_with_procedure(
            db_session, other_practice, test_user.id, "Foreign crown"
        )

        response = await client.put(
            f"/api/v1/treatment/procedures/{foreign.id}",
            headers=auth_headers,
            json={"description": "Tampered crown"},
        )

        assert response.status_code == 404, response.text
        assert response.json()["detail"] == "Treatment procedure not found"
        await db_session.refresh(foreign)
        assert foreign.description == "Foreign crown"

    async def test_delete_rejects_cross_tenant_procedure_with_404(
        self, client, auth_headers, db_session, other_practice, test_user
    ):
        foreign = await self._create_plan_with_procedure(
            db_session, other_practice, test_user.id, "Foreign crown"
        )

        response = await client.delete(
            f"/api/v1/treatment/procedures/{foreign.id}", headers=auth_headers
        )

        assert response.status_code == 404, response.text
        assert response.json()["detail"] == "Treatment procedure not found"
        assert await db_session.get(TreatmentProcedure, foreign.id) is not None

    async def test_update_and_delete_own_procedure_still_work(
        self, client, auth_headers, db_session, test_practice, test_user
    ):
        own = await self._create_plan_with_procedure(
            db_session, test_practice, test_user.id, "Own crown"
        )

        update_response = await client.put(
            f"/api/v1/treatment/procedures/{own.id}",
            headers=auth_headers,
            json={"description": "Own crown, adjusted"},
        )
        assert update_response.status_code == 200, update_response.text
        assert update_response.json()["description"] == "Own crown, adjusted"

        delete_response = await client.delete(
            f"/api/v1/treatment/procedures/{own.id}", headers=auth_headers
        )
        assert delete_response.status_code == 200, delete_response.text
        remaining = (
            await db_session.execute(
                select(TreatmentProcedure).where(TreatmentProcedure.id == own.id)
            )
        ).scalar_one_or_none()
        assert remaining is None
