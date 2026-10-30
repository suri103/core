"""
Treatment Service
Core business logic for treatment operations
"""

from datetime import date
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.core.business_time import business_date, get_practice_timezone, resolve_date_range
from app.models.treatment import (
    TreatmentPlan,
    TreatmentProcedure,
    TreatmentPlanStatus,
)

logger = logging.getLogger(__name__)


class TreatmentService:
    """Service for treatment operations"""

    @staticmethod
    async def create_treatment_plan(
        db: AsyncSession,
        practice_id: UUID,
        patient_id: UUID,
        provider_id: UUID,
        **kwargs
    ) -> TreatmentPlan:
        """Create a treatment plan dated in the practice's local business day."""
        kwargs["created_date"] = business_date(
            await get_practice_timezone(db, practice_id)
        )
        plan = TreatmentPlan(
            practice_id=practice_id,
            patient_id=patient_id,
            provider_id=provider_id,
            **kwargs
        )
        db.add(plan)
        await db.commit()
        await db.refresh(plan)
        logger.info(f"Created treatment plan: {plan.id}")
        return plan

    @staticmethod
    async def get_treatment_plan(
        db: AsyncSession,
        plan_id: UUID,
        practice_id: Optional[UUID] = None,
    ) -> Optional[TreatmentPlan]:
        """Get a treatment plan"""
        query = select(TreatmentPlan).where(TreatmentPlan.id == plan_id)

        if practice_id:
            query = query.where(TreatmentPlan.practice_id == practice_id)

        result = await db.execute(query)
        return result.scalar_one_or_none()

    # M-11 FIX: treatment-plan status transition matrix. The service previously
    # copied whatever status arrived in kwargs, so a COMPLETED or CANCELLED
    # plan could be reopened, and a plan could jump straight from DRAFT to
    # COMPLETED without ever being presented or accepted. Terminal states are
    # terminal.
    _PLAN_TRANSITIONS: dict[TreatmentPlanStatus, set[TreatmentPlanStatus]] = {
        TreatmentPlanStatus.DRAFT: {
            TreatmentPlanStatus.PRESENTED,
            TreatmentPlanStatus.CANCELLED,
        },
        TreatmentPlanStatus.PRESENTED: {
            TreatmentPlanStatus.ACCEPTED,
            TreatmentPlanStatus.PARTIALLY_ACCEPTED,
            TreatmentPlanStatus.DECLINED,
            TreatmentPlanStatus.CANCELLED,
        },
        TreatmentPlanStatus.ACCEPTED: {
            TreatmentPlanStatus.IN_PROGRESS,
            TreatmentPlanStatus.CANCELLED,
        },
        TreatmentPlanStatus.PARTIALLY_ACCEPTED: {
            TreatmentPlanStatus.IN_PROGRESS,
            TreatmentPlanStatus.ACCEPTED,
            TreatmentPlanStatus.CANCELLED,
        },
        TreatmentPlanStatus.IN_PROGRESS: {
            TreatmentPlanStatus.COMPLETED,
            TreatmentPlanStatus.CANCELLED,
        },
        # Terminal.
        TreatmentPlanStatus.DECLINED: set(),
        TreatmentPlanStatus.COMPLETED: set(),
        TreatmentPlanStatus.CANCELLED: set(),
    }

    # Fields a caller may never set through the generic update path: they are
    # ownership/identity columns or derived totals.
    _PLAN_IMMUTABLE_FIELDS = frozenset(
        {"id", "practice_id", "patient_id", "created_at", "updated_at"}
    )

    @staticmethod
    async def update_treatment_plan(
        db: AsyncSession,
        plan_id: UUID,
        practice_id: UUID,
        **kwargs
    ) -> Optional[TreatmentPlan]:
        """Update a treatment plan.

        M-11 FIX: ``practice_id`` is now required and applied as a query
        predicate. The method used to re-fetch the plan by id alone, so it was
        not safe as a reusable mutation primitive -- any caller that forgot its
        own ownership check could edit another tenant's plan. It also copied
        ``status`` verbatim; transitions are now validated.

        Raises ``ValueError`` for an invalid transition so the endpoint can
        translate it to a 409.
        """
        result = await db.execute(
            select(TreatmentPlan).where(
                TreatmentPlan.id == plan_id,
                TreatmentPlan.practice_id == practice_id,
            )
        )
        plan = result.scalar_one_or_none()

        if not plan:
            return None

        # Handle status changes
        if 'status' in kwargs and kwargs['status'] is not None:
            new_status = kwargs['status']
            if new_status != plan.status:
                allowed = TreatmentService._PLAN_TRANSITIONS.get(plan.status, set())
                if new_status not in allowed:
                    raise ValueError(
                        f"Cannot change treatment plan status from "
                        f"{getattr(plan.status, 'value', plan.status)} to "
                        f"{getattr(new_status, 'value', new_status)}"
                    )
            if new_status == TreatmentPlanStatus.PRESENTED and not plan.presented_date:
                plan.presented_date = business_date(
                    await get_practice_timezone(db, plan.practice_id)
                )
            elif new_status == TreatmentPlanStatus.ACCEPTED and not plan.accepted_date:
                plan.accepted_date = business_date(
                    await get_practice_timezone(db, plan.practice_id)
                )

        for key, value in kwargs.items():
            if key in TreatmentService._PLAN_IMMUTABLE_FIELDS:
                continue
            if hasattr(plan, key):
                setattr(plan, key, value)

        await db.commit()
        await db.refresh(plan)
        logger.info(f"Updated treatment plan: {plan_id}")
        return plan

    @staticmethod
    async def list_treatment_plans(
        db: AsyncSession,
        practice_id: UUID,
        patient_id: Optional[UUID] = None,
        status: Optional[TreatmentPlanStatus] = None,
        provider_id: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[TreatmentPlan]:
        """List treatment plans with filtering."""
        query = (
            select(TreatmentPlan)
            .where(TreatmentPlan.practice_id == practice_id)
            .options(
                joinedload(TreatmentPlan.patient),
                joinedload(TreatmentPlan.provider)
            )
        )

        if patient_id:
            query = query.where(TreatmentPlan.patient_id == patient_id)

        if status:
            query = query.where(TreatmentPlan.status == status)

        if provider_id:
            query = query.where(TreatmentPlan.provider_id == provider_id)

        if start_date:
            query = query.where(TreatmentPlan.created_date >= start_date)

        if end_date:
            query = query.where(TreatmentPlan.created_date <= end_date)

        query = query.order_by(TreatmentPlan.created_date.desc())

        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def list_treatment_plans_page(
        db: AsyncSession,
        practice_id: UUID,
        patient_id: Optional[UUID] = None,
        status: Optional[TreatmentPlanStatus] = None,
        provider_id: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        offset: int = 0,
        limit: int = 50,
    ) -> Tuple[List[TreatmentPlan], int]:
        """Return a bounded treatment-plan page and its filtered total.

        Explicit date predicates use the ``created_date`` date column and are
        resolved in the practice's business timezone. Without a requested
        range, pagination spans the complete practice history.
        """
        if offset < 0:
            raise ValueError("offset must be greater than or equal to zero")
        if not 1 <= limit <= 200:
            raise ValueError("limit must be between 1 and 200")

        filters = [TreatmentPlan.practice_id == practice_id]
        if start_date is not None or end_date is not None:
            practice_timezone = await get_practice_timezone(db, practice_id)
            date_range = resolve_date_range(
                practice_timezone,
                start_date,
                end_date,
                default_days=90,
                max_days=366,
            )
            filters.extend(
                [
                    TreatmentPlan.created_date >= date_range.start_date,
                    TreatmentPlan.created_date <= date_range.end_date,
                ]
            )

        if patient_id:
            filters.append(TreatmentPlan.patient_id == patient_id)
        if status:
            filters.append(TreatmentPlan.status == status)
        if provider_id:
            filters.append(TreatmentPlan.provider_id == provider_id)

        count_result = await db.execute(
            select(func.count()).select_from(TreatmentPlan).where(*filters)
        )
        total = int(count_result.scalar_one() or 0)

        result = await db.execute(
            select(TreatmentPlan)
            .where(*filters)
            .options(
                joinedload(TreatmentPlan.patient),
                joinedload(TreatmentPlan.provider),
            )
            .order_by(TreatmentPlan.created_date.desc(), TreatmentPlan.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all(), total

    @staticmethod
    async def delete_treatment_plan(
        db: AsyncSession,
        plan_id: UUID,
    ) -> bool:
        """Soft delete a treatment plan"""
        result = await db.execute(
            select(TreatmentPlan).where(TreatmentPlan.id == plan_id)
        )
        plan = result.scalar_one_or_none()

        if not plan:
            return False

        plan.status = TreatmentPlanStatus.CANCELLED
        await db.commit()
        logger.info(f"Deleted treatment plan: {plan_id}")
        return True

    @staticmethod
    async def get_plan_statistics(
        db: AsyncSession,
        plan_id: UUID,
    ) -> Dict[str, Any]:
        """Get statistics for a treatment plan"""
        plan = await TreatmentService.get_treatment_plan(db, plan_id)

        if not plan:
            return {}

        # Get procedures
        result = await db.execute(
            select(TreatmentProcedure).where(
                TreatmentProcedure.treatment_plan_id == plan_id
            )
        )
        procedures = result.scalars().all()

        total_procedures = len(procedures)
        accepted_procedures = sum(1 for p in procedures if p.is_accepted)
        completed_procedures = sum(1 for p in procedures if p.status == "completed")

        return {
            "total_procedures": total_procedures,
            "accepted_procedures": accepted_procedures,
            "completed_procedures": completed_procedures,
            "acceptance_rate": (accepted_procedures / total_procedures * 100) if total_procedures > 0 else 0,
            "completion_rate": (completed_procedures / total_procedures * 100) if total_procedures > 0 else 0,
            "total_estimated_cost": float(plan.total_estimated_cost or 0),
            "total_insurance_estimate": float(plan.total_insurance_estimate or 0),
            "total_patient_responsibility": float(plan.total_patient_responsibility or 0),
        }
