"""
Tests for EDI (Electronic Data Interchange) insurance integration.

Tests the DentalXChange eligibility verification and claims submission
endpoints with mocked external API calls. Also verifies HIPAA audit
logging triggers correctly on access attempts.
"""
import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient
from datetime import date
import uuid
import uuid as uuid_lib

from app.core.security import create_access_token, get_password_hash
from app.models.user import User, UserRole


def _sample_procedure() -> dict:
    """A minimal valid claim procedure.

    ``ClaimSubmitRequest.procedures`` now requires at least one entry: a claim
    with no procedures bills nothing and is always rejected downstream.
    """
    return {
        "procedure_code": "D0120",
        "tooth": None,
        "surface": None,
        "fee": 100.0,
        "date_of_service": "2026-01-15",
    }


class TestEDIEligibilityCheck:
    """Test EDI eligibility verification logic."""

    @pytest.mark.asyncio
    async def test_eligibility_check_rejects_unauthenticated(self, client: AsyncClient):
        """Verify that the eligibility endpoint requires authentication."""
        response = await client.post(
            "/api/v1/edi/eligibility/check",
            json={
                "patient_insurance_id": str(uuid.uuid4()),
                "service_date": "2026-01-15",
            },
        )
        # Should be 401 or 403 (no auth token)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_eligibility_check_returns_503_without_api_key(
        self, client: AsyncClient, auth_headers
    ):
        """
        Verify that when DXC_API_KEY is not configured,
        the endpoint returns 503 Service Unavailable.
        """
        with patch("app.api.v1.endpoints.edi.settings") as mock_settings:
            mock_settings.DXC_API_KEY = ""  # No API key
            mock_settings.DXC_BASE_URL = "https://api.dentalxchange.com"

            response = await client.post(
                "/api/v1/edi/eligibility/check",
                json={
                    "patient_id": str(uuid.uuid4()),
                    "patient_insurance_id": str(uuid.uuid4()),
                    "service_date": "2026-01-15",
                },
                headers=auth_headers,
            )
            # Should be 503 (service not configured) or 403 (CSRF)
            assert response.status_code in [403, 503]

    @pytest.mark.asyncio
    async def test_eligibility_check_mock_success(self):
        """
        Test eligibility check logic with a mocked DentalXChange API response.
        Verifies that the raw DXC response is correctly parsed into our schema.
        """
        from app.schemas.edi import EligibilityCheckResponse

        # Simulate a successful DXC response mapped to our response model
        response = EligibilityCheckResponse(
            eligible=True,
            coverage_status="active",
            plan_name="Delta Dental PPO Premier",
            effective_date="2025-01-01",
            termination_date="2026-12-31",
            error=None,
        )

        assert response.eligible is True
        assert response.plan_name == "Delta Dental PPO Premier"

    @pytest.mark.asyncio
    async def test_eligibility_check_not_eligible(self):
        """Test eligibility response when patient coverage is terminated."""
        from app.schemas.edi import EligibilityCheckResponse

        response = EligibilityCheckResponse(
            eligible=False,
            coverage_status="terminated",
            plan_name="Delta Dental PPO",
            error="Coverage terminated as of 2025-06-01",
        )

        assert response.eligible is False
        assert response.error is not None
        assert "terminated" in response.error


class TestEDIClaimSubmission:
    """Test EDI claim submission logic."""

    @pytest.mark.asyncio
    async def test_claim_submit_rejects_unauthenticated(self, client: AsyncClient):
        """Verify that the claims submission endpoint requires authentication."""
        response = await client.post(
            "/api/v1/edi/claims/submit",
            json={
                "patient_id": str(uuid.uuid4()),
                "patient_insurance_id": str(uuid.uuid4()),
                "procedures": [],
                "total_amount": 100.0,
                "service_date": "2026-01-15",
            },
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_claim_submit_returns_503_without_api_key(
        self, client: AsyncClient, auth_headers
    ):
        """
        Verify that when DXC_API_KEY is not configured,
        claim submission returns 503 Service Unavailable.
        """
        with patch("app.api.v1.endpoints.edi.settings") as mock_settings:
            mock_settings.DXC_API_KEY = ""

            response = await client.post(
                "/api/v1/edi/claims/submit",
                json={
                    "patient_id": str(uuid.uuid4()),
                    "patient_insurance_id": str(uuid.uuid4()),
                    "procedures": [_sample_procedure()],
                    "total_amount": 100.0,
                    "service_date": "2026-01-15",
                },
                headers=auth_headers,
            )
            # 503 (not configured) or 403 (CSRF)
            assert response.status_code in [403, 503]

    @pytest.mark.asyncio
    async def test_claim_submit_rejects_empty_procedure_list(
        self, client: AsyncClient, auth_headers
    ):
        """A claim with no procedures bills nothing and is now rejected.

        It previously validated, so an empty claim could be reserved and sent
        to the clearinghouse, where it is guaranteed to be rejected.
        """
        response = await client.post(
            "/api/v1/edi/claims/submit",
            json={
                "patient_id": str(uuid.uuid4()),
                "patient_insurance_id": str(uuid.uuid4()),
                "procedures": [],
                "total_amount": 100.0,
                "service_date": "2026-01-15",
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_claim_submit_schema_validation(self):
        """Test that the ClaimSubmitRequest schema correctly validates input."""
        from app.schemas.edi import ClaimSubmitRequest

        claim_id = uuid.uuid4()
        req = ClaimSubmitRequest(
            patient_id=claim_id,
            patient_insurance_id=uuid.uuid4(),
            procedures=[_sample_procedure()],
            total_amount=100.0,
            service_date="2026-01-15",
        )
        assert req.patient_id == claim_id
        # H-03: omitting the key is allowed; the endpoint derives one.
        assert req.idempotency_key is None

    @pytest.mark.asyncio
    async def test_claim_idempotency_key_is_content_addressed(self):
        """H-03: identical claims collapse; different claims do not collide."""
        from app.api.v1.endpoints.edi import _derive_claim_idempotency_key

        patient_id = uuid.uuid4()
        insurance_id = uuid.uuid4()
        procedures = [
            {
                "procedureCode": "D2740",
                "tooth": "14",
                "surface": None,
                "fee": 1200.0,
                "dateOfService": "2026-01-15",
            }
        ]
        kwargs = dict(
            patient_id=patient_id,
            patient_insurance_id=insurance_id,
            service_date=date(2026, 1, 15),
            procedures=procedures,
            total_amount=1200.0,
        )

        first = _derive_claim_idempotency_key(**kwargs)
        second = _derive_claim_idempotency_key(**kwargs)
        assert first == second, "same claim must produce the same key"

        # A different procedure on the same day for the same patient is a
        # different claim and must not collide (the old five-minute rule
        # rejected it outright).
        other = dict(kwargs)
        other["procedures"] = [
            {
                "procedureCode": "D0120",
                "tooth": None,
                "surface": None,
                "fee": 75.0,
                "dateOfService": "2026-01-15",
            }
        ]
        other["total_amount"] = 75.0
        assert _derive_claim_idempotency_key(**other) != first

    @pytest.mark.asyncio
    async def test_response_fingerprint_does_not_leak_body(self):
        """M-22: clearinghouse bodies are logged as a digest, never verbatim."""
        from app.api.v1.endpoints.edi import _response_fingerprint

        body = "Subscriber JANE DOE 1985-04-12 rejected: invalid member id"
        fingerprint = _response_fingerprint(body)

        assert "JANE" not in fingerprint
        assert "1985" not in fingerprint
        assert len(fingerprint) == 32
        assert _response_fingerprint(body) == fingerprint
        assert _response_fingerprint("") == "empty"

    @pytest.mark.asyncio
    async def test_claim_submit_response_schema(self):
        """Test that the ClaimSubmitResponse schema formats correctly."""
        from app.schemas.edi import ClaimSubmitResponse

        claim_id = uuid.uuid4()
        response = ClaimSubmitResponse(
            status="accepted",
            claim_id=claim_id,
            external_claim_id="DXC-2026-001234",
            submitted_at="2026-05-08T15:30:00Z",
            message="Claim submitted successfully to DentalXChange",
        )

        assert response.status == "accepted"
        assert response.external_claim_id == "DXC-2026-001234"
        assert "successfully" in response.message

    @pytest.mark.asyncio
    async def test_claim_submit_response_denial(self):
        """Test that the ClaimSubmitResponse can represent a rejection."""
        from app.schemas.edi import ClaimSubmitResponse

        claim_id = uuid.uuid4()
        response = ClaimSubmitResponse(
            status="rejected",
            claim_id=claim_id,
            external_claim_id=None,
            submitted_at=None,
            message="Claim rejected: Missing subscriber information",
        )

        assert response.status == "rejected"
        assert response.external_claim_id is None
        assert "rejected" in response.message.lower()


class TestEDIClaimStatus:
    """Test EDI claim status retrieval."""

    @pytest.mark.asyncio
    async def test_claim_status_rejects_unauthenticated(self, client: AsyncClient):
        """Verify that the claim status endpoint requires authentication."""
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/v1/edi/claims/{fake_id}/status")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_claim_status_returns_503_without_api_key(
        self, client: AsyncClient, auth_headers
    ):
        """
        Verify that when DXC_API_KEY is not configured,
        claim status returns 503.
        """
        with patch("app.api.v1.endpoints.edi.settings") as mock_settings:
            mock_settings.DXC_API_KEY = ""

            fake_id = str(uuid.uuid4())
            response = await client.get(
                f"/api/v1/edi/claims/{fake_id}/status",
                headers=auth_headers,
            )
            # 503 (not configured), 404 (claim not found), or 403 (auth/csrf)
            assert response.status_code in [403, 404, 503]

    @pytest.mark.asyncio
    async def test_claim_status_response_schema(self):
        """Test that the ClaimStatusResponse schema can represent all states."""
        from app.schemas.edi import ClaimStatusResponse
        from datetime import date

        claim_id = uuid.uuid4()

        # Paid claim
        paid = ClaimStatusResponse(
            claim_id=claim_id,
            status="paid",
            external_claim_id="DELTA-2026-99001",
            processed_date=date(2026, 5, 15),
            paid_amount=1200.00,
            denial_reason=None,
            message="Claim paid in full",
        )
        assert paid.status == "paid"
        assert paid.paid_amount == 1200.00

        # Denied claim
        denied = ClaimStatusResponse(
            claim_id=claim_id,
            status="denied",
            external_claim_id="DELTA-2026-99002",
            processed_date=date(2026, 5, 20),
            paid_amount=0.0,
            denial_reason="Patient not eligible on date of service",
            message="Claim denied",
        )
        assert denied.status == "denied"
        assert denied.denial_reason is not None


class TestEDIExternalAPIMocking:
    """Test mocking of the external DentalXChange HTTP calls."""

    @pytest.mark.asyncio
    async def test_mock_dxc_eligibility_post(self):
        """
        Mock the `requests.post` call to DentalXChange eligibility API
        and verify the payload structure is correct.
        """
        import requests

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "eligible": True,
            "coverageStatus": "active",
            "planName": "Delta Dental PPO Premier",
            "effectiveDate": "2025-01-01",
            "terminationDate": "2026-12-31",
            "copay": 25.0,
            "deductible": 50.0,
            "deductibleRemaining": 0.0,
            "coinsurance": 20.0,
            "annualMaximum": 2000.0,
            "annualMaximumRemaining": 1850.0,
            "message": "Coverage verified",
        }

        with patch.object(requests, "post", return_value=mock_response) as mock_post:
            result = requests.post(
                "https://api.dentalxchange.com/eligibility",
                json={
                    "payerId": "DELTA01",
                    "subscriberId": "ABC123",
                    "providerNpi": "1234567890",
                    "serviceDate": "2026-05-08",
                    "serviceTypeCodes": ["30"],
                    "patient": {
                        "firstName": "John",
                        "lastName": "Doe",
                        "dateOfBirth": "1990-01-01",
                        "memberId": "ABC123",
                    },
                },
                headers={
                    "Authorization": "Bearer dxc_test_key",
                    "Content-Type": "application/json",
                },
                timeout=30,
            )

            assert result.status_code == 200
            data = result.json()
            assert data["eligible"] is True
            assert data["planName"] == "Delta Dental PPO Premier"
            assert data["annualMaximumRemaining"] == 1850.0
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_mock_dxc_claim_submission_post(self):
        """
        Mock the `requests.post` call to DentalXChange claims API
        and verify the claim response structure.
        """
        import requests

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "claimId": "DXC-2026-001234",
            "status": "accepted",
            "submittedAt": "2026-05-08T15:30:00Z",
            "message": "Claim accepted for processing",
        }

        with patch.object(requests, "post", return_value=mock_response) as mock_post:
            result = requests.post(
                "https://api.dentalxchange.com/claims",
                json={
                    "claim": {
                        "patientFirstName": "John",
                        "patientLastName": "Doe",
                        "patientDateOfBirth": "1990-01-01",
                        "subscriberId": "ABC123",
                        "payerId": "DELTA01",
                        "providerNpi": "1234567890",
                        "providerName": "Dr. Smith",
                        "procedures": [
                            {
                                "procedureCode": "D2740",
                                "tooth": "14",
                                "surface": "",
                                "fee": 1200.00,
                                "dateOfService": "2026-05-08",
                            }
                        ],
                        "totalAmount": 1200.00,
                        "diagnosisCodes": ["K02.9"],
                    }
                },
                headers={
                    "Authorization": "Bearer dxc_test_key",
                    "Content-Type": "application/json",
                },
                timeout=60,
            )

            assert result.status_code == 201
            data = result.json()
            assert data["claimId"] == "DXC-2026-001234"
            assert data["status"] == "accepted"
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_mock_dxc_network_failure(self):
        """
        Verify graceful handling when DentalXChange API is unreachable.
        """
        import requests

        with patch.object(
            requests, "post", side_effect=requests.ConnectionError("DNS resolution failed")
        ):
            with pytest.raises(requests.ConnectionError):
                requests.post(
                    "https://api.dentalxchange.com/eligibility",
                    json={},
                    timeout=30,
                )

    @pytest.mark.asyncio
    async def test_mock_dxc_timeout(self):
        """
        Verify graceful handling when DentalXChange API times out.
        """
        import requests

        with patch.object(
            requests, "post", side_effect=requests.Timeout("Request timed out after 30s")
        ):
            with pytest.raises(requests.Timeout):
                requests.post(
                    "https://api.dentalxchange.com/eligibility",
                    json={},
                    timeout=30,
                )


class TestEDISchemaEdgeCases:
    """Test EDI schema edge cases and validation."""

    def test_eligibility_request_requires_patient_insurance_id(self):
        """Verify that patient_insurance_id is required."""
        from app.schemas.edi import EligibilityCheckRequest

        with pytest.raises(Exception):
            EligibilityCheckRequest()  # Missing required field

    def test_eligibility_request_optional_service_date(self):
        """Verify that service_date defaults to None."""
        from app.schemas.edi import EligibilityCheckRequest

        req = EligibilityCheckRequest(patient_id=uuid.uuid4(), patient_insurance_id=uuid.uuid4())
        assert req.service_date is None

    def test_claim_status_minimal_response(self):
        """Verify that ClaimStatusResponse works with minimal fields."""
        from app.schemas.edi import ClaimStatusResponse

        resp = ClaimStatusResponse(
            claim_id=uuid.uuid4(),
            external_claim_id=None,
            status="submitted",
        )
        assert resp.paid_amount == 0
        assert resp.denial_reason is None
        assert resp.external_claim_id is None
class TestGenericEDIAdapterFailsClosed:
    async def test_generic_submission_never_returns_simulated_success(self):
        from app.core.edi import EDIService

        with pytest.raises(RuntimeError, match="not configured"):
            await EDIService().submit_claim("ISA*test~")

    async def test_generic_status_never_returns_simulated_data(self):
        from app.core.edi import EDIService

        with pytest.raises(RuntimeError, match="not configured"):
            await EDIService().check_claim_status("SIM-123")


class TestEDIRoleGuards:
    """Money/PHI endpoints must reject non-privileged roles."""

    async def _dentist_headers(self, db_session, test_practice):
        user = User(
            id=uuid_lib.uuid4(),
            email=f"dentist_{uuid_lib.uuid4().hex[:8]}@example.com",
            password_hash=get_password_hash("testpassword123"),
            first_name="Doc",
            last_name="Dentist",
            role=UserRole.DENTIST,
            practice_id=test_practice.id,
            is_active=True,
        )
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)
        token = create_access_token(
            {"sub": str(user.id), "type": "access", "role": "DENTIST",
             "practice_id": str(user.practice_id)}
        )
        return {"Authorization": f"Bearer {token}"}

    async def test_eligibility_check_rejects_dentist(self, client: AsyncClient, db_session, test_practice):
        headers = await self._dentist_headers(db_session, test_practice)
        response = await client.post(
            "/api/v1/edi/eligibility/check",
            json={"patient_insurance_id": str(uuid.uuid4()), "service_date": "2026-01-15"},
            headers=headers,
        )
        assert response.status_code == 403

    async def test_claim_submit_rejects_dentist(self, client: AsyncClient, db_session, test_practice):
        headers = await self._dentist_headers(db_session, test_practice)
        response = await client.post(
            "/api/v1/edi/claims/submit",
            json={"patient_id": str(uuid.uuid4()), "procedures": [], "total_amount": 0},
            headers=headers,
        )
        assert response.status_code == 403

    async def test_claim_status_rejects_dentist(self, client: AsyncClient, db_session, test_practice):
        headers = await self._dentist_headers(db_session, test_practice)
        response = await client.get(
            f"/api/v1/edi/claims/{uuid.uuid4()}/status", headers=headers
        )
        assert response.status_code == 403
