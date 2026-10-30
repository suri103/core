"""
Treatment Planning Endpoints
CRUD operations for treatment planning
Thin HTTP handlers that delegate to treatment services
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID
import logging

from app.core.database import get_db
from app.core.business_time import business_date, get_practice_timezone
from app.api.deps import get_current_user, verify_csrf, require_role
from app.models.user import User, UserRole
from app.core.audit import log_audit_event
from app.models.treatment import (
    TreatmentPlan,
    TreatmentProcedure,
    ProcedureLibrary,
    TreatmentPlanStatus,
    ProcedureType,
)
from app.models.patient import Patient
from app.schemas.treatment import (
    TreatmentPlanCreate,
    TreatmentPlanUpdate,
    TreatmentPlanResponse,
    TreatmentPlanListResponse,
    TreatmentPhaseCreate,
    TreatmentPhaseUpdate,
    TreatmentPhaseResponse,
    TreatmentPhaseListResponse,
    TreatmentProcedureCreate,
    TreatmentProcedureUpdate,
    TreatmentProcedureResponse,
    TreatmentProcedureListResponse,
    ProcedureLibraryCreate,
    ProcedureLibraryUpdate,
    ProcedureLibraryResponse,
    ProcedureLibraryListResponse,
    CostEstimateRequest,
    CostEstimateResponse,
    PlanAcceptanceRequest,
    PlanAcceptanceResponse,
)

# Import services
from app.services.treatment_service import TreatmentService
from app.services.treatment_planning import TreatmentPlanningService
from app.services.treatment_costing import TreatmentCostingService
from app.services.tenant_refs import require_appointment, require_pre_authorization

router = APIRouter()
logger = logging.getLogger(__name__)


async def _validate_procedure_references(
    db: AsyncSession,
    *,
    practice_id: UUID,
    patient_id: UUID,
    appointment_id: Optional[UUID],
    pre_auth_id: Optional[UUID],
) -> None:
    """M-11 FIX: prove a procedure's optional references belong to this plan.

    Both ids are optional and both were previously written straight from the
    request body. An appointment must belong to this practice *and* this
    plan's patient; a pre-authorization must belong to this patient. Anything
    else would link a procedure to a visit or authorization that is not this
    patient's.
    """
    if appointment_id is not None:
        await require_appointment(
            db, appointment_id, practice_id, patient_id=patient_id, field="Appointment"
        )
    if pre_auth_id is not None:
        await require_pre_authorization(
            db, pre_auth_id, practice_id, patient_id=patient_id, field="Pre-authorization"
        )


def _next_offset(offset: int, count: int, total: int) -> Optional[int]:
    """Return the next offset only when another treatment-plan page exists."""
    return offset + count if offset + count < total else None


# Treatment Plan Endpoints

@router.get("/plans/", response_model=TreatmentPlanListResponse)
async def list_treatment_plans(
    patient_id: Optional[str] = Query(None, description="Filter by patient"),
    status_filter: Optional[TreatmentPlanStatus] = Query(None, description="Filter by status"),
    provider_id: Optional[str] = Query(None, description="Filter by provider"),
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    offset: int = Query(0, ge=0, description="Number of treatment plans to skip"),
    limit: int = Query(50, ge=1, le=200, description="Maximum treatment plans to return"),
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TreatmentPlanListResponse:
    """List a bounded, practice-local-date page of treatment plans."""
    try:
        plans, total = await TreatmentService.list_treatment_plans_page(
            db,
            current_user.practice_id,
            patient_id=patient_id,
            status=status_filter,
            provider_id=provider_id,
            start_date=start_date,
            end_date=end_date,
            offset=offset,
            limit=limit,
        )

        # HIPAA: Log access
        await log_audit_event(db, current_user, "list_treatment_plans", "treatment_plan", None, request)
        await db.commit()

        logger.info("Listed %d of %d treatment plans", len(plans), total)
        return TreatmentPlanListResponse(
            plans=plans,
            count=len(plans),
            total=total,
            next_offset=_next_offset(offset, len(plans), total),
        )
    except ValueError as e:
        logger.error(f"Invalid treatment plan list parameters: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except (TypeError, SQLAlchemyError) as e:
        logger.error(f"Error listing treatment plans: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.get("/patients/{patient_id}/plans", response_model=TreatmentPlanListResponse)
async def list_patient_treatment_plans(
    patient_id: str,
    status_filter: Optional[TreatmentPlanStatus] = Query(None, description="Filter by status"),
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    offset: int = Query(0, ge=0, description="Number of treatment plans to skip"),
    limit: int = Query(50, ge=1, le=200, description="Maximum treatment plans to return"),
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TreatmentPlanListResponse:
    """List a bounded, practice-local-date page of a patient's treatment plans."""
    try:
        # Verify patient belongs to practice
        result = await db.execute(
            select(Patient).where(
                Patient.id == patient_id,
                Patient.practice_id == current_user.practice_id,
            )
        )
        patient = result.scalar_one_or_none()

        if not patient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

        plans, total = await TreatmentService.list_treatment_plans_page(
            db,
            current_user.practice_id,
            patient_id=patient_id,
            status=status_filter,
            start_date=start_date,
            end_date=end_date,
            offset=offset,
            limit=limit,
        )

        # HIPAA: Log access
        await log_audit_event(db, current_user, "list_patient_treatment_plans", "patient", patient_id, request)
        await db.commit()

        logger.info("Listed %d of %d treatment plans for patient: %s", len(plans), total, patient_id)
        return TreatmentPlanListResponse(
            plans=plans,
            count=len(plans),
            total=total,
            next_offset=_next_offset(offset, len(plans), total),
        )
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error listing patient treatment plans: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except (TypeError, SQLAlchemyError) as e:
        logger.error(f"Unexpected error listing patient treatment plans: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.post("/plans/", response_model=TreatmentPlanResponse)
async def create_treatment_plan(
    plan_data: TreatmentPlanCreate,
    request: Request = None,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.DENTIST)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> TreatmentPlanResponse:
    """Create a new treatment plan"""
    try:
        # Verify patient belongs to practice
        result = await db.execute(
            select(Patient).where(
                Patient.id == plan_data.patient_id,
                Patient.practice_id == current_user.practice_id,
            )
        )
        patient = result.scalar_one_or_none()

        if not patient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

        # Verify provider belongs to practice
        result = await db.execute(
            select(User).where(
                User.id == plan_data.provider_id,
                User.practice_id == current_user.practice_id,
            )
        )
        provider = result.scalar_one_or_none()

        if not provider:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

        plan = await TreatmentService.create_treatment_plan(
            db,
            current_user.practice_id,
            plan_data.patient_id,
            plan_data.provider_id,
            **plan_data.dict(exclude={"patient_id", "provider_id"})
        )

        # HIPAA: Log creation
        await log_audit_event(db, current_user, "create_treatment_plan", "treatment_plan", plan.id, request)
        await db.commit()

        logger.info(f"Created treatment plan: {plan.id}")
        return plan
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error creating treatment plan: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid treatment plan data")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Unexpected error creating treatment plan: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.get("/plans/{plan_id}", response_model=TreatmentPlanResponse)
async def get_treatment_plan(
    plan_id: UUID,
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TreatmentPlanResponse:
    """Get treatment plan by ID"""
    try:
        plan = await TreatmentService.get_treatment_plan(db, plan_id, current_user.practice_id)

        if not plan:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Treatment plan not found")

        # HIPAA: Log access
        await log_audit_event(db, current_user, "view_treatment_plan", "treatment_plan", plan.id, request)
        await db.commit()

        logger.info(f"Retrieved treatment plan: {plan_id}")
        return plan
    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Unexpected error getting treatment plan: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.put("/plans/{plan_id}", response_model=TreatmentPlanResponse)
async def update_treatment_plan(
    plan_id: UUID,
    plan_data: TreatmentPlanUpdate,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.DENTIST)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> TreatmentPlanResponse:
    """Update treatment plan"""
    try:
        # Verify plan belongs to practice
        plan = await TreatmentService.get_treatment_plan(db, plan_id, current_user.practice_id)

        if not plan:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Treatment plan not found")

        plan = await TreatmentService.update_treatment_plan(
            db,
            plan_id,
            current_user.practice_id,
            **plan_data.model_dump(exclude_unset=True)
        )
        if plan is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Treatment plan not found")

        logger.info(f"Updated treatment plan: {plan_id}")
        return plan
    except HTTPException:
        raise
    except ValueError as e:
        # M-11: invalid status transition.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (TypeError, SQLAlchemyError) as e:
        logger.error(f"Error updating treatment plan: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.delete("/plans/{plan_id}")
async def delete_treatment_plan(
    plan_id: UUID,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """Delete treatment plan (soft delete via status change)"""
    try:
        # Verify plan belongs to practice
        plan = await TreatmentService.get_treatment_plan(db, plan_id, current_user.practice_id)

        if not plan:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Treatment plan not found")

        success = await TreatmentService.delete_treatment_plan(db, plan_id)

        if not success:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete plan")

        logger.info(f"Deleted treatment plan: {plan_id}")
        return {"message": "Treatment plan cancelled successfully"}
    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error deleting treatment plan: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


# Treatment Phase Endpoints

@router.get("/plans/{plan_id}/phases", response_model=TreatmentPhaseListResponse)
async def list_treatment_phases(
    plan_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TreatmentPhaseListResponse:
    """List phases for a treatment plan"""
    try:
        # Verify plan belongs to practice
        plan = await TreatmentService.get_treatment_plan(db, plan_id, current_user.practice_id)

        if not plan:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Treatment plan not found")

        phases = await TreatmentPlanningService.list_treatment_phases(db, plan_id)

        logger.info(f"Listed {len(phases)} treatment phases")
        return TreatmentPhaseListResponse(phases=phases, count=len(phases))
    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error listing treatment phases: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.post("/plans/{plan_id}/phases", response_model=TreatmentPhaseResponse)
async def create_treatment_phase(
    plan_id: UUID,
    phase_data: TreatmentPhaseCreate,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.DENTIST)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> TreatmentPhaseResponse:
    """Create a new treatment phase"""
    try:
        # Verify plan belongs to practice
        plan = await TreatmentService.get_treatment_plan(db, plan_id, current_user.practice_id)

        if not plan:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Treatment plan not found")

        phase = await TreatmentPlanningService.create_treatment_phase(
            db,
            plan_id,
            **phase_data.model_dump()
        )

        logger.info(f"Created treatment phase: {phase.id}")
        return phase
    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error creating treatment phase: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.put("/phases/{phase_id}", response_model=TreatmentPhaseResponse)
async def update_treatment_phase(
    phase_id: UUID,
    phase_data: TreatmentPhaseUpdate,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.DENTIST)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> TreatmentPhaseResponse:
    """Update treatment phase"""
    try:
        phase = await TreatmentPlanningService.get_treatment_phase(db, phase_id)

        if not phase:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Treatment phase not found")

        # Verify plan belongs to practice (404, not 403 — never confirm a
        # foreign-practice row exists).
        plan = await TreatmentService.get_treatment_plan(db, phase.treatment_plan_id, current_user.practice_id)

        if not plan:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Treatment phase not found")

        phase = await TreatmentPlanningService.update_treatment_phase(
            db,
            phase_id,
            **phase_data.model_dump(exclude_unset=True)
        )

        logger.info(f"Updated treatment phase: {phase_id}")
        return phase
    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error updating treatment phase: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


# Treatment Procedure Endpoints

@router.get("/plans/{plan_id}/procedures", response_model=TreatmentProcedureListResponse)
async def list_treatment_procedures(
    plan_id: UUID,
    phase_id: Optional[UUID] = Query(None, description="Filter by phase"),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    procedure_type: Optional[ProcedureType] = Query(None, description="Filter by type"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TreatmentProcedureListResponse:
    """List procedures for a treatment plan"""
    try:
        # Verify plan belongs to practice
        plan = await TreatmentService.get_treatment_plan(db, plan_id, current_user.practice_id)

        if not plan:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Treatment plan not found")

        query = select(TreatmentProcedure).where(
            TreatmentProcedure.treatment_plan_id == plan_id
        )

        if phase_id:
            query = query.where(TreatmentProcedure.phase_id == phase_id)

        if status_filter:
            query = query.where(TreatmentProcedure.status == status_filter)

        if procedure_type:
            query = query.where(TreatmentProcedure.procedure_type == procedure_type)

        query = query.order_by(TreatmentProcedure.display_order)

        result = await db.execute(query)
        procedures = result.scalars().all()

        logger.info(f"Listed {len(procedures)} treatment procedures")
        return TreatmentProcedureListResponse(procedures=procedures, count=len(procedures))
    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error listing treatment procedures: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.post("/plans/{plan_id}/procedures", response_model=TreatmentProcedureResponse)
async def create_treatment_procedure(
    plan_id: UUID,
    procedure_data: TreatmentProcedureCreate,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.DENTIST)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> TreatmentProcedureResponse:
    """Create a new treatment procedure"""
    try:
        # Verify plan belongs to practice
        plan = await TreatmentService.get_treatment_plan(db, plan_id, current_user.practice_id)

        if not plan:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Treatment plan not found")

        # Verify phase belongs to plan if provided
        if procedure_data.phase_id:
            phase = await TreatmentPlanningService.get_treatment_phase(db, procedure_data.phase_id)

            if not phase or phase.treatment_plan_id != plan_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Treatment phase not found")

        # M-11 FIX: appointment_id and pre_auth_id arrived straight from the
        # request body and were written unvalidated, so a procedure could point
        # at another practice's appointment or another patient's
        # pre-authorization. Validate against the plan's own patient/practice.
        await _validate_procedure_references(
            db,
            practice_id=current_user.practice_id,
            patient_id=plan.patient_id,
            appointment_id=procedure_data.appointment_id,
            pre_auth_id=procedure_data.pre_auth_id,
        )

        procedure = TreatmentProcedure(
            treatment_plan_id=plan_id,
            **procedure_data.dict()
        )

        db.add(procedure)
        await db.commit()
        await db.refresh(procedure)

        # Update plan totals
        await TreatmentCostingService.update_plan_totals(db, plan_id)

        logger.info(f"Created treatment procedure: {procedure.id}")
        return procedure
    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error creating treatment procedure: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.put("/procedures/{procedure_id}", response_model=TreatmentProcedureResponse)
async def update_treatment_procedure(
    procedure_id: str,
    procedure_data: TreatmentProcedureUpdate,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.DENTIST)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> TreatmentProcedureResponse:
    """Update treatment procedure"""
    try:
        try:
            procedure_uuid = UUID(procedure_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Treatment procedure not found")
        # Tenant scoping happens in the fetch itself: join to the parent plan
        # and filter by practice so a cross-tenant procedure id yields 404.
        # The previous pattern loaded the bare-id row first and checked the
        # plan afterwards, which pulled another practice's PHI row into
        # memory and leaked existence via a 403-vs-404 difference.
        result = await db.execute(
            select(TreatmentProcedure, TreatmentPlan)
            .join(
                TreatmentPlan,
                TreatmentProcedure.treatment_plan_id == TreatmentPlan.id,
            )
            .where(
                TreatmentProcedure.id == procedure_uuid,
                TreatmentPlan.practice_id == current_user.practice_id,
            )
        )
        row = result.one_or_none()

        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Treatment procedure not found")
        procedure, plan = row

        update_data = procedure_data.dict(exclude_unset=True)
        if update_data.get("phase_id") is not None:
            phase = await TreatmentPlanningService.get_treatment_phase(db, update_data["phase_id"])
            if not phase or phase.treatment_plan_id != procedure.treatment_plan_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Treatment phase not found",
                )
        # M-11 FIX: same unvalidated references on the update path.
        await _validate_procedure_references(
            db,
            practice_id=current_user.practice_id,
            patient_id=plan.patient_id,
            appointment_id=update_data.get("appointment_id"),
            pre_auth_id=update_data.get("pre_auth_id"),
        )
        effective_fee = update_data.get("fee", procedure.fee)
        effective_ins = update_data.get("insurance_estimate", procedure.insurance_estimate)
        effective_pat = update_data.get("patient_responsibility", procedure.patient_responsibility)
        if effective_fee is not None:
            eff_fee_dec = Decimal(str(effective_fee))
            eff_ins_dec = Decimal(str(effective_ins or 0))
            eff_pat_dec = Decimal(str(effective_pat or 0))
            if eff_ins_dec + eff_pat_dec > eff_fee_dec:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="insurance_estimate + patient_responsibility cannot exceed fee",
                )

        # The parent plan is not client-reassignable: moving a procedure to
        # another plan would move its cost into a different patient's total.
        update_data.pop("treatment_plan_id", None)
        for field, value in update_data.items():
            setattr(procedure, field, value)

        await db.commit()
        await db.refresh(procedure)

        # Update plan totals
        await TreatmentCostingService.update_plan_totals(db, procedure.treatment_plan_id)

        logger.info(f"Updated treatment procedure: {procedure_id}")
        return procedure
    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error updating treatment procedure: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.delete("/procedures/{procedure_id}")
async def delete_treatment_procedure(
    procedure_id: str,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """Delete treatment procedure"""
    try:
        try:
            procedure_uuid = UUID(procedure_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Treatment procedure not found")
        # Same join-scoped fetch as the update path: cross-tenant ids 404,
        # never 403, and no foreign-tenant row is ever loaded.
        result = await db.execute(
            select(TreatmentProcedure, TreatmentPlan)
            .join(
                TreatmentPlan,
                TreatmentProcedure.treatment_plan_id == TreatmentPlan.id,
            )
            .where(
                TreatmentProcedure.id == procedure_uuid,
                TreatmentPlan.practice_id == current_user.practice_id,
            )
        )
        row = result.one_or_none()

        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Treatment procedure not found")
        procedure, _plan = row

        plan_id = procedure.treatment_plan_id

        await db.delete(procedure)
        await db.commit()

        # Update plan totals
        await TreatmentCostingService.update_plan_totals(db, plan_id)

        logger.info(f"Deleted treatment procedure: {procedure_id}")
        return {"message": "Treatment procedure deleted successfully"}
    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error deleting treatment procedure: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


# Procedure Library Endpoints

@router.get("/library/", response_model=ProcedureLibraryListResponse)
async def list_procedure_library(
    search: Optional[str] = Query(None, description="Search by code or description"),
    procedure_type: Optional[ProcedureType] = Query(None, description="Filter by type"),
    category: Optional[str] = Query(None, description="Filter by category"),
    is_active: Optional[bool] = Query(True, description="Filter by active status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProcedureLibraryListResponse:
    """List procedure library entries"""
    try:
        query = select(ProcedureLibrary).where(
            ProcedureLibrary.practice_id == current_user.practice_id,
            ProcedureLibrary.is_archived.is_(False),
        )

        if is_active is not None:
            query = query.where(ProcedureLibrary.is_active == is_active)

        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                or_(
                    ProcedureLibrary.ada_code.ilike(search_pattern),
                    ProcedureLibrary.description.ilike(search_pattern),
                )
            )

        if procedure_type:
            query = query.where(ProcedureLibrary.procedure_type == procedure_type)

        if category:
            query = query.where(ProcedureLibrary.category == category)

        query = query.order_by(ProcedureLibrary.ada_code)

        result = await db.execute(query)
        procedures = result.scalars().all()

        logger.info(f"Listed {len(procedures)} procedure library entries")
        return ProcedureLibraryListResponse(procedures=procedures, count=len(procedures))
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error listing procedure library: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.post("/library/", response_model=ProcedureLibraryResponse)
async def create_procedure_library_entry(
    procedure_data: ProcedureLibraryCreate,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> ProcedureLibraryResponse:
    """Create a new procedure library entry"""
    try:
        # Check for duplicate ADA code
        result = await db.execute(
            select(ProcedureLibrary).where(
                ProcedureLibrary.ada_code == procedure_data.ada_code,
                ProcedureLibrary.practice_id == current_user.practice_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Procedure with this ADA code already exists",
            )

        procedure = ProcedureLibrary(
            practice_id=current_user.practice_id,
            **procedure_data.dict()
        )

        db.add(procedure)
        await db.commit()
        await db.refresh(procedure)

        logger.info(f"Created procedure library entry: {procedure.id}")
        return procedure
    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error creating procedure library entry: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.put("/library/{procedure_id}", response_model=ProcedureLibraryResponse)
async def update_procedure_library_entry(
    procedure_id: str,
    procedure_data: ProcedureLibraryUpdate,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> ProcedureLibraryResponse:
    """Update procedure library entry"""
    try:
        result = await db.execute(
            select(ProcedureLibrary).where(
                ProcedureLibrary.id == procedure_id,
                ProcedureLibrary.practice_id == current_user.practice_id,
            )
        )
        procedure = result.scalar_one_or_none()

        if not procedure:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Procedure library entry not found")

        update_data = procedure_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(procedure, field, value)

        await db.commit()
        await db.refresh(procedure)

        logger.info(f"Updated procedure library entry: {procedure_id}")
        return procedure
    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error updating procedure library entry: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


# Cost Estimation Endpoint

@router.post("/estimate", response_model=CostEstimateResponse)
async def estimate_costs(
    estimate_request: CostEstimateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CostEstimateResponse:
    """Estimate costs for treatment procedures"""
    try:
        result = await TreatmentCostingService.estimate_insurance_coverage(
            db,
            estimate_request.patient_insurance_id,
            estimate_request.procedures,
            practice_id=current_user.practice_id,
        )

        logger.info(f"Generated cost estimate for {len(estimate_request.procedures)} procedures")
        return CostEstimateResponse(**result)
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error estimating costs: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


# Plan Acceptance Endpoint

@router.post("/plans/{plan_id}/accept", response_model=PlanAcceptanceResponse)
async def accept_treatment_plan(
    plan_id: str,
    acceptance_data: PlanAcceptanceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> PlanAcceptanceResponse:
    """Accept a treatment plan"""
    try:
        plan = await TreatmentService.get_treatment_plan(db, plan_id, current_user.practice_id)

        if not plan:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Treatment plan not found")

        # Update plan status
        plan.status = TreatmentPlanStatus.ACCEPTED
        plan.accepted_date = business_date(
            await get_practice_timezone(db, plan.practice_id)
        )
        plan.acceptance_method = acceptance_data.acceptance_method
        plan.acceptance_notes = acceptance_data.acceptance_notes

        # Update accepted procedures if specified
        accepted_procedures = []
        from decimal import Decimal
        total_accepted_cost = Decimal('0')

        if acceptance_data.accepted_procedures:
            # Get all procedures for this plan
            result = await db.execute(
                select(TreatmentProcedure).where(
                    TreatmentProcedure.treatment_plan_id == plan_id
                )
            )
            all_procedures = result.scalars().all()

            for procedure in all_procedures:
                if procedure.id in acceptance_data.accepted_procedures:
                    procedure.is_accepted = True
                    procedure.acceptance_notes = acceptance_data.acceptance_notes
                    accepted_procedures.append(procedure.id)
                    total_accepted_cost += Decimal(str(procedure.fee or 0))
                else:
                    procedure.is_accepted = False
        else:
            # Accept all procedures
            result = await db.execute(
                select(TreatmentProcedure).where(
                    TreatmentProcedure.treatment_plan_id == plan_id
                )
            )
            all_procedures = result.scalars().all()

            for procedure in all_procedures:
                procedure.is_accepted = True
                procedure.acceptance_notes = acceptance_data.acceptance_notes
                accepted_procedures.append(procedure.id)
                total_accepted_cost += Decimal(str(procedure.fee or 0))

        await db.commit()

        logger.info(f"Accepted treatment plan: {plan_id}")
        return PlanAcceptanceResponse(
            plan_id=plan.id,
            status=plan.status,
            accepted_date=plan.accepted_date,
            acceptance_method=plan.acceptance_method,
            total_accepted_cost=str(total_accepted_cost),
            accepted_procedures=accepted_procedures,
        )
    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource already exists")
    except (ValueError, TypeError, SQLAlchemyError) as e:
        logger.error(f"Error accepting treatment plan: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")