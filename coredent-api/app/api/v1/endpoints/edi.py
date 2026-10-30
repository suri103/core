"""
Insurance EDI Endpoints
DentalXChange integration for eligibility and claims
"""

import asyncio
import hashlib
import json
import logging
import requests
import secrets
import string
from datetime import date, datetime, timezone
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config_simple import settings
from app.models.user import User, UserRole
from app.models.insurance import InsuranceClaim, ClaimStatus
from app.models.patient import Patient
from app.core.audit import log_audit_event
from app.api.deps import require_role, verify_csrf
from app.services.tenant_refs import require_patient_insurance
from app.schemas.edi import (
    EligibilityCheckRequest,
    EligibilityCheckResponse,
    ClaimSubmitRequest,
    ClaimSubmitResponse,
    ClaimStatusResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def generate_confirmation_code() -> str:
    """Generate a unique confirmation code"""
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(12))


def _get_dxc_headers() -> dict:
    """Get headers for DentalXChange API"""
    return {
        "Authorization": f"Bearer {settings.DXC_API_KEY}",
        "Content-Type": "application/json",
    }


def _response_fingerprint(body: Optional[str]) -> str:
    """Stable, non-reversible identifier for a clearinghouse response body.

    M-22: clearinghouse rejections echo subscriber ids, names and dates of
    birth. Logging the body puts PHI in application logs, outside the
    centralized redaction in ``app.main``. A digest still lets us correlate
    with the clearinghouse's own records and spot repeated identical
    rejections, without carrying the content.
    """
    if not body:
        return "empty"
    return hashlib.sha256(body.encode("utf-8", errors="replace")).hexdigest()[:32]


def _derive_claim_idempotency_key(
    *,
    patient_id: UUID,
    patient_insurance_id: UUID,
    service_date: date,
    procedures: list[dict[str, Any]],
    total_amount: float,
) -> str:
    """Content-addressed idempotency key for one logical claim submission.

    H-03: two requests describing the same claim must collapse to one external
    submission, and two genuinely different claims for the same patient on the
    same day must not collide. Hashing the identifying content gives both,
    unlike the old "any claim for this patient in the last five minutes" rule.
    """
    canonical = json.dumps(
        {
            "patient_id": str(patient_id),
            "patient_insurance_id": str(patient_insurance_id),
            "service_date": service_date.isoformat(),
            "total_amount": f"{float(total_amount):.2f}",
            "procedures": sorted(
                (
                    str(p.get("procedureCode") or ""),
                    str(p.get("tooth") or ""),
                    str(p.get("surface") or ""),
                    f"{float(p.get('fee') or 0):.2f}",
                    str(p.get("dateOfService") or ""),
                )
                for p in procedures
            ),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return "auto_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _claim_replay_response(claim: InsuranceClaim) -> ClaimSubmitResponse:
    """Response for a repeated submission of an already-reserved claim."""
    if claim.status == ClaimStatus.SUBMITTING:
        message = (
            "This claim is already being submitted. Its outcome with the "
            "clearinghouse is not yet confirmed; no duplicate was created."
        )
    elif claim.status == ClaimStatus.SUBMISSION_FAILED:
        message = (
            "This claim was already attempted and rejected by the "
            "clearinghouse. Correct the claim details to submit a new one."
        )
    else:
        message = "This claim was already submitted; returning the existing claim."
    return ClaimSubmitResponse(
        claim_id=str(claim.id),
        external_claim_id=(
            claim.claim_number
            if claim.status == ClaimStatus.SUBMITTED
            else claim.confirmation_number or ""
        ),
        status=claim.status.value if claim.status else "unknown",
        message=message,
        submitted_at=claim.submission_date.isoformat() if claim.submission_date else "",
    )


@router.post("/eligibility/check", response_model=EligibilityCheckResponse)
async def check_eligibility(
    request: Request,
    eligibility_data: EligibilityCheckRequest,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> EligibilityCheckResponse:
    """
    Check patient insurance eligibility in real-time.
    
    Design decisions:
    - Source of truth: DentalXChange API
    - Derived: Eligibility status from payer response
    - Stored: Check history in database (optional)
    """
    if not settings.DXC_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Insurance verification service not configured",
        )

    # H-02 FIX: prove the policy belongs to this patient AND that the patient
    # is in the caller's practice, in one predicate. The old query checked the
    # policy/patient pairing but never the practice, relying on a separate
    # patient lookup below to catch tenant crossing.
    insurance = await require_patient_insurance(
        db,
        eligibility_data.patient_insurance_id,
        current_user.practice_id,
        patient_id=eligibility_data.patient_id,
    )

    # Get patient details
    result = await db.execute(
        select(Patient).where(
            Patient.id == eligibility_data.patient_id,
            Patient.practice_id == current_user.practice_id,
        )
    )
    patient = result.scalar_one_or_none()

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    # SECURITY: A clearinghouse submission without a real provider NPI would
    # send a fabricated identifier into a PHI-bearing request. Fail loudly
    # instead of silently defaulting.
    if not current_user.npi:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The submitting provider has no NPI on file. Add the provider's NPI before checking eligibility.",
        )

    # Build eligibility request payload
    payload = {
        "payerId": insurance.payer_id,
        "subscriberId": insurance.subscriber_id,
        "providerNpi": current_user.npi,
        "serviceDate": eligibility_data.service_date.isoformat() if eligibility_data.service_date else "",
        "serviceTypeCodes": ["30"],  # Health benefit plan coverage
        "patient": {
            "firstName": patient.first_name,
            "lastName": patient.last_name,
            "dateOfBirth": patient.date_of_birth.isoformat() if patient.date_of_birth else "",
            "memberId": insurance.subscriber_id,
        }
    }

    try:
        response = await asyncio.to_thread(
            requests.post,
            f"{settings.DXC_BASE_URL}/eligibility",
            json=payload,
            headers=_get_dxc_headers(),
            timeout=30,
        )

        if response.status_code == 200:
            data = response.json()
            eligibility_response = EligibilityCheckResponse(
                eligible=data.get("eligible", False),
                coverage_status=data.get("coverageStatus", "Unknown"),
                plan_name=data.get("planName", ""),
                effective_date=data.get("effectiveDate", ""),
                termination_date=data.get("terminationDate", ""),
                copay=data.get("copay", 0),
                deductible=data.get("deductible", 0),
                deductible_remaining=data.get("deductibleRemaining", 0),
                coinsurance=data.get("coinsurance", 0),
                annual_max=data.get("annualMaximum", 0),
                annual_remaining=data.get("annualMaximumRemaining", 0),
                message=data.get("message", ""),
            )
        else:
            # M-22 FIX: do not log the clearinghouse response body. A 271
            # eligibility response carries subscriber names, dates of birth and
            # plan identifiers; logging it puts PHI outside the centralized
            # redaction path. Log a digest instead.
            logger.warning(
                "Eligibility check rejected by clearinghouse: status=%s body_sha256=%s len=%d",
                response.status_code,
                _response_fingerprint(response.text),
                len(response.text or ""),
            )
            await log_audit_event(
                db,
                current_user,
                "check_eligibility_rejected",
                "patient",
                patient.id,
                request,
                {"status_code": response.status_code},
            )
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Eligibility check was rejected by the insurance clearinghouse.",
            )

    except requests.RequestException as e:
        # HIPAA: Log failed eligibility check (still an access attempt).
        # M-22: record the exception type, not str(e) — request exceptions
        # embed the full URL and can embed response fragments.
        await log_audit_event(
            db, current_user, "check_eligibility_failed", "patient", patient.id, request,
            {"error_type": type(e).__name__},
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to reach the insurance verification service. Please retry.",
        )

    # HIPAA: Persist the successful PHI access audit before returning.
    await log_audit_event(
        db, current_user, "check_eligibility_success", "patient", patient.id, request
    )
    await db.commit()
    return eligibility_response


@router.post("/claims/submit", response_model=ClaimSubmitResponse)
async def submit_claim(
    request: Request,
    claim_data: ClaimSubmitRequest,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> ClaimSubmitResponse:
    """
    Submit dental claim electronically to insurance.
    
    Design decisions:
    - Source of truth: DentalXChange API (returns claim ID)
    - Stored: Claim record in database with status tracking
    """
    if not settings.DXC_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Claims submission service not configured",
        )

    # H-02 FIX: the insurance policy must belong to *this* patient, not merely
    # to some patient in this practice. Without the patient match, a caller
    # could pair patient A with patient B's subscriber id and payer, sending
    # one patient's claim under another's policy.
    insurance = await require_patient_insurance(
        db,
        claim_data.patient_insurance_id,
        current_user.practice_id,
        patient_id=claim_data.patient_id,
    )

    # Get patient
    result = await db.execute(
        select(Patient).where(
            Patient.id == claim_data.patient_id,
            Patient.practice_id == current_user.practice_id,
        )
    )
    patient = result.scalar_one_or_none()

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    # Build claim payload (837D format via JSON API)
    procedures = []
    for proc in claim_data.procedures:
        procedures.append({
            "procedureCode": proc.procedure_code,
            "tooth": proc.tooth,
            "surface": proc.surface,
            "fee": proc.fee,
            "dateOfService": proc.date_of_service.isoformat(),
        })

    # SECURITY: Refuse to fabricate an NPI for a real claim. A claim carrying
    # a placeholder NPI would be rejected (or worse, misattributed) by the
    # payer.
    if not current_user.npi:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The submitting provider has no NPI on file. Add the provider's NPI before submitting claims.",
        )

    # H-03 FIX: durable idempotency. The old guard rejected *any* claim for the
    # patient within five minutes, which blocked legitimate second claims and
    # still allowed duplicates after the window. We now derive (or accept) a
    # stable key and reserve the claim row locally BEFORE calling the
    # clearinghouse, committing that reservation. A retry then finds the
    # reservation instead of submitting to the payer a second time.
    idempotency_key = claim_data.idempotency_key or _derive_claim_idempotency_key(
        patient_id=claim_data.patient_id,
        patient_insurance_id=claim_data.patient_insurance_id,
        service_date=claim_data.service_date,
        procedures=procedures,
        total_amount=claim_data.total_amount,
    )

    existing = (
        await db.execute(
            select(InsuranceClaim).where(
                InsuranceClaim.practice_id == current_user.practice_id,
                InsuranceClaim.submission_idempotency_key == idempotency_key,
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        return _claim_replay_response(existing)

    # Phase 1: reserve the claim locally and COMMIT before any external call.
    claim = InsuranceClaim(
        practice_id=current_user.practice_id,
        patient_id=patient.id,
        patient_insurance_id=insurance.id,
        carrier_id=insurance.carrier_id,
        claim_number=f"PENDING-{generate_confirmation_code()}",
        status=ClaimStatus.SUBMITTING,
        billed_amount=claim_data.total_amount,
        service_date=claim_data.service_date,
        # Passed as values, not json.dumps(...). insurance_claims.procedure_codes
        # and diagnosis_codes are JSON columns (migration b1c2d3e4f5a6); encoding
        # them here would store a JSON *string* rather than an array, which is the
        # discrepancy the reader at insurance.py:~690 still tolerates.
        # InsurancePreAuthorization.procedure_codes is a different column and is
        # still Text on purpose - this module's pre-auth route keeps json.dumps.
        diagnosis_codes=claim_data.diagnosis_codes or [],
        procedure_codes=procedures,
        submission_idempotency_key=idempotency_key,
        submission_attempts=1,
    )
    db.add(claim)
    try:
        await db.flush()
        await log_audit_event(
            db,
            current_user,
            "submit_claim_reserved",
            "insurance_claim",
            claim.id,
            request,
        )
        await db.commit()
    except IntegrityError:
        # Concurrent request reserved the same key first.
        await db.rollback()
        winner = (
            await db.execute(
                select(InsuranceClaim).where(
                    InsuranceClaim.practice_id == current_user.practice_id,
                    InsuranceClaim.submission_idempotency_key == idempotency_key,
                )
            )
        ).scalar_one_or_none()
        if winner is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Claim submission conflicted; please retry.",
            )
        return _claim_replay_response(winner)

    await db.refresh(claim)

    payload = {
        "claim": {
            "patientFirstName": patient.first_name,
            "patientLastName": patient.last_name,
            "patientDateOfBirth": patient.date_of_birth.isoformat() if patient.date_of_birth else "",
            "subscriberId": insurance.subscriber_id,
            "payerId": insurance.payer_id,
            "providerNpi": current_user.npi,
            "providerName": f"{current_user.first_name} {current_user.last_name}",
            "serviceFacilityNpi": current_user.practice.npi if (getattr(current_user, "practice", None) and getattr(current_user.practice, "npi", None)) else "",
            "procedures": procedures,
            "totalAmount": claim_data.total_amount,
            "diagnosisCodes": claim_data.diagnosis_codes or [],
            # Pass our key through so the clearinghouse can dedupe too.
            "clientClaimId": str(claim.id),
        }
    }

    try:
        response = await asyncio.to_thread(
            requests.post,
            f"{settings.DXC_BASE_URL}/claims",
            json=payload,
            headers=_get_dxc_headers(),
            timeout=60,
        )

        if response.status_code in (200, 201):
            data = response.json()

            # Phase 2: record the external outcome against the reserved row.
            external_id = data.get("claimId") or ""
            claim.claim_number = external_id or claim.claim_number.replace(
                "PENDING-", "", 1
            )
            claim.status = ClaimStatus.SUBMITTED
            claim.confirmation_number = data.get("confirmationNumber") or external_id or None
            claim.submission_date = datetime.now(timezone.utc).date()
            claim.submission_error = None

            # Persist the clearinghouse outcome and its HIPAA audit atomically.
            await log_audit_event(
                db, current_user, "submit_claim_success", "insurance_claim", claim.id, request
            )
            await db.commit()
            await db.refresh(claim)

            return ClaimSubmitResponse(
                claim_id=str(claim.id),
                external_claim_id=external_id,
                status="submitted",
                message="Claim submitted successfully",
                submitted_at=data.get("submittedAt", ""),
            )
        else:
            # M-22 FIX: never log the clearinghouse response body. A 837D/277
            # rejection echoes back subscriber ids, names and dates of birth,
            # which put PHI into application logs outside the centralized
            # redaction path. Status code and a hashed body fingerprint are
            # enough to correlate with the clearinghouse's own logs.
            logger.warning(
                "Claim submission rejected by clearinghouse: claim=%s status=%s body_sha256=%s len=%d",
                claim.id,
                response.status_code,
                _response_fingerprint(response.text),
                len(response.text or ""),
            )
            claim.status = ClaimStatus.SUBMISSION_FAILED
            claim.submission_error = (
                f"Clearinghouse rejected the claim (HTTP {response.status_code})."
            )
            await log_audit_event(
                db,
                current_user,
                "submit_claim_rejected",
                "insurance_claim",
                claim.id,
                request,
                {"status_code": response.status_code},
            )
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Claim submission was rejected by the insurance clearinghouse.",
            )

    except requests.RequestException as e:
        # H-03: the reservation stays SUBMITTING because we genuinely do not
        # know whether the payer received it. A retry with the same
        # idempotency key returns this row instead of re-submitting; an
        # operator (or the status poller) resolves it against the
        # clearinghouse. Never silently roll the reservation back.
        claim.submission_error = f"Transport failure: {type(e).__name__}"
        # HIPAA: Persist the ambiguous transport outcome and audit atomically.
        # M-22: record the exception type, never the exception text.
        await log_audit_event(
            db, current_user, "submit_claim_failed", "insurance_claim", claim.id, request,
            {"error_type": type(e).__name__},
        )
        await db.commit()
        logger.error(
            "Claim %s submission transport failure (%s); left in SUBMITTING for "
            "reconciliation",
            claim.id,
            type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Unable to reach the insurance clearinghouse. The claim is "
                "recorded as in-flight; retrying with the same details will "
                "not create a duplicate."
            ),
        )


@router.get("/claims/{claim_id}/status", response_model=ClaimStatusResponse)
async def get_claim_status(
    request: Request,
    claim_id: str,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> ClaimStatusResponse:
    """
    Get the status of a submitted claim.
    """
    if not settings.DXC_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Claims service not configured",
        )

    # Scoped-first lookup: join through Patient so a foreign-practice id
    # 404s instead of loading a foreign row then 403ing (existence oracle).
    result = await db.execute(
        select(InsuranceClaim)
        .join(Patient, Patient.id == InsuranceClaim.patient_id)
        .where(
            InsuranceClaim.id == UUID(claim_id),
            Patient.practice_id == current_user.practice_id,
        )
    )
    claim = result.scalar_one_or_none()

    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Claim not found",
        )

    # HIPAA: Log claim status read (PHI read)
    await log_audit_event(
        db, current_user, "view_claim_status", "insurance_claim", claim.id, request
    )
    await db.commit()

    # Query DentalXChange for status
    try:
        response = await asyncio.to_thread(
            requests.get,
            f"{settings.DXC_BASE_URL}/claims/{claim.claim_number}/status",
            headers=_get_dxc_headers(),
            timeout=30,
        )

        if response.status_code == 200:
            data = response.json()
            return ClaimStatusResponse(
                claim_id=str(claim.id),
                external_claim_id=claim.claim_number,
                status=data.get("status", claim.status.value),
                paid_amount=data.get("paidAmount", 0),
                patient_responsibility=data.get("patientResponsibility", 0),
                denial_code=data.get("denialCode"),
                denial_reason=data.get("denialReason"),
                processed_date=data.get("processedDate"),
            )
        else:
            # Return database status if API fails
            return ClaimStatusResponse(
                claim_id=str(claim.id),
                external_claim_id=claim.claim_number,
                status=claim.status.value,
            )

    except requests.RequestException:
        # Return database status if API unavailable
        return ClaimStatusResponse(
            claim_id=str(claim.id),
            external_claim_id=claim.claim_number,
            status=claim.status.value,
        )


@router.get("/claims/{claim_id}/export-837d")
async def export_claim_837d(
    request: Request,
    claim_id: UUID,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN, UserRole.ACCOUNTANT)),
    db: AsyncSession = Depends(get_db),
):
    """Generate and download ANSI ASC X12 837D Dental Claim batch text."""
    from app.services.clearinghouse_service import ClearinghouseService

    x12_content = await ClearinghouseService.export_claim_837d(
        db, claim_id, current_user.practice_id
    )

    await log_audit_event(
        db, current_user, "export_claim_837d", "insurance_claim", claim_id, request
    )
    await db.commit()

    return {
        "claim_id": str(claim_id),
        "format": "ANSI_ASC_X12_005010X224A2",
        "edi_content": x12_content,
    }


@router.post("/era/upload")
async def upload_and_reconcile_era(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN, UserRole.ACCOUNTANT)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
):
    """
    Upload and automatically reconcile an ANSI ASC X12 835 Remittance Advice (ERA) file.
    Matches claims in this practice, updates statuses, interprets CARC denial reason codes,
    and auto-posts insurance payments to the invoice ledger.
    """
    from app.services.clearinghouse_service import ClearinghouseService

    content_bytes = await file.read()
    era_text = content_bytes.decode("utf-8", errors="replace")

    if not era_text.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded ERA file is empty")

    report = await ClearinghouseService.process_era_835(
        db=db,
        era_text=era_text,
        practice_id=current_user.practice_id,
        current_user=current_user,
        request=request,
    )
    return report


@router.post("/era/reconcile-text")
async def reconcile_era_text(
    payload: dict,
    request: Request,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN, UserRole.ACCOUNTANT)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
):
    """Reconcile raw ANSI ASC X12 835 text received via clearinghouse webhook or API."""
    from app.services.clearinghouse_service import ClearinghouseService

    era_text = payload.get("era_text", "").strip()
    if not era_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="era_text is required")

    return await ClearinghouseService.process_era_835(
        db=db,
        era_text=era_text,
        practice_id=current_user.practice_id,
        current_user=current_user,
        request=request,
    )