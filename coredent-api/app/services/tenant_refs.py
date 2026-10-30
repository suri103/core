"""Validation of client-supplied foreign-key references against the tenant.

Audit findings H-02, H-04, H-05, H-06, M-09, M-10, M-11, M-12 are all the
same defect wearing different clothes: an endpoint validated the *primary*
entity in the request (usually the patient) and then wrote every other id
from the payload straight into the row. Those ids are attacker-controlled, so
a caller could attach one practice's provider, appointment, insurance policy,
carrier, or lab to another practice's record -- or combine patient A with
patient B's insurance on a claim.

``app.core.tenant_guard`` already rejects a *literal* ``practice_id`` that
disagrees with the JWT. It cannot help here, because these payloads never
mention a practice: they name a child entity whose practice must be looked up.

This module is the missing piece. Every helper:

* returns a generic 404 for both "does not exist" and "belongs to someone
  else", so the API is not a cross-tenant existence oracle;
* names the offending field so legitimate callers can fix their request;
* treats ``None`` as "not supplied" and returns ``None``, so it drops
  cleanly into optional-field validation.

There is deliberately no "skip validation" flag. If a reference cannot be
proven to belong to the tenant, it does not get written.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable, Optional, Sequence, TypeVar
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment, AppointmentType, Chair
from app.models.insurance import InsuranceCarrier, InsurancePreAuthorization, PatientInsurance
from app.models.patient import Patient
from app.models.user import User

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _reject(field: str, detail: Optional[str] = None) -> None:
    """Raise the uniform 404 used for every failed reference check."""
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=detail or f"{field} not found or access denied",
    )


async def require_practice_scoped(
    db: AsyncSession,
    model: type[T],
    obj_id: Optional[UUID],
    practice_id: Optional[UUID],
    *,
    field: str,
    extra_where: Sequence[Any] = (),
) -> Optional[T]:
    """Load ``model`` by id, requiring ``model.practice_id == practice_id``.

    Only for models that carry ``practice_id`` directly. ``extra_where`` adds
    further predicates (e.g. the row must also belong to a given patient).
    """
    if obj_id is None:
        return None
    stmt = select(model).where(
        model.id == obj_id,
        model.practice_id == practice_id,
        *extra_where,
    )
    obj = (await db.execute(stmt)).scalar_one_or_none()
    if obj is None:
        logger.warning(
            "Rejected cross-tenant reference: %s=%s not in practice %s",
            field,
            obj_id,
            practice_id,
        )
        _reject(field)
    return obj


async def require_patient(
    db: AsyncSession,
    patient_id: Optional[UUID],
    practice_id: Optional[UUID],
    *,
    field: str = "Patient",
) -> Optional[Patient]:
    """The patient must belong to the caller's practice."""
    return await require_practice_scoped(
        db, Patient, patient_id, practice_id, field=field
    )


async def require_provider(
    db: AsyncSession,
    provider_id: Optional[UUID],
    practice_id: Optional[UUID],
    *,
    field: str = "Provider",
    roles: Optional[Iterable[Any]] = None,
) -> Optional[User]:
    """The referenced user must be an active member of the caller's practice.

    ``roles``, when given, additionally restricts which roles may be named as
    the provider -- so a front-desk account cannot be recorded as the
    treating clinician on a clinical note.
    """
    if provider_id is None:
        return None
    stmt = select(User).where(
        User.id == provider_id,
        User.practice_id == practice_id,
    )
    user = (await db.execute(stmt)).scalar_one_or_none()
    if user is None:
        logger.warning(
            "Rejected cross-tenant provider reference: %s=%s not in practice %s",
            field,
            provider_id,
            practice_id,
        )
        _reject(field)
    if not getattr(user, "is_active", True):
        _reject(field, f"{field} is not an active user")
    if roles is not None:
        allowed = {getattr(r, "value", r) for r in roles}
        actual = getattr(user.role, "value", user.role)
        if actual not in allowed:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"{field} must be one of: {', '.join(sorted(allowed))} "
                    f"(got '{actual}')"
                ),
            )
    return user


async def require_appointment(
    db: AsyncSession,
    appointment_id: Optional[UUID],
    practice_id: Optional[UUID],
    *,
    patient_id: Optional[UUID] = None,
    field: str = "Appointment",
) -> Optional[Appointment]:
    """The appointment must belong to the practice, and to the patient if given.

    Requiring the patient match matters: linking a clinical note or procedure
    to a *different* patient's appointment inside the same practice mixes two
    patients' records, which is a PHI integrity problem even without a tenant
    crossing.
    """
    extra = (Appointment.patient_id == patient_id,) if patient_id is not None else ()
    return await require_practice_scoped(
        db, Appointment, appointment_id, practice_id, field=field, extra_where=extra
    )


async def require_appointment_type(
    db: AsyncSession,
    type_id: Optional[UUID],
    practice_id: Optional[UUID],
    *,
    field: str = "Appointment type",
) -> Optional[AppointmentType]:
    return await require_practice_scoped(
        db, AppointmentType, type_id, practice_id, field=field
    )


async def require_chair(
    db: AsyncSession,
    chair_id: Optional[UUID],
    practice_id: Optional[UUID],
    *,
    field: str = "Chair",
) -> Optional[Chair]:
    return await require_practice_scoped(db, Chair, chair_id, practice_id, field=field)


async def require_carrier(
    db: AsyncSession,
    carrier_id: Optional[UUID],
    practice_id: Optional[UUID],
    *,
    field: str = "Insurance carrier",
) -> Optional[InsuranceCarrier]:
    """The carrier must be global (``practice_id IS NULL``) or ours.

    M-10: carrier creation and listing were practice-scoped, but attaching a
    carrier to a patient policy loaded it by id alone, so the foreign key
    could cross tenants. ``InsuranceCarrier.practice_id`` is nullable by
    design -- NULL means a shared/global carrier -- so the predicate is
    "global OR mine", not a plain equality.
    """
    if carrier_id is None:
        return None
    stmt = select(InsuranceCarrier).where(
        InsuranceCarrier.id == carrier_id,
        (InsuranceCarrier.practice_id.is_(None))
        | (InsuranceCarrier.practice_id == practice_id),
    )
    carrier = (await db.execute(stmt)).scalar_one_or_none()
    if carrier is None:
        logger.warning(
            "Rejected cross-tenant carrier reference: %s not global and not in practice %s",
            carrier_id,
            practice_id,
        )
        _reject(field)
    return carrier


async def require_patient_insurance(
    db: AsyncSession,
    insurance_id: Optional[UUID],
    practice_id: Optional[UUID],
    *,
    patient_id: Optional[UUID] = None,
    field: str = "Patient insurance",
) -> Optional[PatientInsurance]:
    """The policy must belong to a patient in this practice.

    ``PatientInsurance`` has no ``practice_id`` column, so ownership is proven
    through its patient. When ``patient_id`` is supplied the policy must
    belong to *that* patient -- this is H-02: a claim could otherwise pair
    patient A with patient B's subscriber and payer details.
    """
    if insurance_id is None:
        return None
    stmt = (
        select(PatientInsurance)
        .join(Patient, Patient.id == PatientInsurance.patient_id)
        .where(
            PatientInsurance.id == insurance_id,
            Patient.practice_id == practice_id,
        )
    )
    if patient_id is not None:
        stmt = stmt.where(PatientInsurance.patient_id == patient_id)
    policy = (await db.execute(stmt)).scalar_one_or_none()
    if policy is None:
        logger.warning(
            "Rejected insurance reference: policy=%s patient=%s practice=%s",
            insurance_id,
            patient_id,
            practice_id,
        )
        _reject(
            field,
            "Patient insurance not found, does not belong to this patient, "
            "or access denied",
        )
    return policy


async def require_pre_authorization(
    db: AsyncSession,
    pre_auth_id: Optional[UUID],
    practice_id: Optional[UUID],
    *,
    patient_id: Optional[UUID] = None,
    field: str = "Pre-authorization",
) -> Optional[InsurancePreAuthorization]:
    """Pre-auths are scoped through their patient (no practice_id column)."""
    if pre_auth_id is None:
        return None
    stmt = (
        select(InsurancePreAuthorization)
        .join(Patient, Patient.id == InsurancePreAuthorization.patient_id)
        .where(
            InsurancePreAuthorization.id == pre_auth_id,
            Patient.practice_id == practice_id,
        )
    )
    if patient_id is not None:
        stmt = stmt.where(InsurancePreAuthorization.patient_id == patient_id)
    pre_auth = (await db.execute(stmt)).scalar_one_or_none()
    if pre_auth is None:
        _reject(field)
    return pre_auth
