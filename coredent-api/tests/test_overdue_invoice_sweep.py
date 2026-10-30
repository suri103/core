"""Tests for the mark_overdue_invoices Celery beat task.

OVERDUE was a dead state: the invoice state machine allowed PENDING ->
OVERDUE and the payment paths handled OVERDUE, but nothing ever performed
the transition. This task sweeps past-due PENDING invoices on an hourly
beat schedule.
"""
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from app.core import tasks
from app.models.billing import InvoiceStatus


def _make_invoice(status=InvoiceStatus.PENDING, due_date=None):
    invoice = MagicMock()
    invoice.status = status
    invoice.due_date = due_date
    return invoice


class TestMarkOverdueInvoices:
    def test_marks_past_due_pending_invoices_overdue(self):
        past_due = _make_invoice(due_date=date.today() - timedelta(days=3))
        db = MagicMock()

        # The sweep issues three distinct db.query() calls: the candidate
        # scan (.all), the C-2 row-lock re-read (.with_for_update().first),
        # and the practice lookup (.first). Mock each precisely — a shared
        # filter mock makes the lock re-read return a fresh auto-MagicMock
        # whose due_date comparison explodes and silently skips the item.
        candidates_query = MagicMock(name="candidates_query")
        # db.query(Invoice).filter(...).all() — the filter chain yields the list.

        candidates_query.filter.return_value.all.return_value = [past_due]
        lock_query = MagicMock(name="lock_query")
        lock_query.filter.return_value.with_for_update.return_value.first.return_value = past_due
        practice_query = MagicMock(name="practice_query")
        practice = MagicMock(name="practice", timezone="UTC", late_fee_percentage=None)
        practice_query.filter.return_value.first.return_value = practice
        db.query.side_effect = [candidates_query, lock_query, practice_query]

        with patch.object(tasks, "SessionLocal", return_value=db):
            result = tasks.mark_overdue_invoices()

        assert result == {"marked_overdue": 1}
        assert past_due.status == InvoiceStatus.OVERDUE
        db.commit.assert_called_once()
        db.close.assert_called_once()

    def test_no_past_due_invoices_no_commit(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []

        with patch.object(tasks, "SessionLocal", return_value=db):
            result = tasks.mark_overdue_invoices()

        assert result == {"marked_overdue": 0}
        db.commit.assert_not_called()
        db.close.assert_called_once()

    def test_session_closed_when_sweep_raises(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")

        task = tasks.mark_overdue_invoices._get_current_object()
        with patch.object(tasks, "SessionLocal", return_value=db), \
             patch.object(task, "retry", side_effect=RuntimeError("retry")):
            # The raised Retry/exception propagates after cleanup.
            try:
                tasks.mark_overdue_invoices()
            except RuntimeError:
                pass

        db.close.assert_called_once()
