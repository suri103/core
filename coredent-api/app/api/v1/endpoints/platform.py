"""
Platform (Super Admin) Endpoints

The SaaS operator's own internal console — NOT a clinic-facing surface.
Every route here is cross-tenant by design and guarded by
``require_super_admin`` (UserRole.SUPER_ADMIN). Regular clinic roles can
never reach these endpoints; a clinic OWNER is still a tenant user.

TenantGuard note: the middleware rejects any authenticated request whose
URL/query/body carries a ``practice_id`` different from the JWT claim. The
GET routes below take plain pagination/search params (no tenant ids), and
the clinic-action routes take the target practice id as a PATH segment
named ``clinic_id`` (deliberately NOT ``practice_id``) so the guard does not
misread it as the caller's own tenant claim.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role, verify_csrf
from app.core.audit import log_audit_event
from app.core.database import get_db
from app.models.user import User, UserRole
from app.services.platform_service import PlatformService

router = APIRouter()

_DEFAULT_PAGE_SIZE = 50
_MAX_PAGE_SIZE = 200


class ClinicStatusUpdate(BaseModel):
    """Body for suspend/reactivate. Empty on purpose — action is in the path."""
    reason: Optional[str] = None


def _page_params(
    page: int = Query(1, ge=1),
    limit: int = Query(_DEFAULT_PAGE_SIZE, ge=1, le=_MAX_PAGE_SIZE),
) -> tuple[int, int]:
    return (page - 1) * limit, limit


# ---------------------------------------------------------------------------
# Dashboard / metrics
# ---------------------------------------------------------------------------


@router.get("/metrics")
async def get_platform_metrics(
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Platform KPIs: clinics, users, active subscriptions, MRR, churn."""
    return await PlatformService.get_platform_metrics(db)


# ---------------------------------------------------------------------------
# Clinic management
# ---------------------------------------------------------------------------


@router.get("/clinics")
async def list_clinics(
    search: Optional[str] = Query(None, max_length=255),
    status_filter: Optional[str] = Query(
        None, pattern="^(active|suspended)$", description="Filter by clinic status"
    ),
    page: int = Query(1, ge=1),
    limit: int = Query(_DEFAULT_PAGE_SIZE, ge=1, le=_MAX_PAGE_SIZE),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Cross-tenant clinic directory."""
    offset, sz = _page_params(page, limit)
    return await PlatformService.list_clinics(
        db, search=search, status_filter=status_filter, limit=sz, offset=offset
    )


@router.get("/clinics/{clinic_id}")
async def get_clinic_detail(
    clinic_id: UUID,
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """One clinic: users, current subscription, usage counts."""
    detail = await PlatformService.get_clinic_detail(db, clinic_id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Clinic not found"
        )
    return detail


@router.put("/clinics/{clinic_id}/suspend")
async def suspend_clinic(
    clinic_id: UUID,
    body: Optional[ClinicStatusUpdate] = None,
    request: Request = None,
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """Suspend a clinic tenant (reversible; no data deleted)."""
    return await _set_clinic_status(
        clinic_id=clinic_id,
        is_active=False,
        reason=(body.reason if body else None),
        request=request,
        current_user=current_user,
        db=db,
    )


@router.put("/clinics/{clinic_id}/reactivate")
async def reactivate_clinic(
    clinic_id: UUID,
    body: Optional[ClinicStatusUpdate] = None,
    request: Request = None,
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """Reactivate a suspended clinic tenant."""
    return await _set_clinic_status(
        clinic_id=clinic_id,
        is_active=True,
        reason=(body.reason if body else None),
        request=request,
        current_user=current_user,
        db=db,
    )


async def _set_clinic_status(
    *,
    clinic_id: UUID,
    is_active: bool,
    reason: Optional[str],
    request: Optional[Request],
    current_user: User,
    db: AsyncSession,
) -> dict:
    try:
        practice = await PlatformService.set_clinic_status(
            db, clinic_id, is_active=is_active
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    action = "clinic_reactivated" if is_active else "clinic_suspended"
    await log_audit_event(
        db,
        current_user,
        action,
        "practice",
        practice.id,
        request,
        changes={
            "clinic_name": practice.name,
            "is_active": is_active,
            "reason": reason,
        },
    )
    await db.commit()
    return {
        "id": str(practice.id),
        "name": practice.name,
        "is_active": bool(practice.is_active),
        "message": f"Clinic {'reactivated' if is_active else 'suspended'}",
    }


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------


@router.get("/users")
async def list_users(
    search: Optional[str] = Query(None, max_length=255),
    role: Optional[str] = Query(
        None,
        description="Filter by role slug (owner, admin, dentist, accountant, ...)",
    ),
    clinic_id: Optional[UUID] = Query(
        None, description="Restrict to one clinic (cross-tenant by design)"
    ),
    page: int = Query(1, ge=1),
    limit: int = Query(_DEFAULT_PAGE_SIZE, ge=1, le=_MAX_PAGE_SIZE),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Cross-tenant user directory with clinic attribution."""
    offset, sz = _page_params(page, limit)
    try:
        return await PlatformService.list_users(
            db,
            search=search,
            role=role,
            practice_id=clinic_id,
            limit=sz,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


class UserStatusUpdate(BaseModel):
    """Body for platform user deactivate/reactivate. Empty on purpose."""
    reason: Optional[str] = None


async def _set_platform_user_active(
    *,
    user_id: UUID,
    is_active: bool,
    reason: Optional[str],
    request: Optional[Request],
    current_user: User,
    db: AsyncSession,
) -> dict:
    """Shared suspend/reactivate logic with self-deactivation + super-admin guard."""
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="You cannot deactivate your own super-admin account.",
        )
    try:
        target = await PlatformService.set_user_active(
            db, user_id, is_active=is_active
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    action = "platform_user_reactivated" if is_active else "platform_user_deactivated"
    await log_audit_event(
        db,
        current_user,
        action,
        "user",
        target.id,
        request,
        changes={
            "target_email": target.email,
            "is_active": is_active,
            "reason": reason,
        },
    )
    await db.commit()
    return {
        "id": str(target.id),
        "email": target.email,
        "is_active": bool(target.is_active),
        "message": f"User {'reactivated' if is_active else 'deactivated'}",
    }


@router.put("/users/{user_id}/deactivate")
async def deactivate_platform_user(
    user_id: UUID,
    body: Optional[UserStatusUpdate] = None,
    request: Request = None,
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """Deactivate any user platform-wide (reversible; no data deleted)."""
    return await _set_platform_user_active(
        user_id=user_id,
        is_active=False,
        reason=(body.reason if body else None),
        request=request,
        current_user=current_user,
        db=db,
    )


@router.put("/users/{user_id}/reactivate")
async def reactivate_platform_user(
    user_id: UUID,
    body: Optional[UserStatusUpdate] = None,
    request: Request = None,
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """Reactivate a deactivated user platform-wide."""
    return await _set_platform_user_active(
        user_id=user_id,
        is_active=True,
        reason=(body.reason if body else None),
        request=request,
        current_user=current_user,
        db=db,
    )


# ---------------------------------------------------------------------------
# Billing / subscriptions
# ---------------------------------------------------------------------------


@router.get("/subscriptions")
async def list_subscriptions(
    status_filter: Optional[str] = Query(
        None,
        description="Filter by subscription status (active, trialing, past_due, ...)",
    ),
    page: int = Query(1, ge=1),
    limit: int = Query(_DEFAULT_PAGE_SIZE, ge=1, le=_MAX_PAGE_SIZE),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Platform-wide subscription directory (clinic-level plans only)."""
    offset, sz = _page_params(page, limit)
    try:
        return await PlatformService.list_subscriptions(
            db, status_filter=status_filter, limit=sz, offset=offset
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


# ---------------------------------------------------------------------------
# Security console
# ---------------------------------------------------------------------------


@router.get("/audit-events")
async def list_audit_events(
    action_contains: Optional[str] = Query(
        None, max_length=100, description="Substring filter on the audit action"
    ),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Recent platform-wide audit events for the security console."""
    offset, sz = _page_params(page, limit)
    await log_audit_event(
        db,
        current_user,
        "platform_audit_console_viewed",
        "platform",
        None,
        None,
        {},
    )
    await db.commit()
    return await PlatformService.list_recent_audit_events(
        db, limit=sz, offset=offset, action_contains=action_contains
    )

