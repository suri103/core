"""Regression tests for Celery communication task retry semantics.

Covers the retry-duplication fix: a failed send must not be requeued twice,
must not be marked FAILED before its Celery retries are exhausted (which made
every retry instantly skip), and must not pollute the stored error_message
with the Retry exception repr.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock

from celery.exceptions import Retry

from app.core import communication_tasks
from app.core.communication_tasks import (
    send_message_task,
    send_bulk_messages_task,
    process_scheduled_messages_task,
    retry_failed_messages_task,
    cleanup_old_messages_task,
)
from app.models.communication import (
    PatientMessage,
    MessageType,
    MessageStatus,
)
from app.models.patient import Patient
from app.models.practice import Practice


def _real_task(task):
    """Unwrap Celery's PromiseProxy so we can patch its attributes."""
    return task._get_current_object() if hasattr(task, "_get_current_object") else task


@pytest.fixture
def _patch_task_retry(monkeypatch):
    """Patch a bound Celery task so `self.retry()` raises Retry without
    touching the broker, and control the retry budget via max_retries."""

    def _apply(max_retries: int = 1):
        task = _real_task(send_message_task)

        def _raise_retry(exc=None, **kwargs):
            raise Retry(exc or Exception("send failed"))

        monkeypatch.setattr(task, "retry", _raise_retry)
        monkeypatch.setattr(task, "max_retries", max_retries)
        return task

    return _apply


def _make_message(message_type=MessageType.SMS, status=MessageStatus.PENDING):
    message = MagicMock(spec=PatientMessage)
    message.id = "msg-1"
    message.status = status
    message.message_type = message_type
    message.practice_id = "practice-1"
    message.patient_id = "patient-1"
    message.content = "Hello"
    message.subject = "Subject"
    message.recipient_phone = "+15551234567"
    message.recipient_email = "patient@example.com"
    message.error_message = None
    message.external_id = None
    message.sent_at = None
    return message


def _make_db(message, practice=None, patient=None):
    practice = practice or MagicMock(spec=Practice)
    practice.name = "Bright Smile Dental"
    patient = patient or MagicMock(spec=Patient)
    patient.phone = "+15551234567"
    patient.email = "patient@example.com"

    lookup = {
        PatientMessage: message,
        Practice: practice,
        Patient: patient,
    }
    db = MagicMock()

    def query_side_effect(model):
        q = MagicMock()
        item = lookup.get(model)
        q.filter.return_value.first.return_value = item
        if model == PatientMessage:
            q.filter.return_value.update.return_value = 1 if getattr(item, "status", None) == MessageStatus.PENDING else 0
        return q

    db.query.side_effect = query_side_effect
    return db


@pytest.fixture(autouse=True)
def _patch_providers(monkeypatch):
    sms_sender = MagicMock()
    sms_sender.send_sms = AsyncMock(return_value={"success": True, "message_id": "ext-1", "error": None})
    monkeypatch.setattr(communication_tasks, "SMSService", lambda *a, **k: sms_sender)
    monkeypatch.setattr(communication_tasks, "SMSProvider", lambda *a, **k: "mock")

    email_sender = MagicMock()
    email_sender.send_email = AsyncMock(return_value={"success": True, "message_id": "ext-2", "error": None})
    monkeypatch.setattr(communication_tasks, "EmailService", lambda *a, **k: email_sender)
    monkeypatch.setattr(communication_tasks, "EmailProvider", lambda *a, **k: "mock")
    return {"sms": sms_sender, "email": email_sender}
class TestSendMessageTask:
    def test_success_sms_marks_sent(self, monkeypatch, _patch_providers):
        message = _make_message()
        db = _make_db(message)
        monkeypatch.setattr(communication_tasks, "get_db_session", lambda: db)

        result = send_message_task(message.id)

        assert result["status"] == "sent"
        assert message.status == MessageStatus.SENT
        assert message.external_id == "ext-1"
        assert message.sent_at is not None
        _patch_providers["sms"].send_sms.assert_awaited_once()

    def test_failure_with_retries_remaining_stays_pending(
        self, monkeypatch, _patch_providers, _patch_task_retry
    ):
        """Regression: previously FAILED was set before self.retry(), the
        Retry was swallowed by the generic except and re-raised (double
        queue), and the retry then skipped because status was FAILED."""
        _patch_task_retry(max_retries=1)
        message = _make_message()
        db = _make_db(message)
        monkeypatch.setattr(communication_tasks, "get_db_session", lambda: db)
        _patch_providers["sms"].send_sms = AsyncMock(
            return_value={"success": False, "message_id": None, "error": "provider down"}
        )

        with pytest.raises(Retry):
            send_message_task(message.id)

        # Message stays re-attemptable; NOT failed.
        assert message.status == MessageStatus.PENDING
        assert message.error_message == "provider down"

    def test_failure_marks_failed_when_retries_exhausted(
        self, monkeypatch, _patch_providers, _patch_task_retry
    ):
        _patch_task_retry(max_retries=0)
        message = _make_message()
        db = _make_db(message)
        monkeypatch.setattr(communication_tasks, "get_db_session", lambda: db)
        _patch_providers["sms"].send_sms = AsyncMock(
            return_value={"success": False, "message_id": None, "error": "provider down"}
        )

        result = send_message_task(message.id)

        assert result["status"] == "failed"
        assert message.status == MessageStatus.FAILED
        assert message.error_message == "provider down"

    def test_retried_execution_attempts_send_again(
        self, monkeypatch, _patch_providers, _patch_task_retry
    ):
        """The first retry wave re-attempts the send (PENDING guard passes)."""
        _patch_task_retry(max_retries=1)
        message = _make_message()
        db = _make_db(message)
        monkeypatch.setattr(communication_tasks, "get_db_session", lambda: db)
        _patch_providers["sms"].send_sms = AsyncMock(
            side_effect=[
                {"success": False, "message_id": None, "error": "down"},
                {"success": True, "message_id": "ext-ok", "error": None},
            ]
        )

        with pytest.raises(Retry):
            send_message_task(message.id)
        result = send_message_task(message.id)

        assert result["status"] == "sent"
        assert message.status == MessageStatus.SENT
        assert _patch_providers["sms"].send_sms.await_count == 2

    def test_generic_exception_requeues_until_exhausted(
        self, monkeypatch, _patch_providers, _patch_task_retry
    ):
        _patch_task_retry(max_retries=1)
        message = _make_message()
        db = _make_db(message)
        monkeypatch.setattr(communication_tasks, "get_db_session", lambda: db)
        _patch_providers["sms"].send_sms = AsyncMock(side_effect=RuntimeError("boom"))

        with pytest.raises(Retry):
            send_message_task(message.id)
        assert message.status == MessageStatus.PENDING

    def test_skips_already_processed_message(self, monkeypatch, _patch_providers):
        message = _make_message(status=MessageStatus.SENT)
        db = _make_db(message)
        monkeypatch.setattr(communication_tasks, "get_db_session", lambda: db)

        result = send_message_task(message.id)

        assert result["status"] == "skipped"
        _patch_providers["sms"].send_sms.assert_not_awaited()

    def test_missing_message_returns_error(self, monkeypatch, _patch_providers):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        monkeypatch.setattr(communication_tasks, "get_db_session", lambda: db)

        result = send_message_task("missing")

        assert result["status"] == "error"


class TestSendBulkMessagesTask:
    def test_bulk_counts_retry_as_retrying_not_failed(self, monkeypatch, _patch_providers):
        message = _make_message()
        db = _make_db(message)
        monkeypatch.setattr(communication_tasks, "get_db_session", lambda: db)

        # Inner send_message_task raises a per-message Celery retry; the bulk
        # task must count it as retrying, not as a batch failure.
        inner = MagicMock(side_effect=Retry())
        monkeypatch.setattr(communication_tasks, "send_message_task", inner)

        result = send_bulk_messages_task([message.id], "sms")

        assert result["status"] == "completed"
        assert result["failed"] == 0
        assert result["skipped"] == 1
        assert result["results"][0]["result"]["status"] == "retrying"


class TestProcessScheduledMessagesTask:
    def test_queues_due_pending_messages(self, monkeypatch, _patch_providers):
        message = _make_message()

        db = MagicMock()
        query = db.query.return_value
        # Fairness query shape: distinct practice ids, then per-practice page.
        query.filter.return_value.distinct.return_value.order_by.return_value.all.return_value = [
            (message.practice_id,)
        ]
        query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [message]
        query.filter.return_value.limit.return_value.all.return_value = [message]
        monkeypatch.setattr(communication_tasks, "get_db_session", lambda: db)

        # Spy on the queued task without requiring a broker.
        monkeypatch.setattr(communication_tasks, "send_message_task", MagicMock())

        result = process_scheduled_messages_task()

        assert result["status"] == "completed"
        assert result["queued"] == 1


class TestRetryFailedMessagesTask:
    def test_requeues_failed_messages_older_than_cutoff(self, monkeypatch, _patch_providers):
        message = _make_message(status=MessageStatus.FAILED)

        db = MagicMock()
        query = db.query.return_value
        query.filter.return_value.limit.return_value.all.return_value = [message]
        monkeypatch.setattr(communication_tasks, "get_db_session", lambda: db)
        queued = MagicMock()
        monkeypatch.setattr(communication_tasks, "send_message_task", queued)

        result = retry_failed_messages_task(24)

        assert result["status"] == "completed"
        assert result["retried"] == 1
        assert message.status == MessageStatus.PENDING
        assert message.error_message is None
        # Late retry wave delegates to a fresh queued execution.
        assert queued.delay.called

    def test_never_requeues_message_that_exhausted_attempt_budget(
        self, monkeypatch, _patch_providers
    ):
        exhausted = _make_message(status=MessageStatus.FAILED)
        exhausted.id = "msg-exhausted"
        exhausted.attempt_count = communication_tasks._MAX_DELIVERY_ATTEMPTS

        db = MagicMock()
        query = db.query.return_value
        query.filter.return_value.limit.return_value.all.return_value = [exhausted]
        monkeypatch.setattr(communication_tasks, "get_db_session", lambda: db)
        queued = MagicMock()
        monkeypatch.setattr(communication_tasks, "send_message_task", queued)

        result = retry_failed_messages_task(24)

        assert result["status"] == "completed"
        assert result["retried"] == 0
        # Terminal state: the row stays FAILED and nothing is published.
        assert exhausted.status == MessageStatus.FAILED
        queued.delay.assert_not_called()

    def test_still_requeues_message_under_attempt_budget(
        self, monkeypatch, _patch_providers
    ):
        message = _make_message(status=MessageStatus.FAILED)
        message.attempt_count = communication_tasks._MAX_DELIVERY_ATTEMPTS - 1

        db = MagicMock()
        query = db.query.return_value
        query.filter.return_value.limit.return_value.all.return_value = [message]
        monkeypatch.setattr(communication_tasks, "get_db_session", lambda: db)
        queued = MagicMock()
        monkeypatch.setattr(communication_tasks, "send_message_task", queued)

        result = retry_failed_messages_task(24)

        assert result["retried"] == 1
        assert message.status == MessageStatus.PENDING
        assert queued.delay.called


class TestCleanupOldMessagesTask:
    def test_deletes_old_processed_messages(self, monkeypatch, _patch_providers):
        fake_query = MagicMock()
        fake_query.filter.return_value.delete.return_value = 5
        db = MagicMock()
        db.query.return_value = fake_query
        monkeypatch.setattr(communication_tasks, "get_db_session", lambda: db)

        result = cleanup_old_messages_task(90)

        assert result["status"] == "completed"
        assert result["deleted"] == 5