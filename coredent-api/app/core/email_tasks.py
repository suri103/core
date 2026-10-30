"""Broker-backed transactional-email tasks.

Transactional email is retried with late acknowledgement so a worker loss
redelivers the broker message. Provider acceptance is checked explicitly: a
``{"success": false}`` result is a failure, not an acknowledged delivery.
Callers that need database-level outbox semantics should use the persisted
``PatientMessage`` path where a patient delivery record exists.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core.celery_app import celery_app
from app.core.email import email_service

logger = logging.getLogger(__name__)

# One initial attempt plus four Celery retries yields the documented five
# total provider attempts with exponential backoff.
_TOTAL_ATTEMPTS = 5


@celery_app.task(
    name="app.core.email_tasks.send_email_task",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=60,
    retry_backoff_max=36000,
    retry_jitter=True,
    max_retries=_TOTAL_ATTEMPTS - 1,
    acks_late=True,
    reject_on_worker_lost=True,
)
def send_email_task(
    self,
    to: str | List[str],
    subject: str,
    html_content: Optional[str] = None,
    text_content: Optional[str] = None,
    template_id: Optional[str] = None,
    dynamic_template_data: Optional[Dict[str, Any]] = None,
    idempotency_key: str = "",
) -> Dict[str, Any]:
    """Deliver email and preserve one identity across every Celery retry."""
    import asyncio

    try:
        delivery_key = idempotency_key or str(self.request.id)
        result = asyncio.run(
            email_service.send_email(
                to=to,
                subject=subject,
                html_content=html_content,
                text_content=text_content,
                template_id=template_id,
                dynamic_template_data=dynamic_template_data,
                idempotency_key=delivery_key,
            )
        )
        if not isinstance(result, dict) or not (
            result.get("success")
            or result.get("status") in {"sent", "queued", "accepted"}
        ):
            error = result.get("error") if isinstance(result, dict) else "Invalid provider response"
            raise RuntimeError(error or "Email provider did not accept the message")
        return result
    except Exception as exc:
        attempt = self.request.retries + 1
        logger.warning(
            "Email send attempt %s/%s failed for %r: %s",
            attempt,
            _TOTAL_ATTEMPTS,
            subject,
            exc,
        )
        if self.request.retries >= self.max_retries:
            _alert_permanent_failure(to, subject, exc)
        raise


def _alert_permanent_failure(to, subject, exc) -> None:
    """Emit a privacy-minimized permanent-failure signal for on-call."""
    logger.error("Email permanently failed after %s attempts: %r", _TOTAL_ATTEMPTS, subject)
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            scope.set_tag("event_type", "email_permanent_failure")
            scope.set_context(
                "email_failure",
                {
                    "recipient_count": len(to) if isinstance(to, list) else 1,
                    "subject": subject,
                    "error": str(exc),
                },
            )
            sentry_sdk.capture_exception(exc)
    except Exception:
        pass


def enqueue_email(
    to: str | List[str],
    subject: str,
    html_content: Optional[str] = None,
    text_content: Optional[str] = None,
    template_id: Optional[str] = None,
    dynamic_template_data: Optional[Dict[str, Any]] = None,
    idempotency_key: Optional[str] = None,
) -> str:
    """Publish one logical email identity and return its broker task ID.

    The generated key is serialized in the task payload, so Celery retries use
    the same RFC 5322 Message-ID rather than creating provider-indistinguishable
    duplicates.
    """
    delivery_key = idempotency_key or uuid4().hex
    result = send_email_task.apply_async(
        kwargs={
            "to": to,
            "subject": subject,
            "html_content": html_content,
            "text_content": text_content,
            "template_id": template_id,
            "dynamic_template_data": dynamic_template_data,
            "idempotency_key": delivery_key,
        },
        task_id=delivery_key,
    )
    return result.id
