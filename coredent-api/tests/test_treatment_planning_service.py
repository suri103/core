"""Tests for TreatmentPlanningService and TreatmentService with mocked DB."""
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.treatment_planning import TreatmentPlanningService
from app.services.treatment_service import TreatmentService
from app.models.treatment import TreatmentPlanStatus


@pytest.mark.asyncio
class TestTreatmentPlanningService:
    async def test_create_treatment_phase(self):
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        phase = MagicMock(id=uuid4())
        mock_db.refresh.return_value = None

        with patch("app.services.treatment_planning.TreatmentPhase", return_value=phase):
            result = await TreatmentPlanningService.create_treatment_phase(
                mock_db, uuid4(), name="Phase 1", phase_number=1
            )
        assert result is phase
        mock_db.add.assert_called_once_with(phase)
        mock_db.commit.assert_awaited_once()

    async def test_get_treatment_phase_found(self):
        phase = MagicMock(id=uuid4())
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = phase

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        result = await TreatmentPlanningService.get_treatment_phase(mock_db, uuid4())
        assert result is phase

    async def test_get_treatment_phase_not_found(self):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        result = await TreatmentPlanningService.get_treatment_phase(mock_db, uuid4())
        assert result is None

    async def test_update_treatment_phase(self):
        phase = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = phase

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        result = await TreatmentPlanningService.update_treatment_phase(
            mock_db, uuid4(), name="Updated", status="active"
        )
        assert result is phase
        assert phase.name == "Updated"
        mock_db.commit.assert_awaited_once()

    async def test_update_treatment_phase_not_found(self):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        result = await TreatmentPlanningService.update_treatment_phase(mock_db, uuid4(), name="X")
        assert result is None

    async def test_list_treatment_phases(self):
        p1 = MagicMock(phase_number=1)
        p2 = MagicMock(phase_number=2)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [p1, p2]

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        result = await TreatmentPlanningService.list_treatment_phases(mock_db, uuid4())
        assert len(result) == 2
        assert result[0].phase_number == 1

    async def test_finalize_treatment_plan_no_phases(self):
        plan = MagicMock()
        plan.status = TreatmentPlanStatus.DRAFT

        mock_db = AsyncMock()
        mock_db.get.return_value = plan
        mock_exec = MagicMock()
        mock_exec.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_exec

        result = await TreatmentPlanningService.finalize_treatment_plan(mock_db, uuid4())
        assert result is False

    async def test_finalize_treatment_plan_success(self):
        plan = MagicMock()
        plan.status = TreatmentPlanStatus.DRAFT
        phase = MagicMock()

        mock_db = AsyncMock()
        mock_db.get.return_value = plan
        mock_exec = MagicMock()
        mock_exec.scalars.return_value.all.return_value = [phase]
        mock_db.execute.return_value = mock_exec

        result = await TreatmentPlanningService.finalize_treatment_plan(mock_db, uuid4())
        assert result is True
        assert plan.status == TreatmentPlanStatus.ACCEPTED
        mock_db.commit.assert_awaited_once()

    async def test_get_phase_procedures(self):
        proc1 = MagicMock(display_order=1)
        proc2 = MagicMock(display_order=2)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [proc1, proc2]

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        result = await TreatmentPlanningService.get_phase_procedures(mock_db, uuid4())
        assert len(result) == 2

    async def test_calculate_phase_duration(self):
        phase = MagicMock()
        p1 = MagicMock(estimated_duration_days=3)
        p2 = MagicMock(estimated_duration_days=5)

        mock_db = AsyncMock()
        with patch.object(TreatmentPlanningService, "get_treatment_phase", return_value=phase):
            with patch.object(TreatmentPlanningService, "get_phase_procedures", return_value=[p1, p2]):
                result = await TreatmentPlanningService.calculate_phase_duration(mock_db, uuid4())
        assert result == 8

    async def test_calculate_phase_duration_no_phase(self):
        mock_db = AsyncMock()
        with patch.object(TreatmentPlanningService, "get_treatment_phase", return_value=None):
            result = await TreatmentPlanningService.calculate_phase_duration(mock_db, uuid4())
        assert result is None

    async def test_validate_plan_structure_no_plan(self):
        mock_db = AsyncMock()
        mock_db.get.return_value = None

        ok, msg = await TreatmentPlanningService.validate_plan_structure(mock_db, uuid4())
        assert ok is False
        assert "Plan not found" in msg

    async def test_validate_plan_structure_no_phases(self):
        plan = MagicMock()
        mock_db = AsyncMock()
        mock_db.get.return_value = plan
        mock_exec = MagicMock()
        mock_exec.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_exec

        ok, msg = await TreatmentPlanningService.validate_plan_structure(mock_db, uuid4())
        assert ok is False
        assert "one phase" in msg

    async def test_validate_plan_structure_valid(self):
        plan = MagicMock()
        phase = MagicMock(id=uuid4(), phase_number=1)
        proc = MagicMock()

        mock_db = AsyncMock()
        mock_db.get.return_value = plan
        mock_exec = MagicMock()
        mock_exec.scalars.return_value.all.side_effect = [[phase], [proc]]
        mock_db.execute.return_value = mock_exec

        ok, msg = await TreatmentPlanningService.validate_plan_structure(mock_db, uuid4())
        assert ok is True
        assert msg is None


@pytest.mark.asyncio
class TestTreatmentService:
    async def test_create_treatment_plan(self):
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.execute.return_value = MagicMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        plan = MagicMock(id=uuid4())

        with patch("app.services.treatment_service.TreatmentPlan", return_value=plan):
            result = await TreatmentService.create_treatment_plan(
                mock_db, uuid4(), uuid4(), uuid4(), title="Plan A"
            )
        assert result is plan
        mock_db.add.assert_called_once_with(plan)
        mock_db.commit.assert_awaited_once()

    async def test_get_treatment_plan_with_practice(self):
        plan = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = plan

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        result = await TreatmentService.get_treatment_plan(mock_db, uuid4(), practice_id=uuid4())
        assert result is plan

    async def test_update_treatment_plan_status_dates(self):
        plan = MagicMock()
        plan.presented_date = None
        plan.accepted_date = None
        plan.status = TreatmentPlanStatus.DRAFT
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = plan

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        practice_id = uuid4()
        result = await TreatmentService.update_treatment_plan(
            mock_db, uuid4(), practice_id, status=TreatmentPlanStatus.PRESENTED
        )
        assert result is plan
        assert plan.presented_date is not None

    async def test_update_treatment_plan_rejects_invalid_transition(self):
        """M-11: a terminal plan cannot be reopened."""
        plan = MagicMock()
        plan.status = TreatmentPlanStatus.COMPLETED
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = plan

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        with pytest.raises(ValueError, match="Cannot change treatment plan status"):
            await TreatmentService.update_treatment_plan(
                mock_db, uuid4(), uuid4(), status=TreatmentPlanStatus.IN_PROGRESS
            )

    async def test_update_treatment_plan_ignores_identity_fields(self):
        """M-11: patient_id is not client-writable through the generic update.

        practice_id cannot even be passed: it is a required positional
        parameter, so the signature itself prevents a caller from smuggling a
        different tenant in through **kwargs.
        """
        plan = MagicMock()
        plan.status = TreatmentPlanStatus.DRAFT
        original_practice = uuid4()
        original_patient = uuid4()
        plan.practice_id = original_practice
        plan.patient_id = original_patient
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = plan

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        await TreatmentService.update_treatment_plan(
            mock_db,
            uuid4(),
            original_practice,
            patient_id=uuid4(),
            plan_name="New name",
        )
        assert plan.patient_id == original_patient
        assert plan.practice_id == original_practice
        assert plan.plan_name == "New name"

        with pytest.raises(TypeError):
            await TreatmentService.update_treatment_plan(
                mock_db,
                uuid4(),
                original_practice,
                practice_id=uuid4(),
            )

    async def test_list_treatment_plans_filters(self):
        p1 = MagicMock()
        p2 = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [p1, p2]

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        result = await TreatmentService.list_treatment_plans(
            mock_db, uuid4(), patient_id=uuid4(), status=TreatmentPlanStatus.DRAFT
        )
        assert len(result) == 2

    async def test_delete_treatment_plan_soft_delete(self):
        plan = MagicMock()
        plan.status = TreatmentPlanStatus.DRAFT
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = plan

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        result = await TreatmentService.delete_treatment_plan(mock_db, uuid4())
        assert result is True
        assert plan.status == TreatmentPlanStatus.CANCELLED
        mock_db.commit.assert_awaited_once()

    async def test_get_plan_statistics(self):
        plan = MagicMock()
        plan.total_estimated_cost = 1000
        plan.total_insurance_estimate = 600
        plan.total_patient_responsibility = 400

        proc1 = MagicMock(is_accepted=True, status="completed")
        proc2 = MagicMock(is_accepted=True, status="pending")
        proc3 = MagicMock(is_accepted=False, status="pending")

        mock_db = AsyncMock()
        with patch.object(TreatmentService, "get_treatment_plan", return_value=plan):
            mock_exec = MagicMock()
            mock_exec.scalars.return_value.all.return_value = [proc1, proc2, proc3]
            mock_db.execute.return_value = mock_exec

            result = await TreatmentService.get_plan_statistics(mock_db, uuid4())

        assert result["total_procedures"] == 3
        assert result["accepted_procedures"] == 2
        assert result["completed_procedures"] == 1
        assert result["acceptance_rate"] == (2 / 3 * 100)
        assert result["completion_rate"] == (1 / 3 * 100)
        assert result["total_estimated_cost"] == 1000.0
