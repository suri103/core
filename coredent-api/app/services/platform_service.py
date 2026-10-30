"""
Platform (Super Admin) Service

Business logic for the SaaS operator's own internal console. Everything in
this module deliberately operates ACROSS tenants â€” that is its purpose â€”
and is therefore only ever called from endpoints guarded by
``require_super_admin`` (never from clinic-facing routes).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, cast
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.audit import AuditLog
from app.models.patient import Patient
from app.models.practice import Practice
from app.models.subscription import (
    Subscription,
    SubscriptionInterval,
    SubscriptionStatus,
)
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

# The interval->months map used to normalize any plan price to MRR.
_INTERVAL_TO_MONTHS = {
    SubscriptionInterval.WEEKLY: Decimal(1) / Decimal(4),
    SubscriptionInterval.MONTHLY: Decimal(1),
    SubscriptionInterval.QUARTERLY: Decimal(3),
    SubscriptionInterval.SEMI_ANNUAL: Decimal(6),
    SubscriptionInterval.ANNUAL: Decimal(12),
}


def _as_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """Best-effort tz-normalization (SQLite returns naive datetimes)."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


class PlatformService:
    """Cross-tenant reads + administrative actions for the SaaS operator."""

    # ------------------------------------------------------------------
    # Metrics / dashboard
    # ------------------------------------------------------------------

    @staticmethod
    async def get_platform_metrics(db: AsyncSession) -> Dict[str, Any]:
        """Whole-platform KPIs: clinics, users, MRR, churn, failed payments."""
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        total_clinics = (
            await db.execute(select(func.count(Practice.id)))
        ).scalar_one()
        active_clinics = (
            await db.execute(
                select(func.count(Practice.id)).where(Practice.is_active.is_(True))
            )
        ).scalar_one()
        total_users = (
            await db.execute(select(func.count(User.id)))
        ).scalar_one()
        active_users = (
            await db.execute(
                select(func.count(User.id)).where(User.is_active.is_(True))
            )
        ).scalar_one()
        new_registrations = (
            await db.execute(
                select(func.count(Practice.id)).where(
                    Practice.created_at >= month_start
                )
            )
        ).scalar_one()

        # Collapse practice-level subscriptions (patient_id NULL) to the
        # newest row per practice, then compute SaaS KPIs from that set.
        subs_result = await db.execute(
            select(Subscription)
            .options(selectinload(Subscription.plan))
            .where(Subscription.patient_id.is_(None))
        )
        subs = subs_result.scalars().all()
        per_practice: Dict[UUID, Subscription] = {}
        for sub in subs:
            # practice_id is a SQLAlchemy Column at the class level, so mypy
            # infers Column[UUID] on the instance and rejects it as a dict key.
            pid = cast(UUID, sub.practice_id)
            if pid is None:
                continue
            current = per_practice.get(pid)
            if current is None or (sub.updated_at or sub.created_at) >= (
                current.updated_at or current.created_at
            ):
                per_practice[pid] = sub
        latest_subs = list(per_practice.values())

        active_subs = [s for s in latest_subs if s.status == SubscriptionStatus.ACTIVE]
        trialing_subs = [s for s in latest_subs if s.status == SubscriptionStatus.TRIALING]
        past_due_subs = [s for s in latest_subs if s.status == SubscriptionStatus.PAST_DUE]
        canceled_this_month = [
            s
            for s in latest_subs
            if s.status == SubscriptionStatus.CANCELED
            and s.canceled_at
            and _as_aware(s.canceled_at) >= month_start
        ]

        mrr = Decimal("0")
        for sub in active_subs:
            if sub.plan is None:
                continue
            months = _INTERVAL_TO_MONTHS.get(sub.plan.interval)
            if months is None or months == 0:
                continue
            amount = Decimal(str(sub.plan.amount or 0))
            mrr += (amount / months).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        denominator = len(active_subs) + len(canceled_this_month)
        churn_rate = (
            round(len(canceled_this_month) / denominator * 100, 2)
            if denominator > 0
            else 0.0
        )

        return {
            "total_clinics": total_clinics,
            "active_clinics": active_clinics,
            "suspended_clinics": total_clinics - active_clinics,
            "total_users": total_users,
            "active_users": active_users,
            "active_subscriptions": len(active_subs),
            "trialing_subscriptions": len(trialing_subs),
            "past_due_subscriptions": len(past_due_subs),
            "failed_payment_clinics": len(past_due_subs),
            "mrr": mrr,
            "churn_rate_percent": churn_rate,
            "new_registrations_this_month": new_registrations,
            "canceled_this_month": len(canceled_this_month),
        }


    # ------------------------------------------------------------------
    # Clinic management
    # ------------------------------------------------------------------

    @staticmethod
    async def list_clinics(
        db: AsyncSession,
        *,
        search: Optional[str] = None,
        status_filter: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Cross-tenant clinic directory with search + pagination."""
        filters = []
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(
                or_(
                    Practice.name.ilike(pattern),
                    Practice.email.ilike(pattern),
                    Practice.public_slug.ilike(pattern),
                )
            )
        if status_filter == "active":
            filters.append(Practice.is_active.is_(True))
        elif status_filter == "suspended":
            filters.append(Practice.is_active.is_(False))

        where = filters if filters else []
        total = (
            await db.execute(select(func.count(Practice.id)).where(*where))
        ).scalar_one()

        result = await db.execute(
            select(Practice)
            .where(*where)
            .order_by(Practice.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        practices = result.scalars().all()

        # Per-clinic user + patient counts in two grouped queries (avoids N+1).
        clinic_ids = [p.id for p in practices]
        user_counts: Dict[UUID, int] = {}
        patient_counts: Dict[UUID, int] = {}
        if clinic_ids:
            rows = await db.execute(
                select(User.practice_id, func.count(User.id))
                .where(User.practice_id.in_(clinic_ids))
                .group_by(User.practice_id)
            )
            user_counts = {pid: cnt for pid, cnt in rows.all()}

            rows = await db.execute(
                select(Patient.practice_id, func.count(Patient.id))
                .where(Patient.practice_id.in_(clinic_ids))
                .group_by(Patient.practice_id)
            )
            patient_counts = {pid: cnt for pid, cnt in rows.all()}

        items = [
            {
                "id": str(p.id),
                "name": p.name,
                "public_slug": p.public_slug,
                "email": p.email,
                "is_active": bool(p.is_active),
                "country": p.country,
                "timezone": p.timezone,
                "currency": p.currency,
                "user_count": user_counts.get(p.id, 0),
                "patient_count": patient_counts.get(p.id, 0),
                "created_at": p.created_at,
            }
            for p in practices
        ]
        return {"clinics": items, "total": total, "limit": limit, "offset": offset}

    @staticmethod
    async def get_clinic_detail(db: AsyncSession, practice_id: UUID) -> Dict[str, Any]:
        """Full cross-tenant view of one clinic: users, subscription, usage."""
        result = await db.execute(select(Practice).where(Practice.id == practice_id))
        practice = result.scalar_one_or_none()
        if not practice:
            return {}

        users_result = await db.execute(
            select(User)
            .where(User.practice_id == practice_id)
            .order_by(User.created_at.desc())
            .limit(200)
        )
        users = users_result.scalars().all()

        sub_result = await db.execute(
            select(Subscription)
            .options(selectinload(Subscription.plan))
            .where(
                Subscription.practice_id == practice_id,
                Subscription.patient_id.is_(None),
            )
            .order_by(Subscription.updated_at.desc().nullslast())
            .limit(1)
        )
        subscription = sub_result.scalars().first()

        patient_count = (
            await db.execute(
                select(func.count(Patient.id)).where(
                    Patient.practice_id == practice_id
                )
            )
        ).scalar_one()

        sub_payload = None
        if subscription is not None:
            sub_payload = {
                "id": str(subscription.id),
                "status": (
                    subscription.status.value
                    if hasattr(subscription.status, "value")
                    else str(subscription.status)
                ),
                "plan_name": subscription.plan.name if subscription.plan else None,
                "plan_amount": (
                    float(subscription.plan.amount) if subscription.plan else None
                ),
                "current_period_end": subscription.current_period_end,
                "trial_end": subscription.trial_end,
            }

        return {
            "clinic": {
                "id": str(practice.id),
                "name": practice.name,
                "public_slug": practice.public_slug,
                "email": practice.email,
                "phone": practice.phone,
                "is_active": bool(practice.is_active),
                "country": practice.country,
                "timezone": practice.timezone,
                "currency": practice.currency,
                "created_at": practice.created_at,
            },
            "users": [
                {
                    "id": str(u.id),
                    "email": u.email,
                    "full_name": u.full_name,
                    "role": u.role.value if hasattr(u.role, "value") else str(u.role),
                    "is_active": bool(u.is_active),
                    "last_login": u.last_login,
                    "is_email_verified": bool(u.is_email_verified),
                }
                for u in users
            ],
            "subscription": sub_payload,
            "patient_count": patient_count,
        }

    @staticmethod
    async def set_clinic_status(
        db: AsyncSession, practice_id: UUID, *, is_active: bool
    ) -> Practice:
        """Suspend (is_active=False) or reactivate a clinic tenant.

        Suspension blocks new logins for that practice's users (login rejects
        inactive practices) without deleting any data â€” reversible at any time.
        """
        result = await db.execute(select(Practice).where(Practice.id == practice_id))
        practice = result.scalar_one_or_none()
        if not practice:
            raise ValueError("Clinic not found")
        practice.is_active = is_active
        await db.flush()
        return practice

    # ------------------------------------------------------------------
    # User management
    # ------------------------------------------------------------------

    @staticmethod
    async def list_users(
        db: AsyncSession,
        *,
        search: Optional[str] = None,
        role: Optional[str] = None,
        practice_id: Optional[UUID] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Cross-tenant user directory (with clinic name) for the console."""
        filters = []
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(
                or_(
                    User.email.ilike(pattern),
                    User.first_name.ilike(pattern),
                    User.last_name.ilike(pattern),
                )
            )
        if role:
            try:
                filters.append(User.role == UserRole(role.upper()))
            except ValueError:
                raise ValueError(f"Unknown role: {role}")
        if practice_id:
            filters.append(User.practice_id == practice_id)

        where = filters if filters else []
        total = (
            await db.execute(select(func.count(User.id)).where(*where))
        ).scalar_one()

        result = await db.execute(
            select(User, Practice.name)
            .join(Practice, User.practice_id == Practice.id, isouter=True)
            .where(*where)
            .order_by(User.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = result.all()

        items = [
            {
                "id": str(u.id),
                "email": u.email,
                "full_name": u.full_name,
                "role": u.role.value if hasattr(u.role, "value") else str(u.role),
                "practice_id": str(u.practice_id),
                "practice_name": pname,
                "is_active": bool(u.is_active),
                "is_email_verified": bool(u.is_email_verified),
                "last_login": u.last_login,
                "created_at": u.created_at,
            }
            for u, pname in rows
        ]
        return {"users": items, "total": total, "limit": limit, "offset": offset}

    @staticmethod
    async def set_user_active(
        db: AsyncSession, user_id: UUID, *, is_active: bool
    ) -> User:
        """Deactivate (is_active=False) or reactivate a user platform-wide.

        SUPER_ADMIN accounts cannot be deactivated this way: locking out the
        last operator would orphan the console. Returns the user for logging.
        """
        result = await db.execute(select(User).where(User.id == user_id))
        target = result.scalar_one_or_none()
        if not target:
            raise ValueError("User not found")
        if target.role == UserRole.SUPER_ADMIN:
            raise PermissionError("Super-admin accounts cannot be deactivated here")
        target.is_active = is_active
        await db.flush()
        return target

    # ------------------------------------------------------------------
    # Billing / subscriptions
    # ------------------------------------------------------------------

    @staticmethod
    async def list_subscriptions(
        db: AsyncSession,
        *,
        status_filter: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Platform-wide subscription directory (clinic-level only)."""
        filters = [Subscription.patient_id.is_(None)]
        if status_filter:
            try:
                filters.append(
                    Subscription.status == SubscriptionStatus(status_filter.lower())
                )
            except ValueError:
                raise ValueError(f"Unknown subscription status: {status_filter}")

        total = (
            await db.execute(
                select(func.count(Subscription.id)).where(*filters)
            )
        ).scalar_one()

        result = await db.execute(
            select(Subscription)
            .options(selectinload(Subscription.plan))
            .join(Practice, Subscription.practice_id == Practice.id, isouter=True)
            .where(*filters)
            .order_by(Subscription.updated_at.desc().nullslast())
            .offset(offset)
            .limit(limit)
        )
        rows = result.scalars().unique().all()

        items = []
        for s in rows:
            items.append(
                {
                    "id": str(s.id),
                    "practice_id": str(s.practice_id),
                    "status": (
                        s.status.value if hasattr(s.status, "value") else str(s.status)
                    ),
                    "plan_name": s.plan.name if s.plan else None,
                    "plan_amount": float(s.plan.amount) if s.plan else None,
                    "interval": (
                        s.plan.interval.value
                        if s.plan and hasattr(s.plan.interval, "value")
                        else None
                    ),
                    "current_period_end": s.current_period_end,
                    "trial_end": s.trial_end,
                    "canceled_at": s.canceled_at,
                }
            )
        return {
            "subscriptions": items,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    # ------------------------------------------------------------------
    # Security console
    # ------------------------------------------------------------------

    @staticmethod
    async def list_recent_audit_events(
        db: AsyncSession,
        *,
        limit: int = 50,
        offset: int = 0,
        action_contains: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Recent audit events, platform-wide, for the security console feed."""
        filters = []
        if action_contains:
            filters.append(AuditLog.action.ilike(f"%{action_contains.strip()}%"))

        total = (
            await db.execute(
                select(func.count(AuditLog.id)).where(*filters)
            )
        ).scalar_one()

        result = await db.execute(
            select(AuditLog)
            .where(*filters)
            .order_by(AuditLog.created_at.desc())
            .offset(offset)
            .limit(min(limit, 200))
        )
        logs = result.scalars().all()

        # Resolve actor emails in one query (audit rows only store user_id).
        user_ids = list({l.user_id for l in logs if l.user_id})
        actors: Dict[UUID, str] = {}
        if user_ids:
            rows = await db.execute(
                select(User.id, User.email).where(User.id.in_(user_ids))
            )
            actors = {uid: email for uid, email in rows.all()}

        items = [
            {
                "id": str(l.id),
                "action": l.action,
                "entity_type": l.entity_type,
                "entity_id": str(l.entity_id) if l.entity_id else None,
                "user_id": str(l.user_id) if l.user_id else None,
                "actor_email": actors.get(l.user_id) if l.user_id else None,
                "ip_address": l.ip_address,
                "created_at": l.created_at,
            }
            for l in logs
        ]
        return {"events": items, "total": total, "limit": limit, "offset": offset}

