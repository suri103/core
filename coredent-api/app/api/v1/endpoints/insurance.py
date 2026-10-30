"""
Insurance Endpoints
CRUD operations for insurance management
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from datetime import datetime, date, timezone
from typing import Optional
from uuid import UUID, uuid4
from decimal import Decimal
import json
import httpx

from app.core.database import get_db
from app.core.config_simple import settings
from app.models.user import User, UserRole
from app.api.deps import get_current_user, require_role, verify_csrf
from app.core.audit import log_audit_event
from app.core.business_time import (
    DateRangeError,
    get_practice_timezone,
    resolve_date_range,
)
from app.models.insurance import (
    InsuranceCarrier,
    PatientInsurance,
    InsuranceClaim,
    InsurancePreAuthorization,
    ClaimStatus,
    Eligibility,
    ExplanationOfBenefits,
    FeeSchedule,
    FeeScheduleEntry,
)
from app.models.patient import Patient
from app.services.tenant_refs import (
    require_carrier,
    require_patient_insurance,
    require_pre_authorization,
)
from app.schemas.insurance import (
    FeeScheduleCreate,
    FeeScheduleResponse,
    FeeScheduleListResponse,
    InsuranceCarrierCreate,
    InsuranceCarrierUpdate,
    InsuranceCarrierResponse,
    InsuranceCarrierListResponse,
    PatientInsuranceCreate,
    PatientInsuranceUpdate,
    PatientInsuranceResponse,
    PatientInsuranceListResponse,
    InsuranceClaimCreate,
    InsuranceClaimUpdate,
    InsuranceClaimResponse,
    InsuranceClaimListResponse,
    PreAuthorizationCreate,
    PreAuthorizationUpdate,
    PreAuthorizationResponse,
    PreAuthorizationListResponse,
    PreAuthorizationStatus,
    EligibilityListResponse,
    ExplanationOfBenefitsListResponse,
)

router = APIRouter()


# Insurance Carrier Endpoints

@router.get("/carriers/", response_model=InsuranceCarrierListResponse)
async def list_carriers(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search by name"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InsuranceCarrierListResponse:
    """
    List insurance carriers
    """
    from sqlalchemy import or_
    query = select(InsuranceCarrier).where(
        or_(
            InsuranceCarrier.practice_id.is_(None),
            InsuranceCarrier.practice_id == current_user.practice_id,
        )
    )

    if is_active is not None:
        query = query.where(InsuranceCarrier.is_active == is_active)

    if search:
        search_pattern = f"%{search}%"
        query = query.where(InsuranceCarrier.name.ilike(search_pattern))

    query = query.order_by(InsuranceCarrier.name)

    result = await db.execute(query)
    carriers = result.scalars().all()

    return InsuranceCarrierListResponse(
        carriers=carriers,
        count=len(carriers),
    )


@router.get("/carriers/{carrier_id}", response_model=InsuranceCarrierResponse)
async def get_carrier(
    carrier_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InsuranceCarrierResponse:
    """
    Get insurance carrier by ID
    """
    from sqlalchemy import or_
    result = await db.execute(
        select(InsuranceCarrier).where(
            InsuranceCarrier.id == carrier_id,
            or_(
                InsuranceCarrier.practice_id.is_(None),
                InsuranceCarrier.practice_id == current_user.practice_id,
            ),
        )
    )
    carrier = result.scalar_one_or_none()

    if not carrier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Insurance carrier not found",
        )

    return carrier


@router.post("/carriers/", response_model=InsuranceCarrierResponse)
async def create_carrier(
    carrier_data: InsuranceCarrierCreate,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> InsuranceCarrierResponse:
    """
    Create new insurance carrier
    """
    from sqlalchemy import or_
    # Check for duplicate payer_id within practice or global
    if carrier_data.payer_id:
        result = await db.execute(
            select(InsuranceCarrier).where(
                InsuranceCarrier.payer_id == carrier_data.payer_id,
                or_(
                    InsuranceCarrier.practice_id.is_(None),
                    InsuranceCarrier.practice_id == current_user.practice_id,
                ),
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Carrier with this payer ID already exists",
            )

    carrier = InsuranceCarrier(
        practice_id=current_user.practice_id,
        **carrier_data.dict()
    )
    db.add(carrier)
    await db.commit()
    await db.refresh(carrier)

    return carrier


@router.put("/carriers/{carrier_id}", response_model=InsuranceCarrierResponse)
async def update_carrier(
    carrier_id: UUID,
    carrier_data: InsuranceCarrierUpdate,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> InsuranceCarrierResponse:
    """
    Update insurance carrier
    """
    result = await db.execute(
        select(InsuranceCarrier).where(
            InsuranceCarrier.id == carrier_id,
            InsuranceCarrier.practice_id == current_user.practice_id,
        )
    )
    carrier = result.scalar_one_or_none()

    if not carrier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Insurance carrier not found or cannot be modified",
        )

    update_data = carrier_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(carrier, field, value)

    await db.commit()
    await db.refresh(carrier)

    return carrier


# Patient Insurance Endpoints

@router.get("/patients/{patient_id}/policies", response_model=PatientInsuranceListResponse)
async def list_patient_insurance(
    patient_id: UUID,
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PatientInsuranceListResponse:
    """
    List patient insurance policies
    """
    # Verify patient belongs to practice
    result = await db.execute(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.practice_id == current_user.practice_id,
        )
    )
    patient = result.scalar_one_or_none()

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    # L-11 hardening: join through Patient so the policy list is proven
    # practice-scoped in one query (patient gate above already 404s cross-tenant).
    query = (
        select(PatientInsurance)
        .join(Patient, Patient.id == PatientInsurance.patient_id)
        .where(
            PatientInsurance.patient_id == patient_id,
            Patient.practice_id == current_user.practice_id,
        )
    )

    if is_active is not None:
        query = query.where(PatientInsurance.is_active == is_active)

    query = query.order_by(
        PatientInsurance.is_primary.desc(),
        PatientInsurance.created_at.desc(),
        PatientInsurance.id.desc(),
    )

    result = await db.execute(query)
    insurances = result.scalars().all()

    # HIPAA: Log patient insurance access
    await log_audit_event(
        db, current_user, "list_patient_insurance", "patient", patient_id, request
    )
    await db.commit()

    return PatientInsuranceListResponse(
        insurances=insurances,
        count=len(insurances),
    )


@router.post("/patients/{patient_id}/policies", response_model=PatientInsuranceResponse)
async def create_patient_insurance(
    patient_id: UUID,
    insurance_data: PatientInsuranceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> PatientInsuranceResponse:
    """
    Add insurance policy to patient
    """
    # Verify patient belongs to practice
    result = await db.execute(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.practice_id == current_user.practice_id,
        )
    )
    patient = result.scalar_one_or_none()

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    # M-10 FIX: the carrier must be global (practice_id IS NULL) or owned by
    # this practice. Loading it by id alone let a patient policy hold a foreign
    # key into another tenant's carrier row, which then surfaced that carrier's
    # name, payer id and fee schedule through every policy read.
    await require_carrier(db, insurance_data.carrier_id, current_user.practice_id)

    insurance = PatientInsurance(
        patient_id=patient_id,
        **insurance_data.model_dump(),
    )

    db.add(insurance)
    await db.commit()
    await db.refresh(insurance)

    return insurance


@router.put("/policies/{policy_id}", response_model=PatientInsuranceResponse)
async def update_patient_insurance(
    policy_id: UUID,
    insurance_data: PatientInsuranceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> PatientInsuranceResponse:
    """Update a patient insurance policy owned by the current practice."""
    insurance = await require_patient_insurance(
        db, policy_id, current_user.practice_id
    )

    update_data = insurance_data.model_dump(exclude_unset=True)
    # M-10 FIX: the update path accepted carrier_id with no ownership check,
    # so a policy could be repointed at another tenant's carrier after
    # creation even once creation was hardened.
    if "carrier_id" in update_data and update_data["carrier_id"] is not None:
        await require_carrier(db, update_data["carrier_id"], current_user.practice_id)
    # patient_id is not client-reassignable: moving a policy to another patient
    # would silently transfer coverage records.
    update_data.pop("patient_id", None)
    for field, value in update_data.items():
        setattr(insurance, field, value)

    await db.commit()
    await db.refresh(insurance)

    return insurance


@router.delete("/policies/{policy_id}")
async def delete_patient_insurance(
    policy_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict[str, str]:
    """Delete an unreferenced policy owned by the current practice."""
    insurance = await require_patient_insurance(
        db, policy_id, current_user.practice_id
    )

    # Preserve referential integrity: policies with claims or pre-authorizations
    # are historical financial records and cannot be physically removed.
    claim_count = (
        await db.execute(
            select(func.count(InsuranceClaim.id)).where(
                InsuranceClaim.patient_insurance_id == insurance.id
            )
        )
    ).scalar_one()
    pre_auth_count = (
        await db.execute(
            select(func.count(InsurancePreAuthorization.id)).where(
                InsurancePreAuthorization.patient_insurance_id == insurance.id
            )
        )
    ).scalar_one()
    if claim_count or pre_auth_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Insurance policy with claims or pre-authorizations cannot be deleted; mark it inactive instead",
        )

    await db.delete(insurance)
    await db.commit()

    return {"message": "Insurance policy deleted successfully"}


# Insurance Claim Endpoints

@router.get("/claims/", response_model=InsuranceClaimListResponse)
async def list_claims(
    status: Optional[ClaimStatus] = Query(None, description="Filter by status"),
    patient_id: Optional[str] = Query(None, description="Filter by patient"),
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    limit: int = Query(50, ge=1, le=200, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InsuranceClaimListResponse:
    """List insurance claims within a bounded practice-local date range."""
    practice_tz = await get_practice_timezone(db, current_user.practice_id)
    try:
        date_range = resolve_date_range(
            practice_tz,
            start_date,
            end_date,
            default_days=366,
        )
    except DateRangeError as exc:
        # ``status`` is a legacy public query parameter in this handler.
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # ``service_date`` is a date-only column, so use the resolver's inclusive
    # practice-local calendar dates rather than its UTC timestamp bounds.
    filters = [
        InsuranceClaim.practice_id == current_user.practice_id,
        InsuranceClaim.service_date >= date_range.start_date,
        InsuranceClaim.service_date <= date_range.end_date,
    ]
    if status:
        filters.append(InsuranceClaim.status == status)
    if patient_id:
        filters.append(InsuranceClaim.patient_id == patient_id)

    total = (
        await db.execute(select(func.count(InsuranceClaim.id)).where(*filters))
    ).scalar_one()
    query = (
        select(InsuranceClaim)
        .where(*filters)
        .order_by(InsuranceClaim.service_date.desc(), InsuranceClaim.id.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(query)
    claims = result.scalars().all()

    # HIPAA: Log claim list access
    await log_audit_event(
        db, current_user, "list_insurance_claims", "insurance_claim", None, request
    )
    await db.commit()

    page_count = len(claims)
    return InsuranceClaimListResponse(
        claims=claims,
        count=page_count,
        total=total,
        limit=limit,
        offset=offset,
        next_offset=offset + page_count if offset + page_count < total else None,
    )


@router.post("/claims/", response_model=InsuranceClaimResponse)
async def create_claim(
    claim_data: InsuranceClaimCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> InsuranceClaimResponse:
    """
    Create insurance claim
    """
    # Ownership: the policy must belong to a patient in this practice.
    # patient_id and carrier_id are derived from the policy rather than taken
    # from the request, so the claim cannot pair mismatched entities.
    patient_insurance = await require_patient_insurance(
        db, claim_data.patient_insurance_id, current_user.practice_id
    )
    # Generate the claim number under a per-practice advisory lock (same
    # concurrency-safety pattern as billing invoice numbers — count+1
    # numbering raced on uq_practice_claim_number under concurrent creates).
    from app.core.database import row_locks_supported
    is_postgres = row_locks_supported()
    from app.core.business_time import business_date, day_bounds_utc

    practice_tz = await get_practice_timezone(db, current_user.practice_id)
    business_day = business_date(practice_tz)
    day_start_utc, day_end_utc = day_bounds_utc(practice_tz, business_day)

    if is_postgres:
        day_key = int(business_day.strftime("%Y%m%d"))
        practice_int = int.from_bytes(
            current_user.practice_id.bytes[:8], byteorder="big", signed=False
        ) & 0x7FFFFFFFFFFFFFFF
        lock_key = (practice_int ^ day_key) & 0x7FFFFFFFFFFFFFFF
        await db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": lock_key})

    claim_count = await db.execute(
        select(func.count(InsuranceClaim.id)).where(
            InsuranceClaim.practice_id == current_user.practice_id,
            InsuranceClaim.created_at >= day_start_utc,
            InsuranceClaim.created_at < day_end_utc,
        )
    )
    count = claim_count.scalar() or 0

    seq = count + 1
    while seq < count + 10000:
        candidate = f"CLM-{business_day.strftime('%Y%m%d')}-{seq:04d}"
        exists = await db.execute(
            select(InsuranceClaim.id).where(
                InsuranceClaim.practice_id == current_user.practice_id,
                InsuranceClaim.claim_number == candidate,
            )
        )
        if exists.scalar_one_or_none() is None:
            claim_number = candidate
            break
        seq += 1
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not allocate a claim number",
        )

    claim = InsuranceClaim(
        practice_id=current_user.practice_id,
        patient_id=patient_insurance.patient_id,
        patient_insurance_id=claim_data.patient_insurance_id,
        carrier_id=patient_insurance.carrier_id,
        claim_number=claim_number,
        service_date=claim_data.service_date,
        billed_amount=claim_data.billed_amount,
        procedure_codes=[pc.model_dump(mode='json') for pc in claim_data.procedure_codes],
        diagnosis_codes=(claim_data.diagnosis_codes or []),
        notes=claim_data.notes,
    )

    db.add(claim)
    await db.commit()
    await db.refresh(claim)

    return claim


_CLAIM_TRANSITIONS = {
    ClaimStatus.DRAFT: {ClaimStatus.SUBMITTED, ClaimStatus.PENDING, ClaimStatus.SUBMITTING},
    ClaimStatus.PENDING: {ClaimStatus.SUBMITTED, ClaimStatus.SUBMITTING, ClaimStatus.IN_REVIEW, ClaimStatus.DENIED},
    ClaimStatus.SUBMITTING: {ClaimStatus.SUBMITTED, ClaimStatus.SUBMISSION_FAILED},
    ClaimStatus.SUBMISSION_FAILED: {ClaimStatus.DRAFT, ClaimStatus.SUBMITTING, ClaimStatus.SUBMITTED},
    ClaimStatus.SUBMITTED: {ClaimStatus.IN_REVIEW, ClaimStatus.APPROVED, ClaimStatus.PARTIALLY_APPROVED, ClaimStatus.DENIED, ClaimStatus.PAID},
    ClaimStatus.IN_REVIEW: {ClaimStatus.APPROVED, ClaimStatus.PARTIALLY_APPROVED, ClaimStatus.DENIED, ClaimStatus.PAID},
    ClaimStatus.APPROVED: {ClaimStatus.PAID, ClaimStatus.PARTIALLY_APPROVED},
    ClaimStatus.PARTIALLY_APPROVED: {ClaimStatus.PAID, ClaimStatus.APPEALED},
    ClaimStatus.DENIED: {ClaimStatus.APPEALED},
    ClaimStatus.APPEALED: {ClaimStatus.IN_REVIEW, ClaimStatus.APPROVED, ClaimStatus.PARTIALLY_APPROVED, ClaimStatus.DENIED, ClaimStatus.PAID},
    ClaimStatus.PAID: set(),  # Terminal state
}


@router.put("/claims/{claim_id}", response_model=InsuranceClaimResponse)
async def update_claim(
    claim_id: UUID,
    claim_data: InsuranceClaimUpdate,
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> InsuranceClaimResponse:
    """
    Update insurance claim with strict status transition and amount bounds validation
    """
    result = await db.execute(
        select(InsuranceClaim).where(
            InsuranceClaim.id == claim_id,
            InsuranceClaim.practice_id == current_user.practice_id,
        )
    )
    claim = result.scalar_one_or_none()

    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Claim not found",
        )

    update_data = claim_data.dict(exclude_unset=True)

    # Validate status transitions
    new_status = update_data.get("status")
    if new_status and new_status != claim.status:
        allowed = _CLAIM_TRANSITIONS.get(claim.status, set())
        if new_status not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid claim status transition from {claim.status} to {new_status}",
            )

    effective_status = new_status or claim.status
    adjudication_fields = (
        "allowed_amount",
        "paid_amount",
        "patient_responsibility",
        "deductible_amount",
        "copay_amount",
    )

    # In DRAFT, claim has not been submitted or adjudicated; money adjudication fields are not writable
    if effective_status == ClaimStatus.DRAFT:
        if any(update_data.get(f) is not None for f in adjudication_fields):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Adjudication money fields cannot be updated while claim is in DRAFT",
            )

    # When claim is in terminal PAID state, money fields cannot be modified
    if claim.status == ClaimStatus.PAID:
        if any(f in update_data for f in adjudication_fields):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Money fields cannot be modified on a paid claim",
            )

    billed = Decimal(str(claim.billed_amount or 0))

    # Validate allowed_amount bounds
    allowed_amt = update_data.get("allowed_amount")
    if allowed_amt is not None:
        if allowed_amt < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Allowed amount cannot be negative",
            )
        if claim.billed_amount is not None and allowed_amt > billed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Allowed amount cannot exceed billed amount",
            )

    # Validate paid_amount bounds
    paid_amt = update_data.get("paid_amount")
    if paid_amt is not None:
        if paid_amt < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Paid amount cannot be negative",
            )
        if claim.billed_amount is not None and paid_amt > billed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Paid amount cannot exceed billed amount",
            )

    # Validate patient_responsibility bounds (<= billed, <= allowed)
    patient_resp = update_data.get("patient_responsibility")
    effective_allowed = (
        allowed_amt
        if allowed_amt is not None
        else (Decimal(str(claim.allowed_amount)) if claim.allowed_amount is not None else None)
    )
    if patient_resp is not None:
        if patient_resp < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Patient responsibility cannot be negative",
            )
        if claim.billed_amount is not None and patient_resp > billed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Patient responsibility cannot exceed billed amount",
            )
        if effective_allowed is not None and patient_resp > effective_allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Patient responsibility cannot exceed allowed amount",
            )
    elif allowed_amt is not None and claim.patient_responsibility is not None:
        if Decimal(str(claim.patient_responsibility)) > allowed_amt:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Allowed amount cannot be less than existing patient responsibility",
            )

    for field, value in update_data.items():
        setattr(claim, field, value)

    # HIPAA: Audit log claim update before committing
    await log_audit_event(
        db, current_user, "update_insurance_claim", "insurance_claim", claim.id, request, update_data
    )

    await db.commit()
    await db.refresh(claim)

    return claim


@router.post("/claims/{claim_id}/submit")
async def submit_claim(
    claim_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> InsuranceClaimResponse:
    """Submit an existing draft claim through DentalXChange.

    The claim is marked submitted only after the clearinghouse returns a
    non-empty external claim ID. Provider and network failures leave the claim
    unchanged so the UI cannot report a false submission.
    """
    if not settings.DXC_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Claims submission service not configured",
        )

    result = await db.execute(
        select(InsuranceClaim).where(
            InsuranceClaim.id == claim_id,
            InsuranceClaim.practice_id == current_user.practice_id,
        )
    )
    claim = result.scalar_one_or_none()
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Claim not found",
        )

    patient_result = await db.execute(
        select(Patient).where(
            Patient.id == claim.patient_id,
            Patient.practice_id == current_user.practice_id,
        )
    )
    patient = patient_result.scalar_one_or_none()
    # L-11 FIX: route linked rows through the tenant validators instead of
    # bare id lookups — the policy must belong to this practice's patient
    # (H-02) and the carrier must be global-or-mine (M-10).
    from app.services.tenant_refs import require_carrier, require_patient_insurance

    try:
        patient_insurance = await require_patient_insurance(
            db,
            claim.patient_insurance_id,
            current_user.practice_id,
            patient_id=claim.patient_id,
        )
        carrier = await require_carrier(db, claim.carrier_id, current_user.practice_id)
    except HTTPException:
        patient_insurance = None
        carrier = None

    if not patient or not patient_insurance or not carrier:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Claim is missing required patient or insurance data",
        )
    if not carrier.edi_enabled or not carrier.payer_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Insurance carrier is not configured for electronic claims",
        )

    procedure_codes = claim.procedure_codes or []
    if isinstance(procedure_codes, str):
        procedure_codes = json.loads(procedure_codes)
    procedures = [
        {
            "procedureCode": procedure.get("code"),
            "tooth": procedure.get("tooth"),
            "surface": procedure.get("surface"),
            "fee": float(procedure.get("fee", 0)),
            "dateOfService": claim.service_date.isoformat(),
        }
        for procedure in procedure_codes
    ]
    payload = {
        "claim": {
            "clientClaimId": claim.claim_number,
            "patientFirstName": patient.first_name,
            "patientLastName": patient.last_name,
            "patientDateOfBirth": patient.date_of_birth.isoformat() if patient.date_of_birth else "",
            "subscriberId": patient_insurance.subscriber_id,
            "groupNumber": patient_insurance.group_number or "",
            "payerId": carrier.payer_id,
            "providerNpi": getattr(current_user, "npi", "") or "",
            "procedures": procedures,
            "totalAmount": float(claim.billed_amount),
            "diagnosisCodes": claim.diagnosis_codes or [],
        }
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{settings.DXC_BASE_URL}/claims",
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.DXC_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
    except httpx.RequestError as exc:
        await log_audit_event(
            db,
            current_user,
            "submit_claim_failed",
            "insurance_claim",
            claim.id,
            request,
            {"reason": "provider_unavailable"},
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Claims provider is unavailable",
        ) from exc

    if response.status_code not in (200, 201):
        await log_audit_event(
            db,
            current_user,
            "submit_claim_failed",
            "insurance_claim",
            claim.id,
            request,
            {"reason": "provider_rejected", "status_code": response.status_code},
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Claims provider rejected the submission",
        )

    try:
        provider_data = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Claims provider returned an invalid response",
        ) from exc

    external_claim_id = provider_data.get("claimId")
    if not external_claim_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Claims provider did not confirm submission",
        )

    claim.status = ClaimStatus.SUBMITTED
    claim.submission_date = datetime.now(timezone.utc).date()
    claim.edi_transaction_id = str(external_claim_id)
    claim.confirmation_number = str(
        provider_data.get("confirmationNumber") or external_claim_id
    )

    await log_audit_event(
        db, current_user, "submit_insurance_claim", "insurance_claim", claim.id, request
    )
    await db.commit()
    await db.refresh(claim)
    return claim


# Pre-Authorization Endpoints

# New Endpoints for Eligibility
@router.get("/eligibility/", response_model=EligibilityListResponse)
async def list_eligibility(
    patient_id: Optional[str] = Query(None, description="Filter by patient"),
    limit: int = Query(50, ge=1, le=200, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
) -> EligibilityListResponse:
    """List paginated eligibility records for the current practice."""
    # Tenant filter stays in SQL; apply the identical filters to the total and
    # page queries so metadata cannot leak or overcount another practice.
    filters = [Patient.practice_id == current_user.practice_id]
    if patient_id:
        filters.append(Eligibility.patient_id == patient_id)

    total = (
        await db.execute(
            select(func.count(Eligibility.id))
            .join(Patient, Eligibility.patient_id == Patient.id)
            .where(*filters)
        )
    ).scalar_one()
    query = (
        select(Eligibility)
        .join(Patient, Eligibility.patient_id == Patient.id)
        .where(*filters)
        .order_by(Eligibility.verified_at.desc(), Eligibility.id.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(query)
    eligibilities = result.scalars().all()

    # HIPAA: Log eligibility access
    await log_audit_event(
        db, current_user, "list_eligibility", "eligibility", None, request
    )
    await db.commit()

    page_count = len(eligibilities)
    return EligibilityListResponse(
        eligibilities=eligibilities,
        count=page_count,
        total=total,
        limit=limit,
        offset=offset,
        next_offset=offset + page_count if offset + page_count < total else None,
    )

# New Endpoints for Explanation of Benefits (EOB)
@router.get("/eobs/", response_model=ExplanationOfBenefitsListResponse)
async def list_eobs(
    claim_id: Optional[str] = Query(None, description="Filter by claim"),
    limit: int = Query(50, ge=1, le=200, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
) -> ExplanationOfBenefitsListResponse:
    """List paginated Explanation of Benefits for the current practice."""
    filters = [InsuranceClaim.practice_id == current_user.practice_id]
    if claim_id:
        filters.append(ExplanationOfBenefits.claim_id == claim_id)

    total = (
        await db.execute(
            select(func.count(ExplanationOfBenefits.id))
            .join(
                InsuranceClaim,
                ExplanationOfBenefits.claim_id == InsuranceClaim.id,
            )
            .where(*filters)
        )
    ).scalar_one()
    query = (
        select(ExplanationOfBenefits)
        .join(
            InsuranceClaim,
            ExplanationOfBenefits.claim_id == InsuranceClaim.id,
        )
        .where(*filters)
        .order_by(ExplanationOfBenefits.generated_at.desc(), ExplanationOfBenefits.id.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(query)
    eobs = result.scalars().all()

    # HIPAA: Log EOB access
    await log_audit_event(
        db, current_user, "list_eobs", "eob", None, request
    )
    await db.commit()

    page_count = len(eobs)
    return ExplanationOfBenefitsListResponse(
        eobs=eobs,
        count=page_count,
        total=total,
        limit=limit,
        offset=offset,
        next_offset=offset + page_count if offset + page_count < total else None,
    )

@router.get("/pre-auth/", response_model=PreAuthorizationListResponse)
async def list_pre_authorizations(
    patient_id: Optional[str] = Query(None, description="Filter by patient"),
    status: Optional[PreAuthorizationStatus] = Query(
        None, description="Filter by status"
    ),
    limit: int = Query(50, ge=1, le=200, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
) -> PreAuthorizationListResponse:
    """List paginated pre-authorizations for the current practice."""
    filters = [Patient.practice_id == current_user.practice_id]
    if patient_id:
        filters.append(InsurancePreAuthorization.patient_id == patient_id)
    if status:
        filters.append(InsurancePreAuthorization.status == status)

    total = (
        await db.execute(
            select(func.count(InsurancePreAuthorization.id))
            .join(
                Patient,
                InsurancePreAuthorization.patient_id == Patient.id,
            )
            .where(*filters)
        )
    ).scalar_one()
    query = (
        select(InsurancePreAuthorization)
        .join(
            Patient,
            InsurancePreAuthorization.patient_id == Patient.id,
        )
        .where(*filters)
        .order_by(
            InsurancePreAuthorization.request_date.desc(),
            InsurancePreAuthorization.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(query)
    pre_auths = result.scalars().all()

    # HIPAA: Log pre-auth access
    await log_audit_event(
        db, current_user, "list_pre_authorizations", "pre_authorization", None, request
    )
    await db.commit()

    page_count = len(pre_auths)
    return PreAuthorizationListResponse(
        pre_authorizations=pre_auths,
        count=page_count,
        total=total,
        limit=limit,
        offset=offset,
        next_offset=offset + page_count if offset + page_count < total else None,
    )


@router.post("/pre-auth/", response_model=PreAuthorizationResponse)
async def create_pre_authorization(
    pre_auth_data: PreAuthorizationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> PreAuthorizationResponse:
    """
    Create pre-authorization request
    """
    # Ownership: the policy must belong to a patient in this practice.
    # patient_id is derived from the policy, not the request.
    patient_insurance = await require_patient_insurance(
        db, pre_auth_data.patient_insurance_id, current_user.practice_id
    )
    # Generate a collision-resistant authorization number. The stored number is
    # a server identifier, not a user-supplied payer authorization value.
    today = datetime.now(timezone.utc)
    auth_number = f"PA-{today.strftime('%Y%m%d')}-{uuid4().hex[:8].upper()}"

    # The legacy model stores procedure codes as JSON text; normalize at the
    # API boundary without changing the database representation.
    procedure_codes_json = json.dumps(
        [pc.model_dump(mode="json") for pc in pre_auth_data.procedure_codes]
    )

    pre_auth = InsurancePreAuthorization(
        patient_id=patient_insurance.patient_id,
        patient_insurance_id=pre_auth_data.patient_insurance_id,
        authorization_number=auth_number,
        request_date=pre_auth_data.request_date,
        procedure_codes=procedure_codes_json,
        estimated_cost=pre_auth_data.estimated_cost,
        notes=pre_auth_data.notes,
    )

    db.add(pre_auth)
    await db.commit()
    await db.refresh(pre_auth)

    return pre_auth


# Fee Schedule Endpoints

@router.get("/fee-schedules/", response_model=FeeScheduleListResponse)
async def list_fee_schedules(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
) -> FeeScheduleListResponse:
    """
    List fee schedules for the practice
    """
    query = select(FeeSchedule).where(FeeSchedule.practice_id == current_user.practice_id)
    if is_active is not None:
        query = query.where(FeeSchedule.is_active == is_active)

    result = await db.execute(query)
    fee_schedules = result.scalars().all()

    # HIPAA Audit log mapping
    await log_audit_event(
        db, current_user, "list_fee_schedules", "fee_schedule", None, request
    )
    await db.commit()

    return FeeScheduleListResponse(
        fee_schedules=fee_schedules,
        count=len(fee_schedules)
    )

@router.post("/fee-schedules/", response_model=FeeScheduleResponse)
async def create_fee_schedule(
    schedule_data: FeeScheduleCreate,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> FeeScheduleResponse:
    """
    Create a new fee schedule
    """
    new_schedule = FeeSchedule(
        practice_id=current_user.practice_id,
        name=schedule_data.name,
        description=schedule_data.description,
        is_active=schedule_data.is_active,
    )
    db.add(new_schedule)
    await db.flush()

    if schedule_data.entries:
        for entry_data in schedule_data.entries:
            entry = FeeScheduleEntry(
                fee_schedule_id=new_schedule.id,
                **entry_data.dict()
            )
            db.add(entry)

    await db.commit()
    await db.refresh(new_schedule)
    return new_schedule


@router.put("/pre-auth/{pre_auth_id}", response_model=PreAuthorizationResponse)
async def update_pre_authorization(
    pre_auth_id: UUID,
    pre_auth_data: PreAuthorizationUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> PreAuthorizationResponse:
    """Update a pre-authorization owned by the current practice."""
    pre_auth = await require_pre_authorization(
        db, pre_auth_id, current_user.practice_id
    )

    update_data = pre_auth_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(pre_auth, field, value)

    await db.commit()
    await db.refresh(pre_auth)

    return pre_auth