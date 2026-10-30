from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.audit import log_audit_event
from app.api.deps import get_current_user, require_role, verify_csrf
from app.models.user import User, UserRole
from app.models.practice import Practice
from app.schemas.settings import (
    BillingPreferencesResponse,
    BillingPreferencesUpdate,
    PracticeSettingsUpdate,
)

router = APIRouter()


def _practice_settings_payload(practice: Practice) -> dict:
    return {
        "id": str(practice.id),
        "name": practice.name,
        "email": practice.email or "",
        "phone": practice.phone or "",
        "website": practice.website or "",
        "logoUrl": practice.logo_url or "",
        "timezone": practice.timezone or "America/New_York",
        "currency": practice.currency or "USD",
        "address": {
            "street": practice.address_street or practice.address or "",
            "city": practice.address_city or practice.city or "",
            "state": practice.address_state or practice.state or "",
            "zipCode": practice.address_zip or practice.zip_code or "",
            "country": practice.country or "US",
        },
        "settings": practice.settings or {},
        # Data-retention override (docs/DATA_RETENTION_POLICY.md § 6): NULL
        # means the platform default applies; min 0 prevents negative windows.
        "retentionYears": practice.retention_years if practice.retention_years is not None else None,
        # Practice jurisdiction for the retention preset picker (NULL = none picked).
        "jurisdiction": practice.jurisdiction or None,
        # Minor-record retention window (NULL = platform defaults 18 / 7).
        "majorityAge": practice.majority_age if practice.majority_age is not None else 18,
        "minorRetentionYears": practice.minor_retention_years
        if practice.minor_retention_years is not None
        else 7,
        "updatedAt": practice.updated_at.isoformat() if practice.updated_at else None,
    }


@router.get("/")
async def get_practice_settings(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get and audit general settings for the current practice."""
    result = await db.execute(
        select(Practice).where(Practice.id == current_user.practice_id)
    )
    practice = result.scalar_one_or_none()
    if not practice:
        raise HTTPException(status_code=404, detail="Practice not found")

    response = _practice_settings_payload(practice)
    await log_audit_event(
        db, current_user, "practice_settings_viewed", "practice", practice.id, request
    )
    await db.commit()
    return response


@router.put("/")
async def update_practice_settings(
    request: Request,
    settings_data: PracticeSettingsUpdate,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """Update validated general settings and audit in the same transaction."""
    result = await db.execute(
        select(Practice).where(Practice.id == current_user.practice_id)
    )
    practice = result.scalar_one_or_none()
    if not practice:
        raise HTTPException(status_code=404, detail="Practice not found")

    update_data = settings_data.model_dump(exclude_unset=True)
    scalar_map = {
        "name": "name",
        "email": "email",
        "phone": "phone",
        "website": "website",
        "timezone": "timezone",
        "currency": "currency",
        "logoUrl": "logo_url",
    }
    for schema_field, model_field in scalar_map.items():
        if schema_field in update_data:
            setattr(practice, model_field, update_data[schema_field])

    # Data-retention override: Pydantic schema enforces ge=0/le=100; the
    # effective-window service takes max(floor, practice value), so a
    # deliberately-lower value (e.g. 0) still cannot shorten below the platform
    # default. Allow unset (not provided) and explicit null (clears override).
    if "retentionYears" in update_data:
        practice.retention_years = update_data["retentionYears"]

    # Jurisdiction code for the retention preset picker. Explicit null clears
    # the stored pick (back to "none picked"); unset leaves it untouched.
    if "jurisdiction" in update_data:
        practice.jurisdiction = update_data["jurisdiction"]

    # Minor-record window: ge/le enforced by schema; NULL clears to platform
    # default (18 / 7) which the anonymize endpoint reads.
    if "majorityAge" in update_data:
        practice.majority_age = update_data["majorityAge"]
    if "minorRetentionYears" in update_data:
        practice.minor_retention_years = update_data["minorRetentionYears"]

    address = update_data.get("address")
    if address is not None:
        address_map = {
            "street": ("address_street", "address"),
            "city": ("address_city", "city"),
            "state": ("address_state", "state"),
            "zipCode": ("address_zip", "zip_code"),
            "country": ("country",),
        }
        for field, model_fields in address_map.items():
            if field in address:
                for model_field in model_fields:
                    setattr(practice, model_field, address[field])

    if "workingHours" in update_data:
        current_settings = dict(practice.settings or {})
        current_settings["workingHours"] = update_data["workingHours"]
        practice.settings = current_settings

    await db.flush()
    await log_audit_event(
        db,
        current_user,
        "practice_settings_updated",
        "practice",
        practice.id,
        request,
        changes={"fields": sorted(update_data.keys())},
    )
    await db.commit()
    await db.refresh(practice)
    return _practice_settings_payload(practice)


@router.post("/logo")
async def upload_practice_logo(
    request: Request,
    logo: UploadFile = File(...),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """
    Upload and set practice logo
    """
    stmt = select(Practice).where(Practice.id == current_user.practice_id)
    result = await db.execute(stmt)
    practice = result.scalar_one_or_none()

    if not practice:
        raise HTTPException(status_code=404, detail="Practice not found")

    # M-21 FIX: actually store the upload bytes through the storage strategy,
    # with MIME allowlisting and a size cap. Previously only a URL derived
    # from the client-controlled filename was recorded -- no file was ever
    # written, and an unvalidated filename reached the stored path.
    MAX_LOGO_BYTES = 2 * 1024 * 1024
    ALLOWED_LOGO_MIME_TYPES = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
    }

    from app.core.file_security import read_stream_with_size_limit, validate_magic_number, FileSecurityError

    try:
        content = await read_stream_with_size_limit(logo, MAX_LOGO_BYTES)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Logo must be 2 MB or smaller",
        )

    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Logo file is empty",
        )

    mime_type = (logo.content_type or "").split(";")[0].strip().lower()
    extension = ALLOWED_LOGO_MIME_TYPES.get(mime_type)
    if extension is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Logo must be a PNG, JPEG, or WebP image",
        )

    # Magic-byte check (M24)
    try:
        validate_magic_number(content, mime_type)
    except FileSecurityError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Logo validation failed: {exc}",
        )

    from app.utils.storage import storage as file_storage, S3StorageStrategy

    destination = f"practices/{practice.id}/logo{extension}"
    file_storage.upload(content, destination, mime_type)

    if isinstance(file_storage, S3StorageStrategy):
        practice.logo_url = file_storage.get_url(destination, expires_in=86400)
    else:
        practice.logo_url = f"/uploads/{destination}"

    await db.flush()
    await log_audit_event(
        db,
        current_user,
        "practice_logo_updated",
        "practice",
        practice.id,
        request,
        changes={"content_type": mime_type},
    )
    await db.commit()

    return {"url": practice.logo_url}


@router.get("/billing", response_model=BillingPreferencesResponse)
async def get_billing_preferences(
    request: Request,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> BillingPreferencesResponse:
    """
    Get billing preferences for the practice
    """
    # Get practice
    stmt = select(Practice).where(Practice.id == current_user.practice_id)
    result = await db.execute(stmt)
    practice = result.scalar_one_or_none()

    if not practice:
        raise HTTPException(status_code=404, detail="Practice not found")

    response = {
        "taxRate": practice.tax_rate or 0.0,
        "currency": practice.currency or "USD",
        "invoicePrefix": practice.invoice_prefix or "INV",
        "paymentTerms": practice.payment_terms or 30,
        "lateFeePercentage": practice.late_fee_percentage or 0.0,
        "acceptedPaymentMethods": practice.accepted_payment_methods or ["cash", "card", "check"],
        "autoSendInvoices": practice.auto_send_invoices or False,
        "autoSendReminders": practice.auto_send_reminders or False,
        "reminderDaysBefore": practice.reminder_days_before or 3,
    }
    await log_audit_event(
        db, current_user, "billing_settings_viewed", "practice", practice.id, request
    )
    await db.commit()
    return response


@router.put("/billing", response_model=BillingPreferencesResponse)
async def update_billing_preferences(
    request: Request,
    preferences: BillingPreferencesUpdate,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> BillingPreferencesResponse:
    """
    Update billing preferences for the practice
    """
    # Get practice
    stmt = select(Practice).where(Practice.id == current_user.practice_id)
    result = await db.execute(stmt)
    practice = result.scalar_one_or_none()

    if not practice:
        raise HTTPException(status_code=404, detail="Practice not found")

    # Update fields (map camelCase schema to snake_case model)
    field_map = {
        "taxRate": "tax_rate",
        "currency": "currency",
        "invoicePrefix": "invoice_prefix",
        "paymentTerms": "payment_terms",
        "lateFeePercentage": "late_fee_percentage",
        "acceptedPaymentMethods": "accepted_payment_methods",
        "autoSendInvoices": "auto_send_invoices",
        "autoSendReminders": "auto_send_reminders",
        "reminderDaysBefore": "reminder_days_before",
    }
    update_data = preferences.model_dump(exclude_unset=True)
    for schema_field, value in update_data.items():
        model_field = field_map.get(schema_field, schema_field)
        if hasattr(practice, model_field):
            setattr(practice, model_field, value)

    await db.flush()
    await log_audit_event(
        db,
        current_user,
        "billing_settings_updated",
        "practice",
        practice.id,
        request,
        changes={"fields": sorted(update_data.keys())},
    )
    await db.commit()
    await db.refresh(practice)

    return {
        "taxRate": practice.tax_rate or 0.0,
        "currency": practice.currency or "USD",
        "invoicePrefix": practice.invoice_prefix or "INV",
        "paymentTerms": practice.payment_terms or 30,
        "lateFeePercentage": practice.late_fee_percentage or 0.0,
        "acceptedPaymentMethods": practice.accepted_payment_methods or ["cash", "card", "check"],
        "autoSendInvoices": practice.auto_send_invoices or False,
        "autoSendReminders": practice.auto_send_reminders or False,
        "reminderDaysBefore": practice.reminder_days_before or 3,
    }
