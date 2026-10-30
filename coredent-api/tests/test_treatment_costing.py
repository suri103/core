"""Tests for TreatmentCostingService with mocked DB session."""
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from app.services.treatment_costing import TreatmentCostingService
from app.models.treatment import ProcedureType


@pytest.mark.asyncio
async def test_calculate_treatment_cost_totals():
    proc1 = MagicMock(fee=100, insurance_estimate=60, patient_responsibility=40)
    proc2 = MagicMock(fee=50, insurance_estimate=20, patient_responsibility=30)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [proc1, proc2]

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    result = await TreatmentCostingService.calculate_treatment_cost(mock_db, uuid4())
    # The service returns cent-quantized money strings (Decimal-safe), not floats.
    assert result == {
        "total_fee": "150.00",
        "total_insurance_estimate": "80.00",
        "total_patient_responsibility": "70.00",
    }


@pytest.mark.asyncio
async def test_estimate_insurance_coverage_missing_insurance():
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    result = await TreatmentCostingService.estimate_insurance_coverage(mock_db, uuid4(), [])
    assert result["total_fee"] == "0.0"
    assert result["procedure_estimates"] == []


@pytest.mark.asyncio
async def test_estimate_insurance_coverage_with_procedures():
    insurance = MagicMock()
    insurance.preventive_coverage = 100
    insurance.basic_coverage = 80
    insurance.major_coverage = 50
    insurance.carrier = MagicMock(name="Carrier")
    insurance.carrier.name = "Carrier"
    insurance.annual_maximum = 1000
    insurance.deductible_met = 100
    insurance.annual_deductible = 200

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = insurance

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    procedures = [
        {"fee": 100.0, "procedure_type": ProcedureType.PREVENTIVE, "ada_code": "D1110", "description": "Prophylaxis"},
        {"fee": 200.0, "procedure_type": ProcedureType.RESTORATIVE, "ada_code": "D2391", "description": "Filling"},
    ]

    result = await TreatmentCostingService.estimate_insurance_coverage(mock_db, uuid4(), procedures)
    assert result["total_fee"] == "300.00"
    assert result["total_insurance_estimate"] == "260.00"
    assert result["total_patient_responsibility"] == "40.00"
    assert len(result["procedure_estimates"]) == 2


@pytest.mark.asyncio
async def test_calculate_patient_responsibility_no_procs():
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    result = await TreatmentCostingService.calculate_patient_responsibility(mock_db, uuid4())
    assert result == {
        "total_fee": "0.0",
        "insurance_coverage": "0.0",
        "patient_responsibility": "0.0",
    }


@pytest.mark.asyncio
async def test_update_plan_totals_updates_values():
    proc1 = MagicMock(fee=100, insurance_estimate=60, patient_responsibility=40)
    proc2 = MagicMock(fee=50, insurance_estimate=20, patient_responsibility=30)

    mock_exec_result = MagicMock()
    mock_exec_result.scalars.return_value.all.return_value = [proc1, proc2]

    plan = MagicMock()
    plan.id = uuid4()

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_exec_result
    mock_db.get.return_value = plan

    ok = await TreatmentCostingService.update_plan_totals(mock_db, uuid4())
    assert ok is True
    assert plan.total_estimated_cost == 150.0
    assert plan.total_insurance_estimate == 80.0
    assert plan.total_patient_responsibility == 70.0
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_cost_breakdown_groups_by_type():
    p1 = MagicMock(fee=100, insurance_estimate=60, patient_responsibility=40, procedure_type=ProcedureType.PREVENTIVE)
    p2 = MagicMock(fee=200, insurance_estimate=80, patient_responsibility=120, procedure_type=ProcedureType.RESTORATIVE)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [p1, p2]

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    result = await TreatmentCostingService.get_cost_breakdown(mock_db, uuid4())
    assert result["total_fee"] == "300.00"
    assert result["breakdown_by_type"][ProcedureType.PREVENTIVE]["count"] == 1
    assert result["breakdown_by_type"][ProcedureType.RESTORATIVE]["total_fee"] == "200.00"
    assert result["procedure_count"] == 2
