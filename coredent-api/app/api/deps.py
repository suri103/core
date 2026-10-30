"""
API Dependencies
Reusable dependencies for FastAPI endpoints
"""

import hmac
import logging
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status, Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Optional, Union
from uuid import UUID

from app.core.database import get_db, SessionLocal
from app.core.config_simple import settings, _LOCAL_ENVIRONMENTS
from app.core.security import decode_token, verify_csrf_token
from app.models.user import User, UserRole
from app.models.subscription import Subscription, SubscriptionStatus

logger = logging.getLogger(__name__)


def get_sync_db():
    """Sync database session for synchronous (threadpool) endpoints."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# HTTP Bearer token scheme
security = HTTPBearer()

# Endpoints reachable while must_change_password is armed. Everything else
# is closed until the user rotates the admin-handed-out temporary password:
# the profile read the UI needs to render the force-change screen, the
# password change itself, and session hygiene (CSRF bootstrap, rotation,
# logout).
_FORCE_CHANGE_ALLOWED_PATHS = {
    "/api/v1/auth/change-password",
    "/api/v1/auth/me",
    "/api/v1/auth/csrf",
    "/api/v1/auth/refresh",
    "/api/v1/auth/logout",
}


_SUBSCRIPTION_BYPASS_PATH_PREFIXES = (
    "/api/v1/auth/",
    "/api/v1/subscriptions",
    "/api/v1/stripe/",
    # Platform console is cross-tenant SaaS-ops, not clinic app usage; the
    # super admin's own bootstrap practice carries no billable subscription.
    "/api/v1/platform/",
)


def _as_aware(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _subscription_is_current(subscription: Subscription, now: datetime) -> bool:
    """Return whether a practice subscription currently permits app access.

    Policy is intentionally explicit: active subscriptions are allowed;
    trialing subscriptions require a future trial_end; canceled subscriptions
    remain available through current_period_end; past_due subscriptions have a
    configurable seven-day default grace period; paused subscriptions remain
    available only through paused_until. Expired, unpaid, incomplete, and
    missing subscriptions are denied rather than silently granting service.
    """
    status_value = getattr(subscription.status, "value", subscription.status)
    status_value = str(status_value).lower()
    if status_value == SubscriptionStatus.ACTIVE.value:
        return True
    if status_value == SubscriptionStatus.TRIALING.value:
        trial_end = _as_aware(subscription.trial_end)
        return trial_end is not None and now <= trial_end
    if status_value == SubscriptionStatus.CANCELED.value:
        period_end = _as_aware(subscription.current_period_end)
        return period_end is not None and now <= period_end
    if status_value == SubscriptionStatus.PAST_DUE.value:
        anchor = _as_aware(
            getattr(subscription, "updated_at", None)
            or getattr(subscription, "current_period_end", None)
            or getattr(subscription, "created_at", None)
        )
        if anchor is None:
            return False
        grace_days = max(0, settings.SUBSCRIPTION_PAST_DUE_GRACE_DAYS)
        return now <= anchor + timedelta(days=grace_days)
    if status_value == SubscriptionStatus.PAUSED.value:
        paused_until = _as_aware(subscription.paused_until)
        return paused_until is not None and now <= paused_until
    return False


async def _enforce_subscription_access(
    db: Union[AsyncSession, Session], user: User, request: Optional[Request]
) -> None:
    """Gate authenticated application access by the practice subscription.

    Local and test environments intentionally bypass this billing policy so
    development and CI can exercise the app without provisioning a processor
    account. Subscription, payment, and authentication routes remain usable
    for renewal/reactivation when an account is delinquent.
    """
    if settings.ENVIRONMENT in _LOCAL_ENVIRONMENTS:
        return
    path = request.url.path if request is not None else ""
    if any(path.startswith(prefix) for prefix in _SUBSCRIPTION_BYPASS_PATH_PREFIXES):
        return
    try:
        stmt = (
            select(Subscription)
            .where(
                Subscription.practice_id == user.practice_id,
                Subscription.patient_id.is_(None),
            )
            .order_by(Subscription.updated_at.desc().nullslast())
            .limit(1)
        )
        if isinstance(db, AsyncSession):
            result = await db.execute(stmt)
        else:
            result = db.execute(stmt)
        subscription = result.scalars().first()
    except Exception as exc:
        logger.error("Subscription access check failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Subscription service is temporarily unavailable",
        ) from exc

    if not subscription or not _subscription_is_current(subscription, datetime.now(timezone.utc)):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="An active subscription or valid trial is required to access this practice.",
        )


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Union[AsyncSession, Session] = Depends(get_db),
    request: Request = None,
) -> User:
    # Bearer-header only by design: no endpoint ever sets an access-token
    # cookie, and a cookie fallback would re-open CSRF exposure that the
    # Bearer strategy explicitly closed.
    token = credentials.credentials if credentials else None
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials", headers={"WWW-Authenticate": "Bearer"})
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials", headers={"WWW-Authenticate": "Bearer"})
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    # SECURITY: Check access-token revocation blacklist (jti claim).
    # H-01: this is now a fail-closed check backed by a durable store, not a
    # process-local deque. See app.core.token_blacklist.
    jti = payload.get("jti")
    if jti:
        from app.core.token_blacklist import is_revoked, is_revoked_sync

        if isinstance(db, AsyncSession):
            revoked = await is_revoked(db, jti)
        else:
            revoked = is_revoked_sync(db, jti)
        if revoked:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    try:
        # Fetch the user and their practice in ONE query (previously this did
        # a second round-trip for the practice on every authenticated request).
        from app.models.practice import Practice
        try:
            uuid_obj = UUID(user_id)
            id_filter = (User.id == uuid_obj)
        except (ValueError, TypeError):
            from sqlalchemy import cast, String
            id_filter = (cast(User.id, String) == user_id)
        query_stmt = (
            select(User, Practice)
            .outerjoin(Practice, Practice.id == User.practice_id)
            .where(id_filter)
        )
        if isinstance(db, AsyncSession):
            result = await db.execute(query_stmt)
        else:
            result = db.execute(query_stmt)
        row = result.first()
        if not row:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        user, practice = row
        user.practice = practice
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive")
        if not user.practice_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not assigned to a practice.")
        if not practice or not practice.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Practice account is suspended or inactive.")
        # First-login security: admin-provisioned accounts carry a temporary
        # password known to the admin. Until the user rotates it themselves,
        # every endpoint outside the password-change flow is closed off — so
        # the handed-out password cannot be used to read PHI.
        if getattr(user, "must_change_password", False):
            request_path = request.url.path.rstrip("/") if request is not None else ""
            if request_path not in _FORCE_CHANGE_ALLOWED_PATHS:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        "You must change your temporary password before accessing "
                        "the application. POST /auth/change-password to continue."
                    ),
                )
        # SECURITY: access tokens issued BEFORE a password change are rejected.
        # A stolen access token therefore no longer survives a password reset
        # for its remaining TTL window. (Refresh sessions are already deleted
        # on reset, and refresh requires the deleted session row to exist.)
        password_changed_at = getattr(user, "password_changed_at", None)
        if password_changed_at is not None:
            from datetime import datetime, timezone as _tz
            issued_at = payload.get("iat")
            try:
                if issued_at is not None:
                    issued_dt = datetime.fromtimestamp(int(issued_at), tz=_tz.utc)
                    changed = password_changed_at
                    if changed.tzinfo is None:
                        changed = changed.replace(tzinfo=_tz.utc)
                    # JWT iat carries only whole-second resolution while
                    # password_changed_at keeps microseconds — compare at the
                    # same precision, otherwise tokens issued after a change
                    # within the same second are rejected and every
                    # password-change flow locks the user out immediately.
                    changed_second = changed.replace(microsecond=0)
                    if issued_dt < changed_second:
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Token is no longer valid. Please sign in again.",
                        )
            except HTTPException:
                raise
            except (ValueError, TypeError, OverflowError):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token is no longer valid. Please sign in again.",
                )
        await _enforce_subscription_access(db, user, request)
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_current_user: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    return current_user


def require_role(*allowed_roles: UserRole):
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions for this action.")
        return current_user
    return role_checker


async def verify_csrf_no_auth(request: Request, x_csrf_token: Optional[str] = Header(None)) -> bool:
    """Verify CSRF token for endpoints where user may not be authenticated"""
    if not x_csrf_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token missing")
    cookie_token = request.cookies.get("csrf_token")
    if not cookie_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF cookie missing")
    if not verify_csrf_token(x_csrf_token, cookie_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")
    return True


async def verify_csrf(request: Request, x_csrf_token: Optional[str] = Header(None), current_user: User = Depends(get_current_user)) -> bool:
    """Verify CSRF token for state-changing requests"""
    if not x_csrf_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token missing")
    cookie_token = request.cookies.get("csrf_token")
    if not cookie_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF cookie missing")
    if not verify_csrf_token(x_csrf_token, cookie_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")
    return True



async def verify_internal_job_token(request: Request) -> bool:
    """Require the shared scheduler token for internal, non-user jobs."""
    provided = request.headers.get("X-Internal-Job-Token") or ""
    expected = settings.MONITORING_TOKEN or ""
    if not expected or not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Internal job authentication required")
    return True



async def verify_twilio_signature(request: Request) -> bool:
    """Validate Twilio HMAC-SHA1 signatures against the full form payload."""
    signature = request.headers.get("X-Twilio-Signature") or ""
    auth_token = getattr(settings, "TWILIO_AUTH_TOKEN", "") or ""
    if not auth_token or not signature:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Twilio webhook is not configured")
    try:
        from twilio.request_validator import RequestValidator
        form = await request.form()
        params = {str(key): str(value) for key, value in form.multi_items()}
        valid = RequestValidator(auth_token).validate(str(request.url), params, signature)
    except ImportError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Twilio webhook is unavailable") from exc
    except Exception as exc:
        logger.warning("Twilio signature validation failed: %s", exc)
        valid = False
    if not valid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid Twilio signature")
    return True



async def get_current_practice_id(current_user: User = Depends(get_current_user)) -> UUID:
    return current_user.practice_id


get_current_practice = get_current_practice_id


class Pagination:
    def __init__(self, page: int = 1, limit: int = 10):
        self.page = max(1, page)
        self.limit = min(100, max(1, limit))
        self.offset = (self.page - 1) * self.limit