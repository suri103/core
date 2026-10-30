"""Celery configuration for CoreDent background work."""

from datetime import timedelta
import logging
import os

from celery import Celery

from app.core.config_simple import settings
from app.core.observability import init_sentry, install_celery_metrics

logger = logging.getLogger(__name__)

broker_url = settings.CELERY_BROKER_URL or settings.REDIS_URL or "redis://localhost:6379/0"
result_backend = settings.CELERY_RESULT_BACKEND or settings.REDIS_URL or broker_url

celery_app = Celery(
    "coredent",
    broker=broker_url,
    backend=result_backend,
    include=[
        "app.core.tasks",
        "app.core.email_tasks",
        "app.core.communication_tasks",
        # Retained only to consume already-published legacy task names; it
        # delegates into communication_tasks and no longer sends directly.
        "app.core.communication_queue",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    # Delivery claims are committed before provider I/O. Late ACK + reject on
    # worker loss lets the broker redeliver interrupted work; the database
    # lease prevents a redelivery from concurrently transmitting the same row.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_publish_retry=True,
    task_publish_retry_policy={
        "max_retries": 3,
        "interval_start": 0,
        "interval_step": 0.2,
        "interval_max": 1,
    },
)

from celery.schedules import crontab

# Beat FIX: every schedule carries expires < period so a late worker never
# fires out-of-window work (claim/lease makes it safe but noisy).
# Daily jobs use fixed UTC crontabs in the 03:00-05:00 band (Decision 6 / H6)
# so deployment restarts do not postpone them.
celery_app.conf.beat_schedule = {
    "send-appointment-reminders": {
        "task": "app.core.tasks.send_appointment_reminders",
        "schedule": timedelta(minutes=15),
        "options": {"expires": 800},
    },
    "send-daily-summary": {
        "task": "app.core.tasks.send_daily_summary",
        "schedule": crontab(hour=3, minute=0),
        "options": {"expires": 3600},
    },
    "process-scheduled-reminders": {
        "task": "app.core.tasks.process_scheduled_reminders",
        "schedule": timedelta(minutes=5),
        "options": {"expires": 280},
    },
    "cleanup-old-notifications": {
        "task": "app.core.tasks.cleanup_old_notifications",
        "schedule": timedelta(hours=1),
        "options": {"expires": 3000},
    },
    "mark-overdue-invoices": {
        "task": "app.core.tasks.mark_overdue_invoices",
        "schedule": timedelta(hours=1),
        "options": {"expires": 3000},
    },
    "process-dunning": {
        "task": "app.core.tasks.process_dunning_task",
        "schedule": timedelta(hours=1),
        "options": {"expires": 3000},
    },
    "process-automated-recalls": {
        "task": "app.core.communication_tasks.process_automated_recalls_task",
        "schedule": crontab(hour=3, minute=30),
        "options": {"queue": "communications", "expires": 3600},
    },
    "process-scheduled-messages": {
        "task": "app.core.communication_tasks.process_scheduled_messages_task",
        "schedule": timedelta(minutes=1),
        "options": {"expires": 50},
    },
    "retry-failed-messages": {
        "task": "app.core.communication_tasks.retry_failed_messages_task",
        "schedule": timedelta(minutes=5),
        "options": {"expires": 280},
    },
    "cleanup-old-messages": {
        "task": "app.core.communication_tasks.cleanup_old_messages_task",
        "schedule": crontab(hour=4, minute=0),
        "options": {"queue": "communications", "expires": 3600},
    },
    "purge-anonymized-patients": {
        "task": "app.core.tasks.purge_expired_anonymized_patients",
        "schedule": crontab(hour=4, minute=30),
        "options": {"expires": 21600},
    },
    "purge-expired-token-revocations": {
        "task": "app.core.tasks.purge_expired_token_revocations",
        "schedule": crontab(hour=5, minute=0),
        "options": {"expires": 21600},
    },
}

celery_app.conf.task_routes = {
    "app.core.tasks.send_appointment_reminders": {"queue": "reminders"},
    "app.core.tasks.process_scheduled_reminders": {"queue": "reminders"},
    "app.core.tasks.*": {"queue": "default"},
    "app.core.communication_tasks.*": {"queue": "communications"},
    "app.core.communication_queue.*": {"queue": "communications"},
    "app.core.email_tasks.*": {"queue": "emails"},
}

# Sentry and task metrics for the worker/beat roles. Sentry used to be
# initialized only in app/main.py, which these processes never import, so every
# capture_exception() inside a Celery task was a silent no-op: a background
# failure was visible only if somebody read the container log.
# PROCESS_TYPE distinguishes worker from beat in Sentry. init_sentry is
# idempotent, so an in-process caller that already initialized it is a no-op.
init_sentry(os.environ.get("PROCESS_TYPE", "worker").strip().lower() or "worker")
install_celery_metrics(celery_app)

logger.info("Celery app initialized with durable delivery settings")
