"""
Comprehensive insurance endpoint tests covering carrier CRUD,
claim creation, and patient insurance policy management.
"""
import datetime
from decimal import Decimal
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.insurance import (
    InsuranceCarrier,
    PatientInsurance,
    InsuranceClaim,
    ClaimStatus,
)

pytestmark = pytest.mark.asyncio


class TestInsuranceCarrierCRUD:
    """Authenticated insurance carrier lifecycle tests."""

    async def test_create_carrier(self, client: AsyncClient, auth_headers):
        """Create a new insurance carrier."""
        response = await client.post(
            "/api/v1/insurance/carriers/",
            headers=auth_headers,
            json={
                "name": "Test Carrier",
                "phone": "555-0200",
                "email": "carrier@example.com",
                "payer_id": "TC-001",
                "is_active": True,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Carrier"
        assert data["payer_id"] == "TC-001"
        assert "id" in data

    async def test_list_carriers(self, client: AsyncClient, auth_headers, db_session):
        """List carriers should include created carriers."""
        carrier = InsuranceCarrier(
            name="Delta Dental",
            phone="555-0300",
            payer_id="DD-001",
            is_active=True,
        )
        db_session.add(carrier)
        await db_session.commit()

        response = await client.get("/api/v1/insurance/carriers/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 1
        assert any(c["name"] == "Delta Dental" for c in data["carriers"])

    async def test_get_carrier_by_id(self, client: AsyncClient, auth_headers, db_session):
        """Retrieve a single carrier by ID."""
        carrier = InsuranceCarrier(
            name="MetLife Dental",
            phone="555-0400",
            payer_id="ML-001",
            is_active=True,
        )
        db_session.add(carrier)
        await db_session.commit()

        response = await client.get(
            f"/api/v1/insurance/carriers/{carrier.id}", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(carrier.id)
        assert data["name"] == "MetLife Dental"

    async def test_update_carrier(self, client: AsyncClient, auth_headers, db_session, test_practice):
        """Update carrier details."""
        carrier = InsuranceCarrier(
            practice_id=test_practice.id,
            name="Old Name",
            phone="555-0500",
            payer_id="ON-001",
            is_active=True,
        )
        db_session.add(carrier)
        await db_session.commit()

        response = await client.put(
            f"/api/v1/insurance/carriers/{carrier.id}",
            headers=auth_headers,
            json={"name": "Updated Name"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"


class TestPatientInsuranceCRUD:
    """Patient policy routes expose only canonical PatientInsurance fields."""

    async def test_policy_lifecycle_and_null_safe_update(
        self,
        client: AsyncClient,
        auth_headers,
        db_session: AsyncSession,
        test_patient,
        test_practice,
    ):
        carrier = InsuranceCarrier(
            practice_id=test_practice.id,
            name="Policy Carrier",
            payer_id="POLICY-001",
            is_active=True,
        )
        db_session.add(carrier)
        await db_session.commit()

        create_response = await client.post(
            f"/api/v1/insurance/patients/{test_patient.id}/policies",
            headers=auth_headers,
            json={
                "carrier_id": str(carrier.id),
                "subscriber_id": "SUB-POLICY-001",
                "relationship_to_subscriber": "self",
                "is_primary": True,
                "annual_maximum": "1500.00",
            },
        )
        assert create_response.status_code == 200
        created = create_response.json()
        assert created["patient_id"] == str(test_patient.id)
        assert created["subscriber_id"] == "SUB-POLICY-001"
        assert created["annual_maximum"] == "1500.00"
        assert "insurance_type" not in created
        assert "policy_number" not in created

        policy_id = created["id"]
        list_response = await client.get(
            f"/api/v1/insurance/patients/{test_patient.id}/policies",
            headers=auth_headers,
        )
        assert list_response.status_code == 200
        assert list_response.json()["insurances"][0]["id"] == policy_id

        null_response = await client.put(
            f"/api/v1/insurance/policies/{policy_id}",
            headers=auth_headers,
            json={"subscriber_id": None},
        )
        assert null_response.status_code == 422

        update_response = await client.put(
            f"/api/v1/insurance/policies/{policy_id}",
            headers=auth_headers,
            json={"group_number": "GROUP-UPDATED", "is_primary": False},
        )
        assert update_response.status_code == 200
        assert update_response.json()["group_number"] == "GROUP-UPDATED"
        assert update_response.json()["is_primary"] is False

        delete_response = await client.delete(
            f"/api/v1/insurance/policies/{policy_id}",
            headers=auth_headers,
        )
        assert delete_response.status_code == 200
        assert delete_response.json() == {
            "message": "Insurance policy deleted successfully"
        }


class TestInsuranceClaimCRUD:
    """Authenticated insurance claim lifecycle tests."""

    async def test_list_claims(self, client: AsyncClient, auth_headers, db_session, test_patient, test_practice):
        """List claims should include practice-scoped claims."""
        carrier = InsuranceCarrier(name="Claim Carrier", is_active=True, practice_id=test_practice.id)
        db_session.add(carrier)
        await db_session.flush()

        policy = PatientInsurance(
            patient_id=test_patient.id,
            carrier_id=carrier.id,
            is_primary=True,
            subscriber_id="SUB-001",
            relationship_to_subscriber="self",
            is_active=True,
        )
        db_session.add(policy)
        await db_session.flush()

        claim = InsuranceClaim(
            practice_id=test_practice.id,
            patient_id=test_patient.id,
            patient_insurance_id=policy.id,
            carrier_id=carrier.id,
            claim_number="CLM-LIST-001",
            status=ClaimStatus.PENDING,
            service_date=datetime.date(2026, 1, 1),
            billed_amount=Decimal("200.00"),
            procedure_codes=[{"code": "D0120", "description": "Exam", "fee": 75.00}],
        )
        db_session.add(claim)
        await db_session.commit()

        response = await client.get("/api/v1/insurance/claims/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 1
        assert any(c["claim_number"] == "CLM-LIST-001" for c in data["claims"])

    async def test_create_claim(self, client: AsyncClient, auth_headers, db_session, test_patient, test_practice):
        """Create an insurance claim via API."""
        carrier = InsuranceCarrier(name="API Carrier", is_active=True, practice_id=test_practice.id)
        db_session.add(carrier)
        await db_session.flush()

        policy = PatientInsurance(
            patient_id=test_patient.id,
            carrier_id=carrier.id,
            is_primary=True,
            subscriber_id="SUB-API-001",
            relationship_to_subscriber="self",
            is_active=True,
        )
        db_session.add(policy)
        await db_session.commit()

        response = await client.post(
            "/api/v1/insurance/claims/",
            headers=auth_headers,
            json={
                "patient_insurance_id": str(policy.id),
                "service_date": "2026-02-01",
                "billed_amount": "350.00",
                "procedure_codes": [
                    {"code": "D0150", "description": "Comprehensive oral evaluation", "fee": 100.00}
                ],
                "diagnosis_codes": ["K02.9"],
                "notes": "Initial claim",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["billed_amount"] == "350.00"
        assert data["status"] == "draft"
        assert "claim_number" in data
        assert data["patient_id"] == str(test_patient.id)

    async def test_update_claim(self, client: AsyncClient, auth_headers, db_session, test_patient, test_practice):
        """Update an existing claim."""
        carrier = InsuranceCarrier(name="Update Carrier", is_active=True, practice_id=test_practice.id)
        db_session.add(carrier)
        await db_session.flush()

        policy = PatientInsurance(
            patient_id=test_patient.id,
            carrier_id=carrier.id,
            is_primary=True,
            subscriber_id="SUB-UPD-001",
            relationship_to_subscriber="self",
            is_active=True,
        )
        db_session.add(policy)
        await db_session.flush()

        claim = InsuranceClaim(
            practice_id=test_practice.id,
            patient_id=test_patient.id,
            patient_insurance_id=policy.id,
            carrier_id=carrier.id,
            claim_number="CLM-UPD-001",
            status=ClaimStatus.PENDING,
            service_date=datetime.date(2026, 3, 1),
            billed_amount=Decimal("150.00"),
            procedure_codes=[{"code": "D0210", "description": "X-Ray", "fee": 50.00}],
        )
        db_session.add(claim)
        await db_session.commit()

        response = await client.put(
            f"/api/v1/insurance/claims/{claim.id}",
            headers=auth_headers,
            json={"status": "submitted"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "submitted"
class TestInsuranceClaimSubmission:
    """Claim status changes only after clearinghouse confirmation."""

    async def test_submit_claim_fails_closed_when_provider_not_configured(
        self, client: AsyncClient, auth_headers, monkeypatch
    ):
        from app.api.v1.endpoints.insurance import settings

        monkeypatch.setattr(settings, "DXC_API_KEY", "")
        response = await client.post(
            f"/api/v1/insurance/claims/{UUID(int=1)}/submit",
            headers=auth_headers,
        )

        assert response.status_code == 503
        assert response.json()["detail"] == "Claims submission service not configured"

    async def test_submit_claim_requires_provider_confirmation(
        self,
        client: AsyncClient,
        auth_headers,
        db_session: AsyncSession,
        test_patient,
        test_practice,
        monkeypatch,
    ):
        from app.api.v1.endpoints.insurance import httpx, settings

        carrier = InsuranceCarrier(
            practice_id=test_practice.id,
            name="EDI Confirmed Carrier",
            payer_id="PAYER-001",
            edi_enabled=True,
            is_active=True,
        )
        db_session.add(carrier)
        await db_session.flush()
        policy = PatientInsurance(
            patient_id=test_patient.id,
            carrier_id=carrier.id,
            is_primary=True,
            subscriber_id="SUB-CONFIRM-001",
            relationship_to_subscriber="self",
            is_active=True,
        )
        db_session.add(policy)
        await db_session.flush()
        claim = InsuranceClaim(
            practice_id=test_practice.id,
            patient_id=test_patient.id,
            patient_insurance_id=policy.id,
            carrier_id=carrier.id,
            claim_number="CLM-CONFIRM-001",
            status=ClaimStatus.DRAFT,
            service_date=datetime.date(2026, 6, 1),
            billed_amount=Decimal("125.00"),
            procedure_codes=[{"code": "D0120", "description": "Exam", "fee": 125.00}],
            diagnosis_codes=["K02.9"],
        )
        db_session.add(claim)
        await db_session.commit()

        captured = {}

        class ProviderResponse:
            status_code = 201

            @staticmethod
            def json():
                return {"claimId": "DXC-123", "confirmationNumber": "CONF-456"}

        class ProviderClient:
            def __init__(self, **kwargs):
                captured["client_kwargs"] = kwargs

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, url, **kwargs):
                captured["url"] = url
                captured["request"] = kwargs
                return ProviderResponse()

        monkeypatch.setattr(settings, "DXC_API_KEY", "test-dxc-key")
        monkeypatch.setattr(settings, "DXC_BASE_URL", "https://dxc.example.test")
        monkeypatch.setattr(httpx, "AsyncClient", ProviderClient)

        response = await client.post(
            f"/api/v1/insurance/claims/{claim.id}/submit",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "submitted"
        assert data["confirmation_number"] == "CONF-456"
        assert captured["url"] == "https://dxc.example.test/claims"
        assert captured["request"]["json"]["claim"]["payerId"] == "PAYER-001"

        await db_session.refresh(claim)
        assert claim.status == ClaimStatus.SUBMITTED
        assert claim.edi_transaction_id == "DXC-123"
        assert claim.confirmation_number == "CONF-456"
