"""Tests for the periodic dunning sweep task (audit finding H2)."""
from unittest.mock import MagicMock

import pytest

from app.core import tasks
from app.core.tasks import _ImmediateBackgroundTasks, process_dunning_task


class _FakeAsyncSessionContext:
    def __init__(self):
        self.session = MagicMock(name="async_session")

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


class TestImmediateBackgroundTasks:
    @pytest.mark.asyncio
    async def test_drain_runs_added_coroutines(self):
        ran = []

        async def job(value):
            ran.append(value)
            return True

        background_tasks = _ImmediateBackgroundTasks()
        background_tasks.add_task(job, "dunning-email")

        await background_tasks.drain()

        assert ran == ["dunning-email"]

    @pytest.mark.asyncio
    async def test_drain_survives_a_failing_follow_up(self):
        ran = []

        async def broken():
            raise RuntimeError("smtp down")

        async def job():
            ran.append("ok")

        background_tasks = _ImmediateBackgroundTasks()
        background_tasks.add_task(broken)
        background_tasks.add_task(job)

        await background_tasks.drain()

        assert ran == ["ok"]


class TestProcessDunningTask:
    def test_sweep_runs_process_dunning_with_session_and_shim(self, monkeypatch):
        session_cm = _FakeAsyncSessionContext()
        monkeypatch.setattr(tasks, "AsyncSessionLocal", MagicMock(return_value=session_cm))

        from app.services.subscription_billing import SubscriptionBillingService

        captured = {}

        async def fake_process_dunning(db, background_tasks, practice_id=None):
            captured["session"] = db
            captured["background_tasks"] = background_tasks
            return {"processed": 1, "failed": 0, "total": 1}

        monkeypatch.setattr(
            SubscriptionBillingService,
            "process_dunning",
            staticmethod(fake_process_dunning),
        )

        result = process_dunning_task()

        assert result == {"processed": 1, "failed": 0, "total": 1}
        assert captured["session"] is session_cm.session
        assert isinstance(captured["background_tasks"], _ImmediateBackgroundTasks)

    def test_skips_when_lock_unavailable(self, monkeypatch):
        monkeypatch.setattr(tasks, "_try_acquire_task_lock", lambda db, name: False)
        exploded = MagicMock(side_effect=AssertionError("sweep must not run"))
        monkeypatch.setattr(tasks, "_run", exploded)

        result = process_dunning_task()

        assert result["status"] == "skipped"
        exploded.assert_not_called()


class TestBeatSchedule:
    def test_process_dunning_is_scheduled_hourly(self):
        from app.core.celery_app import celery_app

        entry = celery_app.conf.beat_schedule.get("process-dunning")
        assert entry is not None
        assert entry["task"] == "app.core.tasks.process_dunning_task"
