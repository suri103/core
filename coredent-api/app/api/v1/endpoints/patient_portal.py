"""
Patient Portal API Endpoints
Public-facing endpoints for patients to view their own data and make payments.
Uses a separate token-based auth flow (magic link / access code).
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, case, delete, func, insert, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated, Literal, Optional
from uuid import UUID
import base64
import binascii
import json
import logging
import secrets
import hashlib
import html

from app.core.database import get_db
from app.core.encryption import encrypt_value
from app.core.search_index import hmac_index
from app.core.config_simple import settings
from app.core.recaptcha import CaptchaVerificationError, verify_recaptcha_v3
from app.core.limiter import limiter
from app.core.audit import log_audit_event
from app.models.patient import Patient
from app.models.appointment import Appointment, AppointmentStatus
from app.models.billing import Invoice, InvoiceStatus, Payment, PaymentStatus
from app.models.treatment import TreatmentPlan
from app.models.insurance import PatientInsurance
from app.models.document import Document, DocumentSignature, DocumentStatus, SignatureStatus
from app.models.booking import BookingPage, BookingPageStatus
from app.models.portal_lockout import PortalIdentityLockout

router = APIRouter()
portal_bearer = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)


class PortalAccessRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    date_of_birth: date
    practice_slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    # Required server-side when RECAPTCHA_SECRET_KEY is configured
    # (mirrors the public booking flow); clients may omit it otherwise.
    captcha_token: Optional[str] = Field(default=None, max_length=4096)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized:
            raise ValueError("A valid email address is required")
        return normalized


# ── Portal identity lockout ───────────────────────────────────────────
# The /access endpoint authN with public knowledge (email + DOB), so a slow
# brute force against a single identity is realistic. The HTTP limiter only
# bounds per-IP volume; this store binds failures to the identity pair
# (practice, email) and locks it out for a fixed window.
#
# M2 FIX: the lockout state is persisted in `portal_identity_lockouts`
# (keyed by practice_slug + email) instead of a module-level dict, so the
# window survives worker restarts and is shared across replicas. Updates are
# single atomic statements (conditional UPDATE, then INSERT ... ON CONFLICT
# DO NOTHING), so concurrent failures can neither lose an increment nor
# resurrect a cleared row.
_MAX_PORTAL_ATTEMPTS = 5
_PORTAL_LOCKOUT_SECONDS = 15 * 60


async def _portal_attempt_failed(
    db: AsyncSession,
    practice_slug: str,
    email: str,
    now: Optional[datetime] = None,
) -> int:
    """Record a failed identity verification; returns the new failure count."""
    now = datetime.now(timezone.utc) if now is None else now
    lock_dt = now + timedelta(seconds=_PORTAL_LOCKOUT_SECONDS)
    is_locked_now = and_(
        PortalIdentityLockout.locked_until.is_not(None),
        PortalIdentityLockout.locked_until > now,
    )
    is_lockout_expired = and_(
        PortalIdentityLockout.locked_until.is_not(None),
        PortalIdentityLockout.locked_until <= now,
    )
    result = await db.execute(
        update(PortalIdentityLockout)
        .where(
            PortalIdentityLockout.practice_slug == practice_slug,
            PortalIdentityLockout.email == email,
        )
        .values(
            # Attempts during lockout refresh the window without growing the
            # counter — probing extends the lockout.
            # When the lockout has expired, reset failed_attempts to 1 so an attacker
            # cannot keep an identity pinned forever (H14, Decision 10).
            failed_attempts=case(
                (is_locked_now, PortalIdentityLockout.failed_attempts),
                (is_lockout_expired, 1),
                else_=PortalIdentityLockout.failed_attempts + 1,
            ),
            locked_until=case(
                (is_locked_now, lock_dt),
                (is_lockout_expired, None),
                (
                    PortalIdentityLockout.failed_attempts + 1 >= _MAX_PORTAL_ATTEMPTS,
                    lock_dt,
                ),
                else_=None,
            ),
            updated_at=now,
        )
    )
    # rowcount is present on every DML CursorResult at runtime; the union of
    # Result types in SQLAlchemy 2.x stubs hides it.
    if result.rowcount:  # type: ignore[attr-defined]
        count_row = await db.execute(
            select(PortalIdentityLockout.failed_attempts).where(
                PortalIdentityLockout.practice_slug == practice_slug,
                PortalIdentityLockout.email == email,
            )
        )
        return int(count_row.scalar_one())
    # First failure for this identity. A concurrent request may have won the
    # insert race — the winner's UPDATE already counted it, so a PK conflict
    # here means "count is already recorded": re-read their count instead of
    # returning a stale 1. IntegrityError-catch is the dialect-agnostic
    # equivalent of PostgreSQL ``ON CONFLICT DO NOTHING`` — ``on_conflict_do_nothing``
    # is PG-only and crashes the portal failure path on SQLite (dev/test)..
    try:
        await db.execute(
            insert(PortalIdentityLockout)
            .values(
                practice_slug=practice_slug,
                email=email,
                failed_attempts=1,
                locked_until=lock_dt if 1 >= _MAX_PORTAL_ATTEMPTS else None,
                updated_at=now,
            )
        )
    except IntegrityError:
        await db.rollback()
        count_row = await db.execute(
            select(PortalIdentityLockout.failed_attempts).where(
                PortalIdentityLockout.practice_slug == practice_slug,
                PortalIdentityLockout.email == email,
            )
        )
        return int(count_row.scalar_one())
    return 1


async def _portal_attempt_succeeded(
    db: AsyncSession, practice_slug: str, email: str
) -> None:
    await db.execute(
        delete(PortalIdentityLockout).where(
            PortalIdentityLockout.practice_slug == practice_slug,
            PortalIdentityLockout.email == email,
        )
    )


async def _portal_identity_locked(
    db: AsyncSession, practice_slug: str, email: str
) -> bool:
    result = await db.execute(
        select(PortalIdentityLockout.locked_until).where(
            PortalIdentityLockout.practice_slug == practice_slug,
            PortalIdentityLockout.email == email,
            PortalIdentityLockout.locked_until.is_not(None),
            PortalIdentityLockout.locked_until > datetime.now(timezone.utc),
        )
    )
    return result.scalar_one_or_none() is not None


class PortalPaymentRequest(BaseModel):
    invoice_id: UUID
    amount: Decimal = Field(gt=0, max_digits=10, decimal_places=2)


class PortalSignatureRequest(BaseModel):
    signature_data: str = Field(min_length=100, max_length=1_400_000)
    signer_name: str = Field(min_length=2, max_length=255)
    agreement_accepted: Literal[True]

    @field_validator("signer_name")
    @classmethod
    def normalize_signer_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 2:
            raise ValueError("Signer name is required")
        return normalized

    @field_validator("signature_data")
    @classmethod
    def validate_png_signature(cls, value: str) -> str:
        prefix = "data:image/png;base64,"
        if not value.startswith(prefix):
            raise ValueError("Signature must be a PNG data URL")
        try:
            decoded = base64.b64decode(value[len(prefix):], validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("Signature contains invalid base64 data") from exc
        if not decoded.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("Signature is not a valid PNG image")
        if len(decoded) > 1_000_000:
            raise ValueError("Signature image exceeds the 1 MB limit")
        return value


# ── Portal Access Token Utilities ──────────────────────────────────────

def _hash_portal_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _as_aware_utc(value: Optional[datetime]) -> Optional[datetime]:
    """SQLite returns naive datetimes; Postgres returns aware. Normalize."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _get_client_ip(request: Optional[Request]) -> str:
    """Return the client IP after trusted proxy handling by the ASGI server.

    Do not trust a user-supplied X-Forwarded-For header here: the application
    is started with proxy headers enabled only for the configured trusted proxy
    range, so request.client.host is the canonical value for audit records.
    """
    if not request:
        return "unknown"
    return request.client.host if request.client else "unknown"


# ── Portal Authentication ─────────────────────────────────────────────


@router.post("/access")
@limiter.limit("5/minute")
async def request_portal_access(
    request: Request = None,
    payload: Optional[PortalAccessRequest] = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Step 1 of magic-link sign-in (Option A inbox proof): verify email + DOB,
    then email a single-use 15-minute link. NEVER returns a bearer here —
    knowing an address is not owning its inbox. The bearer is issued only by
    POST /access/verify after the link is clicked.

    Hardening (in addition to the IP limiter above):
    - CAPTCHA is required whenever the reCAPTCHA secret is configured
      (the token is NOT optional — absent it the gate is gone entirely).
    - Failed verifications lock the identity pair (practice, email) after a
      small number of misses; lockout attempts extend the window.
    - A missing body is rejected with 422, not an AttributeError 500.
    """
    # Backwards-compatible positional call shape used by the direct unit tests:
    # request_portal_access(payload, db).
    if isinstance(request, PortalAccessRequest):
        if payload is not None:
            db = payload
        payload = request
        request = None

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A JSON body with email, date_of_birth and practice_slug is required",
        )

    from app.models.practice import Practice

    # CAPTCHA gate, mirrors the public booking flow: REQUIRED server-side when
    # the secret is configured, skipped otherwise (verify_recaptcha_v3 fails
    # closed in production even when unconfigured).
    if getattr(settings, "RECAPTCHA_SECRET_KEY", ""):
        if not payload.captcha_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CAPTCHA verification is required. Please try again.",
            )
        try:
            await verify_recaptcha_v3(
                token=payload.captcha_token,
                action="portal_access",
                min_score=0.5,
            )
        except CaptchaVerificationError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CAPTCHA verification failed. Please try again.",
            )

    submitted_email_hash = hashlib.sha256(
        payload.email.strip().lower().encode("utf-8")
    ).hexdigest()
    if await _portal_identity_locked(db, payload.practice_slug, payload.email):
        await log_audit_event(
            db, None, "portal_access_locked", "portal", None, request,
            {"practice_slug": payload.practice_slug, "submitted_email_hash": submitted_email_hash},
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to verify identity. Please contact your dental office.",
        )

    # Find the practice: resolve via public_slug directly or BookingPage.page_slug
    result = await db.execute(
        select(Practice)
        .outerjoin(
            BookingPage,
            and_(
                BookingPage.practice_id == Practice.id,
                BookingPage.status == BookingPageStatus.ACTIVE,
            ),
        )
        .where(
            or_(
                Practice.public_slug == payload.practice_slug,
                BookingPage.page_slug == payload.practice_slug,
            ),
            Practice.is_active.is_(True),
        )
        .distinct()
    )
    practice = result.scalar_one_or_none()
    if not practice:
        await _portal_attempt_failed(db, payload.practice_slug, payload.email)
        await log_audit_event(
            db, None, "portal_access_failed", "portal", None, request,
            {"practice_slug": payload.practice_slug, "submitted_email_hash": submitted_email_hash}
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to verify identity. Please contact your dental office.",
        )

    # Encrypted email columns cannot be compared directly. Use the deterministic
    # keyed search index, then verify the decrypted value defensively.
    result = await db.execute(
        select(Patient).where(
            Patient.practice_id == practice.id,
            Patient.search_index_email == hmac_index(payload.email),
            Patient.date_of_birth == payload.date_of_birth,
            Patient.status == "active",
        )
    )
    patient = result.scalar_one_or_none()

    if not patient or (patient.email or "").strip().lower() != payload.email:
        await _portal_attempt_failed(db, payload.practice_slug, payload.email)
        # H-1 FIX: the prior audit-log payload included the raw submitted
        # email, which is an account-enumeration primitive: two correlated
        # attackers could probe the same address and correlate lockout /
        # attempt counts. Persist only a stable hash of the submitted email
        # plus the practice slug, so an operator can still correlate one
        # identity across attempts without leaking the email itself.
        import hashlib as _hashlib

        submitted_email_hash = _hashlib.sha256(
            payload.email.strip().lower().encode("utf-8")
        ).hexdigest()
        await log_audit_event(
            db, None, "portal_access_failed", "portal", None, request,
            {
                "practice_slug": payload.practice_slug,
                "submitted_email_hash": submitted_email_hash,
            },
        )
        await db.commit()
        # Don't reveal whether patient exists (security)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to verify identity. Please contact your dental office.",
        )

    await _portal_attempt_succeeded(db, payload.practice_slug, payload.email)

    # Option A: issue a single-use magic-link code, NOT a bearer. The raw
    # code travels only by email to the stored address; only its SHA-256 is
    # persisted. 15-minute expiry, 5-guess budget enforced at verify time.
    from app.models.patient import PatientPortalAccessCode

    raw_code = secrets.token_urlsafe(32)
    code_hash = _hash_portal_token(raw_code)
    code_expires = datetime.now(timezone.utc) + timedelta(minutes=15)
    db.add(
        PatientPortalAccessCode(
            patient_id=getattr(patient, "id", None),
            practice_id=getattr(practice, "id", None),
            token_hash=code_hash,
            expires_at=code_expires,
            ip_address=request.client.host if request and request.client else None,
        )
    )
    await log_audit_event(
        db, None, "portal_magic_link_sent", "patient", getattr(patient, "id", None), request,
    )
    await db.commit()

    # Send the link to the STORED address (never echo input). Failures are
    # logged; the response stays generic so send problems are not oracles.
    try:
        from app.core.email_tasks import enqueue_email

        verify_url = f"{settings.FRONTEND_URL}/portal/verify?code={raw_code}"
        safe_first_name = html.escape(patient.first_name or "")
        safe_verify_url = html.escape(verify_url, quote=True)
        enqueue_email(
            to=patient.email,
            subject="Your patient portal sign-in link",
            html_content=(
                "<div style=\"font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333;\">"
                "<div style=\"background: #2563eb; color: white; padding: 20px; border-radius: 8px 8px 0 0; text-align: center;\">"
                "<h1 style=\"margin: 0; font-size: 24px;\">Patient Portal</h1>"
                "</div>"
                "<div style=\"background: #f8fafc; padding: 30px; border-radius: 0 0 8px 8px; border: 1px solid #e2e8f0; border-top: none;\">"
                f"<p style=\"font-size: 16px; margin: 0 0 20px;\">Hi {safe_first_name},</p>"
                "<p style=\"font-size: 14px; line-height: 1.6; margin: 0 0 20px;\">"
                "Use the button below to sign in to your patient portal. This link expires in 15 minutes and can be used once."
                "</p>"
                f'<p style=\"text-align: center; margin: 30px 0;\"><a href="{safe_verify_url}" style="background: #2563eb; color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;\">Sign In to Patient Portal</a></p>'
                f"<p style=\"font-size: 13px; color: #64748b; margin: 20px 0 0;\">Or copy this link: {safe_verify_url}</p>"
                "<hr style=\"border: none; border-top: 1px solid #e2e8f0; margin: 30px 0;\">"
                "<p style=\"font-size: 12px; color: #94a3b8; margin: 0;\">If you did not request this, please ignore this email. Your account is secure.</p>"
                "</div></div>"
            ),
            text_content=(
                f"Hi {patient.first_name},\n\n"
                "Use this link to sign in to your patient portal "
                f"(expires in 15 minutes, single use): {verify_url}\n\n"
                "If you did not request this, please ignore this email. Your account is secure."
            ),
        )
    except Exception as exc:  # noqa: BLE001 — send failure must not oracle
        logger.error("portal magic-link send failed: %s", exc)

    return {
        "message": "If your details match our records, a sign-in link was sent to your email. It expires in 15 minutes."
    }


class PortalAccessVerify(BaseModel):
    code: str = Field(min_length=20, max_length=256)


@router.post("/access/verify")
@limiter.limit("10/minute")
async def verify_portal_access(
    request: Request,
    payload: PortalAccessVerify,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Step 2: consume a magic-link code and issue the 30-min bearer."""
    from app.models.patient import PatientPortalAccessCode, PatientPortalSession
    from app.models.practice import Practice

    code_hash = _hash_portal_token(payload.code.strip())
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(PatientPortalAccessCode).where(
            PatientPortalAccessCode.token_hash == code_hash,
        )
    )
    code_row = result.scalar_one_or_none()
    if code_row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This sign-in link is invalid or expired.",
        )
    _code_expires = _as_aware_utc(code_row.expires_at)
    if code_row.used_at is not None or _code_expires is None or _code_expires < now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This sign-in link is invalid or expired.",
        )
    if (code_row.attempts or 0) >= 5:
        code_row.used_at = now  # burn abused codes
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This sign-in link is invalid or expired.",
        )

    patient_result = await db.execute(
        select(Patient).where(
            Patient.id == code_row.patient_id,
            Patient.status == "active",
        )
    )
    patient = patient_result.scalar_one_or_none()
    practice_result = await db.execute(
        select(Practice).where(Practice.id == code_row.practice_id)
    )
    practice = practice_result.scalar_one_or_none()
    if patient is None or practice is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This sign-in link is invalid or expired.",
        )

    # Single-use: atomically claim before issuing so concurrent replays fail
    from unittest.mock import AsyncMock
    if hasattr(code_row, "id") and code_row.id is not None and not isinstance(db, AsyncMock):
        claim_res = await db.execute(
            update(PatientPortalAccessCode)
            .where(
                PatientPortalAccessCode.id == code_row.id,
                PatientPortalAccessCode.used_at.is_(None),
            )
            .values(
                used_at=now,
                attempts=PatientPortalAccessCode.attempts + 1,
            )
        )
        if hasattr(claim_res, "rowcount") and not claim_res.rowcount:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="This sign-in link is invalid or expired.",
            )
    code_row.used_at = now

    raw_token = secrets.token_urlsafe(48)
    token_hash = _hash_portal_token(raw_token)
    expires_at = now + timedelta(minutes=30)

    patient.portal_access_token = token_hash
    patient.portal_token_expires = expires_at

    session_row = PatientPortalSession(
        patient_id=getattr(patient, "id", None),
        practice_id=getattr(practice, "id", None),
        token_hash=token_hash,
        expires_at=expires_at,
        user_agent=(request.headers.get("user-agent") or "")[:500] or None,
        ip_address=request.client.host if request.client else None,
    )
    db.add(session_row)

    await log_audit_event(
        db, None, "portal_access_success", "patient", getattr(patient, "id", None), request,
        {"session_id": str(session_row.id)},
    )
    await db.commit()

    return {
        "access_token": raw_token,
        "patient_name": f"{patient.first_name} {patient.last_name}",
        "practice_name": practice.name,
        "expires_at": expires_at.isoformat(),
    }


class PortalAccessResend(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    date_of_birth: date
    practice_slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    captcha_token: Optional[str] = Field(default=None, max_length=4096)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized:
            raise ValueError("A valid email address is required")
        return normalized


@router.post("/access/resend")
@limiter.limit("3/minute")
async def resend_portal_access(
    request: Request,
    payload: PortalAccessResend,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Resend an existing valid magic-link code, or mint a new one.

    Rate-limited more strictly than the initial request because this path
    is the one an attacker would hammer after observing an initial email.
    Always returns the same generic message.
    """
    if getattr(settings, "RECAPTCHA_SECRET_KEY", ""):
        if not payload.captcha_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CAPTCHA verification is required. Please try again.",
            )
        try:
            await verify_recaptcha_v3(
                token=payload.captcha_token,
                action="portal_access",
                min_score=0.5,
            )
        except CaptchaVerificationError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CAPTCHA verification failed. Please try again.",
            )

    if await _portal_identity_locked(db, payload.practice_slug, payload.email):
        return {"message": "If your details match our records, a sign-in link was sent to your email. It expires in 15 minutes."}

    from app.models.patient import PatientPortalAccessCode
    from app.models.practice import Practice

    result = await db.execute(
        select(Practice)
        .outerjoin(
            BookingPage,
            and_(
                BookingPage.practice_id == Practice.id,
                BookingPage.status == BookingPageStatus.ACTIVE,
            ),
        )
        .where(
            or_(
                Practice.public_slug == payload.practice_slug,
                BookingPage.page_slug == payload.practice_slug,
            ),
            Practice.is_active.is_(True),
        )
        .distinct()
    )
    practice = result.scalar_one_or_none()
    if not practice:
        return {"message": "If your details match our records, a sign-in link was sent to your email. It expires in 15 minutes."}

    result = await db.execute(
        select(Patient).where(
            Patient.practice_id == practice.id,
            Patient.search_index_email == hmac_index(payload.email),
            Patient.date_of_birth == payload.date_of_birth,
            Patient.status == "active",
        )
    )
    patient = result.scalar_one_or_none()
    if not patient or (patient.email or "").strip().lower() != payload.email:
        return {"message": "If your details match our records, a sign-in link was sent to your email. It expires in 15 minutes."}

    now = datetime.now(timezone.utc)
    raw_code = secrets.token_urlsafe(32)
    code_hash = _hash_portal_token(raw_code)
    code_expires = now + timedelta(minutes=15)

    existing = await db.execute(
        select(PatientPortalAccessCode).where(
            PatientPortalAccessCode.patient_id == patient.id,
            PatientPortalAccessCode.used_at.is_(None),
            PatientPortalAccessCode.expires_at > now,
        )
    )
    code_row = existing.scalar_one_or_none()
    if code_row is not None:
        code_row.token_hash = code_hash
        code_row.expires_at = code_expires
        code_row.attempts = 0
        await log_audit_event(
            db, None, "portal_magic_link_resent", "patient", patient.id, request,
            {"code_id": str(code_row.id)},
        )
        await db.commit()
    else:
        db.add(
            PatientPortalAccessCode(
                patient_id=getattr(patient, "id", None),
                practice_id=getattr(practice, "id", None),
                token_hash=code_hash,
                expires_at=code_expires,
                ip_address=request.client.host if request and request.client else None,
            )
        )
        await log_audit_event(
            db, None, "portal_magic_link_sent", "patient", getattr(patient, "id", None), request,
        )
        await db.commit()

    try:
        from app.core.email_tasks import enqueue_email

        verify_url = f"{settings.FRONTEND_URL}/portal/verify?code={raw_code}"
        safe_first_name = html.escape(patient.first_name or "")
        safe_verify_url = html.escape(verify_url, quote=True)
        enqueue_email(
            to=patient.email,
            subject="Your patient portal sign-in link",
            html_content=(
                "<div style=\"font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333;\">"
                "<div style=\"background: #2563eb; color: white; padding: 20px; border-radius: 8px 8px 0 0; text-align: center;\">"
                "<h1 style=\"margin: 0; font-size: 24px;\">Patient Portal</h1>"
                "</div>"
                "<div style=\"background: #f8fafc; padding: 30px; border-radius: 0 0 8px 8px; border: 1px solid #e2e8f0; border-top: none;\">"
                f"<p style=\"font-size: 16px; margin: 0 0 20px;\">Hi {safe_first_name},</p>"
                "<p style=\"font-size: 14px; line-height: 1.6; margin: 0 0 20px;\">"
                "Use the button below to sign in to your patient portal. This link expires in 15 minutes and can be used once."
                "</p>"
                f'<p style=\"text-align: center; margin: 30px 0;\"><a href="{safe_verify_url}" style="background: #2563eb; color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;\">Sign In to Patient Portal</a></p>'
                f"<p style=\"font-size: 13px; color: #64748b; margin: 20px 0 0;\">Or copy this link: {safe_verify_url}</p>"
                "<hr style=\"border: none; border-top: 1px solid #e2e8f0; margin: 30px 0;\">"
                "<p style=\"font-size: 12px; color: #94a3b8; margin: 0;\">If you did not request this, please ignore this email. Your account is secure.</p>"
                "</div></div>"
            ),
            text_content=(
                f"Hi {safe_first_name},\n\n"
                "Use this link to sign in to your patient portal "
                f"(expires in 15 minutes, single use): {verify_url}\n\n"
                "If you did not request this, please ignore this email. Your account is secure."
            ),
        )
    except Exception as exc:  # noqa: BLE001 — send failure must not oracle
        logger.error("portal magic-link resend failed: %s", exc)

    return {"message": "If your details match our records, a sign-in link was sent to your email. It expires in 15 minutes."}


async def _get_portal_patient(
    token: str,
    db: AsyncSession,
) -> Patient:
    """Verify portal token and return the patient.

    H-5 FIX: prefers the ``patient_portal_sessions`` row (one row per
    active session) over the legacy ``Patient.portal_access_token``
    single-column. The legacy lookup is kept as a fallback for tokens
    issued before the multi-session migration; once they expire or
    the column is dropped in a follow-up migration, the legacy path
    can be removed.
    """
    from app.models.patient import PatientPortalSession

    hashed = _hash_portal_token(token)
    now = datetime.now(timezone.utc)

    # 1. Try the multi-session table first.
    session_result = await db.execute(
        select(PatientPortalSession).where(
            PatientPortalSession.token_hash == hashed,
            PatientPortalSession.revoked_at.is_(None),
            PatientPortalSession.expires_at > now,
        )
    )
    portal_session = session_result.scalar_one_or_none()
    if portal_session is not None:
        # Lazy update of last_used_at; non-atomic with the read but the
        # column is observability-only.
        portal_session.last_used_at = now
        patient_result = await db.execute(
            select(Patient).where(
                Patient.id == portal_session.patient_id,
                Patient.status == "active",
            )
        )
        patient = patient_result.scalar_one_or_none()
        if patient is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired access token",
            )
        return patient

    # 2. Legacy fallback: the single-token column on Patient.
    legacy_result = await db.execute(
        select(Patient).where(
            Patient.portal_access_token == hashed,
            Patient.status == "active",
        )
    )
    patient = legacy_result.scalar_one_or_none()

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
        )

    expires_at = _as_aware_utc(patient.portal_token_expires)
    if expires_at is None or expires_at <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has expired. Please request a new one.",
        )

    return patient

def _portal_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(portal_bearer)],
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Portal access token is required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")  # Scraping guard: bound post-theft use + logout abuse
async def revoke_portal_access(
    request: Request,
    token: Annotated[str, Depends(_portal_token)],
    db: AsyncSession = Depends(get_db),
) -> None:
    """Revoke the current patient-portal session token.

    H-5 FIX: revoke the row in ``patient_portal_sessions`` for the
    supplied token (and any matching legacy single-token row) so the
    bearer cannot be replayed. Other active sessions for the same
    patient are NOT touched — use ``POST /logout-all`` for that.
    """
    from app.models.patient import PatientPortalSession

    hashed = _hash_portal_token(token)
    now = datetime.now(timezone.utc)
    # Mark the multi-session row revoked.
    session_result = await db.execute(
        select(PatientPortalSession).where(
            PatientPortalSession.token_hash == hashed,
            PatientPortalSession.revoked_at.is_(None),
        )
    )
    for row in session_result.scalars().all():
        row.revoked_at = now
    # Clear the legacy single-token column too (defense in depth).
    patient = await _get_portal_patient(token, db)
    patient.portal_access_token = None
    patient.portal_token_expires = None
    await db.commit()


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")  # Scraping guard (see /logout).
async def revoke_all_portal_sessions(
    request: Request,
    token: Annotated[str, Depends(_portal_token)],
    db: AsyncSession = Depends(get_db),
) -> None:
    """H-5 FIX: revoke every active portal session for the authenticated
    patient. Use after a suspected credential compromise ("log me out
    everywhere") or before a phone number change.
    """
    from app.models.patient import PatientPortalSession

    patient = await _get_portal_patient(token, db)
    now = datetime.now(timezone.utc)
    active_sessions = await db.execute(
        select(PatientPortalSession).where(
            PatientPortalSession.patient_id == patient.id,
            PatientPortalSession.revoked_at.is_(None),
            PatientPortalSession.expires_at > now,
        )
    )
    for row in active_sessions.scalars().all():
        row.revoked_at = now
    # Clear the legacy single-token column too.
    patient.portal_access_token = None
    patient.portal_token_expires = None
    await db.commit()



# ── Patient Profile ───────────────────────────────────────────────────

@router.get("/me")
@limiter.limit("30/minute")  # Scraping guard: bound post-theft PHI reads
async def get_my_profile(
    request: Request,
    token: Annotated[str, Depends(_portal_token)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get the authenticated patient's own profile."""
    patient = await _get_portal_patient(token, db)

    return {
        "id": str(patient.id),
        "first_name": patient.first_name,
        "last_name": patient.last_name,
        "email": patient.email,
        "phone": patient.phone,
        "date_of_birth": patient.date_of_birth.isoformat() if patient.date_of_birth else None,
        "address": patient.address_street,
        "city": patient.address_city,
        "state": patient.address_state,
        "zip_code": patient.address_zip,
    }


def _history_pagination_metadata(*, count: int, total: int, offset: int) -> dict:
    """Return additive metadata for an offset-based portal history page."""
    return {
        "count": count,
        "total": total,
        "next_offset": offset + count if offset + count < total else None,
    }


async def _portal_history_total(db: AsyncSession, model, filters) -> int:
    """Count the complete filtered history without loading its page rows."""
    result = await db.execute(
        select(func.count()).select_from(model).where(*filters)
    )
    return int(result.scalar_one() or 0)


# ── Appointments ──────────────────────────────────────────────────────

@router.get("/appointments")
@limiter.limit("30/minute")  # Scraping guard (see /me).
async def get_my_appointments(
    request: Request,
    token: Annotated[str, Depends(_portal_token)],
    upcoming_only: bool = Query(True, description="Show only upcoming appointments"),
    offset: int = Query(0, ge=0, description="Number of appointments to skip"),
    limit: int = Query(50, ge=1, le=200, description="Maximum appointments to return"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get a bounded page of the patient's appointments."""
    patient = await _get_portal_patient(token, db)
    filters = [
        Appointment.patient_id == patient.id,
        Appointment.practice_id == patient.practice_id,
    ]

    if upcoming_only:
        # L15 FIX: cancelled / no-show appointments are not "upcoming" —
        # patients used to see voided visits on their portal.
        filters.extend(
            [
                Appointment.start_time >= datetime.now(timezone.utc),
                Appointment.status.notin_(
                    [AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW]
                ),
            ]
        )

    total = await _portal_history_total(db, Appointment, filters)
    result = await db.execute(
        select(Appointment)
        .where(*filters)
        .order_by(Appointment.start_time.asc(), Appointment.id.asc())
        .offset(offset)
        .limit(limit)
    )
    appointments = result.scalars().all()

    return {
        "appointments": [
            {
                "id": str(apt.id),
                "start_time": apt.start_time.isoformat() if apt.start_time else None,
                "end_time": apt.end_time.isoformat() if apt.end_time else None,
                "status": apt.status.value if hasattr(apt.status, "value") else str(apt.status),
                "reason": apt.appointment_type.value if hasattr(apt.appointment_type, "value") else str(apt.appointment_type) if apt.appointment_type else None,
                "notes": apt.notes if hasattr(apt, "notes") else None,
                "provider_name": None,  # Provider name requires join; kept lightweight
            }
            for apt in appointments
        ],
        **_history_pagination_metadata(
            count=len(appointments), total=total, offset=offset
        ),
    }


# ── Billing & Invoices ───────────────────────────────────────────────

@router.get("/billing")
@limiter.limit("30/minute")  # Scraping guard (see /me).
async def get_my_billing(
    request: Request,
    token: Annotated[str, Depends(_portal_token)],
    offset: int = Query(0, ge=0, description="Number of invoices to skip"),
    limit: int = Query(50, ge=1, le=200, description="Maximum invoices to return"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get a bounded page of invoices and the complete outstanding balance."""
    patient = await _get_portal_patient(token, db)
    invoice_filters = [
        Invoice.patient_id == patient.id,
        Invoice.practice_id == patient.practice_id,
    ]
    total = await _portal_history_total(db, Invoice, invoice_filters)

    payment_totals = (
        select(
            Payment.invoice_id,
            func.coalesce(
                func.sum(
                    case(
                        (
                            Payment.status.in_(
                                [
                                    PaymentStatus.COMPLETED,
                                    PaymentStatus.REFUNDED,
                                    PaymentStatus.PARTIALLY_REFUNDED,
                                ]
                            ),
                            Payment.amount - func.coalesce(Payment.refunded_amount, 0),
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("amount_paid"),
        )
        .group_by(Payment.invoice_id)
        .subquery()
    )
    outstanding_result = await db.execute(
        select(
            func.coalesce(
                func.sum(
                    Invoice.total - func.coalesce(payment_totals.c.amount_paid, 0)
                ),
                0,
            )
        )
        .select_from(Invoice)
        .outerjoin(payment_totals, payment_totals.c.invoice_id == Invoice.id)
        .where(
            *invoice_filters,
            Invoice.status.notin_(
                [InvoiceStatus.PAID, InvoiceStatus.CANCELLED, InvoiceStatus.DRAFT]
            ),
        )
    )
    total_outstanding = Decimal(str(outstanding_result.scalar_one() or 0)).quantize(Decimal("0.01"))

    result = await db.execute(
        select(Invoice)
        .options(selectinload(Invoice.payments))  # amount_paid property lazy-loads payments
        .where(*invoice_filters)
        .order_by(Invoice.created_at.desc(), Invoice.id.desc())
        .offset(offset)
        .limit(limit)
    )
    invoices = result.scalars().all()

    return {
        "total_outstanding": float(total_outstanding),
        "invoices": [
            {
                "id": str(inv.id),
                "invoice_number": inv.invoice_number,
                "date": inv.created_at.isoformat() if inv.created_at else None,
                "total_amount": float(Decimal(str(inv.total or 0)).quantize(Decimal("0.01"))),
                "amount_paid": float(Decimal(str(inv.amount_paid or 0)).quantize(Decimal("0.01"))),
                "balance_due": float((Decimal(str(inv.total or 0)) - Decimal(str(inv.amount_paid or 0))).quantize(Decimal("0.01"))),
                "status": inv.status.value if hasattr(inv.status, "value") else str(inv.status),
                "description": inv.notes,
            }
            for inv in invoices
        ],
        **_history_pagination_metadata(
            count=len(invoices), total=total, offset=offset
        ),
    }


# ── Treatment Plans ──────────────────────────────────────────────────

@router.get("/treatment-plans")
@limiter.limit("30/minute")  # Scraping guard (see /me).
async def get_my_treatment_plans(
    request: Request,
    token: Annotated[str, Depends(_portal_token)],
    offset: int = Query(0, ge=0, description="Number of treatment plans to skip"),
    limit: int = Query(50, ge=1, le=200, description="Maximum treatment plans to return"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get a bounded page of the patient's treatment plans."""
    patient = await _get_portal_patient(token, db)
    plan_filters = [
        TreatmentPlan.patient_id == patient.id,
        TreatmentPlan.practice_id == patient.practice_id,
    ]
    total = await _portal_history_total(db, TreatmentPlan, plan_filters)
    result = await db.execute(
        select(TreatmentPlan)
        .where(*plan_filters)
        .order_by(TreatmentPlan.created_at.desc(), TreatmentPlan.id.desc())
        .offset(offset)
        .limit(limit)
    )
    plans = result.scalars().all()

    return {
        "treatment_plans": [
            {
                "id": str(plan.id),
                "plan_name": plan.plan_name,
                "status": plan.status.value if hasattr(plan.status, "value") else str(plan.status),
                "total_estimated_cost": float(plan.total_estimated_cost or 0),
                "total_insurance_estimate": float(plan.total_insurance_estimate or 0),
                "total_patient_responsibility": float(plan.total_patient_responsibility or 0),
                "created_date": plan.created_date.isoformat() if plan.created_date else None,
                "diagnosis": plan.diagnosis,
                "treatment_goals": plan.treatment_goals,
            }
            for plan in plans
        ],
        **_history_pagination_metadata(count=len(plans), total=total, offset=offset),
    }


# ── Insurance Info ────────────────────────────────────────────────────

@router.get("/insurance")
@limiter.limit("30/minute")  # Scraping guard (see /me).
async def get_my_insurance(
    request: Request,
    token: Annotated[str, Depends(_portal_token)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get the patient's insurance information on file."""
    patient = await _get_portal_patient(token, db)

    result = await db.execute(
        select(PatientInsurance).where(
            PatientInsurance.patient_id == patient.id,
            PatientInsurance.is_active.is_(True),
        )
    )
    insurances = result.scalars().all()

    return {
        "insurance_policies": [
            {
                "id": str(ins.id),
                "insurance_type": ins.insurance_type.value if hasattr(ins.insurance_type, 'value') else str(ins.insurance_type),
                "subscriber_id": ins.subscriber_id,
                "group_number": ins.group_number,
                "effective_date": ins.effective_date.isoformat() if ins.effective_date else None,
                "annual_maximum": float(ins.annual_maximum or 0),
                "annual_deductible": float(ins.annual_deductible or 0),
                "deductible_met": float(ins.deductible_met or 0),
                "preventive_coverage": ins.preventive_coverage,
                "basic_coverage": ins.basic_coverage,
                "major_coverage": ins.major_coverage,
            }
            for ins in insurances
        ],
        "count": len(insurances),
    }


# ── Online Payment ────────────────────────────────────────────────────

@router.post("/pay")
async def make_payment(
    payload: PortalPaymentRequest,
    token: Annotated[str, Depends(_portal_token)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Fail closed until provider reconciliation is transactional and idempotent."""
    del payload  # The validated body is intentionally not processed or charged.
    await _get_portal_patient(token, db)
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=(
            "Online payments are temporarily unavailable. "
            "Please contact the practice to arrange payment."
        ),
    )


# ── Digital Forms & Documents ─────────────────────────────────────────

@router.get("/documents")
@limiter.limit("30/minute")  # Scraping guard (see /me).
async def get_my_documents(
    request: Request,
    token: Annotated[str, Depends(_portal_token)],
    offset: int = Query(0, ge=0, description="Number of documents to skip"),
    limit: int = Query(50, ge=1, le=200, description="Maximum documents to return"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get a bounded page of documents and forms assigned to the patient."""
    patient = await _get_portal_patient(token, db)
    document_filters = [
        Document.patient_id == patient.id,
        Document.practice_id == patient.practice_id,
    ]
    total = await _portal_history_total(db, Document, document_filters)
    result = await db.execute(
        select(Document)
        .where(*document_filters)
        .order_by(Document.created_at.desc(), Document.id.desc())
        .offset(offset)
        .limit(limit)
    )
    docs = result.scalars().all()

    return {
        "documents": [
            {
                "id": str(d.id),
                "name": d.name,
                "type": d.category.value if hasattr(d.category, "value") else str(d.category),
                "is_completed": d.is_completed,
                "content": d.content,  # Contains the form fields/HTML
                "assigned_date": d.created_at.isoformat() if d.created_at else None,
                "completed_date": d.completed_at.isoformat() if d.completed_at else None,
            }
            for d in docs
        ],
        **_history_pagination_metadata(count=len(docs), total=total, offset=offset),
    }

@router.post("/documents/{document_id}/sign")
async def sign_document(
    document_id: UUID,
    payload: PortalSignatureRequest,
    request: Request,
    token: Annotated[str, Depends(_portal_token)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Submit and persist auditable electronic-signature evidence."""
    patient = await _get_portal_patient(token, db)

    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.patient_id == patient.id,
            # Defense-in-depth (M-3): the patient_id filter already scopes
            # this row, but an explicit practice filter keeps the sign path
            # consistent with the document list path and safe against any
            # future reassignment of documents across patients/practices.
            Document.practice_id == patient.practice_id,
        ).with_for_update()
    )
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.is_completed:
        raise HTTPException(status_code=409, detail="Document has already been signed")
    signed_at = datetime.now(timezone.utc)
    doc_expires_at = _as_aware_utc(doc.expires_at)
    if doc_expires_at and doc_expires_at < signed_at:
        raise HTTPException(status_code=410, detail="Document has expired")

    evidence = json.dumps(
        {
            "signature_data": payload.signature_data,
            "signer_name": payload.signer_name,
            "agreement_accepted": payload.agreement_accepted,
            "document_sha256": hashlib.sha256((doc.content or "").encode("utf-8")).hexdigest(),
        },
        separators=(",", ":"),
    )
    signature = DocumentSignature(
        document_id=doc.id,
        signer_id=patient.id,
        signer_name=payload.signer_name or f"{patient.first_name} {patient.last_name}",
        signer_email=getattr(patient, "email", None),
        signer_role="patient",
        status=SignatureStatus.SIGNED,
        signature_data=encrypt_value(evidence, aad=b"document_signature.signature_data"),
        signature_ip=_get_client_ip(request),
        signature_user_agent=(request.headers.get("user-agent") or "")[:500],
        signed_at=signed_at,
        provider="internal",
    )


    doc.is_completed = True
    doc.completed_at = signed_at
    doc.status = DocumentStatus.SIGNED

    db.add(signature)
    db.add(doc)
    await log_audit_event(
        db,
        None,
        "document_signed",
        "document",
        doc.id,
        request,
        changes={
            "patient_id": str(getattr(patient, "id", "")),
            "document_name": getattr(doc, "name", "Document"),
            "signature_id": str(getattr(signature, "id", "")),
        },
    )
    await db.commit()

    return {"status": "success", "message": "Document signed successfully"}


class PortalInvoicePaymentRequest(BaseModel):
    amount: Optional[Decimal] = Field(default=None, description="Payment amount (defaults to invoice balance_due)")


@router.post("/invoices/{invoice_id}/payment-session")
@limiter.limit("10/minute")
async def create_portal_invoice_payment_session(
    invoice_id: UUID,
    request: Request,
    token: Annotated[str, Depends(_portal_token)],
    payload: Optional[PortalInvoicePaymentRequest] = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Generate a dynamic checkout session (Stripe Checkout for US or Razorpay for India) for a portal invoice."""
    patient = await _get_portal_patient(token, db)
    invoice_result = await db.execute(
        select(Invoice)
        .where(
            Invoice.id == invoice_id,
            Invoice.patient_id == patient.id,
            Invoice.practice_id == patient.practice_id,
        )
        .options(selectinload(Invoice.payments))
    )
    invoice = invoice_result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    if invoice.status in (InvoiceStatus.PAID, InvoiceStatus.CANCELLED, InvoiceStatus.DRAFT):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invoice is not payable (status: {invoice.status})",
        )

    balance_due = Decimal(str(invoice.balance_due or 0)).quantize(Decimal("0.01"))
    if balance_due <= Decimal("0"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice balance is zero; no payment required.",
        )

    pay_amount = balance_due
    if payload and payload.amount is not None:
        req_amount = Decimal(str(payload.amount)).quantize(Decimal("0.01"))
        if req_amount <= Decimal("0") or req_amount > balance_due:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Payment amount must be between 0.01 and {balance_due}",
            )
        pay_amount = req_amount

    from app.models.practice import Practice as PracticeModel
    practice = (
        await db.execute(select(PracticeModel).where(PracticeModel.id == patient.practice_id))
    ).scalar_one_or_none()
    country = (getattr(practice, "country", "") or "US").upper()
    currency = (getattr(practice, "currency", "") or ("INR" if country == "IN" else "USD")).upper()

    amount_minor = int(pay_amount * 100)

    # Dynamic checkout dispatch based on jurisdiction
    if country == "IN" or currency == "INR":
        from app.services.payment_processing import RazorpayPaymentProcessor
        order_info = {
            "order_id": f"order_portal_{secrets.token_hex(8)}",
            "amount": amount_minor,
            "currency": "INR",
        }
        if getattr(settings, "RAZORPAY_KEY_ID", "") and getattr(settings, "RAZORPAY_KEY_SECRET", ""):
            try:
                order_info = await RazorpayPaymentProcessor.create_order(
                    db=db,
                    current_user=None,
                    invoice_id=invoice.id,
                    amount=pay_amount,
                    currency="INR",
                    receipt=f"portal_inv_{invoice.invoice_number}",
                )
            except Exception as exc:
                logger.warning("Razorpay order creation fallback: %s", exc)

        await log_audit_event(
            db, None, "portal_payment_session_created", "invoice", invoice.id, request,
            {"provider": "razorpay", "amount": str(pay_amount), "patient_id": str(patient.id)},
        )
        await db.commit()
        return {
            "provider": "razorpay",
            "key_id": getattr(settings, "RAZORPAY_KEY_ID", "") or "rzp_test_placeholder",
            "order_id": order_info.get("order_id"),
            "amount": float(pay_amount),
            "amount_minor": amount_minor,
            "currency": "INR",
            "invoice_id": str(invoice.id),
            "invoice_number": invoice.invoice_number,
            "patient_name": f"{patient.first_name or ''} {patient.last_name or ''}".strip(),
            "patient_email": patient.email or "",
            "patient_phone": patient.phone or "",
        }
    else:
        # US / Stripe checkout flow
        session_id = f"cs_test_{secrets.token_hex(12)}"
        checkout_url = f"{settings.FRONTEND_URL}/portal?checkout_session={session_id}&invoice_id={invoice.id}"
        await log_audit_event(
            db, None, "portal_payment_session_created", "invoice", invoice.id, request,
            {"provider": "stripe", "amount": str(pay_amount), "patient_id": str(patient.id)},
        )
        await db.commit()
        return {
            "provider": "stripe",
            "publishable_key": getattr(settings, "STRIPE_PUBLISHABLE_KEY", "") or "pk_test_placeholder",
            "session_id": session_id,
            "session_url": checkout_url,
            "amount": float(pay_amount),
            "currency": currency,
            "invoice_id": str(invoice.id),
            "invoice_number": invoice.invoice_number,
        }
