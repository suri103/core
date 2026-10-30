"""Deprecated compatibility facade for the legacy communications queue.

The former implementation had an independent select/PENDING/send/commit state
machine, so HTTP and billing producers could race the modern worker and
transmit the same message twice. Keep its public import paths and Celery task
name for queued legacy callers, but route every delivery through the durable
``communication_tasks.send_message_task`` claimant.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from celery import shared_task

from app.core.communication_tasks import send_message_task as _durable_send_message

logger = logging.getLogger(__name__)


def _queue_durable_message(message_id: str):
    """Publish only; a committed PENDING row is recovered by Beat on failure."""
    try:
        return _durable_send_message.delay(str(message_id))
    except Exception as exc:
        logger.warning(
            "Could not publish legacy message %s; durable dispatcher will recover it: %s",
            message_id,
            exc,
        )
        return None


@shared_task(
    bind=True,
    name="app.core.communication_queue.send_message_celery_task",
)
def send_message_celery_task(self, msg_id: str) -> Dict[str, Any]:
    """Compatibility task for messages already present in older brokers."""
    result = _queue_durable_message(msg_id)
    return {
        "status": "queued" if result is not None else "pending_recovery",
        "message_id": str(msg_id),
        "task_id": getattr(result, "id", None),
    }


def send_message_task(message_id: str):
    """Deprecated public wrapper retained for existing imports."""
    return _queue_durable_message(message_id)


def _do_send_message(message_id: str) -> Dict[str, Any]:
    """Compatibility alias; never sends directly outside the durable worker."""
    result = _queue_durable_message(message_id)
    return {
        "status": "queued" if result is not None else "pending_recovery",
        "message_id": str(message_id),
        "task_id": getattr(result, "id", None),
    }


def send_message_sync(message_id: str) -> Dict[str, Any]:
    """Synchronous legacy adapter for callers that explicitly need a result."""
    result = _durable_send_message.apply(args=(str(message_id),))
    return result.get(propagate=True)
