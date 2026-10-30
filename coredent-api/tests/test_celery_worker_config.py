"""Regression test: Celery worker queue coverage.

Verifies that every queue routed in celery_app.conf.task_routes is
accounted for in the documented worker CLI invocation in celery_worker.py.
"""
from pathlib import Path
from app.core.celery_app import celery_app


def test_celery_task_routes_queues_covered_by_worker():
    # Extract all distinct queue names configured in task_routes
    routes = celery_app.conf.task_routes or {}
    routed_queues = {
        rule["queue"]
        for rule in routes.values()
        if isinstance(rule, dict) and "queue" in rule
    }
    assert "reminders" in routed_queues
    assert "communications" in routed_queues
    assert "emails" in routed_queues

    # Read celery_worker.py docstring and verify every routed queue is present
    worker_file = Path(__file__).resolve().parent.parent / "celery_worker.py"
    worker_content = worker_file.read_text(encoding="utf-8")

    for queue in routed_queues:
        assert queue in worker_content, (
            f"Queue {queue!r} is routed in celery_app.conf.task_routes but missing "
            f"from celery_worker.py worker usage specification."
        )
