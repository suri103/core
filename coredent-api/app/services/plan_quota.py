"""
Plan limit (quota) enforcement.

Plans carry a JSON ``limits`` map such as ``{"patients": 1000, "users": 10}``
(see ``SubscriptionPlan.limits``).  This module exposes a FastAPI dependency
that rejects resource-creation once the practice's current subscription plan
has been exhausted for a dimension, so a plan limit is something the product
actually enforces and not just a number stored in the plan row.

Design rules
------------
* Additive and safe: enforcement only ever *adds* a 403. If there is no
  current subscription, no plan, the plan has not configured a limit for the
  requested dimension, or the limit is negative (unlimited), access is
  granted. Existing trial/legacy accounts behave exactly as before.
* Guided by the real subscription row: the same "is the subscription current"
  policy that gates app access (``deps._subscription_is_current``) decides
  whether a plan's limits apply, so a PAST_DUE/CANCELED account is not quota-
  blocked in a transient way that would compound its own recovery.
* Counted from live data, never from the plan defaults: ``patients`` and
  ``users`` are counted per practice at request time so over-quota writes are
  rejected with current numbers.

Wire-up
-------
    from app.services.plan_quota import enforce_plan_quota

    @router.post("/patients")
    async def create_patient(
        ...,
        _quota: None = Depends(enforce_plan_quota("patients")),
    ) -> ...:

Add a new dimension by extending ``_DIMENSION_COUNTERS`` with a counter
that returns the current usage for the practice.
"""

from datetime import datetime, timezone
from typing import Callable, Dict, Optional, Tuple

from fastapi import Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import _subscription_is_current, get_current_user
from app.core.database import get_db
from app.models.subscription import Subscription, SubscriptionPlan
from app.models.user import User

# Dimensions that can be enforced, keyed by the ``limits`` key used on the
# plan. Extend this map when a new countable resource is added to the plan
# contract (e.g. "storage_gb": sum of document bytes / 2**30).
_DIMENSION_COUNTERS: Dict[str, Callable[[AsyncSession, object], int]] = {}


async def _count_dimension(db: AsyncSession, practice_id: object, dimension: str) -> int:
    counter = _DIMENSION_COUNTERS.get(dimension)
    if counter is None:
        # Unknown dimension -> no enforcement, but stay observable.
        return 0
    return await counter(db, practice_id)


async def _count_patients(db: AsyncSession, practice_id: object) -> int:
    from app.models.patient import Patient

    result = await db.execute(
        select(func.count(Patient.id)).where(Patient.practice_id == practice_id)
    )
    return int(result.scalar() or 0)


async def _count_users(db: AsyncSession, practice_id: object) -> int:
    from app.models.user import User as UserModel

    result = await db.execute(
        select(func.count(UserModel.id)).where(UserModel.practice_id == practice_id)
    )
    return int(result.scalar() or 0)


_DIMENSION_COUNTERS["patients"] = _count_patients
_DIMENSION_COUNTERS["users"] = _count_users


async def _active_plan(
    db: AsyncSession,
    practice_id: object,
    now: Optional[datetime] = None,
) -> Optional[Tuple[SubscriptionPlan, Subscription]]:
    """Return ``(plan, subscription)`` for the practice's *current* plan.

    Uses exactly the ``_subscription_is_current`` policy so this stays in
    lock-step with the app-level subscription gate rather than inventing a
    second, inconsistent definition of "current".
    """
    result = await db.execute(
        select(SubscriptionPlan, Subscription)
        .join(Subscription, Subscription.plan_id == SubscriptionPlan.id)
        .where(
            Subscription.practice_id == practice_id,
            Subscription.patient_id.is_(None),
        )
        .order_by(Subscription.updated_at.desc().nullslast())
        .limit(1)
    )
    row = result.first()
    if row is None:
        return None
    plan, subscription = row
    if not _subscription_is_current(subscription, now or datetime.now(timezone.utc)):
        return None
    return plan, subscription


def enforce_plan_quota(dimension: str):
    """Return a dependency that rejects creation past the plan limit.

    Returns a FastAPI dependency compatible with ``Depends(...)`` for the
    endpoint of the resource that consumes count from ``dimension``.
    """

    async def dependency(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> None:
        await ensure_quota_available(db, current_user.practice_id, dimension)

    return dependency


async def ensure_quota_available(
    db: AsyncSession, practice_id: object, dimension: str
) -> None:
    """Raise HTTP 403 if the practice's plan has reached its ``dimension`` limit.

    Reusable outside the dependency graph (e.g. the public staff-invitation
    accept endpoint, where the actor is an invitee rather than an
    authenticated practice user). No-op in every situation where enforcement
    is undefined: no current subscription, no plan limit for the dimension,
    or a negative (unlimited) limit.
    """
    active = await _active_plan(db, practice_id)
    if active is None:
        return
    plan, _subscription = active

    limits = plan.limits or {}
    if dimension not in limits:
        return
    try:
        limit = int(limits[dimension])
    except (TypeError, ValueError):
        # Non-integer limit values are misconfiguration, not a reason to
        # break creation for paying customers.
        return
    if limit < 0:
        # Negative limit explicitly means "unlimited".
        return

    current = await _count_dimension(db, practice_id, dimension)
    if current >= limit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"{dimension.capitalize()} limit reached for this practice "
                f"({current}/{limit}). Please upgrade your plan to add more."
            ),
        )


# Backward-compatible alias for ensure_quota_available
check_plan_quota = ensure_quota_available