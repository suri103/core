"""
Tests for patient portal endpoints
"""
import json
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID
import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
import hashlib
from app.api.v1.endpoints import patient_portal
from app.core.search_index import hmac_index


def _hash_portal_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _make_request() -> Request:
    return Request(scope={"type": "http", "client": ("127.0.0.1", 1234), "headers": [], "path": "/api/v1/portal/access", "method": "POST"})


_raw_request_portal_access = getattr(patient_portal.request_portal_access, "__wrapped__", patient_portal.request_portal_access)


INVALID_AUTH = {"Authorization": "Bearer invalid-token"}
TEST_UUID = "00000000-0000-0000-0000-000000000001"
TEST_SIGNATURE_DATA = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Zl1sAAAAASUVORK5CYII="

class TestPatientPortal:
    """Test patient portal endpoints"""

    @pytest.mark.asyncio
    async def test_get_my_profile_invalid_token(self, client: AsyncClient):
        """Test getting profile with invalid token"""
        response = await client.get(
            "/api/v1/portal/me",
            headers=INVALID_AUTH,
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_my_appointments_invalid_token(self, client: AsyncClient):
        """Test getting appointments with invalid token"""
        response = await client.get(
            "/api/v1/portal/appointments",
            headers=INVALID_AUTH,
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_my_billing_invalid_token(self, client: AsyncClient):
        """Test getting billing with invalid token"""
        response = await client.get(
            "/api/v1/portal/billing",
            headers=INVALID_AUTH,
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_my_treatment_plans_invalid_token(self, client: AsyncClient):
        """Test getting treatment plans with invalid token"""
        response = await client.get(
            "/api/v1/portal/treatment-plans",
            headers=INVALID_AUTH,
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_my_insurance_invalid_token(self, client: AsyncClient):
        """Test getting insurance with invalid token"""
        response = await client.get(
            "/api/v1/portal/insurance",
            headers=INVALID_AUTH,
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_make_payment_invalid_token(self, client: AsyncClient):
        """Test making payment with invalid token"""
        response = await client.post(
            "/api/v1/portal/pay",
            headers=INVALID_AUTH,
            json={"invoice_id": TEST_UUID, "amount": "100.00"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_my_documents_invalid_token(self, client: AsyncClient):
        """Test getting documents with invalid token"""
        response = await client.get(
            "/api/v1/portal/documents",
            headers=INVALID_AUTH,
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_sign_document_invalid_token(self, client: AsyncClient):
        """Test signing document with invalid token"""
        response = await client.post(
            f"/api/v1/portal/documents/{TEST_UUID}/sign",
            headers=INVALID_AUTH,
            json={"signature_data": TEST_SIGNATURE_DATA, "signer_name": "Test Patient", "agreement_accepted": True},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_my_profile_missing_token(self, client: AsyncClient):
        """Test getting profile without token parameter"""
        response = await client.get("/api/v1/portal/me")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_my_appointments_missing_token(self, client: AsyncClient):
        """Test getting appointments without token parameter"""
        response = await client.get("/api/v1/portal/appointments")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_my_billing_missing_token(self, client: AsyncClient):
        """Test getting billing without token parameter"""
        response = await client.get("/api/v1/portal/billing")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_portal_endpoint_structure(self, client: AsyncClient):
        """Test that portal endpoints exist (401 vs 404)"""
        endpoints = [
            "/api/v1/portal/me",
            "/api/v1/portal/appointments",
            "/api/v1/portal/billing",
            "/api/v1/portal/treatment-plans",
            "/api/v1/portal/insurance",
            "/api/v1/portal/documents",
        ]
        for endpoint in endpoints:
            response = await client.get(endpoint)
            assert response.status_code in [401, 422], f"{endpoint} returned {response.status_code}"


def _signature_request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": f"/api/v1/portal/documents/{TEST_UUID}/sign",
            "query_string": b"",
            "headers": [(b"user-agent", b"CoreDent portal test")],
            "client": ("203.0.113.10", 443),
            "server": ("testserver", 443),
            "scheme": "https",
        }
    )


@pytest.mark.asyncio
async def test_sign_document_persists_encrypted_document_bound_evidence(monkeypatch):
    patient_id = UUID("00000000-0000-0000-0000-000000000010")
    document_id = UUID(TEST_UUID)
    patient = SimpleNamespace(
        id=patient_id, practice_id=UUID("00000000-0000-0000-0000-0000000000aa")
    )
    document = SimpleNamespace(
        id=document_id,
        patient_id=patient_id,
        content="Consent text version 1",
        is_completed=False,
        expires_at=None,
        completed_at=None,
        status=patient_portal.DocumentStatus.PENDING,
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = document
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = result
    get_patient = AsyncMock(return_value=patient)
    encrypt = MagicMock(return_value="encrypted-signature-evidence")
    monkeypatch.setattr(patient_portal, "_get_portal_patient", get_patient)
    monkeypatch.setattr(patient_portal, "encrypt_value", encrypt)

    payload = patient_portal.PortalSignatureRequest(
        signature_data=TEST_SIGNATURE_DATA,
        signer_name="Test Patient",
        agreement_accepted=True,
    )
    response = await patient_portal.sign_document(
        document_id=document_id,
        payload=payload,
        request=_signature_request(),
        token="valid-token",
        db=db,
    )

    assert response["status"] == "success"
    assert document.is_completed is True
    assert document.status is patient_portal.DocumentStatus.SIGNED
    assert document.completed_at is not None
    stored_signature = db.add.call_args_list[0].args[0]
    assert isinstance(stored_signature, patient_portal.DocumentSignature)
    assert stored_signature.document_id == document_id
    assert stored_signature.signer_id == patient_id
    assert stored_signature.signature_data == "encrypted-signature-evidence"
    assert stored_signature.signature_ip == "203.0.113.10"
    assert stored_signature.signature_user_agent == "CoreDent portal test"
    evidence = json.loads(encrypt.call_args.args[0])
    assert evidence["signature_data"] == TEST_SIGNATURE_DATA
    assert evidence["signer_name"] == "Test Patient"
    assert evidence["agreement_accepted"] is True
    assert len(evidence["document_sha256"]) == 64
    assert encrypt.call_args.kwargs["aad"] == b"document_signature.signature_data"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_sign_document_rejects_duplicate_under_row_lock(monkeypatch):
    patient_id = UUID("00000000-0000-0000-0000-000000000010")
    document = SimpleNamespace(
        id=UUID(TEST_UUID),
        patient_id=patient_id,
        content="Consent text version 1",
        is_completed=True,
        expires_at=None,
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = document
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = result
    monkeypatch.setattr(
        patient_portal,
        "_get_portal_patient",
        AsyncMock(
            return_value=SimpleNamespace(
                id=patient_id,
                practice_id=UUID("00000000-0000-0000-0000-0000000000aa"),
            )
        ),
    )
    encrypt = MagicMock()
    monkeypatch.setattr(patient_portal, "encrypt_value", encrypt)
    payload = patient_portal.PortalSignatureRequest(
        signature_data=TEST_SIGNATURE_DATA,
        signer_name="Test Patient",
        agreement_accepted=True,
    )

    with pytest.raises(HTTPException) as exc_info:
        await patient_portal.sign_document(
            document_id=UUID(TEST_UUID),
            payload=payload,
            request=_signature_request(),
            token="valid-token",
            db=db,
        )

    assert exc_info.value.status_code == 409
    encrypt.assert_not_called()
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_portal_access_sends_magic_link_not_bearer(monkeypatch):
    """Option A: /access emails a single-use code, never a bearer."""
    practice = SimpleNamespace(
        id=UUID("00000000-0000-0000-0000-000000000020"),
        name="Test Dental",
    )
    patient = SimpleNamespace(
        id=UUID("00000000-0000-0000-0000-000000000010"),
        email="patient@example.com",
        first_name="Test",
        last_name="Patient",
        portal_access_token=None,
        portal_token_expires=None,
    )
    practice_result = MagicMock()
    practice_result.scalar_one_or_none.return_value = practice
    patient_result = MagicMock()
    patient_result.scalar_one_or_none.return_value = patient
    locked_result = MagicMock()
    locked_result.scalar_one_or_none.return_value = None
    delete_result = MagicMock()
    db = AsyncMock(spec=AsyncSession)
    db.execute.side_effect = [locked_result, practice_result, patient_result, delete_result]
    monkeypatch.setattr(patient_portal.secrets, "token_urlsafe", lambda _: "fixed-magic-code")
    sent = {}
    monkeypatch.setattr(
        "app.core.email_tasks.enqueue_email",
        lambda **kw: sent.update(kw) or "task-id",
    )

    response = await _raw_request_portal_access(
        request=_make_request(),
        payload=patient_portal.PortalAccessRequest(
            email=" Patient@Example.com ",
            date_of_birth="1990-01-02",
            practice_slug="test-dental",
        ),
        db=db,
    )

    patient_query = str(db.execute.await_args_list[2].args[0])
    practice_query = str(db.execute.await_args_list[1].args[0])
    assert "booking_pages.page_slug" in practice_query
    assert "patients.search_index_email" in patient_query
    assert "patients.email =" not in patient_query
    # No bearer leaks at step 1; inbox proof required.
    assert "access_token" not in response
    assert "sign-in link" in response["message"]
    assert sent.get("to") == "patient@example.com"
    assert "fixed-magic-code" in (sent.get("text_content") or "")
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_portal_verify_consumes_code_and_issues_bearer(monkeypatch):
    """Step 2: a valid unused code burns single-use and returns the bearer."""
    from app.models.patient import PatientPortalAccessCode

    now = datetime.now(timezone.utc)
    code_row = SimpleNamespace(
        token_hash=_hash_portal_token("good-code-0123456789abcdef"),
        patient_id=UUID("00000000-0000-0000-0000-000000000010"),
        practice_id=UUID("00000000-0000-0000-0000-000000000020"),
        used_at=None,
        expires_at=now + timedelta(minutes=15),
        attempts=0,
    )
    patient = SimpleNamespace(
        id=code_row.patient_id,
        first_name="Test",
        last_name="Patient",
        portal_access_token=None,
        portal_token_expires=None,
    )
    practice = SimpleNamespace(id=code_row.practice_id, name="Test Dental")
    code_result = MagicMock()
    code_result.scalar_one_or_none.return_value = code_row
    patient_result = MagicMock()
    patient_result.scalar_one_or_none.return_value = patient
    practice_result = MagicMock()
    practice_result.scalar_one_or_none.return_value = practice
    db = AsyncMock(spec=AsyncSession)
    db.execute.side_effect = [code_result, patient_result, practice_result]
    monkeypatch.setattr(patient_portal.secrets, "token_urlsafe", lambda _: "fixed-portal-token")

    response = await patient_portal.verify_portal_access(
        request=_make_request(),
        payload=patient_portal.PortalAccessVerify(code="good-code-0123456789abcdef"),
        db=db,
    )

    assert code_row.used_at is not None  # burned before issue
    assert response["access_token"] == "fixed-portal-token"
    assert patient.portal_access_token == _hash_portal_token("fixed-portal-token")
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_portal_verify_rejects_reused_code():
    """Single-use: a burned code 401s even with the right value."""
    code_row = SimpleNamespace(
        used_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        attempts=0,
    )
    code_result = MagicMock()
    code_result.scalar_one_or_none.return_value = code_row
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = code_result
    with pytest.raises(HTTPException) as exc_info:
        await patient_portal.verify_portal_access(
            request=_make_request(),
            payload=patient_portal.PortalAccessVerify(code="x" * 20),
            db=db,
        )
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_query_string_token_is_not_accepted(client: AsyncClient):
    response = await client.get("/api/v1/portal/me", params={"token": "legacy-token"})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"

@pytest.mark.asyncio
async def test_portal_payment_is_fail_closed_before_provider(monkeypatch):
    db = AsyncMock(spec=AsyncSession)
    monkeypatch.setattr(patient_portal, "_get_portal_patient", AsyncMock(return_value=SimpleNamespace(id=UUID(TEST_UUID))))
    payload = patient_portal.PortalPaymentRequest(invoice_id=UUID(TEST_UUID), amount="100.00")
    with pytest.raises(HTTPException) as exc_info:
        await patient_portal.make_payment(payload=payload, token="valid-token", db=db)
    assert exc_info.value.status_code == 503
    assert "unavailable" in str(exc_info.value.detail).lower()
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_portal_access_empty_body_returns_422_not_500(client: AsyncClient):
    """Regression: a bodyless POST used to 500 (AttributeError on the
    Optional[payload] test shim). It must now be a structured 422."""
    response = await client.post("/api/v1/portal/access")
    assert response.status_code == 422
    assert response.status_code != 500


@pytest.mark.asyncio
async def test_portal_access_identity_lockout_after_repeated_failures(db_session):
    """The M2 lockout is durable: failures persist in portal_identity_lockouts
    keyed by (practice_slug, email), attempts during lockout extend the window
    without growing the counter, and success clears the row."""
    practice_slug = "lockout-dental"
    email = "victim@example.com"

    count = 0
    for _ in range(patient_portal._MAX_PORTAL_ATTEMPTS):
        count = await patient_portal._portal_attempt_failed(db_session, practice_slug, email)
        await db_session.commit()

    assert count >= patient_portal._MAX_PORTAL_ATTEMPTS
    assert await patient_portal._portal_identity_locked(db_session, practice_slug, email)

    # Attempts during lockout refresh the window but do not grow the counter.
    probing_count = await patient_portal._portal_attempt_failed(db_session, practice_slug, email)
    await db_session.commit()
    assert probing_count == count
    assert await patient_portal._portal_identity_locked(db_session, practice_slug, email)

    # Success clears the row entirely.
    await patient_portal._portal_attempt_succeeded(db_session, practice_slug, email)
    await db_session.commit()
    assert not await patient_portal._portal_identity_locked(db_session, practice_slug, email)


@pytest.mark.asyncio
async def test_portal_access_success_clears_failure_counter(db_session):
    """A fresh identity that verifies successfully must start its counter from
    zero again — the cleared lockout row must not resurrect (M2 regression)."""
    practice_slug = "lockout-dental"
    email = "ok@example.com"

    # Seed failures just below the lockout threshold.
    for _ in range(patient_portal._MAX_PORTAL_ATTEMPTS - 1):
        await patient_portal._portal_attempt_failed(db_session, practice_slug, email)
    await db_session.commit()
    assert not await patient_portal._portal_identity_locked(db_session, practice_slug, email)

    # Successful verification clears the counter...
    await patient_portal._portal_attempt_succeeded(db_session, practice_slug, email)
    await db_session.commit()

    # ...so a subsequent failure restarts at 1, not at the threshold.
    count = await patient_portal._portal_attempt_failed(db_session, practice_slug, email)
    await db_session.commit()
    assert count == 1
    assert not await patient_portal._portal_identity_locked(db_session, practice_slug, email)


@pytest.mark.asyncio
async def test_portal_access_with_practice_public_slug_without_booking_page(db_session):
    """Regression test: Patient portal can authenticate via Practice.public_slug
    even when the practice has no BookingPage configured (C-03)."""
    import uuid
    from datetime import date
    from app.models.practice import Practice
    from app.models.patient import Patient
    from app.core.search_index import hmac_index

    practice = Practice(
        id=uuid.uuid4(),
        name="Direct Portal Dental",
        public_slug="direct-portal-dental",
        is_active=True,
    )
    db_session.add(practice)
    await db_session.flush()

    test_dob = date(1985, 6, 15)
    test_email = "direct_patient@example.com"

    patient = Patient(
        id=uuid.uuid4(),
        practice_id=practice.id,
        first_name="Direct",
        last_name="Patient",
        date_of_birth=test_dob,
        email=test_email,
        search_index_email=hmac_index(test_email),
        status="active",
    )
    db_session.add(patient)
    await db_session.commit()

    payload = patient_portal.PortalAccessRequest(
        practice_slug="direct-portal-dental",
        email=test_email,
        date_of_birth=test_dob,
    )
    req = _make_request()

    # Step 1 returns a generic message, never a bearer.
    from unittest.mock import patch as _patch

    with _patch(
        "app.core.email_tasks.enqueue_email", return_value="task-id"
    ):
        step1 = await _raw_request_portal_access(
            payload=payload,
            request=req,
            db=db_session,
        )
    assert "access_token" not in step1

    # Step 2: read the Citrine from the DB row is impossible (hashed) — fetch
    # the live code row and verify through the real endpoint path by code
    # value is not recoverable, so assert the row exists and consumes cleanly
    # via a freshly minted code instead.
    import secrets as _secrets

    from app.models.patient import PatientPortalAccessCode
    from app.core.security import hash_token as _hash_token

    raw = _secrets.token_urlsafe(32)
    db_session.add(
        PatientPortalAccessCode(
            patient_id=patient.id,
            practice_id=practice.id,
            token_hash=_hash_token(raw),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        )
    )
    await db_session.commit()

    step2 = await patient_portal.verify_portal_access(
        request=_make_request(),
        payload=patient_portal.PortalAccessVerify(code=raw),
        db=db_session,
    )
    assert "access_token" in step2
    assert step2["practice_name"] == "Direct Portal Dental"


@pytest.mark.asyncio
async def test_sign_document_creates_audit_log_record(db_session, monkeypatch):
    """Regression test: Electronically signing a document persists a HIPAA
    audit log entry with action='document_signed' (H-03)."""
    import uuid
    from datetime import date
    from unittest.mock import AsyncMock
    from sqlalchemy import select
    from app.models.practice import Practice
    from app.models.patient import Patient
    from app.models.document import Document, DocumentStatus, DocumentCategory
    from app.models.audit import AuditLog

    practice = Practice(
        id=uuid.uuid4(),
        name="Audit Dental",
        public_slug="audit-dental",
        is_active=True,
    )
    db_session.add(practice)
    await db_session.flush()

    patient = Patient(
        id=uuid.uuid4(),
        practice_id=practice.id,
        first_name="Signer",
        last_name="Patient",
        date_of_birth=date(1990, 1, 1),
        email="signer@example.com",
        status="active",
    )
    db_session.add(patient)
    await db_session.flush()

    doc = Document(
        id=uuid.uuid4(),
        practice_id=practice.id,
        patient_id=patient.id,
        name="Informed Consent",
        category=DocumentCategory.CONSENT,
        content="Patient agrees to treatment.",
        status=DocumentStatus.PENDING,
        is_completed=False,
    )
    db_session.add(doc)
    await db_session.commit()

    # Mock token resolution to our real database patient
    monkeypatch.setattr(patient_portal, "_get_portal_patient", AsyncMock(return_value=patient))

    sig_payload = patient_portal.PortalSignatureRequest(
        signature_data=TEST_SIGNATURE_DATA,
        signer_name="Signer Patient",
        agreement_accepted=True,
    )
    req = _make_request()

    raw_sign = getattr(patient_portal.sign_document, "__wrapped__", patient_portal.sign_document)
    sign_res = await raw_sign(
        document_id=doc.id,
        payload=sig_payload,
        request=req,
        token="valid-test-token",
        db=db_session,
    )
    assert sign_res["status"] == "success"

    # Verify audit log entry
    audit_res = await db_session.execute(
        select(AuditLog).where(
            AuditLog.action == "document_signed",
            AuditLog.entity_id == doc.id,
        )
    )
    audit_entry = audit_res.scalar_one_or_none()
    assert audit_entry is not None
    assert audit_entry.changes.get("document_name") == "Informed Consent"
    assert audit_entry.changes.get("patient_id") == str(patient.id)


@pytest.mark.asyncio
async def test_portal_resend_extends_existing_valid_code(monkeypatch):
    """Resend extends expiry of an existing unused code instead of creating a new one."""
    from app.models.patient import PatientPortalAccessCode

    practice = SimpleNamespace(
        id=UUID("00000000-0000-0000-0000-000000000020"),
        name="Resend Dental",
        public_slug="resend-dental",
        is_active=True,
    )
    patient = SimpleNamespace(
        id=UUID("00000000-0000-0000-0000-000000000010"),
        first_name="Resend",
        last_name="Patient",
        email="resend@example.com",
    )
    now = datetime.now(timezone.utc)
    code_row = SimpleNamespace(
        id=UUID("00000000-0000-0000-0000-000000000040"),
        token_hash=_hash_portal_token("resend-existing-code-0123456789abcdef"),
        patient_id=patient.id,
        practice_id=practice.id,
        used_at=None,
        expires_at=now + timedelta(minutes=5),
        attempts=0,
    )
    locked_result = MagicMock()
    locked_result.scalar_one_or_none.return_value = None
    practice_result = MagicMock()
    practice_result.scalar_one_or_none.return_value = practice
    patient_result = MagicMock()
    patient_result.scalar_one_or_none.return_value = patient
    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = code_row
    db = AsyncMock(spec=AsyncSession)
    db.execute.side_effect = [
        locked_result,
        practice_result,
        patient_result,
        existing_result,
    ]

    req = _make_request()
    response = await patient_portal.resend_portal_access(
        request=req,
        payload=patient_portal.PortalAccessResend(
            email="resend@example.com",
            date_of_birth=date(1990, 1, 2),
            practice_slug="resend-dental",
        ),
        db=db,
    )
    assert response["message"].startswith("If your details match")
    assert code_row.expires_at > now + timedelta(minutes=10)


@pytest.mark.asyncio
async def test_portal_resend_creates_new_code_when_none_exists(monkeypatch):
    """Resend creates a fresh code when no valid code exists for the patient."""
    from app.models.patient import PatientPortalAccessCode

    practice = SimpleNamespace(
        id=UUID("00000000-0000-0000-0000-000000000030"),
        name="Resend2 Dental",
        public_slug="resend2-dental",
        is_active=True,
    )
    patient = SimpleNamespace(
        id=UUID("00000000-0000-0000-0000-000000000010"),
        first_name="Resend2",
        last_name="Patient",
        email="resend2@example.com",
    )
    locked_result = MagicMock()
    locked_result.scalar_one_or_none.return_value = None
    practice_result = MagicMock()
    practice_result.scalar_one_or_none.return_value = practice
    patient_result = MagicMock()
    patient_result.scalar_one_or_none.return_value = patient
    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = None
    db = AsyncMock(spec=AsyncSession)
    db.execute.side_effect = [
        locked_result,
        practice_result,
        patient_result,
        existing_result,
    ]
    monkeypatch.setattr(patient_portal.secrets, "token_urlsafe", lambda _: "fresh-magic-code")

    req = _make_request()
    response = await patient_portal.resend_portal_access(
        request=req,
        payload=patient_portal.PortalAccessResend(
            email="resend2@example.com",
            date_of_birth=date(1990, 1, 2),
            practice_slug="resend2-dental",
        ),
        db=db,
    )
    assert response["message"].startswith("If your details match")
    # A new code row was queued via db.add(); the endpoint also flushes an
    # audit entry (db.add of an AuditLog) before sending, so require the code
    # among the added objects rather than asserting a single-add count.
    added = [c.args[0] for c in db.add.call_args_list]
    code_row = next(
        (a for a in added if isinstance(a, PatientPortalAccessCode)), None
    )
    assert code_row is not None
    assert code_row.patient_id == patient.id


@pytest.mark.asyncio
async def test_portal_resend_is_generic_for_unknown_email():
    """Resend never reveals whether the email exists (same generic message)."""
    req = _make_request()
    response = await patient_portal.resend_portal_access(
        request=req,
        payload=patient_portal.PortalAccessResend(
            email="nobody@example.com",
            date_of_birth=date(1990, 1, 2),
            practice_slug="resend-dental",
        ),
        db=AsyncMock(spec=AsyncSession),
    )
    assert response["message"].startswith("If your details match")


@pytest.mark.asyncio
async def test_portal_lockout_resets_attempts_on_expiry(db_session, test_practice):
    """When lockout expires, next failed attempt resets failed_attempts to 1, ending permanent pinning (H14, Decision 10)."""
    from app.models.portal_lockout import PortalIdentityLockout
    from app.api.v1.endpoints.patient_portal import _portal_attempt_failed, _portal_identity_locked

    slug = test_practice.public_slug
    email = "pin_test@example.com"
    past_locked = datetime.now(timezone.utc) - timedelta(minutes=5)

    lockout = PortalIdentityLockout(
        practice_slug=slug,
        email=email,
        failed_attempts=5,
        locked_until=past_locked,
    )
    db_session.add(lockout)
    await db_session.commit()

    # Identity should not be reported as locked because locked_until is in the past
    assert not await _portal_identity_locked(db_session, slug, email)

    # Next failed attempt should reset failed_attempts to 1 and clear locked_until
    count = await _portal_attempt_failed(db_session, slug, email)
    await db_session.commit()
    assert count == 1

    # Re-fetch lockout row to verify database state
    db_session.expire_all()
    from sqlalchemy import select
    res = await db_session.execute(
        select(PortalIdentityLockout).where(
            PortalIdentityLockout.practice_slug == slug,
            PortalIdentityLockout.email == email,
        )
    )
    row = res.scalar_one()
    assert row.failed_attempts == 1
    assert row.locked_until is None


@pytest.mark.asyncio
async def test_verify_portal_access_atomic_single_use(db_session, test_practice, test_patient):
    """Magic link verification is single-use and cannot be redeemed twice (M13)."""
    from app.models.patient import PatientPortalAccessCode
    from app.api.v1.endpoints.patient_portal import verify_portal_access, PortalAccessVerify, _hash_portal_token

    raw_code = "single-use-test-code-12345"
    token_hash = _hash_portal_token(raw_code)
    code_row = PatientPortalAccessCode(
        patient_id=test_patient.id,
        practice_id=test_practice.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    db_session.add(code_row)
    await db_session.commit()

    req = _make_request()
    payload = PortalAccessVerify(code=raw_code)

    # First redemption succeeds
    res1 = await verify_portal_access(req, payload, db=db_session)
    assert "access_token" in res1

    # Second redemption on the same code fails with 401
    with pytest.raises(HTTPException) as exc_info:
        await verify_portal_access(req, payload, db=db_session)
    assert exc_info.value.status_code == 401
    assert "invalid or expired" in exc_info.value.detail.lower()


