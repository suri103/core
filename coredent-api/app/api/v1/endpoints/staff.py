"""
Staff Management Endpoints
CRUD operations for practice staff (staff users)
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List
from uuid import UUID
from datetime import datetime, timezone, timedelta

from app.core.database import get_db
from app.api.deps import require_role, verify_csrf
from app.models.user import User, UserRole
from app.models.audit import Session as UserSession
from app.models.staff_invitation import StaffInvitation
from app.core.audit import log_audit_event
from app.core.security import get_password_hash, validate_password_strength
from app.schemas.user import (
    UserResponse,
    UserCreate,
    StaffInvitationCreate,
    StaffInvitationResponse,
)
from app.services.plan_quota import enforce_plan_quota

router = APIRouter()

# How long a staff invitation link stays usable.
INVITATION_EXPIRY_HOURS = 72

# Roles that belong to the SaaS operator, not to a clinic. They are provisioned
# directly (platform bootstrap), never through a practice-scoped route:
# SUPER_ADMIN is the only gate on the cross-tenant /platform/* console, so any
# practice ADMIN or OWNER able to assign it would gain platform-wide access.
_PLATFORM_ONLY_ROLES = frozenset({UserRole.SUPER_ADMIN})


def _validate_practice_role_assignment(role: UserRole | str, actor: User) -> UserRole:
    """Validate an assignment made through a practice-scoped staff route."""
    if not isinstance(role, UserRole):
        try:
            role = UserRole(role.upper()) if isinstance(role, str) else UserRole(role)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid staff role",
            ) from exc

    if role in _PLATFORM_ONLY_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform roles cannot be assigned from a practice-scoped endpoint",
        )
    if role in (UserRole.GROUP_OWNER, UserRole.GROUP_ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Group roles cannot be assigned from a practice-scoped endpoint",
        )
    if role in (UserRole.OWNER, UserRole.ADMIN) and actor.role != UserRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only practice owners can assign owner or admin roles",
        )
    return role


async def _send_invitation_email(invitation: StaffInvitation, token: str, practice_name: str) -> None:
    """Queue an escaped invitation without logging its one-time credential."""
    from html import escape

    from app.core.config_simple import settings
    from app.core.email import log_email_failure
    from app.core.email_tasks import enqueue_email

    accept_link = f"{settings.FRONTEND_URL}/accept-invitation#token={token}"
    safe_first_name = escape(invitation.first_name or "")
    safe_practice_name = escape(practice_name or "CoreDent Practice")
    safe_role = escape(invitation.role.value.replace("_", " ").title())
    subject_practice = (practice_name or "CoreDent Practice").replace("\r", " ").replace("\n", " ").strip()
    try:
        enqueue_email(
            to=invitation.email,
            subject=f"You're invited to join {subject_practice} on CoreDent",
            html_content=(
                f"<p>Hi {safe_first_name},</p>"
                f"<p>You have been invited to join <strong>{safe_practice_name}</strong> "
                f"as <strong>{safe_role}</strong>.</p>"
                f'<p><a href="{escape(accept_link, quote=True)}">Create your account</a></p>'
                f"<p>Or copy this link: {escape(accept_link)}</p>"
                f"<p>This invitation expires in {invitation.expires_at.date()}.</p>"
            ),
            text_content=(
                f"Hi {invitation.first_name},\n\n"
                f"You have been invited to join {practice_name} on CoreDent.\n"
                f"Create your account: {accept_link}\n\n"
                f"This invitation expires on {invitation.expires_at.date()}."
            ),
        )
    except Exception as exc:
        # Centralized reporting records the delivery failure without ever
        # including the token or acceptance URL.
        log_email_failure(exc, "staff_invitation", invitation.email)


@router.get("/", response_model=List[UserResponse])
async def list_staff(
    request: Request,
    is_active: bool = Query(True, description="Filter by active status"),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> List[UserResponse]:
    """
    List all staff members in the practice
    """
    stmt = select(User).where(
        User.practice_id == current_user.practice_id,
        User.is_active == is_active,
    ).order_by(User.role, User.last_name)
    result = await db.execute(stmt)
    staff_members = result.scalars().all()
    await log_audit_event(
        db, current_user, "staff_list_viewed", "user", None, request
    )
    await db.commit()
    return staff_members

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_staff(
    request: Request,
    staff_data: UserCreate,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    _quota: None = Depends(enforce_plan_quota("users")),  # plan users limit
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> UserResponse:
    """
    Add a new staff member to the practice (capped by plan ``limits.users``).
    """
    # Check if email exists
    email = staff_data.email
    stmt = select(User).where(User.email == email)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists"
        )

    # Initial temporary password (staff should change on first login)
    password = staff_data.password
    is_valid, msg = validate_password_strength(password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=msg)

    # Role assignment is centralized so create, update, and invitation flows
    # enforce the same group-role and escalation boundary.
    assigned_role = _validate_practice_role_assignment(staff_data.role, current_user)

    new_staff = User(
        email=email,
        password_hash=get_password_hash(password),
        first_name=staff_data.first_name,
        last_name=staff_data.last_name,
        role=assigned_role,
        practice_id=current_user.practice_id,
        is_active=True,
        # Admin-attested account: there is no email-verification flow for
        # provisioned staff, and unverified accounts lose login access
        # after the grace period.
        is_email_verified=True,
        # The temporary password is known to the admin. Force the user to
        # rotate it on first login before the API gate unlocks.
        must_change_password=True,
    )

    db.add(new_staff)
    await db.flush()

    # The workforce mutation and its HIPAA audit row are one transaction.
    await log_audit_event(
        db, current_user, "staff_created", "user", new_staff.id, request
    )
    await db.commit()
    await db.refresh(new_staff)

    return new_staff

@router.put("/{user_id}", response_model=UserResponse)
async def update_staff(
    request: Request,
    user_id: UUID,
    staff_data: dict,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> UserResponse:
    """
    Update staff member details
    """
    stmt = select(User).where(
        User.id == user_id,
        User.practice_id == current_user.practice_id
    )
    result = await db.execute(stmt)
    staff = result.scalar_one_or_none()

    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")

    # SECURITY: Only an OWNER can modify another OWNER's account in any way.
    # Without this guard an ADMIN could change an OWNER's password and take
    # over the account, bypassing the role-escalation check below.
    if staff.role == UserRole.OWNER and current_user.role != UserRole.OWNER:
        raise HTTPException(
            status_code=403,
            detail="Only practice owners can modify another owner's account",
        )

    # SECURITY: Only OWNER can promote/demote roles
    if "role" in staff_data and current_user.role != UserRole.OWNER:
         raise HTTPException(
             status_code=403, 
             detail="Only practice owners can modify staff roles"
         )

    # SECURITY: Explicit allowlist — mass-assigning the raw dict would let an
    # ADMIN set practice_id (tenant pivot), is_active, locked_until,
    # failed_login_attempts (lockout bypass), etc.
    ALLOWED_FIELDS = {
        "first_name", "last_name", "email", "role", "password",
    }
    # Account-control fields are OWNER-only.
    OWNER_ONLY_FIELDS = {"is_active", "locked_until", "failed_login_attempts"}

    unknown = set(staff_data) - ALLOWED_FIELDS - OWNER_ONLY_FIELDS
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Fields not allowed: {', '.join(sorted(unknown))}",
        )
    if OWNER_ONLY_FIELDS & set(staff_data) and current_user.role != UserRole.OWNER:
        raise HTTPException(
            status_code=403,
            detail="Only practice owners can modify account-control fields",
        )

    if "role" in staff_data:
        staff_data["role"] = _validate_practice_role_assignment(
            staff_data["role"], current_user
        )

    if "password" in staff_data:
        password = staff_data["password"]
        if not isinstance(password, str):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Password must be a string",
            )
        is_valid, msg = validate_password_strength(password)
        if not is_valid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    # Email changes must not collide with another account, and the new
    # address is unverified until the user re-confirms it.
    new_email = staff_data.get("email")
    raw_email_verification_token = None
    if new_email and new_email != staff.email:
        dup = await db.execute(select(User).where(User.email == new_email))
        if dup.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists",
            )
        from app.core.security import generate_password_reset_token, hash_token as _hash_token
        from app.core.config_simple import EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS

        raw_email_verification_token = generate_password_reset_token()
        staff.is_email_verified = False
        staff.email_verification_token = _hash_token(raw_email_verification_token)
        staff.email_verification_token_expires_at = (
            datetime.now(timezone.utc)
            + timedelta(hours=EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS)
        )

    sessions_terminated = False
    for field, value in staff_data.items():
        if field == "password":
             staff.password_hash = get_password_hash(value)
             staff.password_changed_at = datetime.now(timezone.utc)
             # Admin reset hands out another known password — re-arm the
             # forced rotation so the account must change it again.
             staff.must_change_password = True
             sessions_terminated = True
        else:
             setattr(staff, field, value)

    # SECURITY: a password change (admin reset or self-change) must also kill
    # refresh sessions, not just access tokens — otherwise the old refresh
    # token keeps minting new access tokens. Mirrors reset-password behavior
    # (delete rows, not just expire — consistent + no dead-row buildup).
    if sessions_terminated:
        from sqlalchemy import delete as _delete

        await db.execute(
            _delete(UserSession).where(UserSession.user_id == staff.id)
        )

    await db.flush()
    await log_audit_event(
        db,
        current_user,
        "staff_updated",
        "user",
        staff.id,
        request,
        changes={"fields": sorted(staff_data.keys())},
    )
    await db.commit()
    await db.refresh(staff)

    if raw_email_verification_token and staff.email:
        try:
            import html as _html

            from app.core.config_simple import settings
            from app.core.email import log_email_failure
            from app.core.email_tasks import enqueue_email

            verify_link = f"{settings.FRONTEND_URL}/verify-email?code={raw_email_verification_token}"
            safe_name = _html.escape(staff.first_name or "")
            safe_link = _html.escape(verify_link, quote=True)
            enqueue_email(
                to=staff.email,
                subject="CoreDent - Verify Your Updated Email Address",
                html_content=(
                    f"<p>Hi {safe_name},</p>"
                    f"<p>Your CoreDent email address was updated. Please verify it: "
                    f'<a href="{safe_link}">Verify Email</a></p>'
                ),
                text_content=f"Verify your updated CoreDent email address: {verify_link}",
            )
        except Exception as exc:
            log_email_failure(exc, "staff_email_change_verification", staff.email)

    return staff

@router.put("/{user_id}/deactivate", response_model=UserResponse)
async def deactivate_staff_route(
    request: Request,
    user_id: UUID,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> UserResponse:
    """Deactivate a staff member (M-15: route the frontend actually calls)."""
    return await _set_staff_active(request, user_id, False, current_user, db)


@router.put("/{user_id}/reactivate", response_model=UserResponse)
async def reactivate_staff_route(
    request: Request,
    user_id: UUID,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> UserResponse:
    """Reactivate a previously deactivated staff member (M-15)."""
    return await _set_staff_active(request, user_id, True, current_user, db)


async def _set_staff_active(
    request: Request,
    user_id: UUID,
    active: bool,
    current_user: User,
    db: AsyncSession,
) -> UserResponse:
    """Shared activate/deactivate path with identical ownership guards."""
    if not active and user_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot inactivate your own account")

    stmt = select(User).where(
        User.id == user_id,
        User.practice_id == current_user.practice_id
    )
    result = await db.execute(stmt)
    staff = result.scalar_one_or_none()

    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")

    # Expert Hardening: Only an OWNER can change an OWNER-role account.
    # This prevents an ADMIN from locking out (or silently resurrecting) a
    # practice OWNER.
    if staff.role == UserRole.OWNER and current_user.role != UserRole.OWNER:
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions to modify a practice owner account"
        )

    staff.is_active = active

    if not active:
        # Terminate all active sessions IMMEDIATELY upon deactivation.
        await db.execute(
            update(UserSession)
            .where(UserSession.user_id == user_id)
            .values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        )

    await db.flush()
    await log_audit_event(
        db,
        current_user,
        "staff_reactivated" if active else "staff_inactivated",
        "user",
        staff.id,
        request,
    )
    await db.commit()
    await db.refresh(staff)

    return staff


@router.delete("/{user_id}")
async def inactivate_staff(
    request: Request,
    user_id: UUID,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> UserResponse:
    """
    Inactivate a staff member (Soft Delete)
    """
    return await _set_staff_active(request, user_id, False, current_user, db)


# ---------------------------------------------------------------------------
# Staff invitations
# ---------------------------------------------------------------------------


async def _invitation_to_response(
    invitation: StaffInvitation, db: AsyncSession, invited_by_name: str
) -> StaffInvitationResponse:
    return StaffInvitationResponse(
        id=invitation.id,
        email=invitation.email,
        first_name=invitation.first_name,
        last_name=invitation.last_name,
        role=invitation.role,
        invited_by_name=invited_by_name,
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
    )


@router.get("/invitations", response_model=List[StaffInvitationResponse])
async def list_invitations(
    request: Request,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> List[StaffInvitationResponse]:
    """List pending (unexpired, unaccepted) invitations for the practice."""
    result = await db.execute(
        select(StaffInvitation)
        .where(
            StaffInvitation.practice_id == current_user.practice_id,
            StaffInvitation.accepted_at.is_(None),
        )
        .order_by(StaffInvitation.created_at.desc())
    )
    invitations = result.scalars().all()

    # Expiry filtered in Python: SQLite returns naive datetimes, so a SQL
    # comparison would need per-dialect timezone handling for little gain
    # (the pending list is small).
    now = datetime.now(timezone.utc)
    invitations = [
        inv for inv in invitations
        if inv.expires_at is None
        or (inv.expires_at.replace(tzinfo=timezone.utc) if inv.expires_at.tzinfo is None else inv.expires_at) > now
    ]

    inviter_names = {}
    responses = []
    for invitation in invitations:
        inviter_name = inviter_names.get(invitation.invited_by)
        if inviter_name is None and invitation.invited_by:
            inviter_result = await db.execute(
                select(User).where(User.id == invitation.invited_by)
            )
            inviter = inviter_result.scalar_one_or_none()
            inviter_name = inviter.full_name if inviter else "Unknown"
            inviter_names[invitation.invited_by] = inviter_name
        responses.append(
            await _invitation_to_response(
                invitation, db, inviter_name or "Practice administrator"
            )
        )
    await log_audit_event(
        db,
        current_user,
        "staff_invitations_viewed",
        "staff_invitation",
        None,
        request,
    )
    await db.commit()
    return responses


@router.post(
    "/invitations",
    response_model=StaffInvitationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_invitation(
    request: Request,
    invitation_data: StaffInvitationCreate,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> StaffInvitationResponse:
    """
    Invite a new staff member. Issues a one-time acceptance link (72h) so
    the invitee chooses their own password; no temporary password is ever
    communicated.
    """
    from app.core.security import generate_password_reset_token, hash_token

    _validate_practice_role_assignment(invitation_data.role, current_user)

    email = invitation_data.email.lower()

    existing_account = await db.execute(select(User).where(User.email == email))
    if existing_account.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    existing_invitation = await db.execute(
        select(StaffInvitation).where(
            StaffInvitation.practice_id == current_user.practice_id,
            StaffInvitation.email == email,
            StaffInvitation.accepted_at.is_(None),
        )
    )
    if existing_invitation.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A pending invitation already exists for this email",
        )

    token = generate_password_reset_token()
    invitation = StaffInvitation(
        practice_id=current_user.practice_id,
        email=email,
        first_name=invitation_data.first_name,
        last_name=invitation_data.last_name,
        role=invitation_data.role,
        invited_by=current_user.id,
        token_hash=hash_token(token),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=INVITATION_EXPIRY_HOURS),
    )
    db.add(invitation)
    await db.flush()

    from app.models.practice import Practice

    practice_result = await db.execute(
        select(Practice).where(Practice.id == current_user.practice_id)
    )
    practice = practice_result.scalar_one_or_none()

    await log_audit_event(
        db, current_user, "staff_invitation_created", "staff_invitation", invitation.id, request
    )
    await db.commit()
    await db.refresh(invitation)

    # Publish only after the invitation and its audit record are durable.
    await _send_invitation_email(
        invitation, token, practice.name if practice else "your practice"
    )

    return await _invitation_to_response(invitation, db, current_user.full_name)


@router.post("/invitations/{invitation_id}/resend", response_model=StaffInvitationResponse)
async def resend_invitation(
    request: Request,
    invitation_id: UUID,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> StaffInvitationResponse:
    """Resend the invitation email. Mints a fresh token + expiry (an expired
    link cannot be revived)."""
    from app.core.security import generate_password_reset_token, hash_token

    result = await db.execute(
        select(StaffInvitation).where(
            StaffInvitation.id == invitation_id,
            StaffInvitation.practice_id == current_user.practice_id,
        )
    )
    invitation = result.scalar_one_or_none()
    if not invitation or invitation.accepted_at is not None:
        raise HTTPException(status_code=404, detail="Invitation not found")

    token = generate_password_reset_token()
    invitation.token_hash = hash_token(token)
    invitation.expires_at = datetime.now(timezone.utc) + timedelta(
        hours=INVITATION_EXPIRY_HOURS
    )
    await db.flush()

    from app.models.practice import Practice

    practice_result = await db.execute(
        select(Practice).where(Practice.id == current_user.practice_id)
    )
    practice = practice_result.scalar_one_or_none()
    await log_audit_event(
        db, current_user, "staff_invitation_resent", "staff_invitation", invitation.id, request
    )
    await db.commit()
    await db.refresh(invitation)

    # Publish only after the rotated token and its audit record are durable.
    await _send_invitation_email(
        invitation, token, practice.name if practice else "your practice"
    )

    return await _invitation_to_response(invitation, db, current_user.full_name)


@router.delete("/invitations/{invitation_id}")
async def cancel_invitation(
    request: Request,
    invitation_id: UUID,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """Cancel (revoke) a pending invitation."""
    result = await db.execute(
        select(StaffInvitation).where(
            StaffInvitation.id == invitation_id,
            StaffInvitation.practice_id == current_user.practice_id,
        )
    )
    invitation = result.scalar_one_or_none()
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")

    await db.delete(invitation)
    await log_audit_event(
        db, current_user, "staff_invitation_cancelled", "staff_invitation", invitation_id, request
    )
    await db.commit()
    return {"message": "Invitation cancelled"}