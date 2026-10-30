"""Verify the Celery beat schedule is actually runnable by the worker.

Catches two silent-failure modes, both of which leave a scheduled job never
running while every log line still looks healthy:

1. A beat entry naming a task that nothing registers.
2. A scheduled task routed to a queue the worker does not consume - Celery
   publishes it and it then sits in the broker forever.

This matters more than it looks: a background job that never fires is invisible.
It is the same class of defect as the retention purge that raised NameError on
every run for months because nothing observed the failure.

Exits non-zero on a problem so CI fails, rather than printing a finding that
nobody reads.
"""
import os
import sys
from pathlib import Path

# Invoked as `python scripts/check_celery_wiring.py` from coredent-api/: sys.path[0]
# is the script's own directory, so the application package is not importable
# without adding the project root. This script previously crashed on that alone.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.celery_app import celery_app  # noqa: E402

# Mirrors worker startup: the worker imports conf.include modules before it
# starts consuming, so registration must be checked after importing them.
for _mod in celery_app.conf.include or []:
    __import__(_mod)

# Mirrors the CELERY_QUEUES default in start.py; a deployment may override it.
consumed = [
    q.strip()
    for q in os.environ.get(
        "CELERY_QUEUES", "default,communications,reminders,emails"
    ).split(",")
    if q.strip()
]

beat = celery_app.conf.beat_schedule or {}
failures: list[str] = []

from celery.schedules import crontab

daily_jobs = [
    "send-daily-summary",
    "process-automated-recalls",
    "cleanup-old-messages",
    "purge-anonymized-patients",
    "purge-expired-token-revocations",
]
for dj in daily_jobs:
    if dj not in beat:
        failures.append(f"{dj}: task is missing from beat_schedule")
    elif not isinstance(beat[dj].get("schedule"), crontab):
        failures.append(f"{dj}: schedule must be a crontab, got {type(beat[dj].get('schedule'))}")

print(f"Worker consumes queues: {consumed}")
print(f"Beat schedule entries: {len(beat)}")

for name, entry in sorted(beat.items()):
    task = entry.get("task")
    problems: list[str] = []

    if task not in celery_app.tasks:
        problems.append("task is not registered")

    # An explicit `queue` in the entry's options wins; otherwise ask the router
    # what it would actually do with this task name.
    queue = (entry.get("options") or {}).get("queue")
    if not queue:
        try:
            queue = celery_app.amqp.router.route({}, task).get("queue")
        except Exception as exc:  # noqa: BLE001 - report, do not crash
            problems.append(f"could not resolve queue: {exc}")
            queue = None
    if queue is None:
        queue = celery_app.conf.task_default_queue or "celery"
    elif not isinstance(queue, str):
        # The router returns a Queue object, not a name.
        queue = getattr(queue, "name", None) or str(queue)

    if queue not in consumed:
        problems.append(f"queue '{queue}' is not consumed by the worker")

    print(f"  {name}: task={task} queue={queue} -> " + (", ".join(problems) or "ok"))
    if problems:
        failures.append(f"{name}: " + "; ".join(problems))

if failures:
    print("\nFAIL: the worker would never run these scheduled tasks:")
    for item in failures:
        print(f"  - {item}")
    sys.exit(1)

print("\nOK: every scheduled task is registered and routed to a consumed queue.")
