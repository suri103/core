"""
Treatment Planning Service
Treatment planning logic and phase management
"""

from typing import Optional, List
from uuid import UUID
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.treatment import (
    TreatmentPlan,
    TreatmentPhase,
    TreatmentProcedure,
    TreatmentPlanStatus,
)

logger = logging.getLogger(__name__)


class TreatmentPlanningService:
    """Service for treatment planning operations"""

    @staticmethod
    async def create_treatment_phase(
        db: AsyncSession,
        plan_id: UUID,
        **kwargs
    ) -> TreatmentPhase:
        """Create a new treatment phase"""
        phase = TreatmentPhase(
            treatment_plan_id=plan_id,
            **kwargs
        )
        db.add(phase)
        await db.commit()
        await db.refresh(phase)
        logger.info(f"Created treatment phase: {phase.id}")
        return phase

    @staticmethod
    async def get_treatment_phase(
        db: AsyncSession,
        phase_id: UUID,
    ) -> Optional[TreatmentPhase]:
        """Get a treatment phase"""
        result = await db.execute(
            select(TreatmentPhase).where(TreatmentPhase.id == phase_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def update_treatment_phase(
        db: AsyncSession,
        phase_id: UUID,
        **kwargs
    ) -> Optional[TreatmentPhase]:
        """Update a treatment phase"""
        result = await db.execute(
            select(TreatmentPhase).where(TreatmentPhase.id == phase_id)
        )
        phase = result.scalar_one_or_none()

        if not phase:
            return None

        for key, value in kwargs.items():
            if hasattr(phase, key):
                setattr(phase, key, value)

        await db.commit()
        await db.refresh(phase)
        logger.info(f"Updated treatment phase: {phase_id}")
        return phase

    @staticmethod
    async def list_treatment_phases(
        db: AsyncSession,
        plan_id: UUID,
    ) -> List[TreatmentPhase]:
        """List phases for a treatment plan"""
        query = (
            select(TreatmentPhase)
            .where(TreatmentPhase.treatment_plan_id == plan_id)
            .order_by(TreatmentPhase.phase_number)
        )

        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def finalize_treatment_plan(
        db: AsyncSession,
        plan_id: UUID,
    ) -> bool:
        """Finalize a treatment plan"""
        plan = await db.get(TreatmentPlan, plan_id)

        if not plan:
            return False

        # Verify all phases are complete
        result = await db.execute(
            select(TreatmentPhase).where(
                TreatmentPhase.treatment_plan_id == plan_id
            )
        )
        phases = result.scalars().all()

        if not phases:
            logger.warning(f"Cannot finalize plan without phases: {plan_id}")
            return False

        # Update plan status
        plan.status = TreatmentPlanStatus.ACCEPTED
        await db.commit()
        logger.info(f"Finalized treatment plan: {plan_id}")
        return True

    @staticmethod
    async def get_phase_procedures(
        db: AsyncSession,
        phase_id: UUID,
    ) -> List[TreatmentProcedure]:
        """Get all procedures in a phase"""
        query = (
            select(TreatmentProcedure)
            .where(TreatmentProcedure.phase_id == phase_id)
            .order_by(TreatmentProcedure.display_order)
        )

        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def calculate_phase_duration(
        db: AsyncSession,
        phase_id: UUID,
    ) -> Optional[int]:
        """Calculate estimated duration for a phase in days"""
        phase = await TreatmentPlanningService.get_treatment_phase(db, phase_id)

        if not phase:
            return None

        procedures = await TreatmentPlanningService.get_phase_procedures(db, phase_id)

        if not procedures:
            return 0

        # Sum up estimated durations
        total_duration = sum(proc.estimated_duration_days or 0 for proc in procedures)

        return total_duration

    @staticmethod
    async def validate_plan_structure(
        db: AsyncSession,
        plan_id: UUID,
    ) -> tuple[bool, Optional[str]]:
        """Validate treatment plan structure"""
        plan = await db.get(TreatmentPlan, plan_id)

        if not plan:
            return False, "Plan not found"

        # Check if plan has phases
        result = await db.execute(
            select(TreatmentPhase).where(
                TreatmentPhase.treatment_plan_id == plan_id
            )
        )
        phases = result.scalars().all()

        if not phases:
            return False, "Plan must have at least one phase"

        # Check if each phase has procedures
        for phase in phases:
            result = await db.execute(
                select(TreatmentProcedure).where(
                    TreatmentProcedure.phase_id == phase.id
                )
            )
            procedures = result.scalars().all()

            if not procedures:
                return False, f"Phase {phase.phase_number} must have at least one procedure"

        return True, None
