"""
Enterprise & Multi-Practice Endpoints
Consolidated analytics and management for practice groups
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import require_role, verify_csrf
from app.core.business_time import (
    DateRangeError,
    get_practice_timezone,
    resolve_instant_range,
)
from app.core.database import get_db
from app.core.search_index import hmac_index
from app.core.security import create_access_token
from app.models.appointment import Appointment, AppointmentStatus, Chair
from app.models.billing import Invoice, InvoiceStatus, Payment, PaymentStatus
from app.models.patient import Patient, PatientStatus
from app.models.practice import Practice, PracticeGroup
from app.models.user import User, UserRole

class PracticeAnalytics(BaseModel):
    practice_id: str
    practice_name: str
    production: float
    collections: float
    new_patients: int
    utilization: float

class Period(BaseModel):
    start: datetime
    end: datetime

class ConsolidatedMetrics(BaseModel):
    production: float
    collections: float
    new_patients: int
    avg_utilization: float

class GroupAnalyticsResponse(BaseModel):
    group_id: str
    period: Period
    consolidated: ConsolidatedMetrics
    by_location: List[PracticeAnalytics]

class GroupPracticeResponse(BaseModel):
    """Public shape of a practice in a group listing.

    NOTE: response_model must be a Pydantic model — using the SQLAlchemy
    ``Practice`` model raised FastAPIError at import time.
    """
    id: str
    name: str
    address_city: Optional[str] = None
    address_state: Optional[str] = None

router = APIRouter()

_DEFAULT_ANALYTICS_RANGE_DAYS = 30
_DEFAULT_PAGE_SIZE = 50
_MAX_PAGE_SIZE = 100

# M-2 FIX: the billable-invoice statuses used by reports.py ("M12 FIX:
# revenue counts only billable invoices"). DRAFT and CANCELLED totals must
# not count toward group production, matching the practice dashboard.
_BILLABLE_INVOICE_STATUSES = (
    InvoiceStatus.PENDING,
    InvoiceStatus.PARTIALLY_PAID,
    InvoiceStatus.PAID,
    InvoiceStatus.OVERDUE,
)


@router.get("/group/analytics", response_model=GroupAnalyticsResponse)
async def get_group_analytics(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    current_user: User = Depends(require_role(UserRole.GROUP_OWNER, UserRole.GROUP_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> GroupAnalyticsResponse:
    """Get consolidated analytics for every practice in the caller's group."""
    # Group membership is derived only from the authenticated caller's practice.
    result = await db.execute(
        select(Practice).where(Practice.id == current_user.practice_id)
    )
    user_practice = result.scalar_one_or_none()

    if not user_practice or not user_practice.group_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with an enterprise practice group",
        )

    tz = await get_practice_timezone(db, current_user.practice_id)
    try:
        window = resolve_instant_range(
            tz,
            start_date,
            end_date,
            default_days=_DEFAULT_ANALYTICS_RANGE_DAYS,
            max_days=366,
        )
    except DateRangeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    group_id = user_practice.group_id
    result = await db.execute(
        select(Practice).where(Practice.group_id == group_id)
    )
    practices = result.scalars().all()

    analytics = []
    for practice in practices:
        # Production (Total Invoiced). M-2 FIX: count only billable invoices —
        # DRAFT and CANCELLED totals used to inflate group production while
        # every other money surface (reports.py "M12 FIX", billing summary)
        # excludes them. Group analytics must not disagree with the practice
        # dashboard for the same period.
        prod_result = await db.execute(
            select(func.sum(Invoice.total)).where(
                and_(
                    Invoice.practice_id == practice.id,
                    Invoice.status.in_(_BILLABLE_INVOICE_STATUSES),
                    Invoice.created_at >= window.start_utc,
                    Invoice.created_at < window.end_utc,
                )
            )
        )
        total_production = prod_result.scalar() or 0

        # Collections (Total Paid). amount_paid is a Python @property, not a
        # column — aggregate completed/refunded Payment rows instead.
        # M-2 FIX: net-of-refunds over (COMPLETED, REFUNDED), exactly like
        # reports.py and billing.py. The previous COMPLETED-only raw sum (a)
        # ignored refunds, overstating collections after any refund, and
        # (b) double-counted REFUNDED rows' residual value differently from
        # every other surface. Refunded amounts subtract; a fully refunded
        # payment contributes zero.
        coll_result = await db.execute(
            select(
                func.sum(
                    Payment.amount - func.coalesce(Payment.refunded_amount, 0)
                )
            )
            .join(Invoice, Payment.invoice_id == Invoice.id)
            .where(
                and_(
                    Invoice.practice_id == practice.id,
                    Payment.status.in_(
                        (
                            PaymentStatus.COMPLETED,
                            PaymentStatus.REFUNDED,
                            PaymentStatus.PARTIALLY_REFUNDED,
                        )
                    ),
                    Payment.created_at >= window.start_utc,
                    Payment.created_at < window.end_utc,
                )
            )
        )
        total_collections = coll_result.scalar() or 0

        # New Patients
        pat_result = await db.execute(
            select(func.count(Patient.id)).where(
                and_(
                    Patient.practice_id == practice.id,
                    Patient.created_at >= window.start_utc,
                    Patient.created_at < window.end_utc,
                )
            )
        )
        new_patients = pat_result.scalar() or 0

        # Appointment Utilization: completed appointments over all appointments.
        app_result = await db.execute(
            select(
                func.count(Appointment.id),
                func.count(Appointment.id).filter(Appointment.status == AppointmentStatus.COMPLETED),
            ).where(
                and_(
                    Appointment.practice_id == practice.id,
                    Appointment.start_time >= window.start_utc,
                    Appointment.start_time < window.end_utc,
                )
            )
        )
        total_apps, completed_apps = app_result.one()
        util_rate = (completed_apps / total_apps * 100) if total_apps > 0 else 0

        analytics.append(
            {
                "practice_id": str(practice.id),
                "practice_name": practice.name,
                "production": float(total_production),
                "collections": float(total_collections),
                "new_patients": new_patients,
                "utilization": round(util_rate, 2),
            }
        )

    return {
        "group_id": str(group_id),
        "period": {
            "start": window.start_utc,
            "end": window.end_utc,
        },
        "consolidated": {
            "production": sum(a["production"] for a in analytics),
            "collections": sum(a["collections"] for a in analytics),
            "new_patients": sum(a["new_patients"] for a in analytics),
            "avg_utilization": (
                sum(a["utilization"] for a in analytics) / len(analytics)
                if analytics
                else 0
            ),
        },
        "by_location": analytics,
    }


@router.get("/group/practices", response_model=List[GroupPracticeResponse])
async def list_group_practices(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(
        _DEFAULT_PAGE_SIZE,
        ge=1,
        le=_MAX_PAGE_SIZE,
        description="Page size (max 100)",
    ),
    response: Response = None,
    current_user: User = Depends(require_role(UserRole.GROUP_OWNER, UserRole.GROUP_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> List[GroupPracticeResponse]:
    """List group locations with pagination metadata in response headers.

    The legacy response is a bare array, so total/page metadata is exposed as
    additive ``X-Total-Count``, ``X-Page``, and ``X-Page-Size`` headers rather
    than replacing the JSON response shape.
    """
    result = await db.execute(
        select(Practice).where(Practice.id == current_user.practice_id)
    )
    user_practice = result.scalar_one_or_none()

    if not user_practice or not user_practice.group_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Enterprise access required",
        )

    filters = [Practice.group_id == user_practice.group_id]
    total = (
        await db.execute(select(func.count(Practice.id)).where(*filters))
    ).scalar_one()
    result = await db.execute(
        select(Practice)
        .where(*filters)
        .order_by(Practice.name, Practice.id)
        .limit(limit)
        .offset((page - 1) * limit)
    )
    practices = result.scalars().all()

    if response is not None:
        response.headers["X-Total-Count"] = str(total)
        response.headers["X-Page"] = str(page)
        response.headers["X-Page-Size"] = str(limit)

    return [
        GroupPracticeResponse(
            id=str(practice.id),
            name=practice.name,
            address_city=practice.address_city,
            address_state=practice.address_state,
        )
        for practice in practices
    ]


# ── Pillar 4: DSO Multi-Location Endpoints ───────────────────────────────

class SwitchContextRequest(BaseModel):
    target_practice_id: UUID


@router.get("/dso/overview")
async def get_dso_overview(
    current_user: User = Depends(require_role(UserRole.GROUP_OWNER, UserRole.GROUP_ADMIN, UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Consolidated roll-up reporting for Dental Service Organizations (DSO).
    Aggregates financial KPIs, 0-30/31-60/61-90/90+ AR aging, provider productivity,
    and cross-clinic location metrics.
    """
    user_practice = (
        await db.execute(select(Practice).where(Practice.id == current_user.practice_id))
    ).scalar_one_or_none()

    if not user_practice or not user_practice.group_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Enterprise DSO access required. Clinic is not linked to a practice group.",
        )

    group_id = user_practice.group_id
    practices = (
        await db.execute(select(Practice).where(Practice.group_id == group_id))
    ).scalars().all()

    if not practices:
        return {
            "group_id": str(group_id),
            "total_clinics": 0,
            "financials": {"total_production": 0.0, "total_collections": 0.0, "total_outstanding_ar": 0.0, "collection_rate": 100.0},
            "ar_aging": {"current_30": 0.0, "days_31_60": 0.0, "days_61_90": 0.0, "over_90": 0.0},
            "locations": [],
            "provider_leaderboard": [],
        }

    practice_ids = [p.id for p in practices]
    practice_map = {p.id: p for p in practices}

    # 1. Consolidated Invoiced Production (billable invoices)
    prod_stmt = select(
        Invoice.practice_id,
        func.sum(Invoice.total).label("total_prod"),
    ).where(
        Invoice.practice_id.in_(practice_ids),
        Invoice.status.in_(_BILLABLE_INVOICE_STATUSES),
    ).group_by(Invoice.practice_id)
    prod_res = (await db.execute(prod_stmt)).all()
    clinic_production = {row[0]: Decimal(str(row[1] or 0)) for row in prod_res}

    # 2. Consolidated Collections (net of refunds)
    coll_stmt = select(
        Invoice.practice_id,
        func.sum(Payment.amount - func.coalesce(Payment.refunded_amount, 0)).label("net_coll"),
    ).join(
        Invoice, Payment.invoice_id == Invoice.id
    ).where(
        Invoice.practice_id.in_(practice_ids),
        Payment.status.in_([PaymentStatus.COMPLETED, PaymentStatus.REFUNDED, PaymentStatus.PARTIALLY_REFUNDED]),
    ).group_by(Invoice.practice_id)
    coll_res = (await db.execute(coll_stmt)).all()
    clinic_collections = {row[0]: Decimal(str(row[1] or 0)) for row in coll_res}

    # 3. Open AR and AR Aging calculation
    open_inv_stmt = (
        select(Invoice)
        .options(selectinload(Invoice.payments))
        .where(
            Invoice.practice_id.in_(practice_ids),
            Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE]),
        )
    )
    open_invoices = (await db.execute(open_inv_stmt)).scalars().all()

    today = datetime.now(timezone.utc).date()
    ar_0_30 = Decimal("0.00")
    ar_31_60 = Decimal("0.00")
    ar_61_90 = Decimal("0.00")
    ar_over_90 = Decimal("0.00")
    clinic_open_ar: Dict[UUID, Decimal] = {p.id: Decimal("0.00") for p in practices}

    for inv in open_invoices:
        bal = inv.balance_due
        if bal <= Decimal("0.00"):
            continue
        inv_pid = UUID(str(inv.practice_id))
        clinic_open_ar[inv_pid] = clinic_open_ar.get(inv_pid, Decimal("0.00")) + bal
        inv_date = inv.due_date or (inv.created_at.date() if inv.created_at else today)
        age_days = (today - inv_date).days
        if age_days <= 30:
            ar_0_30 += bal
        elif age_days <= 60:
            ar_31_60 += bal
        elif age_days <= 90:
            ar_61_90 += bal
        else:
            ar_over_90 += bal

    # 4. Active Patients count per clinic
    patient_counts_stmt = select(
        Patient.practice_id,
        func.count(Patient.id),
    ).where(
        Patient.practice_id.in_(practice_ids),
        Patient.status != PatientStatus.INACTIVE,
    ).group_by(Patient.practice_id)
    patient_counts_res = (await db.execute(patient_counts_stmt)).all()
    clinic_patients = {row[0]: row[1] for row in patient_counts_res}

    # 5. Clinical Staff count per clinic (DENTIST, HYGIENIST)
    staff_counts_stmt = select(
        User.practice_id,
        func.count(User.id),
    ).where(
        User.practice_id.in_(practice_ids),
        User.is_active == True,
        User.role.in_([UserRole.DENTIST, UserRole.HYGIENIST]),
    ).group_by(User.practice_id)
    staff_counts_res = (await db.execute(staff_counts_stmt)).all()
    clinic_providers = {row[0]: row[1] for row in staff_counts_res}

    # 6. Provider Productivity Leaderboard
    prod_leaders_stmt = select(
        User.id,
        User.first_name,
        User.last_name,
        User.role,
        User.practice_id,
        func.count(Appointment.id).label("completed_appts"),
    ).join(
        Appointment, Appointment.provider_id == User.id
    ).where(
        User.practice_id.in_(practice_ids),
        Appointment.status == AppointmentStatus.COMPLETED,
    ).group_by(
        User.id, User.first_name, User.last_name, User.role, User.practice_id
    ).order_by(func.count(Appointment.id).desc()).limit(15)
    prod_leaders = (await db.execute(prod_leaders_stmt)).all()

    leaderboard = []
    for row in prod_leaders:
        uid, fn, ln, role, pid, appt_count = row
        leaderboard.append({
            "provider_id": str(uid),
            "provider_name": f"Dr. {fn} {ln}" if role == UserRole.DENTIST else f"{fn} {ln}",
            "role": role.value if hasattr(role, "value") else str(role),
            "clinic_name": practice_map[pid].name if pid in practice_map else "Unknown",
            "completed_appointments": appt_count,
        })

    # 5b. Chair capacity per clinic
    chair_counts_stmt = select(
        Chair.practice_id,
        func.count(Chair.id),
    ).where(
        Chair.practice_id.in_(practice_ids),
        Chair.is_active == True,
    ).group_by(Chair.practice_id)
    chair_counts_res = (await db.execute(chair_counts_stmt)).all()
    clinic_chairs = {row[0]: row[1] for row in chair_counts_res}

    # Location comparison
    locations = []
    total_prod = sum(clinic_production.values(), Decimal("0.00"))
    total_coll = sum(clinic_collections.values(), Decimal("0.00"))
    total_ar = sum(clinic_open_ar.values(), Decimal("0.00"))

    for p in practices:
        locations.append({
            "practice_id": str(p.id),
            "practice_name": p.name,
            "city": p.address_city or p.city,
            "state": p.address_state or p.state,
            "chair_capacity": max(clinic_chairs.get(p.id, 1), 1),
            "active_providers": clinic_providers.get(p.id, 0),
            "active_patients": clinic_patients.get(p.id, 0),
            "production": float(clinic_production.get(p.id, Decimal("0.00"))),
            "collections": float(clinic_collections.get(p.id, Decimal("0.00"))),
            "outstanding_ar": float(clinic_open_ar.get(p.id, Decimal("0.00"))),
        })

    collection_rate = (float(total_coll) / float(total_prod) * 100) if total_prod > 0 else 100.0

    return {
        "group_id": str(group_id),
        "total_clinics": len(practices),
        "financials": {
            "total_production": float(total_prod),
            "total_collections": float(total_coll),
            "total_outstanding_ar": float(total_ar),
            "collection_rate": round(collection_rate, 2),
        },
        "ar_aging": {
            "current_30": float(ar_0_30),
            "days_31_60": float(ar_31_60),
            "days_61_90": float(ar_61_90),
            "over_90": float(ar_over_90),
        },
        "locations": locations,
        "provider_leaderboard": leaderboard,
    }


@router.get("/dso/clinics")
async def get_dso_clinics(
    current_user: User = Depends(require_role(UserRole.GROUP_OWNER, UserRole.GROUP_ADMIN, UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List clinics in the caller's enterprise group with chair capacity and provider details."""
    user_practice = (
        await db.execute(select(Practice).where(Practice.id == current_user.practice_id))
    ).scalar_one_or_none()

    if not user_practice or not user_practice.group_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Enterprise DSO access required",
        )

    practices = (
        await db.execute(
            select(Practice)
            .where(Practice.group_id == user_practice.group_id)
            .order_by(Practice.name)
        )
    ).scalars().all()

    practice_ids = [p.id for p in practices]
    chair_counts_stmt = select(
        Chair.practice_id,
        func.count(Chair.id),
    ).where(
        Chair.practice_id.in_(practice_ids),
        Chair.is_active == True,
    ).group_by(Chair.practice_id)
    chair_counts_res = (await db.execute(chair_counts_stmt)).all()
    clinic_chairs = {row[0]: row[1] for row in chair_counts_res}

    clinics = []
    for p in practices:
        clinics.append({
            "id": str(p.id),
            "name": p.name,
            "slug": p.public_slug,
            "phone": p.phone,
            "email": p.email,
            "city": p.address_city or p.city,
            "state": p.address_state or p.state,
            "timezone": p.timezone,
            "chair_capacity": max(clinic_chairs.get(p.id, 1), 1),
            "is_active": p.is_active,
        })
    return clinics


@router.post("/dso/switch-context")
async def switch_dso_context(
    payload: SwitchContextRequest,
    current_user: User = Depends(require_role(UserRole.GROUP_OWNER, UserRole.GROUP_ADMIN, UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> Dict[str, Any]:
    """
    Switch active clinic context for a group owner or administrator.
    Validates group membership and issues an updated JWT token scoped to the target practice.
    """
    user_practice = (
        await db.execute(select(Practice).where(Practice.id == current_user.practice_id))
    ).scalar_one_or_none()

    if not user_practice or not user_practice.group_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Enterprise DSO access required",
        )

    target_practice = (
        await db.execute(
            select(Practice).where(
                Practice.id == payload.target_practice_id,
                Practice.group_id == user_practice.group_id,
            )
        )
    ).scalar_one_or_none()

    if not target_practice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target clinic not found in your enterprise group",
        )

    token_data = {
        "sub": str(current_user.id),
        "role": current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role),
        "practice_id": str(target_practice.id),
    }
    new_token = create_access_token(token_data)

    return {
        "success": True,
        "access_token": new_token,
        "active_practice_id": str(target_practice.id),
        "active_practice_name": target_practice.name,
        "active_practice_slug": target_practice.public_slug,
        "message": f"Switched active clinic context to {target_practice.name}",
    }


@router.get("/dso/patients/search")
async def search_dso_patients(
    q: str = Query(..., min_length=2, description="Search query: name, phone, email"),
    limit: int = Query(25, ge=1, le=100),
    current_user: User = Depends(require_role(UserRole.GROUP_OWNER, UserRole.GROUP_ADMIN, UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """
    Cross-location patient search across all clinics within the enterprise group.
    """
    user_practice = (
        await db.execute(select(Practice).where(Practice.id == current_user.practice_id))
    ).scalar_one_or_none()

    if not user_practice or not user_practice.group_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Enterprise DSO access required",
        )

    group_practice_ids = (
        await db.execute(
            select(Practice.id).where(Practice.group_id == user_practice.group_id)
        )
    ).scalars().all()

    clean_q = q.strip()
    h_idx = hmac_index(clean_q)

    clauses = [
        Patient.first_name.ilike(f"%{clean_q}%"),
        Patient.last_name.ilike(f"%{clean_q}%"),
    ]
    if h_idx:
        clauses.extend([
            Patient.search_index_email == h_idx,
            Patient.search_index_phone == h_idx,
            Patient.search_index_last_name == h_idx,
        ])

    stmt = (
        select(Patient, Practice)
        .join(Practice, Patient.practice_id == Practice.id)
        .where(
            Patient.practice_id.in_(group_practice_ids),
            Patient.status != PatientStatus.INACTIVE,
            or_(*clauses),
        )
    )

    stmt = stmt.limit(limit)
    rows = (await db.execute(stmt)).all()

    results = []
    for patient, practice in rows:
        results.append({
            "id": str(patient.id),
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "date_of_birth": patient.date_of_birth.isoformat() if patient.date_of_birth else None,
            "email": patient.email,
            "phone": patient.phone,
            "practice_id": str(practice.id),
            "practice_name": practice.name,
            "practice_city": practice.address_city or practice.city,
        })
    return results

