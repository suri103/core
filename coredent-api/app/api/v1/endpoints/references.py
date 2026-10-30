"""Reference / lookup endpoints for the scheduling UI.

Provides the provider, chair and appointment-type lookups that the React
scheduling services (`schedulingApi`) resolve against. All routes are
tenant-scoped to the caller's practice and require an authenticated user.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import uuid
from uuid import UUID

from app.core.database import get_db
from app.api.deps import get_current_user, get_current_practice_id, require_role, verify_csrf
from app.models.user import User, UserRole
from app.models.appointment import AppointmentType, Chair
from app.schemas.reference import (
    AppointmentTypeConfigRef,
    AppointmentTypeCreate,
    AppointmentTypeUpdate,
    ChairCreate,
    ChairRef,
    ChairUpdate,
    ProviderRef,
)

router = APIRouter()

# Providers available for scheduling: clinical roles plus owners/admins who
# may also treat patients.
PROVIDER_ROLES = (
    UserRole.DENTIST,
    UserRole.HYGIENIST,
    UserRole.OWNER,
    UserRole.ADMIN,
)

# Standard dental appointment types used as a fallback when a practice has
# not configured its own appointment_types rows yet.
STANDARD_APPOINTMENT_TYPES = [
    {"id": "checkup", "name": "Checkup", "code": "D0150", "duration": 30, "color": "#3B82F6", "allow_online_booking": True},
    {"id": "cleaning", "name": "Cleaning", "code": "D1110", "duration": 60, "color": "#10B981", "allow_online_booking": True},
    {"id": "filling", "name": "Filling", "code": "D2391", "duration": 45, "color": "#F59E0B", "allow_online_booking": False},
    {"id": "crown", "name": "Crown", "code": "D2740", "duration": 60, "color": "#EF4444", "allow_online_booking": False},
    {"id": "extraction", "name": "Extraction", "code": "D7140", "duration": 45, "color": "#8B5CF6", "allow_online_booking": False},
    {"id": "root_canal", "name": "Root Canal", "code": "D3310", "duration": 90, "color": "#EC4899", "allow_online_booking": False},
    {"id": "whitening", "name": "Whitening", "code": "D9972", "duration": 60, "color": "#06B6D4", "allow_online_booking": True},
    {"id": "consultation", "name": "Consultation", "code": "D9310", "duration": 30, "color": "#6366F1", "allow_online_booking": True},
    {"id": "follow_up", "name": "Follow-up", "code": "D0120", "duration": 30, "color": "#14B8A6", "allow_online_booking": True},
    {"id": "emergency", "name": "Emergency", "code": "D0140", "duration": 30, "color": "#DC2626", "allow_online_booking": False},
]


@router.get("/providers", response_model=List[ProviderRef])
async def list_providers(
    practice_id: UUID = Depends(get_current_practice_id),
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ProviderRef]:
    """List clinical providers in the caller's practice."""
    result = await db.execute(
        select(User)
        .where(
            User.practice_id == practice_id,
            User.role.in_(PROVIDER_ROLES),
            User.is_active.is_(True),
        )
        .order_by(User.first_name, User.last_name)
    )
    providers = result.scalars().all()
    return [
        ProviderRef(
            id=provider.id,
            name=f"{provider.first_name or ''} {provider.last_name or ''}".strip(),
            role=provider.role.value if hasattr(provider.role, "value") else str(provider.role),
        )
        for provider in providers
    ]


@router.get("/chairs", response_model=List[ChairRef])
async def list_chairs(
    practice_id: UUID = Depends(get_current_practice_id),
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ChairRef]:
    """List chairs/operatories in the caller's practice."""
    result = await db.execute(
        select(Chair).where(Chair.practice_id == practice_id).order_by(Chair.name)
    )
    chairs = result.scalars().all()
    return [
        ChairRef(
            id=chair.id,
            name=chair.name,
            color=chair.color or "#6B7280",
            description=getattr(chair, "description", None),
            is_active=bool(chair.is_active),
        )
        for chair in chairs
    ]


@router.get("/appointment-types", response_model=List[AppointmentTypeConfigRef])
async def list_appointment_types(
    practice_id: UUID = Depends(get_current_practice_id),
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[AppointmentTypeConfigRef]:
    """List configured appointment types, falling back to the standard set."""
    result = await db.execute(
        select(AppointmentType)
        .where(
            AppointmentType.practice_id == practice_id,
            AppointmentType.is_active.is_(True),
        )
        .order_by(AppointmentType.name)
    )
    configured = result.scalars().all()
    if configured:
        return [
            AppointmentTypeConfigRef(
                id=str(type_row.id),
                name=type_row.name,
                duration=type_row.duration,
                color=type_row.color or "#3B82F6",
                description=type_row.description,
                is_active=bool(type_row.is_active),
            )
            for type_row in configured
        ]

    return [
        AppointmentTypeConfigRef(
            id=entry["id"],
            name=entry["name"],
            code=entry["code"],
            duration=entry["duration"],
            color=entry["color"],
            allow_online_booking=entry["allow_online_booking"],
            description=f"Standard {entry['name']} appointment",
        )
        for entry in STANDARD_APPOINTMENT_TYPES
    ]


# ── Chair / operatory write operations ─────────────────────────────────────
# Scheduling config: restricted to owners/admins. Deletes are soft (is_active
# flipped) so existing appointments that reference the chair keep their FK.

@router.post("/chairs", response_model=ChairRef, status_code=status.HTTP_201_CREATED)
async def create_chair(
    data: ChairCreate,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    _csrf: bool = Depends(verify_csrf),
    db: AsyncSession = Depends(get_db),
) -> ChairRef:
    """Create a chair/operatory in the caller's practice."""
    chair = Chair(
        id=uuid.uuid4(),
        practice_id=current_user.practice_id,
        name=data.name,
        color=data.color or "#6B7280",
        is_active=data.is_active,
    )
    db.add(chair)
    await db.commit()
    await db.refresh(chair)
    return ChairRef(
        id=chair.id,
        name=chair.name,
        color=chair.color or "#6B7280",
        is_active=bool(chair.is_active),
    )


@router.put("/chairs/{chair_id}", response_model=ChairRef)
async def update_chair(
    chair_id: UUID,
    data: ChairUpdate,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    _csrf: bool = Depends(verify_csrf),
    db: AsyncSession = Depends(get_db),
) -> ChairRef:
    """Update a chair/operatory owned by the caller's practice."""
    result = await db.execute(
        select(Chair).where(
            Chair.id == chair_id, Chair.practice_id == current_user.practice_id
        )
    )
    chair = result.scalar_one_or_none()
    if not chair:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chair not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(chair, field, value)
    await db.commit()
    await db.refresh(chair)
    return ChairRef(
        id=chair.id,
        name=chair.name,
        color=chair.color or "#6B7280",
        is_active=bool(chair.is_active),
    )


@router.delete("/chairs/{chair_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chair(
    chair_id: UUID,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    _csrf: bool = Depends(verify_csrf),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete a chair/operatory (keeps appointment history intact)."""
    result = await db.execute(
        select(Chair).where(
            Chair.id == chair_id, Chair.practice_id == current_user.practice_id
        )
    )
    chair = result.scalar_one_or_none()
    if not chair:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chair not found")
    chair.is_active = False
    await db.commit()


# ── Appointment-type write operations ──────────────────────────────────────

@router.post(
    "/appointment-types",
    response_model=AppointmentTypeConfigRef,
    status_code=status.HTTP_201_CREATED,
)
async def create_appointment_type(
    data: AppointmentTypeCreate,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    _csrf: bool = Depends(verify_csrf),
    db: AsyncSession = Depends(get_db),
) -> AppointmentTypeConfigRef:
    """Create an appointment type in the caller's practice."""
    type_row = AppointmentType(
        id=uuid.uuid4(),
        practice_id=current_user.practice_id,
        name=data.name,
        duration=data.duration,
        color=data.color,
        description=data.description,
        is_active=data.is_active,
    )
    db.add(type_row)
    await db.commit()
    await db.refresh(type_row)
    return AppointmentTypeConfigRef(
        id=str(type_row.id),
        name=type_row.name,
        duration=type_row.duration,
        color=type_row.color or "#3B82F6",
        is_active=bool(type_row.is_active),
        description=type_row.description,
    )


@router.put(
    "/appointment-types/{type_id}",
    response_model=AppointmentTypeConfigRef,
)
async def update_appointment_type(
    type_id: UUID,
    data: AppointmentTypeUpdate,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    _csrf: bool = Depends(verify_csrf),
    db: AsyncSession = Depends(get_db),
) -> AppointmentTypeConfigRef:
    """Update an appointment type owned by the caller's practice."""
    result = await db.execute(
        select(AppointmentType).where(
            AppointmentType.id == type_id,
            AppointmentType.practice_id == current_user.practice_id,
        )
    )
    type_row = result.scalar_one_or_none()
    if not type_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Appointment type not found"
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(type_row, field, value)
    await db.commit()
    await db.refresh(type_row)
    return AppointmentTypeConfigRef(
        id=str(type_row.id),
        name=type_row.name,
        duration=type_row.duration,
        color=type_row.color or "#3B82F6",
        is_active=bool(type_row.is_active),
        description=type_row.description,
    )


@router.delete("/appointment-types/{type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_appointment_type(
    type_id: UUID,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    _csrf: bool = Depends(verify_csrf),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete an appointment type (keeps appointment history intact)."""
    result = await db.execute(
        select(AppointmentType).where(
            AppointmentType.id == type_id,
            AppointmentType.practice_id == current_user.practice_id,
        )
    )
    type_row = result.scalar_one_or_none()
    if not type_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Appointment type not found"
        )
    type_row.is_active = False
    await db.commit()