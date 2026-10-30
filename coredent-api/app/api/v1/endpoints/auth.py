"""
Authentication Endpoints
Login, logout, token refresh, password reset
"""

import inspect
import re
import uuid as uuid_lib

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, case
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from app.core.database import get_db
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
    validate_password_strength,
    generate_password_reset_token,
)
from app.core.config_simple import settings
from app.core.email import log_email_failure
from app.models.user import User, UserRole
from app.models.audit import Session as UserSession
from app.models.password_reset import PasswordResetToken
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    TokenResponse,
    TokenRefreshRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
    InvitationValidateRequest,
)
from app.schemas.user import (
    UserResponse,
    PasswordChange,
    StaffInvitationAccept,
)
from app.api.deps import get_current_user, verify_csrf, verify_csrf_no_auth
from app.core.limiter import limiter
from app.core.audit import log_audit_event

router = APIRouter()


async def _await_if_needed(value: Any) -> Any:
    """Await if the value is awaitable (supports sync+async sessions)."""
    if inspect.isawaitable(value):
        return await value
    return value


# F2 FIX: Removed the shadowed local wrapper that re-imported
# log_email_failure. Callers now use the module-level import directly.
# Account lockout configuration
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15

# M-2 FIX: constant dummy bcrypt hash so unknown-email logins cost the same
# ~700ms (14 rounds) as known-email logins. Without this, response timing
# distinguishes valid emails despite the collapsed 401 message.
# Generated once at import; never used for real authentication.
_DUMMY_PASSWORD_HASH: str | None = None


def _get_dummy_hash() -> str:
    global _DUMMY_PASSWORD_HASH
    if _DUMMY_PASSWORD_HASH is None:
        _DUMMY_PASSWORD_HASH = get_password_hash(
            "dummy-password-for-timing-mitigation-only-do-not-use-0000"
        )
    return _DUMMY_PASSWORD_HASH

# Email verification: tokens expire, and unverified accounts lose access
# after the grace period (staff provisioned by an admin are attested and
# start verified; existing accounts were grandfathered by migration).
EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS = 24
EMAIL_VERIFICATION_GRACE_DAYS = 7

REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"

# H8 FIX: how long a superseded refresh token remains acceptable. Two tabs
# refreshing in a race both complete within milliseconds; 5 seconds is ample
# for that window while bounding how long a replayed token stays usable.
# (Previously 30s.) Reuse within the window is additionally single-use — see
# ``previous_token_consumed`` in the refresh endpoint below.
REFRESH_TOKEN_OVERLAP_SECONDS = 5


def _slugify_unique(name: str) -> str:
    """Deterministically derive a globally-unique public_slug for a practice.

    A readable slug is derived from the practice name; when the name yields
    an empty or overly-generic slug, a short random suffix is appended so
    every practice gets a collision-resistant public_slug without a query.
    """
    base = (name or "").lower()
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    base = re.sub(r"-+", "-", base)[:48]
    if not base or base in {"practice", "dental", "clinic", "smile"}:
        base = "practice"
    return f"{base}-{uuid_lib.uuid4().hex[:6]}"


def _as_aware_utc(dt: datetime) -> datetime:
    """Normalize a possibly naive DB datetime (SQLite) to aware UTC."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _email_verification_overdue(user: User) -> bool:
    """True when an unverified account is past its verification grace period."""
    if user.is_email_verified:
        return False
    if getattr(user, "email_verification_required", False):
        return True
    exp = getattr(user, "email_verification_token_expires_at", None)
    if exp is not None:
        exp_aware = _as_aware_utc(exp)
        if exp_aware and datetime.now(timezone.utc) > exp_aware:
            return True
    created_at = _as_aware_utc(user.created_at)
    if created_at is None:
        return False
    return datetime.now(timezone.utc) > created_at + timedelta(days=EMAIL_VERIFICATION_GRACE_DAYS)


def _set_refresh_cookie(response, token: str) -> None:
    """Keep the durable refresh credential out of browser-readable storage."""
    is_production = settings.ENVIRONMENT == "production"
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=is_production,
        samesite="none" if is_production else "lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path=REFRESH_COOKIE_PATH,
    )

@router.get("/csrf")
async def get_csrf_token() -> dict:
    """Issue a CSRF token for a new browser tab before refresh is attempted."""
    from fastapi.responses import JSONResponse
    from app.core.security import generate_csrf_token

    csrf_token = generate_csrf_token()
    response = JSONResponse(content={"csrf_token": csrf_token})
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="none" if settings.ENVIRONMENT == "production" else "lax",
        max_age=86400,
        path="/",
    )
    return response


@router.post("/login", response_model=LoginResponse)
@limiter.limit("5/minute")  # SECURITY FIX: Only 5 login attempts per minute
async def login(
    request: Request,
    credentials: LoginRequest,
    db: AsyncSession = Depends(get_db),
    # NOTE: CSRF is NOT required on login because user doesn't have a session yet.
    # CSRF protection applies to state-changing endpoints AFTER authentication.
) -> LoginResponse:
    """
    Login with email and password
    Returns access and refresh tokens
    SECURITY: Implements account lockout after failed attempts
    """
    # Find user by email
    result = await _await_if_needed(db.execute(select(User).where(User.email == credentials.email)))
    user = result.scalar_one_or_none()

    if not user:
        # H-7 FIX: a missing user and a wrong password used to share the same
        # response, but the post-lookup branches (locked / inactive / unverified)
        # returned 429 or 403 on a known email. An attacker could therefore
        # enumerate valid emails by status code alone. Collapse every
        # post-lookup failure to a single 401 with a constant string. The
        # global rate limit (5/minute per IP) plus the lockout window keep
        # brute-force infeasible.
        # M-2 FIX: run a dummy bcrypt verification so timing matches the
        # known-email path (verify_password below).
        try:
            verify_password(credentials.password, _get_dummy_hash())
        except Exception:
            pass
        await log_audit_event(
            db, None, "login_failed", "user", None, request,
            {"email_present": False},
        )
        await _await_if_needed(db.commit())
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    # Check if account is locked (normalize tz: SQLite returns naive datetimes)
    if user.locked_until:
        locked_until = _as_aware_utc(user.locked_until)
        if datetime.now(timezone.utc) < locked_until:
            await log_audit_event(db, user, "login_locked", "user", user.id, request)
            await _await_if_needed(db.commit())
            # H-7: collapse to 401 + generic detail. The edge rate limiter
            # continues to throttle lockout-aware brute force.
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )
        else:
            # Lockout expired, reset
            user.failed_login_attempts = 0
            user.locked_until = None

    if not verify_password(credentials.password, user.password_hash):
        # Increment atomically in SQL — a Python read-modify-write lets
        # parallel requests under-count and exceed the attempt cap.
        new_lockout = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
        await _await_if_needed(
            db.execute(
                update(User)
                .where(User.id == user.id)
                .values(
                    failed_login_attempts=User.failed_login_attempts + 1,
                    last_failed_login=datetime.now(timezone.utc),
                    locked_until=case(
                        (User.failed_login_attempts + 1 >= MAX_FAILED_ATTEMPTS, new_lockout),
                        else_=None,
                    ),
                )
            )
        )
        await log_audit_event(
            db, user, "login_failed", "user", user.id, request,
            {"email_present": True},
        )
        await _await_if_needed(db.commit())
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    if not user.is_active:
        await log_audit_event(db, user, "login_inactive", "user", user.id, request)
        await _await_if_needed(db.commit())
        # H-7: collapse to 401 + generic detail; the audit log distinguishes
        # the cause internally so support can still tell a user why.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    # Platform-suspension gate: a super admin can suspend a whole clinic
    # (Practice.is_active=False) from the platform console. Every user of
    # that practice is locked out at login. SUPER_ADMINs live in their own
    # bootstrap practice and are never affected by tenant suspension.
    if user.role != UserRole.SUPER_ADMIN:
        from app.models.practice import Practice as _Practice

        practice_row = await _await_if_needed(
            db.execute(select(_Practice).where(_Practice.id == user.practice_id))
        )
        practice_obj = practice_row.scalar_one_or_none()
        if practice_obj is not None and not practice_obj.is_active:
            await log_audit_event(
                db, user, "login_practice_suspended", "practice", user.practice_id, request,
            )
            await _await_if_needed(db.commit())
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This clinic account is suspended. Please contact support.",
            )

    # Email verification gate: new self-registered accounts must verify
    # within the grace period before they can keep signing in.
    if _email_verification_overdue(user):
        await log_audit_event(db, user, "login_unverified", "user", user.id, request)
        await _await_if_needed(db.commit())
        # H-7: collapse to 401 + generic detail; the audit log distinguishes
        # the cause internally so support can still tell a user why.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    # M1 FIX: invitation-accepted accounts have no grace period — the 72h
    # invite token is not proof of inbox ownership, so the account stays
    # locked out of login until the verification email is confirmed.
    if user.email_verification_required and not user.is_email_verified:
        await log_audit_event(db, user, "login_unverified", "user", user.id, request)
        await _await_if_needed(db.commit())
        # H-7: collapse to 401 + generic detail.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    # Reset failed attempts on successful login
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_failed_login = None

    # Create tokens
    token_data = {
        "sub": str(user.id),
        "role": user.role.value,
        "practice_id": str(user.practice_id),
    }

    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    # Update last login
    await _await_if_needed(
        db.execute(
            update(User)
            .where(User.id == user.id)
            .values(last_login=datetime.now(timezone.utc))
        )
    )

    # SECURITY FIX: Hash refresh token before storing
    from app.core.security import hash_token
    token_hash = hash_token(refresh_token)

    # Store refresh token in database (hashed only, no plaintext)
    session = UserSession(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(session)

    # HIPAA: Audit log login success
    await log_audit_event(db, user, "login_success", "user", user.id, request)
    await _await_if_needed(db.commit())

    # Set CSRF cookie for client-side protection
    from fastapi.responses import JSONResponse
    from app.core.security import generate_csrf_token
    csrf_token = generate_csrf_token()

    # CRIT-01/CRIT-03 FIX: Use Bearer token auth strategy for cross-origin deployment.
    # httpOnly cookies don't work cross-origin unless domains share a parent domain.
    # For Railway deployment with separate frontend/backend domains, use Authorization header.
    # Tokens are returned in response body - frontend stores in memory (NOT localStorage).
    response = JSONResponse(content={
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "csrf_token": csrf_token,
        "must_change_password": bool(user.must_change_password),
        "message": "Login successful",
    })

    # CSRF cookie: SameSite=None + Secure are required for cross-origin
    # subresource requests in production (fetch/XHR). Outside production we
    # keep the cookie usable over plain HTTP for local development.
    is_production = settings.ENVIRONMENT == "production"
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=True,
        secure=is_production,
        samesite="none" if is_production else "lax",
        max_age=86400,  # 24 hours
        path="/"
    )
    _set_refresh_cookie(response, refresh_token)

    return response


# Country -> sensible locale defaults for new practices
_COUNTRY_DEFAULTS = {
    "US": ("America/New_York", "USD"),
    "IN": ("Asia/Kolkata", "INR"),
    "GB": ("Europe/London", "GBP"),
    "CA": ("America/Toronto", "CAD"),
    "AU": ("Australia/Sydney", "AUD"),
}


@router.post("/register", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("3/minute")  # SECURITY: Throttle self-serve signups to limit abuse
async def register(
    request: Request,
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create an unverified owner account without revealing email existence."""
    del request  # consumed by the rate limiter
    from html import escape as _html_escape

    from app.core.email_tasks import enqueue_email
    from app.core.security import hash_token as _hash_token
    from app.models.practice import Practice
    from app.models.user import UserRole

    is_valid, error_message = validate_password_strength(payload.password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message,
        )

    generic_response = {
        "message": (
            "If this email can be registered, a verification link has been sent. "
            "Check your inbox before signing in."
        )
    }
    existing = await _await_if_needed(
        db.execute(select(User).where(User.email == payload.email))
    )
    if existing.scalar_one_or_none() is not None:
        # Same status and body as a newly-created account. Recovery is handled
        # by the equally generic public resend-verification endpoint.
        return generic_response

    country = (payload.country or "US").upper()
    tz, currency = _COUNTRY_DEFAULTS.get(country, ("UTC", "USD"))
    practice = Practice(
        name=payload.practice_name,
        # PUBLIC booking URLs are /book/{practice_slug}/{page_slug}, so every
        # practice needs a globally-unique public_slug. Derive one from the
        # practice name; if that collides the IntegrityError on flush falls
        # through to the generic registration-success response (a duplicate
        # slug must never leak the account's existence).
        public_slug=_slugify_unique(payload.practice_name),
        email=payload.email,
        phone=payload.phone,
        country=country,
        timezone=tz,
        currency=currency,
        auto_send_reminders=True,
        is_active=True,
    )
    db.add(practice)
    await _await_if_needed(db.flush())

    # Decision 4: Seed default chairs and appointment types for newly registered practice
    from app.models.appointment import Chair, AppointmentType
    db.add_all([
        Chair(practice_id=practice.id, name="Operatory 1", color="#3B82F6", is_active=True),
        Chair(practice_id=practice.id, name="Operatory 2", color="#10B981", is_active=True),
        AppointmentType(practice_id=practice.id, name="Routine Cleaning", duration=45, color="#3B82F6", description="Prophylaxis and hygiene cleaning", is_active=True),
        AppointmentType(practice_id=practice.id, name="Comprehensive Exam", duration=60, color="#10B981", description="Initial exam and dental evaluation", is_active=True),
        AppointmentType(practice_id=practice.id, name="Emergency / Toothache", duration=30, color="#EF4444", description="Urgent pain assessment", is_active=True),
    ])

    verification_token = generate_password_reset_token()
    user = User(
        email=payload.email,
        password_hash=get_password_hash(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        role=UserRole.OWNER,
        practice_id=practice.id,
        is_active=True,
        is_email_verified=False,
        email_verification_token=_hash_token(verification_token),
        email_verification_token_expires_at=(
            datetime.now(timezone.utc)
            + timedelta(hours=EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS)
        ),
    )
    db.add(user)
    try:
        await _await_if_needed(db.commit())
    except IntegrityError:
        # A concurrent request won the unique-email race. Preserve the same
        # externally observable response as every other registration attempt.
        await _await_if_needed(db.rollback())
        return generic_response
    except Exception:
        await _await_if_needed(db.rollback())
        raise

    verification_link = f"{settings.FRONTEND_URL}/verify-email?code={verification_token}"
    try:
        safe_first_name = _html_escape(user.first_name or "")
        enqueue_email(
            to=user.email,
            subject="Welcome to CoreDent - Verify Your Email",
            html_content=(
                f"<p>Welcome to CoreDent, {safe_first_name}!</p>"
                f"<p>Please verify your email: "
                f'<a href="{_html_escape(verification_link, quote=True)}">Verify Email</a></p>'
            ),
            text_content=f"Welcome to CoreDent! Verify your email: {verification_link}",
        )
    except Exception as exc:
        log_email_failure(exc, "welcome_verification", user.email)

    return generic_response


@router.post("/logout")
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf_no_auth),
) -> LoginResponse:
    """
    Logout and invalidate refresh token + revoke access token.

    L2 FIX: resolves the caller from the access token when still valid, and
    otherwise from the refresh credential itself — a client whose 15-minute
    access token has expired must still be able to revoke its refresh
    session without minting a new access token first.
    """
    # The refresh cookie is the only accepted durable session credential.
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)

    # Resolve the acting user: access token first, then refresh credential.
    user_id = None
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        payload = decode_token(auth_header[7:])
        if payload and payload.get("type") == "access":
            user_id = payload.get("sub")
    if user_id is None and refresh_token:
        payload = decode_token(refresh_token)
        if payload and payload.get("type") == "refresh":
            user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    try:
        user_uuid = UUID(user_id)
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )

    # Delete session if refresh token provided (F-7 FIX: match both the
    # current and overlap-window previous legs — logging out with the
    # superseded cookie inside REFRESH_TOKEN_OVERLAP_SECONDS must still kill
    # the session row).
    if refresh_token:
        from sqlalchemy import or_ as _or_

        from app.core.security import hash_token
        token_hash = hash_token(refresh_token)
        result = await _await_if_needed(
            db.execute(
                select(UserSession).where(
                    UserSession.user_id == user_uuid,
                    _or_(
                        UserSession.token_hash == token_hash,
                        UserSession.previous_token_hash == token_hash,
                    ),
                )
            )
        )
        session = result.scalar_one_or_none()
        if session:
            await log_audit_event(db, None, "logout", "user", user_uuid, request)
            await _await_if_needed(db.delete(session))
            await _await_if_needed(db.commit())

    # SECURITY: Revoke the access token (jti blacklist) so it can't be used
    # even within its remaining TTL window.
    # H-01: the revocation is now written durably to `revoked_tokens`, so it is
    # visible to every worker and survives a Redis restart. A *cache* failure
    # is still tolerated (the durable row already kills the token), but a
    # failure of the durable write is reported: telling a user "logged out"
    # when their token still works is the wrong answer for a PHI system.
    from app.core.token_blacklist import revoke_token_durable
    revocation_failed = False
    if auth_header.lower().startswith("bearer "):
        payload = decode_token(auth_header[7:])
        if payload and payload.get("jti"):
            exp_ts = payload.get("exp", 0)
            remaining = int(exp_ts - datetime.now(timezone.utc).timestamp())
            try:
                await revoke_token_durable(
                    db,
                    payload["jti"],
                    ttl_seconds=max(remaining, 1),
                    user_id=user_uuid,
                    reason="logout",
                )
                await _await_if_needed(db.commit())
            except Exception as revoke_exc:
                revocation_failed = True
                import logging
                logging.getLogger(__name__).critical(
                    "Durable access-token revocation failed during logout: %s",
                    revoke_exc,
                )
                try:
                    await _await_if_needed(db.rollback())
                except Exception:
                    pass

    # Clear CSRF cookie only (no token cookies to clear with Bearer auth)
    from fastapi.responses import JSONResponse
    if revocation_failed:
        # The refresh session is gone, so no new access tokens can be minted,
        # but the current one may survive until it expires. Say so rather than
        # reporting a clean logout.
        response = JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "message": (
                    "Signed out. Your session was ended, but the current access "
                    "token could not be revoked immediately and may remain valid "
                    "until it expires."
                ),
                "fully_revoked": False,
            },
        )
    else:
        response = JSONResponse(
            content={"message": "Successfully logged out", "fully_revoked": True}
        )
    response.delete_cookie(key="csrf_token", path="/")
    response.delete_cookie(key=REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)

    return response


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    refresh_in: TokenRefreshRequest | None = None,
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf_no_auth),
) -> TokenResponse:
    """Rotate the authoritative HttpOnly refresh cookie."""
    from sqlalchemy import and_, or_

    del refresh_in  # Body credentials are intentionally ignored.
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
        )

    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    from app.core.security import hash_token
    token_hash = hash_token(refresh_token)
    now = datetime.now(timezone.utc)

    result = await _await_if_needed(
        db.execute(
            select(UserSession).where(
                or_(
                    UserSession.token_hash == token_hash,
                    and_(
                        UserSession.previous_token_hash == token_hash,
                        UserSession.previous_token_consumed.is_(False),
                        UserSession.previous_token_valid_until.is_not(None),
                        UserSession.previous_token_valid_until >= now,
                    ),
                )
            )
        )
    )
    session = result.scalar_one_or_none()
    expires_at = _as_aware_utc(session.expires_at) if session is not None else None

    if session is None:
        # A valid refresh JWT that is not current, not inside the narrow
        # overlap window, or whose overlap use has already been consumed is
        # treated as credential reuse. H8 FIX: this now also fires for a token
        # replayed WITHIN the window — the previous-token leg is single-use, so
        # a second presentation of any superseded token revokes all sessions
        # immediately instead of silently rotating again.
        sub = payload.get("sub")
        try:
            replayed_user_id = UUID(sub) if sub else None
        except (ValueError, TypeError):
            replayed_user_id = None
        if replayed_user_id is not None:
            await log_audit_event(db, None, "refresh_token_reuse_revocation", "user", replayed_user_id, request)
            await _await_if_needed(
                db.execute(delete(UserSession).where(UserSession.user_id == replayed_user_id))
            )
            await _await_if_needed(db.commit())
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired or invalid",
        )

    if expires_at is None or expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired or invalid",
        )

    # M-4 FIX: absolute lifetime cap — sliding expires_at alone lets an
    # active user refresh forever. created_at is the family birth; beyond
    # REFRESH_ABSOLUTE_EXPIRE_DAYS the session is dead even if idle expiry
    # has not hit. Grandfathering: pre-existing rows have a real created_at
    # from their insert, so worst case is one re-login within 30d of deploy.
    created_at = _as_aware_utc(session.created_at) if session.created_at else None
    if created_at is not None:
        absolute_deadline = created_at + timedelta(days=settings.REFRESH_ABSOLUTE_EXPIRE_DAYS)
        if now >= absolute_deadline:
            await _await_if_needed(
                db.execute(delete(UserSession).where(UserSession.id == session.id))
            )
            await _await_if_needed(db.commit())
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token expired or invalid",
            )

    result = await _await_if_needed(db.execute(select(User).where(User.id == session.user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    if _email_verification_overdue(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required. Please verify your email address to continue.",
        )
    # M1 FIX: mirror the login gate — invitation-accepted accounts must
    # verify their inbox before token refresh keeps their session alive.
    if user.email_verification_required and not user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required. Please verify your email address to continue.",
        )

    token_data = {
        "sub": str(user.id),
        "role": user.role.value,
        "practice_id": str(user.practice_id),
    }
    access_token = create_access_token(token_data)
    new_refresh_token = create_refresh_token(token_data)
    new_token_hash = hash_token(new_refresh_token)
    overlap_until = now + timedelta(seconds=REFRESH_TOKEN_OVERLAP_SECONDS)

    # Accept either the current hash or the immediately previous hash during
    # the overlap. Each successful rotation keeps the superseded current hash
    # for one short window, preventing normal two-tab races from revoking all
    # sessions while still bounding replay exposure.
    #
    # H8 FIX: the previous-token leg is single-use. When the presented token
    # was the previous hash (a parallel-refresh leg), ``previous_token_consumed``
    # flips to True so a replayed token cannot keep rotating inside the window:
    # its next presentation matches nothing and triggers the all-sessions
    # revocation above. A rotation off the CURRENT hash re-arms the flag so a
    # fresh two-tab race still resolves normally.
    rotate_result = await _await_if_needed(
        db.execute(
            update(UserSession)
            .where(
                UserSession.id == session.id,
                or_(
                    UserSession.token_hash == token_hash,
                    and_(
                        UserSession.previous_token_hash == token_hash,
                        UserSession.previous_token_consumed.is_(False),
                        UserSession.previous_token_valid_until.is_not(None),
                        UserSession.previous_token_valid_until >= now,
                    ),
                ),
            )
            .values(
                previous_token_hash=UserSession.token_hash,
                previous_token_valid_until=overlap_until,
                previous_token_consumed=case(
                    (UserSession.previous_token_hash == token_hash, True),
                    else_=False,
                ),
                token_hash=new_token_hash,
                # M-4: clamp sliding expiry to the absolute family deadline so
                # the last rotation before the cap does not overshoot it.
                expires_at=min(
                    now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
                    (
                        created_at + timedelta(days=settings.REFRESH_ABSOLUTE_EXPIRE_DAYS)
                        if created_at is not None
                        else now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
                    ),
                ),
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
        )
    )
    if rotate_result.rowcount == 0:
        await _await_if_needed(db.rollback())
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token was superseded; retry with the latest cookie",
        )

    await log_audit_event(db, user, "token_refreshed", "user", user.id, request)
    await _await_if_needed(db.commit())

    from fastapi.responses import JSONResponse

    response = JSONResponse(content=TokenResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    ).model_dump(exclude_none=True))
    _set_refresh_cookie(response, new_refresh_token)
    return response


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Get current user information, including the practice metadata used by the UI.
    """
    from app.models.practice import Practice

    result = await _await_if_needed(
        db.execute(select(Practice).where(Practice.id == current_user.practice_id))
    )
    practice = result.scalar_one_or_none()
    response = UserResponse.model_validate(current_user)
    return response.model_copy(update={
        "practice_name": practice.name if practice else None,
        "practice_country": practice.country if practice else None,
        "practice_currency": practice.currency if practice else None,
    })


@router.post("/forgot-password")
@limiter.limit("5/minute")  # SECURITY: Prevent email enumeration/brute force
async def forgot_password(
    request: Request,
    forgot_in: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Request password reset
    Sends email with reset token
    """
    # Find user
    result = await _await_if_needed(db.execute(select(User).where(User.email == forgot_in.email)))
    user = result.scalar_one_or_none()

    # Always return success to prevent email enumeration
    if not user:
        return {"message": "If the email exists, a password reset link has been sent"}

    # Generate reset token
    from app.core.security import generate_password_reset_token, hash_token
    from datetime import datetime, timedelta
    reset_token = generate_password_reset_token()
    token_hash = hash_token(reset_token)

    # Store reset token in separate table for security (with expiration)
    # First, invalidate any existing tokens for this user
    existing_tokens = await _await_if_needed(
        db.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.is_used.is_(False),
                PasswordResetToken.expires_at > datetime.now(timezone.utc)
            )
        )
    )
    for token in existing_tokens.scalars().all():
        token.is_used = True

    # Create new reset token (hashed only)
    password_reset = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        ip_address=request.client.host if request.client else None,
    )
    db.add(password_reset)
    # Audit gap FIX: log the reset request by user id (never email) — login/
    # refresh paths log; forgot previously relied on INFO only.
    await log_audit_event(
        db, user, "password_reset_requested", "user", user.id, request
    )
    await _await_if_needed(db.commit())

    # Durable-queue password-reset email.
    try:
        from app.core.email_tasks import enqueue_email
        from html import escape as _html_escape

        reset_link = f"{settings.FRONTEND_URL}/reset-password#token={reset_token}"
        # M3 FIX: escape the interpolated link (the token is URL-safe, but the
        # FRONTEND_URL may contain characters that must not reach the HTML
        # verbatim) — register() already escaped; the reset path did not.
        safe_reset_link = _html_escape(reset_link, quote=True)
        enqueue_email(
            to=user.email,
            subject="Password Reset - CoreDent",
            html_content=f"""
            <html>
                <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h1>Password Reset Request</h1>
                    <p>You requested a password reset. Click the link below to reset your password:</p>
                    <p><a href="{safe_reset_link}" style="background: #007bff; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px;">Reset Password</a></p>
                    <p>Or copy this link: {safe_reset_link}</p>
                    <p>This link expires in 24 hours.</p>
                    <p>If you didn't request this, please ignore this email.</p>
                    <hr>
                    <p style="color: #666; font-size: 12px;">CoreDent Dental Practice Management</p>
                </body>
            </html>
            """,
            text_content=f"Reset your password: {reset_link}. This link expires in 24 hours."
        )
    except Exception as e:
        # SECURITY: For HIPAA, a failed password-reset email is a
        # notification failure.  The user thinks "I requested a reset"
        # but no email went out.  Log to Sentry at error level.
        log_email_failure(e, "password_reset", user.email)

    return {"message": "If the email exists, a password reset link has been sent"}


@router.post("/resend-verification")
@limiter.limit("3/minute")
async def resend_verification_email(
    request: Request,
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Public, generic verification recovery that does not enumerate users."""
    del request  # consumed by the rate limiter
    generic = {
        "message": "If the account exists and needs verification, a new link has been sent."
    }
    result = await _await_if_needed(
        db.execute(select(User).where(User.email == payload.email))
    )
    user = result.scalar_one_or_none()
    if user is None or user.is_email_verified or not user.is_active:
        return generic

    from app.core.security import hash_token as _hash_token

    verification_token = generate_password_reset_token()
    user.email_verification_token = _hash_token(verification_token)
    user.email_verification_token_expires_at = (
        datetime.now(timezone.utc)
        + timedelta(hours=EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS)
    )
    await _await_if_needed(db.commit())

    try:
        from app.core.email_tasks import enqueue_email
        from html import escape as _html_escape

        verification_link = f"{settings.FRONTEND_URL}/verify-email?code={verification_token}"
        # M3 FIX: escape the interpolated link, consistent with register().
        safe_verification_link = _html_escape(verification_link, quote=True)
        enqueue_email(
            to=user.email,
            subject="Verify Your Email - CoreDent",
            html_content=(
                "<p>Please verify your CoreDent email address:</p>"
                f'<p><a href="{safe_verification_link}">Verify Email</a></p>'
                "<p>This link expires in 24 hours.</p>"
            ),
            text_content=f"Verify your email: {verification_link}. This link expires in 24 hours.",
        )
    except Exception as exc:
        log_email_failure(exc, "resend_verification", user.email)

    return generic


@router.post("/verify-email")
@limiter.limit("10/minute")  # F-11 FIX: throttle token-guessing + spam on public endpoint
async def verify_email(
    request: Request,
    payload: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf_no_auth),
) -> dict:
    """
    Verify email with token.

    SECURITY: token is accepted in the request body (not the URL query
    string) so it does not land in proxy/access logs, and only its hash is
    compared against the stored value.

    L-3 FIX: CSRF is required even on this endpoint because the route is
    reachable from an authenticated browser session once the user has
    any CSRF cookie set; without the gate, an attacker could mark a
    victim's account as verified via cross-site POST.

    M-11 FIX: the verification link is now sent as
    ``/verify-email?code=…`` (query param) instead of a URL fragment.
    The fragment was persisted in browser history and never reached the
    server; the query string is exchanged by the frontend for a POST
    to this endpoint with the token in the body. Tokens are stored
    hashed (``hash_token``), never in plaintext — the old plaintext
    columns were dropped by migration
    ``20260901_0900_f1a3c5e7d9b2_drop_dead_email_token_hash_columns``.
    """
    from app.core.security import hash_token as _hash_token
    token_hash = _hash_token(payload.token)

    # Find user with matching verification token (stored hashed)
    result = await _await_if_needed(
        db.execute(
            select(User).where(
                User.email_verification_token == token_hash,
                User.is_email_verified.is_(False)
            )
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )

    # M1 FIX: enforce the 24-hour expiry the emails already promise.
    # (A NULL expiry is a pre-migration legacy token — the migration
    # grandfathered those accounts to verified, so treat it as expired.)
    token_expires_at = _as_aware_utc(user.email_verification_token_expires_at)
    if token_expires_at is None or token_expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )

    # Mark email as verified
    user.is_email_verified = True
    user.email_verification_token = None
    user.email_verification_token_expires_at = None
    # M1: verification satisfies any immediate-verification requirement
    # (invitation-accepted accounts).
    user.email_verification_required = False
    # Audit gap FIX (was INFO-only in middleware).
    await log_audit_event(
        db, user, "email_verified", "user", user.id, request
    )
    await _await_if_needed(db.commit())

    return {"message": "Email verified successfully"}


@router.post("/reset-password")
@limiter.limit("5/minute")  # SECURITY: Prevent brute force
async def reset_password(
    request: Request,
    reset_in: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Reset password with token
    """
    # Validate reset token using separate table
    from datetime import datetime
    from app.core.security import hash_token

    # SECURITY FIX: Hash the provided token to compare with stored hash
    token_hash = hash_token(reset_in.token)

    # Only check hashed tokens (no legacy plaintext fallback)
    result = await _await_if_needed(
        db.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.is_used.is_(False),
                PasswordResetToken.expires_at > datetime.now(timezone.utc)
            )
        )
    )
    password_reset = result.scalar_one_or_none()

    if not password_reset:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    # Get user from token
    user_result = await _await_if_needed(
        db.execute(
            select(User).where(User.id == password_reset.user_id)
        )
    )
    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    # Validate password strength
    is_valid, error_message = validate_password_strength(reset_in.new_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message,
        )

    # Update user password
    user.password_hash = get_password_hash(reset_in.new_password)
    user.password_changed_at = datetime.now(timezone.utc)

    # SECURITY FIX: Invalidate all sessions on password change
    await _await_if_needed(
        db.execute(
            delete(UserSession).where(UserSession.user_id == user.id)
        )
    )
    # Mark reset token as used
    password_reset.is_used = True
    password_reset.used_at = datetime.now(timezone.utc)

    # Audit gap FIX (was INFO-only in middleware).
    await log_audit_event(
        db, user, "password_reset_completed", "user", user.id, request
    )
    await _await_if_needed(db.commit())

    return {"message": "Password reset successful"}


@router.post("/change-password", response_model=LoginResponse)
@limiter.limit("5/minute")  # M-1 FIX: throttle current_password guessing inside a stolen session
async def change_password(
    request: Request,
    payload: PasswordChange,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _csrf: bool = Depends(verify_csrf),
) -> LoginResponse:
    """
    Change the signed-in user's password (self-service; also used for the
    admin-set temporary password on first login).
    """
    result = await _await_if_needed(
        db.execute(select(User).where(User.id == current_user.id))
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    is_valid, error_message = validate_password_strength(payload.new_password)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_message)

    user.password_hash = get_password_hash(payload.new_password)
    user.password_changed_at = datetime.now(timezone.utc)
    # Self-service rotation satisfies the forced first-login change.
    user.must_change_password = False

    # SECURITY: a password change invalidates every refresh session (theft
    # containment), then a fresh session is issued so the caller stays
    # signed in on this device.
    await _await_if_needed(
        db.execute(delete(UserSession).where(UserSession.user_id == user.id))
    )

    token_data = {
        "sub": str(user.id),
        "role": user.role.value,
        "practice_id": str(user.practice_id),
    }
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    from app.core.security import hash_token
    db.add(UserSession(
        user_id=user.id,
        token_hash=hash_token(refresh_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    ))
    # Audit gap FIX (was INFO-only in middleware).
    await log_audit_event(
        db, user, "password_changed", "user", user.id, request
    )
    await _await_if_needed(db.commit())

    from app.core.security import generate_csrf_token
    from fastapi.responses import JSONResponse
    csrf_token = generate_csrf_token()
    is_production = settings.ENVIRONMENT == "production"
    response = JSONResponse(content={
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "csrf_token": csrf_token,
        "must_change_password": bool(user.must_change_password),
        "message": "Password changed successfully",
    })
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=True,
        secure=is_production,
        samesite="none" if is_production else "lax",
        max_age=86400,
        path="/",
    )
    _set_refresh_cookie(response, refresh_token)
    return response


# ---------------------------------------------------------------------------
# Staff invitation onboarding (public, token-holder-facing endpoints)
# ---------------------------------------------------------------------------

# How long an invitation link stays usable. The admin can resend it to mint
# a fresh token once expired.
INVITATION_TOKEN_EXPIRY_HOURS = 72


async def _find_open_invitation(db, token: str):
    """Resolve a plaintext invitation token to a live, unexpired, unaccepted
    invitation row, or None. Tokens are stored hashed, never plaintext."""
    from app.core.security import hash_token as _hash_token
    from app.models.staff_invitation import StaffInvitation

    token_hash = _hash_token(token)
    result = await _await_if_needed(
        db.execute(select(StaffInvitation).where(StaffInvitation.token_hash == token_hash))
    )
    invitation = result.scalar_one_or_none()
    if invitation is None or invitation.accepted_at is not None:
        return None
    expires_at = _as_aware_utc(invitation.expires_at)
    if expires_at is None or expires_at < datetime.now(timezone.utc):
        return None
    return invitation


@router.post("/invitations/validate")
@limiter.limit("10/minute")
async def validate_invitation(
    request: Request,
    payload: InvitationValidateRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Validate a body-carried invitation token without URL leakage."""
    del request  # consumed by the rate limiter
    from app.models.practice import Practice

    invitation = await _find_open_invitation(db, payload.token)
    if invitation is None:
        return {
            "email": None,
            "firstName": None,
            "lastName": None,
            "role": None,
            "practiceName": None,
            "invitedBy": None,
            "isValid": False,
        }

    practice_result = await _await_if_needed(
        db.execute(select(Practice).where(Practice.id == invitation.practice_id))
    )
    practice = practice_result.scalar_one_or_none()

    inviter_name = None
    if invitation.invited_by:
        inviter_result = await _await_if_needed(
            db.execute(select(User).where(User.id == invitation.invited_by))
        )
        inviter = inviter_result.scalar_one_or_none()
        inviter_name = inviter.full_name if inviter else None

    return {
        "email": invitation.email,
        "firstName": invitation.first_name,
        "lastName": invitation.last_name,
        "role": invitation.role.value.lower(),
        "practiceName": practice.name if practice else None,
        "invitedBy": inviter_name or "your practice administrator",
        "isValid": True,
    }


@router.post("/invitations/accept")
@limiter.limit("10/minute")  # F-11 FIX: throttle invite-token guessing + account-creation spam
async def accept_invitation(
    request: Request,
    payload: StaffInvitationAccept,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Accept an invitation by choosing the account password.

    The invitee sets their own password (validated against policy), so no
    temporary password is ever shared out-of-band. The created account does
    NOT carry must_change_password, because the password is self-chosen.

    M1 FIX: the 72h invitation link is proof that someone who could open the
    link knew its URL — not that the invited inbox is under the accepter's
    control. The account is therefore created UNVERIFIED and must confirm the
    standard verification email before login; the admin-assigned role is kept.
    """
    invitation = await _find_open_invitation(db, payload.token)
    if invitation is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired invitation link",
        )

    is_valid, error_message = validate_password_strength(payload.password)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_message)

    existing = await _await_if_needed(
        db.execute(select(User).where(User.email == invitation.email))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    # QUOTA: minting an account here consumes a user seat, so the same
    # plan limits.users cap that guards POST /staff/ must also guard the
    # invitation-accept path — otherwise a full practice could grow unbounded
    # through invites. No-op when there is no active plan limit configured.
    from app.services.plan_quota import ensure_quota_available

    await ensure_quota_available(db, invitation.practice_id, "users")

    # Standard verification flow, exactly as self-registration uses it: a
    # fresh token (hashed at rest, 24h expiry) plus the verification email.
    from app.core.security import hash_token as _hash_token

    verification_token = generate_password_reset_token()
    user = User(
        email=invitation.email,
        password_hash=get_password_hash(payload.password),
        first_name=invitation.first_name,
        last_name=invitation.last_name,
        role=invitation.role,
        practice_id=invitation.practice_id,
        is_active=True,
        is_email_verified=False,
        email_verification_required=True,
        email_verification_token=_hash_token(verification_token),
        email_verification_token_expires_at=(
            datetime.now(timezone.utc)
            + timedelta(hours=EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS)
        ),
        must_change_password=False,
    )
    db.add(user)

    invitation.accepted_at = datetime.now(timezone.utc)

    await _await_if_needed(db.commit())

    try:
        from app.core.email_tasks import enqueue_email
        from html import escape as _html_escape

        verification_link = f"{settings.FRONTEND_URL}/verify-email?code={verification_token}"
        enqueue_email(
            to=user.email,
            subject="Verify Your Email - CoreDent",
            html_content=(
                f"<p>Welcome to CoreDent, {_html_escape(user.first_name or '')}!</p>"
                "<p>Your practice administrator invited you. Please verify your "
                "email to finish activating your account:</p>"
                f'<p><a href="{_html_escape(verification_link, quote=True)}">'
                "Verify Email</a></p>"
                "<p>This link expires in 24 hours. Your invitation link remains "
                "valid for 72 hours in case you need to start over.</p>"
            ),
            text_content=(
                f"Welcome to CoreDent! Verify your email to activate your "
                f"account: {verification_link}"
            ),
        )
    except Exception as exc:
        log_email_failure(exc, "invite_accept_verification", user.email)

    return {
        "message": (
            "Invitation accepted. Check your inbox to verify your email "
            "address before signing in."
        )
    }