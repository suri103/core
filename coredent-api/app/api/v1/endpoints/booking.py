"""
Online Booking Endpoints
Public and admin endpoints for online booking
Thin HTTP handlers that delegate to booking services
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import case, select, and_, or_, update, func
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from datetime import datetime, date, time, timedelta, timezone
from typing import Optional
import hmac as _hmac_lib
import uuid
import logging
import hashlib
from html import escape as _html_escape
from urllib.parse import quote

from pydantic import BaseModel, Field

from app.core.database import get_db
from app.api.deps import get_current_user, require_role, verify_csrf
from app.models.user import User, UserRole
from app.core.email import email_service, log_email_failure
from app.core.security import create_access_token, decode_token
from app.core.sms import sms_service
from app.core.limiter import limiter
from app.core.config_simple import settings
from app.core.audit import log_audit_event
from app.core.business_time import (
    DateRangeError,
    MAX_AVAILABILITY_RANGE_DAYS,
    business_date,
    ensure_utc,
    get_practice_timezone,
    local_datetime,
    range_bounds_utc,
    resolve_date_range,
)
from app.core.ip_rate_limit import booking_rate_limiter
from app.models.booking import (
    BookingPage,
    OnlineBooking,
    WaitlistEntry,
    BookingPageStatus,
    BookingStatus,
    WaitlistStatus,
)
from app.models.patient import Patient, PatientStatus
from app.models.practice import Practice
from app.models.appointment import Appointment, AppointmentStatus, AppointmentType, AppointmentTypeEnum
from app.services.tenant_refs import require_appointment_type, require_practice_scoped, require_provider
from app.schemas.appointment import _coerce_appointment_type
from app.schemas.booking import (
    AppointmentTypePublicInfo,
    BookingPageCreate,
    BookingPageUpdate,
    BookingPageResponse,
    BookingPageListResponse,
    BookingPagePublicResponse,
    OnlineBookingCreate,
    OnlineBookingUpdate,
    OnlineBookingResponse,
    OnlineBookingListResponse,
    OnlineBookingPublicResponse,
    WaitlistEntryCreate,
    WaitlistEntryUpdate,
    WaitlistEntryResponse,
    WaitlistEntryListResponse,
    AvailabilityRequest,
    AvailabilityResponse,
    DayAvailability,
    TimeSlot,
    EmailVerificationRequest,
    PhoneVerificationRequest,
    VerificationResponse,
    BookingConfirmationRequest,
    BookingConfirmationResponse,
    BookingAnalytics,
)

# Import services
from app.services.booking_service import BookingService

# CAPTCHA verification for public booking endpoints
from app.core.recaptcha import verify_recaptcha_v3, CaptchaVerificationError

router = APIRouter()
logger = logging.getLogger(__name__)

# H-04: roles that may be requested as the provider on a public booking.
# A public caller must not be able to name an admin or front-desk account as
# the treating provider.
BOOKABLE_PROVIDER_ROLES = (UserRole.DENTIST, UserRole.HYGIENIST, UserRole.OWNER)


class PublicBookingProviderInfo(BaseModel):
    """Minimal, safe provider data exposed on a public booking page."""

    id: uuid.UUID
    name: str


class PublicBookingPageResponse(BookingPagePublicResponse):
    """Additive public booking metadata needed by the browser flow."""

    providers: list[PublicBookingProviderInfo] = Field(default_factory=list)
    captcha_required: bool = False


def _provider_accepted(result: object) -> bool:
    """Whether an outbound provider accepted a message for delivery.

    Provider acceptance is not the same as a delivered/opened receipt, so
    callers must not report it as final delivery.
    """
    return isinstance(result, dict) and (
        bool(result.get("success"))
        or str(result.get("status", "")).lower() in {"sent", "queued", "accepted"}
    )


# H10 FIX (bookings): allowed status transitions. CONFIRMED can no longer be
# flipped back to PENDING, which used to re-arm an already-confirmed booking
# for a second confirmation (duplicate appointments).
_BOOKING_TRANSITIONS = {
    BookingStatus.PENDING: {BookingStatus.CONFIRMED, BookingStatus.DECLINED, BookingStatus.CANCELLED},
    BookingStatus.CONFIRMED: {BookingStatus.COMPLETED, BookingStatus.CANCELLED},
    BookingStatus.DECLINED: set(),
    BookingStatus.CANCELLED: set(),
}

# Public availability accepts a legacy optional duration field, but duration is
# intentionally resolved from the practice's appointment-type configuration.
# These bounds match the historical request contract and reject bad database
# configuration rather than publishing an unsafe slot length.
_DEFAULT_PUBLIC_BOOKING_DURATION_MINUTES = 30
_MIN_PUBLIC_BOOKING_DURATION_MINUTES = 5
_MAX_PUBLIC_BOOKING_DURATION_MINUTES = 480


def _page_allows_id(allowed_ids, selected_id: uuid.UUID) -> bool:
    """Return whether an optional JSON allowlist permits ``selected_id``."""
    return not allowed_ids or str(selected_id) in {str(value) for value in allowed_ids}


async def _resolve_public_booking_selection(
    db: AsyncSession,
    page: BookingPage,
    appointment_type_id: Optional[uuid.UUID],
    provider_id: Optional[uuid.UUID],
) -> tuple[Optional[AppointmentType], int]:
    """Tenant- and page-validate public selections and resolve duration safely."""
    appointment_type = None
    duration_minutes = _DEFAULT_PUBLIC_BOOKING_DURATION_MINUTES

    if appointment_type_id:
        appointment_type = await require_appointment_type(
            db, appointment_type_id, page.practice_id
        )
        if not appointment_type.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Requested appointment type is not active",
            )
        if not _page_allows_id(page.allowed_appointment_types, appointment_type_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Requested appointment type is not offered on this booking page",
            )
        duration_minutes = appointment_type.duration
        if not (
            isinstance(duration_minutes, int)
            and _MIN_PUBLIC_BOOKING_DURATION_MINUTES
            <= duration_minutes
            <= _MAX_PUBLIC_BOOKING_DURATION_MINUTES
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Requested appointment type has an invalid configured duration",
            )

    if provider_id:
        await require_provider(
            db,
            provider_id,
            page.practice_id,
            field="Provider",
            roles=BOOKABLE_PROVIDER_ROLES,
        )
        if not _page_allows_id(page.allowed_providers, provider_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Requested provider is not available on this booking page",
            )

    return appointment_type, duration_minutes


async def _eligible_public_providers(
    db: AsyncSession,
    page: BookingPage,
    selected_provider_id: Optional[uuid.UUID] = None,
) -> list[User]:
    """Return concrete, page-allowed providers in deterministic order."""
    filters = [
        User.practice_id == page.practice_id,
        User.is_active.is_(True),
        User.role.in_(BOOKABLE_PROVIDER_ROLES),
    ]
    if selected_provider_id is not None:
        filters.append(User.id == selected_provider_id)

    providers = (
        await db.execute(
            select(User)
            .where(*filters)
            .order_by(User.last_name, User.first_name, User.id)
        )
    ).scalars().all()
    allowed_ids = {str(value) for value in (page.allowed_providers or [])}
    return [
        provider
        for provider in providers
        if not allowed_ids or str(provider.id) in allowed_ids
    ]


async def _load_provider_busy_ranges(
    db: AsyncSession,
    page: BookingPage,
    providers: list[User],
    practice_tz,
    start_date: date,
    end_date: date,
) -> dict[uuid.UUID, list[tuple[datetime, datetime]]]:
    """Load appointment and accepted-booking reservations by provider."""
    provider_ids = [provider.id for provider in providers]
    busy: dict[uuid.UUID, list[tuple[datetime, datetime]]] = {
        provider_id: [] for provider_id in provider_ids
    }
    if not provider_ids:
        return busy

    window_start, window_end = range_bounds_utc(practice_tz, start_date, end_date)
    appointment_rows = (
        await db.execute(
            select(Appointment.provider_id, Appointment.start_time, Appointment.end_time)
            .where(
                Appointment.practice_id == page.practice_id,
                Appointment.provider_id.in_(provider_ids),
                Appointment.status != AppointmentStatus.CANCELLED,
                Appointment.start_time < window_end,
                Appointment.end_time > window_start,
            )
        )
    ).all()
    for provider_id, start, end in appointment_rows:
        normalized_start = ensure_utc(start)
        normalized_end = ensure_utc(end)
        if provider_id in busy and normalized_start and normalized_end:
            busy[provider_id].append((normalized_start, normalized_end))

    booking_rows = (
        await db.execute(
            select(
                OnlineBooking.provider_id,
                OnlineBooking.requested_date,
                OnlineBooking.requested_time,
                OnlineBooking.duration_minutes,
            ).where(
                OnlineBooking.practice_id == page.practice_id,
                OnlineBooking.provider_id.in_(provider_ids),
                OnlineBooking.requested_date >= start_date,
                OnlineBooking.requested_date <= end_date,
                OnlineBooking.status.in_((BookingStatus.PENDING, BookingStatus.CONFIRMED)),
            )
        )
    ).all()
    for provider_id, requested_date, requested_time, duration_minutes in booking_rows:
        if provider_id not in busy or requested_time is None:
            continue
        try:
            start = _resolve_public_slot_start(
                practice_tz, requested_date, requested_time
            ).astimezone(timezone.utc)
        except DateRangeError:
            continue
        busy[provider_id].append(
            (start, start + timedelta(minutes=duration_minutes or 30))
        )

    return busy


def _provider_is_free(
    busy_ranges: dict[uuid.UUID, list[tuple[datetime, datetime]]],
    provider_id: uuid.UUID,
    slot_start: datetime,
    slot_end: datetime,
) -> bool:
    return not any(
        slot_start < busy_end and slot_end > busy_start
        for busy_start, busy_end in busy_ranges.get(provider_id, [])
    )


def _create_booking_verification_session(booking: OnlineBooking, page: BookingPage) -> str:
    return create_access_token(
        {
            "purpose": "public_booking_verification",
            "booking_id": str(booking.id),
            "page_slug": page.page_slug,
        },
        expires_delta=timedelta(minutes=10),
    )


async def _resolve_booking_verification_session(
    db: AsyncSession, verification_session: str
) -> tuple[Optional[OnlineBooking], Optional[BookingPage]]:
    payload = decode_token(verification_session)
    if not payload or payload.get("purpose") != "public_booking_verification":
        return None, None
    try:
        booking_id = uuid.UUID(str(payload.get("booking_id")))
    except (TypeError, ValueError):
        return None, None

    row = (
        await db.execute(
            select(OnlineBooking, BookingPage)
            .join(BookingPage, BookingPage.id == OnlineBooking.booking_page_id)
            .where(
                OnlineBooking.id == booking_id,
                BookingPage.page_slug == str(payload.get("page_slug") or ""),
            )
        )
    ).first()
    return row if row else (None, None)


def _verification_response(
    booking: Optional[OnlineBooking],
    page: Optional[BookingPage],
    *,
    verified: bool,
    message: str,
) -> VerificationResponse:
    if booking is None or page is None:
        return VerificationResponse(verified=False, message=message)
    return VerificationResponse(
        verified=verified,
        message=message,
        confirmation_code=booking.confirmation_code if verified else None,
        email_verified=bool(booking.email_verified),
        phone_verified=bool(booking.phone_verified),
        require_email_verification=bool(page.require_email_verification),
        require_phone_verification=bool(page.require_phone_verification),
    )


# M-06 FIX: every non-success outcome of the public verify endpoints returns
# this exact message with an otherwise-empty body. Previously a wrong token
# still echoed the booking's verification state (email_verified, require_*
# flags) while an invalid session returned a bare body, so a caller holding a
# verification session could distinguish failure causes and probe booking
# state. Now only the success branch reveals anything; failures are uniform
# regardless of whether the session or the token was wrong.
_VERIFICATION_FAILED_MESSAGE = "Verification could not be completed"


def _is_ambiguous_local_time(practice_tz, day: date, wall_time: time) -> bool:
    """Whether a time-only public input could name two distinct instants."""
    first = local_datetime(practice_tz, day, wall_time, fold=0)
    second = local_datetime(practice_tz, day, wall_time, fold=1)
    return first.astimezone(timezone.utc) != second.astimezone(timezone.utc)


def _resolve_public_slot_start(practice_tz, day: date, wall_time: time) -> datetime:
    """Resolve one unambiguous, existent public wall-clock start instant."""
    start_local = local_datetime(practice_tz, day, wall_time)
    if _is_ambiguous_local_time(practice_tz, day, wall_time):
        raise DateRangeError("requested local time is ambiguous in this timezone")
    return start_local


# Booking Page Endpoints (Admin)

@router.get("/pages/", response_model=BookingPageListResponse)
async def list_booking_pages(
    request: Request,
    status_filter: Optional[BookingPageStatus] = Query(
        None, alias="status", description="Filter by status"
    ),
    limit: int = Query(50, ge=1, le=200, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> BookingPageListResponse:
    """List booking pages for the current practice with bounded pagination."""
    try:
        filters = [BookingPage.practice_id == current_user.practice_id]
        if status_filter:
            filters.append(BookingPage.status == status_filter)

        total = (
            await db.execute(select(func.count(BookingPage.id)).where(*filters))
        ).scalar_one()
        result = await db.execute(
            select(BookingPage)
            .options(selectinload(BookingPage.practice))
            .where(*filters)
            .order_by(BookingPage.created_at.desc(), BookingPage.id.desc())
            .offset(offset)
            .limit(limit)
        )
        pages = result.scalars().all()
        page_count = len(pages)

        return BookingPageListResponse(
            pages=pages,
            count=page_count,
            total=total,
            limit=limit,
            offset=offset,
            next_offset=offset + page_count if offset + page_count < total else None,
        )
    except (ValueError, TypeError, SQLAlchemyError) as exc:
        logger.error("Error listing booking pages: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from exc


@router.post("/pages/", response_model=BookingPageResponse)
async def create_booking_page(
    page_data: BookingPageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> BookingPageResponse:
    """Create a new booking page"""
    try:
        # Page slugs are PUBLIC URL segments, but they are PRACTICE-SCOPED:
        # the public URL carries both segments (/book/{practice_slug}/{page_slug}),
        # so two practices may freely use the same page slug without making
        # public resolution ambiguous. This check gives a clean 409 up front
        # for duplicates WITHIN the practice; the authoritative guard is the
        # composite unique index uq_booking_pages_practice_page_slug, whose
        # violation lands in the IntegrityError handler below and closes the
        # race window.
        result = await db.execute(
            select(BookingPage).where(
                BookingPage.practice_id == current_user.practice_id,
                BookingPage.page_slug == page_data.page_slug,
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Booking page with this slug already exists")

        # Convert business_hours to dict
        business_hours_dict = {}
        if page_data.business_hours:
            for day, hours in page_data.business_hours.items():
                business_hours_dict[day] = hours.model_dump()

        # Convert intake_form_fields to list of dicts
        intake_form_fields_list = [field.model_dump() for field in page_data.intake_form_fields] if page_data.intake_form_fields else []

        page = BookingPage(
            practice_id=current_user.practice_id,
            page_slug=page_data.page_slug,
            page_title=page_data.page_title,
            welcome_message=page_data.welcome_message,
            logo_url=page_data.logo_url,
            primary_color=page_data.primary_color,
            background_image_url=page_data.background_image_url,
            allow_new_patients=page_data.allow_new_patients,
            allow_existing_patients=page_data.allow_existing_patients,
            require_phone_verification=page_data.require_phone_verification,
            require_email_verification=page_data.require_email_verification,
            booking_window_days=page_data.booking_window_days,
            min_notice_hours=page_data.min_notice_hours,
            max_bookings_per_day=page_data.max_bookings_per_day,
            allowed_appointment_types=[str(id) for id in page_data.allowed_appointment_types],
            allowed_providers=[str(id) for id in page_data.allowed_providers],
            business_hours=business_hours_dict,
            blocked_dates=[d.isoformat() for d in page_data.blocked_dates],
            intake_form_fields=intake_form_fields_list,
            require_insurance_info=page_data.require_insurance_info,
            require_medical_history=page_data.require_medical_history,
            send_confirmation_email=page_data.send_confirmation_email,
            send_confirmation_sms=page_data.send_confirmation_sms,
            send_reminder_email=page_data.send_reminder_email,
            send_reminder_sms=page_data.send_reminder_sms,
            reminder_hours_before=page_data.reminder_hours_before,
            status=page_data.status,
            meta_title=page_data.meta_title,
            meta_description=page_data.meta_description,
            meta_keywords=page_data.meta_keywords,
        )

        db.add(page)
        await db.commit()
        # Re-fetch with the practice relationship loaded so the response can
        # carry practice_public_slug without triggering an async lazy load.
        page = (
            await db.execute(
                select(BookingPage)
                .options(selectinload(BookingPage.practice))
                .where(BookingPage.id == page.id)
            )
        ).scalar_one()
        logger.info(f"Created booking page: {page.id}")
        return page
    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error creating booking page: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.get("/pages/{page_id}", response_model=BookingPageResponse)
async def get_booking_page(
    page_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BookingPageResponse:
    """Get booking page by ID"""
    try:
        result = await db.execute(
            select(BookingPage)
            .options(selectinload(BookingPage.practice))
            .where(
                BookingPage.id == page_id,
                BookingPage.practice_id == current_user.practice_id,
            )
        )
        page = result.scalar_one_or_none()

        if not page:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking page not found")

        return page
    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error getting booking page: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.put("/pages/{page_id}", response_model=BookingPageResponse)
async def update_booking_page(
    page_id: uuid.UUID,
    page_data: BookingPageUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> BookingPageResponse:
    """Update booking page"""
    try:
        result = await db.execute(
            select(BookingPage)
            .options(selectinload(BookingPage.practice))
            .where(
                BookingPage.id == page_id,
                BookingPage.practice_id == current_user.practice_id,
            )
        )
        page = result.scalar_one_or_none()

        if not page:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking page not found")

        update_data = page_data.model_dump(exclude_unset=True)

        # JSON columns cannot bind UUID instances. Keep update behavior aligned
        # with page creation so public allowlists remain configurable after a
        # page is created.
        for field in ("allowed_appointment_types", "allowed_providers"):
            if field in update_data and update_data[field] is not None:
                update_data[field] = [str(value) for value in update_data[field]]

        # Convert business_hours if provided
        if 'business_hours' in update_data and update_data['business_hours']:
            business_hours_dict = {}
            for day, hours in update_data['business_hours'].items():
                business_hours_dict[day] = hours.model_dump() if hasattr(hours, 'model_dump') else hours
            update_data['business_hours'] = business_hours_dict

        # Convert intake_form_fields if provided
        if 'intake_form_fields' in update_data and update_data['intake_form_fields']:
            intake_form_fields_list = [field.model_dump() if hasattr(field, 'model_dump') else field for field in update_data['intake_form_fields']]
            update_data['intake_form_fields'] = intake_form_fields_list

        # Convert dates if provided
        if 'blocked_dates' in update_data and update_data['blocked_dates']:
            update_data['blocked_dates'] = [d.isoformat() if hasattr(d, 'isoformat') else d for d in update_data['blocked_dates']]

        for field, value in update_data.items():
            setattr(page, field, value)

        await db.commit()
        # Re-fetch with the practice relationship loaded so the response can
        # carry practice_public_slug without triggering an async lazy load.
        page = (
            await db.execute(
                select(BookingPage)
                .options(selectinload(BookingPage.practice))
                .where(BookingPage.id == page.id)
            )
        ).scalar_one()
        logger.info(f"Updated booking page: {page_id}")
        return page
    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error updating booking page: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


async def _resolve_public_page(
    db: AsyncSession, practice_slug: str, page_slug: str
) -> BookingPage:
    """Resolve a public booking page from its two-segment URL.

    Page slugs are practice-scoped (two practices may use the same page slug
    without ambiguity), so the public URL carries both segments:
    ``/book/{practice_slug}/{page_slug}``. Only ACTIVE pages resolve.
    """
    result = await db.execute(
        select(BookingPage)
        .options(selectinload(BookingPage.practice))
        .join(Practice, BookingPage.practice_id == Practice.id)
        .where(
            Practice.public_slug == practice_slug,
            BookingPage.page_slug == page_slug,
            BookingPage.status == BookingPageStatus.ACTIVE,
        )
    )
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking page not found or inactive",
        )
    return page


# Public Booking Page Endpoint

@router.get("/public/{practice_slug}/{page_slug}", response_model=PublicBookingPageResponse)
@limiter.limit("60/minute")  # Anti-abuse: public GET must not write on every hit
async def get_public_booking_page(
    request: Request,
    practice_slug: str,
    page_slug: str,
    db: AsyncSession = Depends(get_db),
) -> PublicBookingPageResponse:
    """Get public booking page by slug (no authentication required)"""
    try:
        page = await _resolve_public_page(db, practice_slug, page_slug)

        # Increment view count (guarded — a page view is still a write, so keep
        # it cheap and rate-limited above).
        # M22 FIX: atomic increment — the Python read-modify-write lost
        # updates under concurrency and corrupted the analytics derived
        # from these counters.
        await db.execute(
            update(BookingPage)
            .where(BookingPage.id == page.id)
            .values(total_views=BookingPage.total_views + 1)
        )
        await db.commit()

        # Return only public-facing data
        # Query active appointment types for practice
        from app.models.appointment import AppointmentType
        apt_query = select(AppointmentType).where(
            AppointmentType.practice_id == page.practice_id,
            AppointmentType.is_active.is_(True),
        )
        apt_result = await db.execute(apt_query)
        all_apts = apt_result.scalars().all()

        allowed_ids = set(str(id) for id in (page.allowed_appointment_types or []))
        public_apts = [
            AppointmentTypePublicInfo(
                id=apt.id,
                name=apt.name,
                duration_minutes=apt.duration or _DEFAULT_PUBLIC_BOOKING_DURATION_MINUTES,
                description=apt.description,
                color=apt.color,
                icon=getattr(apt, "icon", None) or "🦷",
            )
            for apt in all_apts
            if not allowed_ids or str(apt.id) in allowed_ids
        ]

        allowed_provider_ids = {
            str(provider_id) for provider_id in (page.allowed_providers or [])
        }
        provider_result = await db.execute(
            select(User)
            .where(
                User.practice_id == page.practice_id,
                User.is_active.is_(True),
                User.role.in_(BOOKABLE_PROVIDER_ROLES),
            )
            .order_by(User.last_name, User.first_name, User.id)
        )
        public_providers = [
            PublicBookingProviderInfo(
                id=provider.id,
                name=provider.full_name.strip() or "Provider",
            )
            for provider in provider_result.scalars().all()
            if not allowed_provider_ids or str(provider.id) in allowed_provider_ids
        ]

        practice_tz = await get_practice_timezone(db, page.practice_id)
        return PublicBookingPageResponse(
            practice_public_slug=practice_slug,
            page_slug=page.page_slug,
            page_title=page.page_title,
            welcome_message=page.welcome_message,
            logo_url=page.logo_url,
            primary_color=page.primary_color,
            background_image_url=page.background_image_url,
            allow_new_patients=page.allow_new_patients,
            allow_existing_patients=page.allow_existing_patients,
            require_phone_verification=page.require_phone_verification,
            require_email_verification=page.require_email_verification,
            booking_window_days=page.booking_window_days,
            min_notice_hours=page.min_notice_hours,
            practice_timezone=str(practice_tz),
            business_hours=page.business_hours,
            blocked_dates=page.blocked_dates,
            intake_form_fields=page.intake_form_fields,
            require_insurance_info=page.require_insurance_info,
            require_medical_history=page.require_medical_history,
            allowed_appointment_types=list(allowed_ids),
            appointment_types=public_apts,
            providers=public_providers,
            captcha_required=bool(getattr(settings, "RECAPTCHA_SECRET_KEY", "")),
        )
    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error getting public booking page: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


# Online Booking Endpoints

@router.post("/public/{practice_slug}/{page_slug}/book", response_model=OnlineBookingPublicResponse)
@limiter.limit("2/hour")
async def create_online_booking(
    request: Request,
    practice_slug: str,
    page_slug: str,
    booking_data: OnlineBookingCreate,
    db: AsyncSession = Depends(get_db),
) -> OnlineBookingPublicResponse:
    """Create a new online booking (public endpoint, no authentication)"""
    try:
        # SECURITY FIX #1: Honeypot check (anti-bot)
        if booking_data.honeypot:
            logger.warning(f"Honeypot triggered for booking attempt from {request.client.host if request.client else 'unknown'}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid request"
            )

        # SECURITY FIX #2: IP-based rate limiting (10 bookings per hour per IP)
        await booking_rate_limiter.check_rate_limit(request)

        # SECURITY FIX #3: CAPTCHA verification (reCAPTCHA v3). When the
        # backend is configured with a reCAPTCHA secret, the token is REQUIRED
        # (previously optional, which let bots skip the gate entirely).
        if getattr(settings, "RECAPTCHA_SECRET_KEY", ""):
            if not booking_data.captcha_token:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="CAPTCHA verification is required. Please try again."
                )
            try:
                await verify_recaptcha_v3(
                    token=booking_data.captcha_token,
                    action="booking",
                    min_score=0.5
                )
            except CaptchaVerificationError as e:
                logger.warning(f"CAPTCHA verification failed: {e}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="CAPTCHA verification failed. Please try again."
                )

        page = await _resolve_public_page(db, practice_slug, page_slug)

        # Page-level intake controls are authorization boundaries for this
        # public endpoint, not merely UI hints. Reject direct API submissions
        # that the page configuration does not allow.
        if booking_data.is_new_patient and not page.allow_new_patients:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This booking page is not accepting new patients",
            )
        if not booking_data.is_new_patient and not page.allow_existing_patients:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This booking page is not accepting existing patients",
            )
        if page.require_insurance_info and not (
            booking_data.has_insurance
            and (booking_data.insurance_carrier_name or "").strip()
            and (booking_data.insurance_member_id or "").strip()
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Insurance carrier and member ID are required for this booking page",
            )
        if page.require_medical_history and not booking_data.medical_history:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Medical history is required for this booking page",
            )

        # Resolve the appointment type and provider before accepting a time.
        # In particular, never trust the public duration_minutes request field:
        # a type's configured duration is the source of truth for both the
        # advertised slot and the persisted booking.
        appointment_type, duration_minutes = await _resolve_public_booking_selection(
            db,
            page,
            booking_data.appointment_type_id,
            booking_data.provider_id,
        )

        # Validate an exact practice-local instant. A later calendar day can
        # still name an instant before the minimum-notice cutoff, and a DST
        # spring-forward wall time may not exist at all.
        practice_tz = await get_practice_timezone(db, page.practice_id)
        now_utc = datetime.now(timezone.utc)
        minimum_start_utc = now_utc + timedelta(hours=page.min_notice_hours)
        try:
            requested_start_local = _resolve_public_slot_start(
                practice_tz, booking_data.requested_date, booking_data.requested_time
            )
        except DateRangeError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        requested_start_utc = requested_start_local.astimezone(timezone.utc)
        if requested_start_utc < minimum_start_utc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Requested time must be at least "
                    f"{page.min_notice_hours} hours from now"
                ),
            )

        # The full configured duration must fit one business-hours interval.
        # This keeps direct submissions aligned with advertised availability.
        requested_end_utc = requested_start_utc + timedelta(minutes=duration_minutes)
        requested_end_local = requested_end_utc.astimezone(practice_tz)
        day_name = booking_data.requested_date.strftime("%A").lower()
        day_hours = (page.business_hours or {}).get(day_name)
        day_slots = day_hours.get("slots") if day_hours else None
        if (
            day_hours is None
            or not day_hours.get("enabled", False)
            or not day_slots
            or requested_end_local.date() != booking_data.requested_date
            or requested_start_local.utcoffset() != requested_end_local.utcoffset()
            or _is_ambiguous_local_time(
                practice_tz, requested_end_local.date(), requested_end_local.time()
            )
            or not any(
                slot.get("start")
                and slot.get("end")
                and slot["start"]
                <= booking_data.requested_time.strftime("%H:%M")
                < slot["end"]
                and requested_end_local.strftime("%H:%M") <= slot["end"]
                for slot in day_slots
            )
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Requested time is outside business hours",
            )

        # Validate booking dates in the practice's local calendar. A public
        # date is a wall-calendar date for the practice, never the API host.
        practice_tz = await get_practice_timezone(db, page.practice_id)
        now_utc = datetime.now(timezone.utc)
        min_date = business_date(
            practice_tz, now_utc + timedelta(hours=page.min_notice_hours)
        )
        max_date = business_date(practice_tz, now_utc) + timedelta(
            days=page.booking_window_days
        )

        if booking_data.requested_date < min_date or booking_data.requested_date > max_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Requested date must be between {min_date} and {max_date}",
            )

        # Check if date is blocked
        if booking_data.requested_date.isoformat() in (page.blocked_dates or []):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Requested date is not available")

        # M19 FIX: enforce the rest of the booking page's configuration.
        # Previously only the cooldown, the window and blocked dates were
        # checked — 3 AM requests passed, max_bookings_per_day was dead
        # config, and allowed types/providers were ignored.
        day_name = booking_data.requested_date.strftime("%A").lower()
        day_hours = (page.business_hours or {}).get(day_name)
        if day_hours is None or not day_hours.get("enabled", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Requested date is not a business day",
            )
        if booking_data.requested_time is not None:
            day_slots = day_hours.get("slots") or []
            if day_slots and not any(
                s.get("start") and s.get("end")
                and s["start"] <= booking_data.requested_time.strftime("%H:%M") < s["end"]
                for s in day_slots
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Requested time is outside business hours",
                )
        # Serialize on the contact dimensions (email/phone): the anti-spam
        # cooldown below is keyed on either contact, so two concurrent
        # bookings sharing an email or phone must queue here.
        from app.api.v1.endpoints.appointments import _acquire_booking_lock
        await _acquire_booking_lock(
            db,
            page.practice_id,
            ("contact", booking_data.email),
            ("contact", booking_data.phone),
        )

        # H-1 FIX: Check for duplicate bookings (anti-spam) under lock to avoid TOCTOU races
        # (aware UTC — submitted_at is a UTC server-default; the old local
        # naive `datetime.now()` skewed the 24h window by the server offset)
        cooldown_window = datetime.now(timezone.utc) - timedelta(hours=24)
        duplicate_check = await db.execute(
            select(OnlineBooking).where(
                and_(
                    OnlineBooking.practice_id == page.practice_id,
                    or_(
                        OnlineBooking.email == booking_data.email,
                        OnlineBooking.phone == booking_data.phone
                    ),
                    OnlineBooking.status == BookingStatus.PENDING,
                    OnlineBooking.submitted_at >= cooldown_window
                )
            ).limit(1)
        )
        if duplicate_check.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="A booking request from this email or phone is already pending. Please wait for confirmation or contact the office."
            )

        # Resolve "any provider" to one concrete, currently free provider while
        # holding the same practice-scoped transaction lock used by booking
        # writes. Pending online bookings are reservations for this purpose.
        eligible_providers = await _eligible_public_providers(
            db, page, booking_data.provider_id
        )
        busy_ranges = await _load_provider_busy_ranges(
            db,
            page,
            eligible_providers,
            practice_tz,
            booking_data.requested_date,
            booking_data.requested_date,
        )
        assigned_provider = next(
            (
                provider
                for provider in eligible_providers
                if _provider_is_free(
                    busy_ranges,
                    provider.id,
                    requested_start_utc,
                    requested_end_utc,
                )
            ),
            None,
        )
        if assigned_provider is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This time slot is no longer available. Please choose another time.",
            )

        # C-02 FIX: Acquire slot lock on the assigned provider to eliminate TOCTOU races
        # between distinct prospective patients attempting to reserve the same slot.
        slot_key = f"{assigned_provider.id}:{booking_data.requested_date.isoformat()}:{booking_data.requested_time.strftime('%H:%M')}"
        await _acquire_booking_lock(
            db,
            page.practice_id,
            ("provider_slot", slot_key),
            ("provider", assigned_provider.id),
        )

        # Under the provider lock, re-verify that the slot has not been taken
        # by a concurrent transaction that committed while resolving.
        busy_ranges_locked = await _load_provider_busy_ranges(
            db,
            page,
            [assigned_provider],
            practice_tz,
            booking_data.requested_date,
            booking_data.requested_date,
        )
        if not _provider_is_free(
            busy_ranges_locked,
            assigned_provider.id,
            requested_start_utc,
            requested_end_utc,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This time slot is no longer available. Please choose another time.",
            )

        if page.max_bookings_per_day:
            # Day-cap FIX: count under a day-level lock, not just the assigned
            # provider's slot lock — two providers same day could both pass.
            await _acquire_booking_lock(
                db,
                page.practice_id,
                ("booking_day", f"{booking_data.requested_date.isoformat()}"),
            )
            day_count = await db.execute(
                select(func.count(OnlineBooking.id)).where(
                    OnlineBooking.practice_id == page.practice_id,
                    OnlineBooking.requested_date == booking_data.requested_date,
                    OnlineBooking.status.in_((BookingStatus.PENDING, BookingStatus.CONFIRMED)),
                )
            )
            if (day_count.scalar() or 0) >= page.max_bookings_per_day:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="No more bookings can be accepted for this date",
                )

        # H-04 FIX: validate the referenced provider and appointment type
        # unconditionally, not only when the page happens to publish an
        # allowlist. The old code checked membership in
        # page.allowed_appointment_types / page.allowed_providers, but those
        # lists are optional -- an empty list short-circuited the whole check,
        # so a public, unauthenticated caller could submit any UUID and have it
        # written onto the booking (and later onto the Appointment) even if it
        # belonged to a different practice.
        if booking_data.appointment_type_id:
            await require_appointment_type(
                db, booking_data.appointment_type_id, page.practice_id
            )
            if (
                page.allowed_appointment_types
                and str(booking_data.appointment_type_id) not in page.allowed_appointment_types
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Requested appointment type is not offered on this booking page",
                )

        if booking_data.provider_id:
            await require_provider(
                db,
                booking_data.provider_id,
                page.practice_id,
                field="Provider",
                roles=BOOKABLE_PROVIDER_ROLES,
            )
            if (
                page.allowed_providers
                and str(booking_data.provider_id) not in page.allowed_providers
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Requested provider is not available on this booking page",
                )

        # Create booking using service (exclude security fields). The provider
        # is always the concrete provider selected under the booking lock,
        # never a nullable "any provider" placeholder.
        booking_dict = booking_data.model_dump(exclude={'captcha_token', 'honeypot'})
        booking_dict["provider_id"] = assigned_provider.id

        # Existing-patient requests are associated only on an exact,
        # tenant-scoped identity match. A non-match remains pending for staff
        # review without revealing whether a patient record exists.
        matched_patient_id = None
        if not booking_data.is_new_patient:
            from app.core.search_index import hmac_index as _hmac

            patient_candidates = (
                await db.execute(
                    select(Patient).where(
                        Patient.practice_id == page.practice_id,
                        Patient.status == PatientStatus.ACTIVE,
                        or_(
                            Patient.search_index_email == _hmac(booking_data.email),
                            Patient.search_index_phone == _hmac(booking_data.phone),
                        ),
                    )
                )
            ).scalars().all()
            submitted_digits = "".join(
                character for character in booking_data.phone if character.isdigit()
            )
            for patient in patient_candidates:
                patient_digits = "".join(
                    character for character in (patient.phone or "") if character.isdigit()
                )
                if (
                    patient.date_of_birth == booking_data.date_of_birth
                    and (patient.email or "").strip().lower()
                    == booking_data.email.strip().lower()
                    and patient_digits == submitted_digits
                ):
                    matched_patient_id = patient.id
                    break

        # M-10 FIX: store only the SHA-256 hash of the verification token.
        # The plaintext token is held in the local ``raw_email_token``
        # variable so it can be returned to the caller (the only place that
        # ever needs the plaintext), and is never persisted.
        raw_email_token: Optional[str] = None
        email_token_hash: Optional[str] = None
        if page.require_email_verification:
            raw_email_token = BookingService.generate_verification_token()
            email_token_hash = hashlib.sha256(
                raw_email_token.encode("utf-8")
            ).hexdigest()

        booking = OnlineBooking(
            booking_page_id=page.id,
            practice_id=page.practice_id,
            patient_id=matched_patient_id,
            confirmation_code=BookingService.generate_confirmation_code(),
            email_verification_token=None,
            email_verification_token_hash=email_token_hash,
            phone_verification_code=BookingService.generate_verification_code() if page.require_phone_verification else None,
            email_verified=not page.require_email_verification,
            phone_verified=not page.require_phone_verification,
            duration_minutes=duration_minutes,
            **booking_dict
        )

        db.add(booking)
        # M22 FIX: atomic increment (read-modify-write lost updates).
        # H-3 FIX: also persist ``conversion_rate`` in the same atomic UPDATE
        # so the value is durable. Previously this was computed in Python
        # after ``db.refresh(page)`` and immediately overwritten by the
        # refresh — the read-modify-write of ``conversion_rate`` was therefore
        # lost on every write. Postgres ``CASE`` is used to guard the
        # divide-by-zero (a view count of 0 produces a conversion of 0).
        await db.execute(
            update(BookingPage)
            .where(BookingPage.id == page.id)
            .values(
                total_bookings=BookingPage.total_bookings + 1,
                conversion_rate=case(
                    (
                        BookingPage.total_views > 0,
                        (BookingPage.total_bookings + 1)
                        * 100
                        // BookingPage.total_views,
                    ),
                    else_=0,
                ),
            )
        )
        await db.flush()
        await db.refresh(page)

        await db.commit()
        await db.refresh(booking)
        logger.info(f"Created online booking: {booking.id}")

        verification_session = _create_booking_verification_session(booking, page)
        patient_full_name = f"{booking.first_name} {booking.last_name}".strip()

        # Deliver the actual verification material. The opaque session binds
        # later verification to this booking page and expires after 10 minutes;
        # internal booking UUIDs are never exposed to the public client.
        if page.require_email_verification and raw_email_token:
            verification_link = (
                f"{settings.FRONTEND_URL.rstrip('/')}/book/"
                f"{quote(page.practice.public_slug)}/{quote(page.page_slug)}"
                f"#verification_session={quote(verification_session)}"
                f"&email_token={quote(raw_email_token)}"
            )
            try:
                safe_name = _html_escape(patient_full_name or "Patient")
                safe_link = _html_escape(verification_link, quote=True)
                await email_service.send_email(
                    to=booking.email,
                    subject=f"Verify your booking request for {page.page_title}",
                    html_content=(
                        f"<p>Hello {safe_name},</p>"
                        "<p>Verify your email to continue your booking request.</p>"
                        f'<p><a href="{safe_link}">Verify email</a></p>'
                        "<p>This link expires in 10 minutes.</p>"
                    ),
                    text_content=(
                        f"Hello {patient_full_name or 'Patient'}, verify your email "
                        f"to continue your booking request: {verification_link}\n"
                        "This link expires in 10 minutes."
                    ),
                    idempotency_key=f"booking-email-verification:{booking.id}",
                )
            except Exception as exc:
                log_email_failure(exc, "booking_email_verification", booking.email)
        else:
            try:
                await email_service.send_appointment_confirmation(
                    to=booking.email,
                    patient_name=patient_full_name,
                    appointment_date=booking.requested_date.strftime('%B %d, %Y'),
                    appointment_time=booking.requested_time.strftime('%I:%M %p'),
                    procedure=appointment_type.name if appointment_type else "Dental Appointment",
                )
            except Exception as exc:
                log_email_failure(exc, "booking_request_confirmation", booking.email)

        if page.require_phone_verification:
            try:
                sms_result = await sms_service.send_verification_code(
                    to=booking.phone,
                    code=booking.phone_verification_code or "",
                    practice_name=page.page_title,
                )
                if not sms_result.get("success"):
                    logger.warning(
                        "Booking phone verification was not accepted for %s: %s",
                        booking.id,
                        sms_result.get("error", "unknown provider error"),
                    )
            except Exception as exc:
                logger.warning(
                    "Booking phone verification delivery failed for %s: %s",
                    booking.id,
                    exc,
                )

        return OnlineBookingPublicResponse(
            confirmation_code=booking.confirmation_code,
            status=booking.status,
            first_name=booking.first_name,
            last_name=booking.last_name,
            requested_date=booking.requested_date,
            requested_time=booking.requested_time,
            verification_session=verification_session,
            require_email_verification=page.require_email_verification,
            require_phone_verification=page.require_phone_verification,
            email_verified=bool(booking.email_verified),
            phone_verified=bool(booking.phone_verified),
        )
    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error creating online booking: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.get("/bookings/", response_model=OnlineBookingListResponse)
async def list_online_bookings(
    request: Request,
    status_filter: Optional[BookingStatus] = Query(None, description="Filter by status"),
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    is_new_patient: Optional[bool] = Query(None, description="Filter by new patient"),
    limit: int = Query(50, ge=1, le=200, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN, UserRole.DENTIST)),
    db: AsyncSession = Depends(get_db),
) -> OnlineBookingListResponse:
    """List online bookings for the current practice with safe bounds."""
    try:
        practice_tz = await get_practice_timezone(db, current_user.practice_id)
        date_range = resolve_date_range(practice_tz, start_date, end_date)
        filters = [
            OnlineBooking.practice_id == current_user.practice_id,
            OnlineBooking.requested_date >= date_range.start_date,
            OnlineBooking.requested_date <= date_range.end_date,
        ]
        if status_filter:
            filters.append(OnlineBooking.status == status_filter)
        if is_new_patient is not None:
            filters.append(OnlineBooking.is_new_patient == is_new_patient)

        total = (
            await db.execute(select(func.count(OnlineBooking.id)).where(*filters))
        ).scalar_one()
        result = await db.execute(
            select(OnlineBooking)
            .where(*filters)
            .order_by(OnlineBooking.submitted_at.desc(), OnlineBooking.id.desc())
            .offset(offset)
            .limit(limit)
        )
        bookings = result.scalars().all()

        # HIPAA: Log access
        await log_audit_event(db, current_user, "list_online_bookings", "online_booking", None, request)
        await db.commit()

        page_count = len(bookings)
        return OnlineBookingListResponse(
            bookings=bookings,
            count=page_count,
            total=total,
            limit=limit,
            offset=offset,
            next_offset=offset + page_count if offset + page_count < total else None,
        )
    except DateRangeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except (ValueError, TypeError, SQLAlchemyError) as exc:
        logger.error("Error listing online bookings: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from exc


@router.get("/bookings/{booking_id}", response_model=OnlineBookingResponse)
async def get_online_booking(
    request: Request,
    booking_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN, UserRole.DENTIST)),
    db: AsyncSession = Depends(get_db),
) -> OnlineBookingResponse:
    """Get online booking by ID"""
    try:
        result = await db.execute(
            select(OnlineBooking).where(
                OnlineBooking.id == booking_id,
                OnlineBooking.practice_id == current_user.practice_id,
            )
        )
        booking = result.scalar_one_or_none()

        if not booking:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

        # HIPAA: Log access
        await log_audit_event(db, current_user, "view_online_booking", "online_booking", booking.id, request)
        await db.commit()

        return booking
    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error getting online booking: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.put("/bookings/{booking_id}", response_model=OnlineBookingResponse)
async def update_online_booking(
    request: Request,
    booking_id: uuid.UUID,
    booking_data: OnlineBookingUpdate,
    current_user: User = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN, UserRole.DENTIST)
    ),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> OnlineBookingResponse:
    """Update a booking with staff authorization and tenant-safe links."""
    try:
        result = await db.execute(
            select(OnlineBooking).where(
                OnlineBooking.id == booking_id,
                OnlineBooking.practice_id == current_user.practice_id,
            )
        )
        booking = result.scalar_one_or_none()

        if not booking:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

        update_data = booking_data.model_dump(exclude_unset=True)

        # Staff may resolve an unmatched existing-patient request, but only to
        # an active patient in the same tenant. Associations are immutable
        # once set so this endpoint cannot silently move PHI or appointments
        # between patients.
        if "patient_id" in update_data:
            patient_id = update_data["patient_id"]
            if patient_id is None:
                if booking.patient_id is not None:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="An existing patient association cannot be removed",
                    )
            else:
                if booking.patient_id and booking.patient_id != patient_id:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Booking is already associated with a different patient",
                    )
                patient = (
                    await db.execute(
                        select(Patient).where(
                            Patient.id == patient_id,
                            Patient.practice_id == booking.practice_id,
                            Patient.status == PatientStatus.ACTIVE,
                        )
                    )
                ).scalar_one_or_none()
                if patient is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Active patient not found for this practice",
                    )
                if booking.appointment_id:
                    linked_appointment_patient = (
                        await db.execute(
                            select(Appointment.patient_id).where(
                                Appointment.id == booking.appointment_id,
                                Appointment.practice_id == booking.practice_id,
                            )
                        )
                    ).scalar_one_or_none()
                    if linked_appointment_patient != patient_id:
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="Patient does not match the linked appointment",
                        )
                booking.patient_id = patient_id

        # A generic update may link an existing appointment, but it must not
        # create a cross-practice or cross-patient association, reassign an
        # already-linked booking, or leave a pending booking looking confirmed.
        if "appointment_id" in update_data:
            appointment_id = update_data["appointment_id"]
            if appointment_id is None:
                if booking.appointment_id is not None:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="An existing appointment link cannot be removed through a booking update",
                    )
            else:
                if booking.appointment_id and booking.appointment_id != appointment_id:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Booking is already linked to a different appointment",
                    )

                appointment_result = await db.execute(
                    select(Appointment).where(
                        Appointment.id == appointment_id,
                        Appointment.practice_id == booking.practice_id,
                    )
                )
                appointment = appointment_result.scalar_one_or_none()
                if not appointment:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Appointment not found for this practice",
                    )

                existing_link_result = await db.execute(
                    select(OnlineBooking.id)
                    .where(
                        OnlineBooking.appointment_id == appointment_id,
                        OnlineBooking.id != booking.id,
                    )
                    .limit(1)
                )
                if existing_link_result.scalar_one_or_none():
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Appointment is already linked to another booking",
                    )

                if booking.patient_id and appointment.patient_id != booking.patient_id:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="Appointment belongs to a different patient",
                    )
                if booking.patient_id is None:
                    booking.patient_id = appointment.patient_id

                if booking.status == BookingStatus.PENDING:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "Pending bookings must be confirmed through the "
                            "confirmation endpoint before linking an appointment"
                        ),
                    )
                if booking.status != BookingStatus.CONFIRMED:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Cannot link an appointment to a {booking.status.value} booking",
                    )

        # Handle status changes.
        if "status" in update_data:
            new_status = update_data["status"]
            if new_status is not None and new_status != booking.status:
                if new_status == BookingStatus.CONFIRMED:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "Use the confirmation endpoint to confirm a booking; "
                            "it enforces verification and conflict checks"
                        ),
                    )
                allowed = _BOOKING_TRANSITIONS.get(booking.status, set())
                if new_status not in allowed:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "Cannot change booking status from "
                            f"{booking.status.value} to {new_status.value}"
                        ),
                    )
            if new_status == BookingStatus.CONFIRMED and not booking.confirmed_at:
                booking.confirmed_at = datetime.now(timezone.utc)
            elif new_status == BookingStatus.DECLINED and not booking.declined_at:
                booking.declined_at = datetime.now(timezone.utc)
            elif new_status == BookingStatus.CANCELLED and not booking.cancelled_at:
                booking.cancelled_at = datetime.now(timezone.utc)
                booking.cancelled_by = "staff"

        for field, value in update_data.items():
            setattr(booking, field, value)

        audit_changes: dict[str, object] = {"updated_fields": sorted(update_data)}
        if update_data.get("status") is not None:
            audit_changes["status"] = update_data["status"].value
        if update_data.get("appointment_id") is not None:
            audit_changes["appointment_id"] = str(update_data["appointment_id"])
        if update_data.get("patient_id") is not None:
            audit_changes["patient_id"] = str(update_data["patient_id"])
        await log_audit_event(
            db,
            current_user,
            "update_online_booking",
            "online_booking",
            booking.id,
            request,
            audit_changes,
        )

        await db.commit()
        await db.refresh(booking)
        logger.info("Updated online booking: %s", booking_id)
        return booking
    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error("Error updating online booking: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error") from e


@router.post("/bookings/{booking_id}/confirm", response_model=BookingConfirmationResponse)
async def confirm_booking(
    request: Request,
    booking_id: uuid.UUID,
    confirmation_data: BookingConfirmationRequest,
    current_user: User = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN, UserRole.DENTIST)
    ),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> BookingConfirmationResponse:
    """Confirm a booking and optionally create an appointment"""
    try:
        if confirmation_data.booking_id != booking_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Booking ID in the request body must match the URL",
            )

        from app.core.database import row_locks_supported
        stmt = (
            select(OnlineBooking)
            .where(
                OnlineBooking.id == booking_id,
                OnlineBooking.practice_id == current_user.practice_id,
            )
        )
        if row_locks_supported():
            stmt = stmt.with_for_update()
        result = await db.execute(stmt)
        booking = result.scalar_one_or_none()

        if not booking:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

        # Serialize on the dimensions the appointment-creation checks below
        # use (provider, patient). The `__unassigned__` sentinel makes
        # provider-less bookings serialize against each other, matching the
        # `provider_id IS NULL` branch of the conflict check. The booking row
        # itself is locked FOR UPDATE above, which makes double-confirm
        # idempotent.
        from app.api.v1.endpoints.appointments import _acquire_booking_lock
        await _acquire_booking_lock(
            db,
            booking.practice_id,
            ("provider", booking.provider_id or "__unassigned__"),
            ("patient", booking.patient_id),
        )

        # H13 FIX: Check booking page verification requirements
        if booking.booking_page_id:
            page_res = await db.execute(
                select(BookingPage).where(BookingPage.id == booking.booking_page_id)
            )
            b_page = page_res.scalar_one_or_none()
            if b_page:
                if b_page.require_email_verification and not booking.email_verified:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Email verification is required before confirming booking",
                    )
                if b_page.require_phone_verification and not booking.phone_verified:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Phone verification is required before confirming booking",
                    )

        # C6 FIX: make confirmation idempotent. A staff double-click or a
        # client retry used to create a second Appointment row for the same
        # booking and orphan the first.
        if booking.status not in (BookingStatus.PENDING, BookingStatus.CONFIRMED):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Booking is already {booking.status.value} and cannot be confirmed",
            )
        if booking.appointment_id:
            return BookingConfirmationResponse(
                booking_id=booking.id,
                appointment_id=booking.appointment_id,
                confirmation_code=booking.confirmation_code,
                status=booking.status,
                message="Booking was already confirmed with an appointment",
            )

        # Update booking status
        booking.status = BookingStatus.CONFIRMED
        booking.confirmed_at = datetime.now(timezone.utc)

        appointment_id = None

        # Create appointment if requested
        if confirmation_data.create_appointment:
            patient_id = booking.patient_id

            if not patient_id and booking.is_new_patient:
                # The Patient model requires a date of birth. If intake did
                # not capture one, fail with a clear message instead of a
                # misleading IntegrityError -> 409.
                if not booking.date_of_birth:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Cannot create a new patient: date of birth is required. Ask the patient to complete the intake form first.",
                    )
                # Create new patient. Populate the HMAC search-index columns
                # exactly like the patients endpoint so the patient is findable
                # via search (the raw PHI columns are encrypted at rest and
                # cannot be queried directly).
                from app.core.search_index import hmac_index as _hmac
                from app.services.plan_quota import check_plan_quota

                await check_plan_quota(db, booking.practice_id, "patients")
                insurance_info = None
                if getattr(booking, "has_insurance", False):
                    insurance_info = {
                        "carrier_name": getattr(booking, "insurance_carrier_name", None),
                        "member_id": getattr(booking, "insurance_member_id", None),
                        "group_number": getattr(booking, "insurance_group_number", None),
                    }
                patient = Patient(
                    practice_id=booking.practice_id,
                    first_name=booking.first_name,
                    last_name=booking.last_name,
                    email=booking.email,
                    phone=booking.phone,
                    date_of_birth=booking.date_of_birth,
                    status="active",
                    medical_history=getattr(booking, "medical_history", None) or {},
                    insurance_info=insurance_info,
                    search_index_email=_hmac(booking.email or ""),
                    search_index_phone=_hmac(booking.phone or ""),
                    search_index_last_name=_hmac(booking.last_name or ""),
                )
                db.add(patient)
                await db.flush()
                patient_id = patient.id
                booking.patient_id = patient_id

            # An appointment cannot exist without a patient. If an "existing"
            # patient was never matched during booking, fail with a clear
            # message instead of crashing on the NOT NULL constraint.
            if not patient_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot create an appointment: no patient is associated with this booking. Match an existing patient first.",
                )

            # Tenant safety: the patient must belong to the booking's practice.
            patient_check = await db.execute(
                select(Patient).where(
                    Patient.id == patient_id,
                    Patient.practice_id == booking.practice_id,
                )
            )
            if not patient_check.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Patient does not belong to this practice.",
                )

            # H-04 FIX: re-validate the stored provider and appointment type at
            # confirmation time. These ids were supplied by an unauthenticated
            # caller when the booking was created; even with create-time
            # validation they must be re-checked here, because the referenced
            # row may have been deleted or moved between submission and
            # confirmation, and confirmation is what writes them onto a real
            # Appointment.
            if booking.provider_id:
                await require_provider(
                    db,
                    booking.provider_id,
                    booking.practice_id,
                    field="Provider",
                    roles=BOOKABLE_PROVIDER_ROLES,
                )
            if booking.appointment_type_id:
                await require_appointment_type(
                    db, booking.appointment_type_id, booking.practice_id
                )

            duration = booking.duration_minutes or 30
            # H9 FIX: interpret the requested wall-clock time in the
            # PRACTICE's timezone and store the UTC instant — the naive
            # `datetime.combine` used to store local digits as UTC, putting
            # every online-confirmed appointment at the wrong instant for
            # any practice outside the server's timezone.
            practice_tz = await get_practice_timezone(db, booking.practice_id)
            if booking.requested_time is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Booking must include a requested time before confirmation",
                )
            try:
                local_start = local_datetime(
                    practice_tz, booking.requested_date, booking.requested_time
                )
            except DateRangeError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=str(exc),
                ) from exc
            start_time = local_start.astimezone(timezone.utc)
            end_time = start_time + timedelta(minutes=duration)

            # Prevent double-booking: reject when an overlapping non-cancelled
            # appointment already exists for the same provider (or, when no
            # provider was selected, for the practice).
            conflict_query = select(Appointment.id).where(
                Appointment.practice_id == booking.practice_id,
                Appointment.start_time < end_time,
                Appointment.end_time > start_time,
                Appointment.status != AppointmentStatus.CANCELLED,
            )
            if booking.provider_id:
                conflict_query = conflict_query.where(Appointment.provider_id == booking.provider_id)
            else:
                conflict_query = conflict_query.where(Appointment.provider_id.is_(None))
            if (await db.execute(conflict_query)).first():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This time slot is no longer available. Please choose another time.",
                )

            # H-04 FIX: also reject when the *patient* already has an
            # overlapping appointment. The provider-only check above let one
            # patient be booked twice at the same instant as long as the two
            # appointments had different providers -- a patient cannot be in
            # two chairs at once, and the duplicate then drove reminders,
            # billing and no-show statistics for a visit that never existed.
            patient_conflict = await db.execute(
                select(Appointment.id).where(
                    Appointment.practice_id == booking.practice_id,
                    Appointment.patient_id == patient_id,
                    Appointment.start_time < end_time,
                    Appointment.end_time > start_time,
                    Appointment.status != AppointmentStatus.CANCELLED,
                )
            )
            if patient_conflict.first():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "This patient already has an appointment at that time. "
                        "Please choose another time."
                    ),
                )

            # Resolve the appointment-type enum. Online bookings reference the
            # practice's AppointmentType config row (appointment_type_id), which
            # is NOT a column on Appointment — map its name through the same
            # coercion used by the authenticated create endpoint (OTHER default
            # so an unresolvable type never crashes the confirmation).
            appointment_type = AppointmentTypeEnum.OTHER
            if booking.appointment_type_id:
                apt_result = await db.execute(
                    select(AppointmentType).where(
                        AppointmentType.id == booking.appointment_type_id,
                        AppointmentType.practice_id == booking.practice_id,
                    )
                )
                apt = apt_result.scalar_one_or_none()
                if apt:
                    appointment_type = _coerce_appointment_type(apt.name)

            # Create appointment
            appointment = Appointment(
                practice_id=booking.practice_id,
                patient_id=patient_id,
                provider_id=booking.provider_id,
                appointment_type=appointment_type,
                status=AppointmentStatus.SCHEDULED,
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                notes=f"Online booking: {booking.reason or booking.chief_complaint or ''}",
            )
            db.add(appointment)
            await db.flush()

            appointment_id = appointment.id
            booking.appointment_id = appointment_id

        await log_audit_event(
            db,
            current_user,
            "confirm_online_booking",
            "online_booking",
            booking.id,
            request,
            {
                "create_appointment": confirmation_data.create_appointment,
                "appointment_id": str(appointment_id) if appointment_id else None,
            },
        )
        await db.commit()
        logger.info(f"Confirmed booking: {booking_id}")

        # Send confirmation email if requested. OnlineBooking has no
        # send_confirmation_email column; honor the page-level config.
        send_confirmation = confirmation_data.send_confirmation
        if send_confirmation and booking.booking_page_id:
            page_result = await db.execute(
                select(BookingPage).where(BookingPage.id == booking.booking_page_id)
            )
            page = page_result.scalar_one_or_none()
            if page is not None:
                send_confirmation = page.send_confirmation_email is not False

        if send_confirmation:
            try:
                # OnlineBooking has no patient_name/appointment_type columns;
                # build the display name from first/last and resolve the
                # procedure label from the appointment-type config when known.
                patient_display = f"{booking.first_name} {booking.last_name}".strip() or "Patient"
                procedure = "Dental Appointment"
                if booking.appointment_type_id:
                    apt_result = await db.execute(
                        select(AppointmentType).where(AppointmentType.id == booking.appointment_type_id)
                    )
                    apt = apt_result.scalar_one_or_none()
                    if apt:
                        procedure = apt.name
                await email_service.send_appointment_confirmation(
                    to=booking.email,
                    patient_name=patient_display,
                    appointment_date=booking.requested_date.strftime('%B %d, %Y'),
                    appointment_time=booking.requested_time.strftime('%I:%M %p') if booking.requested_time else 'TBD',
                    procedure=procedure
                )
            except Exception as e:
                log_email_failure(e, "booking_confirmation", booking.email)

        return BookingConfirmationResponse(
            booking_id=booking.id,
            appointment_id=appointment_id,
            confirmation_code=booking.confirmation_code,
            status=booking.status,
            message="Booking confirmed successfully",
        )
    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error confirming booking: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


# Availability Endpoints

@router.post("/public/{practice_slug}/{page_slug}/availability", response_model=AvailabilityResponse)
@limiter.limit("10/minute")
async def get_availability(
    request: Request,
    practice_slug: str,
    page_slug: str,
    availability_request: AvailabilityRequest,
    db: AsyncSession = Depends(get_db),
) -> AvailabilityResponse:
    """Get available time slots (public endpoint)"""
    try:
        page = await _resolve_public_page(db, practice_slug, page_slug)

        # Validate page-scoped selections and derive the duration from the
        # configured appointment type. The optional request duration remains
        # accepted for compatibility but never controls public availability.
        _, duration_minutes = await _resolve_public_booking_selection(
            db,
            page,
            availability_request.appointment_type_id,
            availability_request.provider_id,
        )

        # A public availability request is a practice-local date range. Keep
        # the calendar-window contract aligned with the later booking check,
        # and cap the scan even for pages that allow a longer booking horizon.
        practice_tz = await get_practice_timezone(db, page.practice_id)
        now_utc = datetime.now(timezone.utc)
        minimum_start_utc = now_utc + timedelta(hours=page.min_notice_hours)
        practice_today = business_date(practice_tz, now_utc)
        latest_bookable_date = practice_today + timedelta(days=page.booking_window_days)
        try:
            date_range = resolve_date_range(
                practice_tz,
                availability_request.start_date,
                availability_request.end_date,
                default_days=MAX_AVAILABILITY_RANGE_DAYS,
                max_days=MAX_AVAILABILITY_RANGE_DAYS,
            )
        except DateRangeError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        if (
            date_range.start_date < practice_today
            or date_range.end_date > latest_bookable_date
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Availability must fall within this practice's booking "
                    f"window ({practice_today.isoformat()} through "
                    f"{latest_bookable_date.isoformat()})."
                ),
            )

        daily_booking_counts: dict[date, int] = {}
        if page.max_bookings_per_day:
            daily_count_result = await db.execute(
                select(OnlineBooking.requested_date, func.count(OnlineBooking.id))
                .where(
                    OnlineBooking.practice_id == page.practice_id,
                    OnlineBooking.requested_date >= date_range.start_date,
                    OnlineBooking.requested_date <= date_range.end_date,
                    OnlineBooking.status.in_((BookingStatus.PENDING, BookingStatus.CONFIRMED)),
                )
                .group_by(OnlineBooking.requested_date)
            )
            daily_booking_counts = dict(daily_count_result.all())

        eligible_providers = await _eligible_public_providers(
            db, page, availability_request.provider_id
        )
        busy_ranges = await _load_provider_busy_ranges(
            db,
            page,
            eligible_providers,
            practice_tz,
            date_range.start_date,
            date_range.end_date,
        )

        # Use availability service to get slots
        days = []
        current_date = date_range.start_date
        total_slots = 0

        while current_date <= date_range.end_date:
            day_name = current_date.strftime("%A").lower()

            # Check if day is in business hours (hoisted once; the OR-fallback
            # dict literal is otherwise typed dict[Never, Never] and re-built
            # twice per iteration).
            business_hours = page.business_hours or {}
            if day_name in business_hours and business_hours[day_name].get("enabled", False):
                # Check if date is not blocked
                if (
                    current_date.isoformat() not in (page.blocked_dates or [])
                    and (
                        not page.max_bookings_per_day
                        or daily_booking_counts.get(current_date, 0)
                        < page.max_bookings_per_day
                    )
                ):
                    slots = []

                    # Get business hours for this day
                    day_hours = page.business_hours[day_name].get('slots', [])

                    for slot_config in day_hours:
                        start_time_str = slot_config.get('start', '09:00')
                        end_time_str = slot_config.get('end', '17:00')

                        # Parse times
                        start_hour, start_minute = map(int, start_time_str.split(':'))
                        end_hour, end_minute = map(int, end_time_str.split(':'))

                        # Generate slots as practice-local wall times and
                        # compare them to stored appointment instants in UTC.
                        current_time = time(start_hour, start_minute)
                        end_time_obj = time(end_hour, end_minute)
                        duration = duration_minutes

                        while current_time < end_time_obj:
                            next_time = (
                                datetime.combine(current_date, current_time)
                                + timedelta(minutes=duration)
                            ).time()
                            try:
                                slot_start_local = _resolve_public_slot_start(
                                    practice_tz, current_date, current_time
                                )
                            except DateRangeError:
                                # A spring-forward wall time is not a real
                                # bookable instant; omit it rather than
                                # remapping it to a different appointment.
                                current_time = next_time
                                continue

                            slot_start_utc = slot_start_local.astimezone(timezone.utc)
                            slot_end_utc = slot_start_utc + timedelta(minutes=duration)
                            slot_end_local = slot_end_utc.astimezone(practice_tz)
                            if (
                                slot_end_local.date() != current_date
                                or slot_end_local.time() > end_time_obj
                            ):
                                break

                            # The response only names wall-clock times, so do
                            # not advertise a slot that has two meanings, crosses
                            # a timezone transition, or begins before notice.
                            if (
                                slot_start_utc < minimum_start_utc
                                or slot_start_local.utcoffset() != slot_end_local.utcoffset()
                                or _is_ambiguous_local_time(
                                    practice_tz,
                                    slot_end_local.date(),
                                    slot_end_local.time(),
                                )
                            ):
                                current_time = next_time
                                continue

                            assigned_provider = next(
                                (
                                    provider
                                    for provider in eligible_providers
                                    if _provider_is_free(
                                        busy_ranges,
                                        provider.id,
                                        slot_start_utc,
                                        slot_end_utc,
                                    )
                                ),
                                None,
                            )
                            if assigned_provider is not None:
                                slots.append(
                                    TimeSlot(
                                        start_time=current_time,
                                        end_time=slot_end_local.time(),
                                        duration_minutes=duration,
                                        is_available=True,
                                        provider_id=assigned_provider.id,
                                        provider_name=(
                                            assigned_provider.full_name.strip()
                                            or "Provider"
                                        ),
                                    )
                                )
                                total_slots += 1

                            current_time = next_time

                    day_availability = DayAvailability(
                        date=current_date,
                        day_of_week=day_name.capitalize(),
                        is_available=len(slots) > 0,
                        slots=slots,
                    )
                    days.append(day_availability)

            current_date += timedelta(days=1)

        return AvailabilityResponse(days=days, total_slots=total_slots)
    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error getting availability: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


# Waitlist Endpoints

@router.post("/public/{practice_slug}/{page_slug}/waitlist", response_model=WaitlistEntryResponse)
@limiter.limit("5/hour")
async def add_to_waitlist(
    request: Request,
    practice_slug: str,
    page_slug: str,
    waitlist_data: WaitlistEntryCreate,
    db: AsyncSession = Depends(get_db),
) -> WaitlistEntryResponse:
    """Add to waitlist (public endpoint)"""
    try:
        page = await _resolve_public_page(db, practice_slug, page_slug)

        if waitlist_data.appointment_type_id:
            await require_appointment_type(
                db, waitlist_data.appointment_type_id, page.practice_id
            )
            if (
                page.allowed_appointment_types
                and str(waitlist_data.appointment_type_id) not in page.allowed_appointment_types
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Requested appointment type is not offered on this booking page",
                )
        for pref_provider_id in waitlist_data.preferred_providers or []:
            await require_provider(
                db,
                pref_provider_id,
                page.practice_id,
                field="Preferred provider",
                roles=BOOKABLE_PROVIDER_ROLES,
            )
            if (
                page.allowed_providers
                and str(pref_provider_id) not in page.allowed_providers
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Requested provider is not available on this booking page",
                )

        # Create waitlist entry
        entry = WaitlistEntry(
            booking_page_id=page.id,
            practice_id=page.practice_id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            **waitlist_data.model_dump()
        )

        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        logger.info(f"Added to waitlist: {entry.id}")

        return entry
    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error adding to waitlist: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.get("/waitlist/", response_model=WaitlistEntryListResponse)
async def list_waitlist_entries(
    status_filter: Optional[WaitlistStatus] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WaitlistEntryListResponse:
    """List waitlist entries for the current practice with pagination."""
    try:
        filters = [WaitlistEntry.practice_id == current_user.practice_id]
        if status_filter:
            filters.append(WaitlistEntry.status == status_filter)

        total = (
            await db.execute(select(func.count(WaitlistEntry.id)).where(*filters))
        ).scalar_one()
        result = await db.execute(
            select(WaitlistEntry)
            .where(*filters)
            .order_by(WaitlistEntry.priority, WaitlistEntry.created_at, WaitlistEntry.id)
            .offset(offset)
            .limit(limit)
        )
        entries = result.scalars().all()
        page_count = len(entries)

        return WaitlistEntryListResponse(
            entries=entries,
            count=page_count,
            total=total,
            limit=limit,
            offset=offset,
            next_offset=offset + page_count if offset + page_count < total else None,
        )
    except (ValueError, TypeError, SQLAlchemyError) as exc:
        logger.error("Error listing waitlist entries: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from exc


@router.put("/waitlist/{entry_id}", response_model=WaitlistEntryResponse)
async def update_waitlist_entry(
    request: Request,
    entry_id: uuid.UUID,
    entry_data: WaitlistEntryUpdate,
    current_user: User = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN, UserRole.DENTIST)
    ),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> WaitlistEntryResponse:
    """Update a waitlist entry with an auditable staff mutation."""
    try:
        result = await db.execute(
            select(WaitlistEntry).where(
                WaitlistEntry.id == entry_id,
                WaitlistEntry.practice_id == current_user.practice_id,
            )
        )
        entry = result.scalar_one_or_none()

        if not entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Waitlist entry not found")

        update_data = entry_data.model_dump(exclude_unset=True)
        if update_data.get("booking_id") is not None:
            await require_practice_scoped(
                db,
                OnlineBooking,
                update_data["booking_id"],
                current_user.practice_id,
                field="Booking",
            )
        for field, value in update_data.items():
            setattr(entry, field, value)

        audit_changes: dict[str, object] = {"updated_fields": sorted(update_data)}
        if update_data.get("status") is not None:
            audit_changes["status"] = update_data["status"].value
        if update_data.get("booking_id") is not None:
            audit_changes["booking_id"] = str(update_data["booking_id"])
        await log_audit_event(
            db,
            current_user,
            "update_waitlist_entry",
            "waitlist_entry",
            entry.id,
            request,
            audit_changes,
        )

        await db.commit()
        await db.refresh(entry)
        logger.info("Updated waitlist entry: %s", entry_id)

        return entry
    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error("Error updating waitlist entry: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error") from e


@router.post("/waitlist/{entry_id}/notify")
async def notify_waitlist_entry(
    request: Request,
    entry_id: uuid.UUID,
    current_user: User = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN, UserRole.DENTIST)
    ),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """Request an availability notification and report provider acceptance truthfully."""
    try:
        result = await db.execute(
            select(WaitlistEntry).where(
                WaitlistEntry.id == entry_id,
                WaitlistEntry.practice_id == current_user.practice_id,
            )
        )
        entry = result.scalar_one_or_none()

        if not entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Waitlist entry not found")

        appointment_type_name = "Dental Appointment"
        if entry.appointment_type_id:
            appointment_type_result = await db.execute(
                select(AppointmentType).where(
                    AppointmentType.id == entry.appointment_type_id,
                    AppointmentType.practice_id == entry.practice_id,
                )
            )
            appointment_type = appointment_type_result.scalar_one_or_none()
            if appointment_type and appointment_type.name:
                appointment_type_name = appointment_type.name

        def format_preferred_date(value: object) -> str:
            if isinstance(value, date):
                return value.strftime("%B %d, %Y")
            try:
                return date.fromisoformat(str(value)).strftime("%B %d, %Y")
            except (TypeError, ValueError):
                return str(value)

        preferred_dates = ", ".join(
            format_preferred_date(value) for value in (entry.preferred_dates or [])
        ) or "the next available date"
        preferred_times = ", ".join(
            str(value) for value in (entry.preferred_times or []) if value
        ) or "any available time"
        patient_name = f"{entry.first_name} {entry.last_name}".strip() or "Patient"
        safe_patient_name = _html_escape(patient_name)
        safe_dates = _html_escape(preferred_dates)
        safe_times = _html_escape(preferred_times)
        safe_appointment_type = _html_escape(appointment_type_name)

        try:
            provider_result = await email_service.send_email(
                to=entry.email,
                subject="An appointment may be available",
                html_content=(
                    "<html><body style='font-family: Arial, sans-serif; max-width: 600px; "
                    "margin: 0 auto;'>"
                    "<h1>Appointment Availability</h1>"
                    f"<p>Dear {safe_patient_name},</p>"
                    "<p>An appointment may be available for your waitlist request. "
                    "Please contact the practice to confirm a time.</p>"
                    "<ul>"
                    f"<li><strong>Appointment type:</strong> {safe_appointment_type}</li>"
                    f"<li><strong>Preferred dates:</strong> {safe_dates}</li>"
                    f"<li><strong>Preferred times:</strong> {safe_times}</li>"
                    "</ul></body></html>"
                ),
                text_content=(
                    f"Hello {patient_name}, an appointment may be available for your "
                    f"{appointment_type_name} request. Preferred dates: {preferred_dates}. "
                    f"Preferred times: {preferred_times}. Please contact the practice to confirm."
                ),
                idempotency_key=(
                    f"waitlist-notification:{entry.id}:{(entry.notified_count or 0) + 1}"
                ),
            )
        except Exception as exc:
            log_email_failure(exc, "waitlist_notification", entry.email)
            logger.warning("Waitlist notification provider error for %s: %s", entry.id, exc)
            return {
                "message": "Notification delivery failed",
                "delivery_status": "failed",
                "provider_accepted": False,
            }

        if not _provider_accepted(provider_result):
            provider_error = "Email provider did not accept the waitlist notification"
            if isinstance(provider_result, dict) and provider_result.get("error"):
                provider_error = str(provider_result["error"])
            log_email_failure(RuntimeError(provider_error), "waitlist_notification", entry.email)
            logger.warning("Waitlist notification was not accepted for %s: %s", entry.id, provider_error)
            return {
                "message": "Email provider did not accept the notification",
                "delivery_status": "not_accepted",
                "provider_accepted": False,
            }

        provider_message_id = None
        if isinstance(provider_result, dict):
            external_id = provider_result.get("provider_message_id") or provider_result.get("external_id")
            provider_message_id = str(external_id) if external_id else None

        # The current model records a successful provider hand-off, not a
        # delivery receipt. Do not increment or mark NOTIFIED until that hand-off
        # succeeds, and return the distinction explicitly to callers.
        entry.notified_count = (entry.notified_count or 0) + 1
        entry.last_notified_at = datetime.now(timezone.utc)
        entry.status = WaitlistStatus.NOTIFIED
        await log_audit_event(
            db,
            current_user,
            "notify_waitlist_entry",
            "waitlist_entry",
            entry.id,
            request,
            {
                "channel": "email",
                "delivery_status": "accepted",
                "provider_message_id": provider_message_id,
            },
        )
        await db.commit()
        logger.info("Waitlist notification accepted for entry: %s", entry_id)

        return {
            "message": "Notification accepted by the email provider",
            "delivery_status": "accepted",
            "provider_accepted": True,
            "provider_message_id": provider_message_id,
        }
    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error("Error notifying waitlist entry: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error") from e


# Verification Endpoints

@router.post("/public/verify-email", response_model=VerificationResponse)
@limiter.limit("10/minute")  # M20 FIX: brute-force throttle on public token checks
async def verify_email(
    request: Request,
    verification_data: EmailVerificationRequest,
    db: AsyncSession = Depends(get_db),
) -> VerificationResponse:
    """Verify email address (public endpoint)"""
    try:
        booking, page = await _resolve_booking_verification_session(
            db, verification_data.verification_session
        )
        if booking is None or page is None or not page.require_email_verification:
            return _verification_response(
                None,
                None,
                verified=False,
                message=_VERIFICATION_FAILED_MESSAGE,
            )

        if booking.email_verified:
            return _verification_response(
                booking,
                page,
                verified=True,
                message="Email verified successfully",
            )

        stored_email_token_hash = booking.email_verification_token_hash
        if not stored_email_token_hash:
            return _verification_response(
                None,
                None,
                verified=False,
                message=_VERIFICATION_FAILED_MESSAGE,
            )
        # M-10 FIX: the verification path now compares against the stored
        # SHA-256 hash in constant time, so a database leak cannot be used
        # to forge email confirmations.
        submitted_hash = hashlib.sha256(
            (verification_data.verification_token or "").encode("utf-8")
        ).hexdigest()
        if not _hmac_lib.compare_digest(
            str(stored_email_token_hash), submitted_hash
        ):
            return _verification_response(
                None,
                None,
                verified=False,
                message=_VERIFICATION_FAILED_MESSAGE,
            )

        booking.email_verified = True
        booking.email_verification_token = None
        booking.email_verification_token_hash = None
        await db.commit()
        logger.info("Email verified for booking: %s", booking.id)
        return _verification_response(
            booking,
            page,
            verified=True,
            message="Email verified successfully",
        )
    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error verifying email: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.post("/public/verify-phone", response_model=VerificationResponse)
@limiter.limit("10/minute")  # M20 FIX: the 6-digit code was brute-forceable
async def verify_phone(
    request: Request,
    verification_data: PhoneVerificationRequest,
    db: AsyncSession = Depends(get_db),
) -> VerificationResponse:
    """Verify phone number (public endpoint)"""
    try:
        booking, page = await _resolve_booking_verification_session(
            db, verification_data.verification_session
        )
        if booking is None or page is None or not page.require_phone_verification:
            return _verification_response(
                None,
                None,
                verified=False,
                message=_VERIFICATION_FAILED_MESSAGE,
            )

        if booking.phone_verified:
            return _verification_response(
                booking,
                page,
                verified=True,
                message="Phone verified successfully",
            )

        stored_phone_code = booking.phone_verification_code
        if not stored_phone_code or not _hmac_lib.compare_digest(
            str(stored_phone_code),
            verification_data.verification_code,
        ):
            return _verification_response(
                None,
                None,
                verified=False,
                message=_VERIFICATION_FAILED_MESSAGE,
            )

        booking.phone_verified = True
        booking.phone_verification_code = None
        await db.commit()
        logger.info("Phone verified for booking: %s", booking.id)
        return _verification_response(
            booking,
            page,
            verified=True,
            message="Phone verified successfully",
        )
    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error verifying phone: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


# Analytics Endpoint

@router.get("/analytics/", response_model=BookingAnalytics)
async def get_booking_analytics(
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BookingAnalytics:
    """Get booking analytics for the current practice"""
    try:
        practice_tz = await get_practice_timezone(db, current_user.practice_id)
        try:
            date_range = resolve_date_range(practice_tz, start_date, end_date)
        except DateRangeError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

        query = select(OnlineBooking).where(
            OnlineBooking.practice_id == current_user.practice_id,
            OnlineBooking.submitted_at >= date_range.start_utc,
            OnlineBooking.submitted_at < date_range.end_utc,
        )
        result = await db.execute(query)
        bookings = result.scalars().all()

        # Calculate analytics
        total_bookings = len(bookings)
        confirmed_bookings = sum(1 for b in bookings if b.status == BookingStatus.CONFIRMED)
        pending_bookings = sum(1 for b in bookings if b.status == BookingStatus.PENDING)
        declined_bookings = sum(1 for b in bookings if b.status == BookingStatus.DECLINED)
        cancelled_bookings = sum(1 for b in bookings if b.status == BookingStatus.CANCELLED)
        new_patients = sum(1 for b in bookings if b.is_new_patient)
        existing_patients = total_bookings - new_patients

        # Get total views from booking pages
        pages_result = await db.execute(select(BookingPage).where(BookingPage.practice_id == current_user.practice_id))
        pages = pages_result.scalars().all()
        total_views = sum(p.total_views for p in pages)

        # Calculate conversion rate
        conversion_rate = (total_bookings / total_views * 100) if total_views > 0 else 0

        # Calculate average response time
        response_times = []
        for booking in bookings:
            confirmed_at = ensure_utc(booking.confirmed_at)
            submitted_at = ensure_utc(booking.submitted_at)
            if confirmed_at is not None and submitted_at is not None:
                response_time = (confirmed_at - submitted_at).total_seconds() / 3600
                response_times.append(response_time)

        average_response_time = sum(response_times) / len(response_times) if response_times else 0

        # Popular times
        popular_times = {}
        for booking in bookings:
            hour = booking.requested_time.hour
            time_slot = f"{hour:02d}:00"
            popular_times[time_slot] = popular_times.get(time_slot, 0) + 1

        # Referral sources
        referral_sources = {}
        for booking in bookings:
            if booking.referral_source:
                referral_sources[booking.referral_source] = referral_sources.get(booking.referral_source, 0) + 1

        logger.info(f"Generated booking analytics for practice: {current_user.practice_id}")

        return BookingAnalytics(
            total_bookings=total_bookings,
            total_views=total_views,
            conversion_rate=conversion_rate,
            confirmed_bookings=confirmed_bookings,
            pending_bookings=pending_bookings,
            declined_bookings=declined_bookings,
            cancelled_bookings=cancelled_bookings,
            new_patients=new_patients,
            existing_patients=existing_patients,
            average_response_time_hours=average_response_time,
            popular_times=popular_times,
            popular_appointment_types={},
            referral_sources=referral_sources,
        )
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error getting booking analytics: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")