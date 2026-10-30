from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Dict, Any
from uuid import UUID
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models.treatment import (
    TreatmentPlan,
    TreatmentProcedure,
    ProcedureType,
)
from app.models.insurance import PatientInsurance
from app.models.patient import Patient

logger = logging.getLogger(__name__)

CENT = Decimal("0.01")
# L-4 FIX: pin ROUND_HALF_UP to match payment_processing._to_cents and avoid
# .005-edge 1c divergence between gateway cents and ledger totals.
_MONEY_ROUNDING = ROUND_HALF_UP


def _dec(val) -> Decimal:
    if val is None:
        return Decimal("0.00")
    if isinstance(val, Decimal):
        return val.quantize(CENT, rounding=_MONEY_ROUNDING)
    return Decimal(str(val)).quantize(CENT, rounding=_MONEY_ROUNDING)


class TreatmentCostingService:
    """Service for treatment costing operations"""

    @staticmethod
    async def calculate_treatment_cost(
        db: AsyncSession,
        plan_id: UUID,
    ) -> Dict[str, str]:
        """Calculate total cost for a treatment plan"""
        result = await db.execute(
            select(TreatmentProcedure).where(
                TreatmentProcedure.treatment_plan_id == plan_id
            )
        )
        procedures = result.scalars().all()

        total_fee = sum((_dec(proc.fee) for proc in procedures), Decimal("0.00")).quantize(CENT, rounding=_MONEY_ROUNDING)
        total_insurance_estimate = sum((_dec(proc.insurance_estimate) for proc in procedures), Decimal("0.00")).quantize(CENT, rounding=_MONEY_ROUNDING)
        total_patient_responsibility = sum((_dec(proc.patient_responsibility) for proc in procedures), Decimal("0.00")).quantize(CENT, rounding=_MONEY_ROUNDING)

        return {
            "total_fee": str(total_fee),
            "total_insurance_estimate": str(total_insurance_estimate),
            "total_patient_responsibility": str(total_patient_responsibility),
        }

    @staticmethod
    async def estimate_insurance_coverage(
        db: AsyncSession,
        patient_insurance_id: UUID,
        procedures: List[Dict[str, Any]],
        practice_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """Estimate insurance coverage for procedures.

        SECURITY: when ``practice_id`` is supplied the policy is only
        resolved if it belongs to a patient of that practice — the raw ID
        alone would let any tenant read another tenant's policy details
        (IDOR). Callers inside authenticated endpoints MUST pass it.
        """
        stmt = (
            select(PatientInsurance)
            .join(Patient, PatientInsurance.patient_id == Patient.id)
            .where(PatientInsurance.id == patient_insurance_id)
            # Eager-load the carrier: the response serializes carrier.name,
            # and a lazy load here raises MissingGreenlet on AsyncSession.
            .options(joinedload(PatientInsurance.carrier))
        )
        if practice_id is not None:
            stmt = stmt.where(Patient.practice_id == practice_id)
        result = await db.execute(stmt)
        patient_insurance = result.scalar_one_or_none()

        if not patient_insurance:
            return {
                "total_fee": "0.0",
                "total_insurance_estimate": "0.0",
                "total_patient_responsibility": "0.0",
                "procedure_estimates": [],
            }

        total_fee = Decimal("0.00")
        total_insurance_estimate = Decimal("0.00")
        total_patient_responsibility = Decimal("0.00")
        procedure_estimates = []

        # Coverage percentages
        coverage_percentages = {
            "preventive": Decimal(str(patient_insurance.preventive_coverage or 100)),
            "basic": Decimal(str(patient_insurance.basic_coverage or 80)),
            "major": Decimal(str(patient_insurance.major_coverage or 50)),
        }

        for proc_data in procedures:
            procedure_fee = _dec(proc_data.get("fee", 0))
            procedure_type = proc_data.get("procedure_type", ProcedureType.RESTORATIVE)

            # Determine coverage percentage
            if procedure_type == ProcedureType.PREVENTIVE:
                coverage_pct = coverage_percentages["preventive"]
            elif procedure_type in [ProcedureType.RESTORATIVE, ProcedureType.ENDODONTIC]:
                coverage_pct = coverage_percentages["basic"]
            elif procedure_type in [ProcedureType.PROSTHODONTIC, ProcedureType.ORAL_SURGERY, ProcedureType.ORTHODONTIC]:
                coverage_pct = coverage_percentages["major"]
            else:
                coverage_pct = Decimal("0")

            insurance_coverage = (procedure_fee * (coverage_pct / Decimal("100"))).quantize(CENT, rounding=_MONEY_ROUNDING)
            patient_responsibility = (procedure_fee - insurance_coverage).quantize(CENT, rounding=_MONEY_ROUNDING)

            total_fee += procedure_fee
            total_insurance_estimate += insurance_coverage
            total_patient_responsibility += patient_responsibility

            procedure_estimates.append({
                "ada_code": proc_data.get("ada_code"),
                "description": proc_data.get("description"),
                "fee": str(procedure_fee),
                "insurance_coverage": str(insurance_coverage),
                "patient_responsibility": str(patient_responsibility),
                "coverage_percentage": str(coverage_pct),
            })

        return {
            "total_fee": str(total_fee),
            "total_insurance_estimate": str(total_insurance_estimate),
            "total_patient_responsibility": str(total_patient_responsibility),
            "procedure_estimates": procedure_estimates,
            "insurance_details": {
                "carrier_name": patient_insurance.carrier.name if patient_insurance.carrier else None,
                "coverage_percentages": {k: str(v) for k, v in coverage_percentages.items()},
                "annual_maximum": str(patient_insurance.annual_maximum or 0),
                "deductible_met": str(patient_insurance.deductible_met or 0),
                "annual_deductible": str(patient_insurance.annual_deductible or 0),
            },
        }

    @staticmethod
    async def calculate_patient_responsibility(
        db: AsyncSession,
        plan_id: UUID,
        patient_insurance_id: Optional[UUID] = None,
        practice_id: Optional[UUID] = None,
    ) -> Dict[str, float]:
        """Calculate patient responsibility for a plan"""
        result = await db.execute(
            select(TreatmentProcedure).where(
                TreatmentProcedure.treatment_plan_id == plan_id
            )
        )
        procedures = result.scalars().all()

        if not procedures:
            return {
                "total_fee": "0.0",
                "insurance_coverage": "0.0",
                "patient_responsibility": "0.0",
            }

        total_fee = sum((_dec(proc.fee) for proc in procedures), Decimal("0.00")).quantize(CENT, rounding=_MONEY_ROUNDING)

        if patient_insurance_id:
            # SECURITY: same tenant-scoping rule as estimate_insurance_coverage.
            stmt = (
                select(PatientInsurance)
                .join(Patient, PatientInsurance.patient_id == Patient.id)
                .where(PatientInsurance.id == patient_insurance_id)
            )
            if practice_id is not None:
                stmt = stmt.where(Patient.practice_id == practice_id)
            result = await db.execute(stmt)
            patient_insurance = result.scalar_one_or_none()

            if patient_insurance:
                # Calculate insurance coverage
                insurance_coverage = Decimal("0.00")
                for proc in procedures:
                    if proc.procedure_type == ProcedureType.PREVENTIVE:
                        coverage_pct = Decimal(str(patient_insurance.preventive_coverage or 100))
                    elif proc.procedure_type in [ProcedureType.RESTORATIVE, ProcedureType.ENDODONTIC]:
                        coverage_pct = Decimal(str(patient_insurance.basic_coverage or 80))
                    elif proc.procedure_type in [ProcedureType.PROSTHODONTIC, ProcedureType.ORAL_SURGERY, ProcedureType.ORTHODONTIC]:
                        coverage_pct = Decimal(str(patient_insurance.major_coverage or 50))
                    else:
                        coverage_pct = Decimal("0")

                    insurance_coverage += (_dec(proc.fee) * (coverage_pct / Decimal("100"))).quantize(CENT, rounding=_MONEY_ROUNDING)

                patient_responsibility = (total_fee - insurance_coverage).quantize(CENT, rounding=_MONEY_ROUNDING)

                return {
                    "total_fee": str(total_fee),
                    "insurance_coverage": str(insurance_coverage),
                    "patient_responsibility": str(patient_responsibility),
                }

        # No insurance
        return {
            "total_fee": str(total_fee),
            "insurance_coverage": "0.0",
            "patient_responsibility": str(total_fee),
        }

    @staticmethod
    async def update_plan_totals(
        db: AsyncSession,
        plan_id: UUID,
    ) -> bool:
        """Update treatment plan totals based on procedures"""
        result = await db.execute(
            select(TreatmentProcedure).where(
                TreatmentProcedure.treatment_plan_id == plan_id
            )
        )
        procedures = result.scalars().all()

        # Calculate totals
        total_fee = sum((_dec(proc.fee) for proc in procedures), Decimal("0.00")).quantize(CENT, rounding=_MONEY_ROUNDING)
        total_insurance_estimate = sum((_dec(proc.insurance_estimate) for proc in procedures), Decimal("0.00")).quantize(CENT, rounding=_MONEY_ROUNDING)
        total_patient_responsibility = sum((_dec(proc.patient_responsibility) for proc in procedures), Decimal("0.00")).quantize(CENT, rounding=_MONEY_ROUNDING)

        # Update plan
        plan = await db.get(TreatmentPlan, plan_id)

        if not plan:
            return False

        plan.total_estimated_cost = total_fee
        plan.total_insurance_estimate = total_insurance_estimate
        plan.total_patient_responsibility = total_patient_responsibility

        await db.commit()
        logger.info(f"Updated plan totals: {plan_id}")
        return True

    @staticmethod
    async def get_cost_breakdown(
        db: AsyncSession,
        plan_id: UUID,
    ) -> Dict[str, Any]:
        """Get detailed cost breakdown for a plan"""
        result = await db.execute(
            select(TreatmentProcedure).where(
                TreatmentProcedure.treatment_plan_id == plan_id
            )
        )
        procedures = result.scalars().all()

        breakdown_by_type = {}

        for proc in procedures:
            proc_type = proc.procedure_type or "unknown"

            if proc_type not in breakdown_by_type:
                breakdown_by_type[proc_type] = {
                    "count": 0,
                    "total_fee": Decimal("0.00"),
                    "total_insurance": Decimal("0.00"),
                    "total_patient": Decimal("0.00"),
                }

            breakdown_by_type[proc_type]["count"] += 1
            breakdown_by_type[proc_type]["total_fee"] += _dec(proc.fee)
            breakdown_by_type[proc_type]["total_insurance"] += _dec(proc.insurance_estimate)
            breakdown_by_type[proc_type]["total_patient"] += _dec(proc.patient_responsibility)

        total_fee = sum((_dec(proc.fee) for proc in procedures), Decimal("0.00")).quantize(CENT, rounding=_MONEY_ROUNDING)
        total_insurance = sum((_dec(proc.insurance_estimate) for proc in procedures), Decimal("0.00")).quantize(CENT, rounding=_MONEY_ROUNDING)
        total_patient = sum((_dec(proc.patient_responsibility) for proc in procedures), Decimal("0.00")).quantize(CENT, rounding=_MONEY_ROUNDING)

        formatted_breakdown = {
            k: {
                "count": v["count"],
                "total_fee": str(v["total_fee"]),
                "total_insurance": str(v["total_insurance"]),
                "total_patient": str(v["total_patient"]),
            }
            for k, v in breakdown_by_type.items()
        }

        return {
            "total_fee": str(total_fee),
            "total_insurance": str(total_insurance),
            "total_patient": str(total_patient),
            "breakdown_by_type": formatted_breakdown,
            "procedure_count": len(procedures),
        }
