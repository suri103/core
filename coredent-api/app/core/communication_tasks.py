"""Durable Celery tasks for outbound patient communications.

``PatientMessage`` is the delivery outbox: a producer commits it before it
tries to publish a Celery task. Workers claim rows atomically with a short
lease, perform provider I/O, then complete the same claim token. This prevents
concurrent workers from delivering the same row at once and lets Beat recover
broker-publish gaps or a worker lost while processing.

A provider acceptance followed by a process crash before the final database
commit remains an unavoidable at-least-once boundary for SMTP/SMS providers
without an idempotency API. The stable message ID is retained as the
reconciliation key and the lease bounds retry/duplicate exposure.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from celery import shared_task
from celery.exceptions import Retry
from sqlalchemy import and_, func, or_
from sqlalchemy.exc import IntegrityError

from app.core.config_simple import settings
from app.core.email import EmailProvider, EmailService
from app.core.sms import SMSProvider, SMSService
from app.models.communication import (
    MessageDirection,
    MessageStatus,
    MessageTemplate,
    MessageType,
    PatientMessage,
)
from app.models.patient import Patient
from app.models.practice import Practice
from app.services.communications_service import CommunicationsEngine

logger = logging.getLogger(__name__)

_CLAIM_LEASE = timedelta(minutes=5)
_MAX_DISPATCH_BATCH = 100
# Total delivery attempts before a message is permanently failed. One
# dispatch wave costs up to 4 claims (initial + 3 Celery retries), so 10
# allows two daily recovery waves before the retry sweep stops reviving it.
_MAX_DELIVERY_ATTEMPTS = 10


def get_db_session():
    """Get a synchronous database session for a Celery worker."""
    from app.core.database import SessionLocal

    return SessionLocal()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _retry_delay(retries: int) -> int:
    """Bounded exponential retry delay shared by state and Celery retry."""
    return min(3600, 60 * (2 ** min(max(retries, 0), 6)))


def _delivery_due_clause(now: datetime):
    """Rows are eligible only when both schedule and retry windows allow it."""
    return and_(
        or_(
            PatientMessage.scheduled_at.is_(None),
            PatientMessage.scheduled_at <= now,
        ),
        or_(
            PatientMessage.next_attempt_at.is_(None),
            PatientMessage.next_attempt_at <= now,
        ),
    )


def _reclaim_expired_message_claims(db, now: datetime) -> int:
    """Return interrupted SENDING rows to PENDING after their lease expires."""
    return db.query(PatientMessage).filter(
        PatientMessage.status == MessageStatus.SENDING,
        or_(
            PatientMessage.claim_expires_at.is_(None),
            PatientMessage.claim_expires_at <= now,
        ),
    ).update(
        {
            PatientMessage.status: MessageStatus.PENDING,
            PatientMessage.claim_token: None,
            PatientMessage.claimed_at: None,
            PatientMessage.claim_expires_at: None,
            PatientMessage.next_attempt_at: now,
            PatientMessage.error_message: "Delivery claim expired; requeued for recovery.",
            PatientMessage.updated_at: now,
        },
        synchronize_session=False,
    )


def _claim_message(db, message_id: str, now: datetime):
    """Atomically claim one due PENDING message and return it with its token."""
    token = uuid4().hex
    updated = db.query(PatientMessage).filter(
        PatientMessage.id == message_id,
        PatientMessage.status == MessageStatus.PENDING,
        _delivery_due_clause(now),
    ).update(
        {
            PatientMessage.status: MessageStatus.SENDING,
            PatientMessage.claim_token: token,
            PatientMessage.claimed_at: now,
            PatientMessage.claim_expires_at: now + _CLAIM_LEASE,
            PatientMessage.attempt_count: func.coalesce(PatientMessage.attempt_count, 0) + 1,
            PatientMessage.updated_at: now,
        },
        synchronize_session=False,
    )
    db.commit()
    if not updated:
        return None, None

    message = db.query(PatientMessage).filter(
        PatientMessage.id == message_id,
        PatientMessage.claim_token == token,
    ).first()
    return message, token


def _finish_message(
    db,
    message: PatientMessage,
    token: str,
    *,
    status: MessageStatus,
    now: datetime,
    external_id: Optional[str] = None,
    error_message: Optional[str] = None,
    next_attempt_at: Optional[datetime] = None,
) -> bool:
    """Finish only the worker claim that performed the provider operation."""
    values = {
        PatientMessage.status: status,
        PatientMessage.claim_token: None,
        PatientMessage.claimed_at: None,
        PatientMessage.claim_expires_at: None,
        PatientMessage.next_attempt_at: next_attempt_at,
        PatientMessage.error_message: error_message[:1000] if error_message else None,
        PatientMessage.updated_at: now,
    }
    if status == MessageStatus.SENT:
        values[PatientMessage.sent_at] = now
        values[PatientMessage.external_id] = external_id

    updated = db.query(PatientMessage).filter(
        PatientMessage.id == message.id,
        PatientMessage.status == MessageStatus.SENDING,
        PatientMessage.claim_token == token,
    ).update(values, synchronize_session=False)
    db.commit()
    if not updated:
        return False

    # Keep the loaded instance useful to synchronous callers and unit tests;
    # the conditional UPDATE above remains the concurrency authority.
    message.status = status
    message.claim_token = None
    message.claimed_at = None
    message.claim_expires_at = None
    message.next_attempt_at = next_attempt_at
    message.error_message = values[PatientMessage.error_message]
    if status == MessageStatus.SENT:
        message.sent_at = now
        message.external_id = external_id
    return True


def _provider_succeeded(result: Any) -> bool:
    """Treat provider accepted/queued responses as successful hand-off."""
    if not isinstance(result, dict):
        return False
    return bool(result.get("success")) or result.get("status") in {
        "sent",
        "queued",
        "accepted",
    }


def _send_message_via_provider(message: PatientMessage, practice: Optional[Practice]):
    """Return provider result without mutating delivery state."""
    if message.message_type == MessageType.SMS:
        if not message.recipient_phone:
            return {"success": False, "error": "No SMS recipient configured"}
        service = SMSService(provider=SMSProvider(settings.SMS_PROVIDER))
        return asyncio.run(
            service.send_sms(to=message.recipient_phone, message=message.content)
        )

    if message.message_type == MessageType.EMAIL:
        if not message.recipient_email:
            return {"success": False, "error": "No email recipient configured"}
        email_service = EmailService(provider=EmailProvider(settings.EMAIL_PROVIDER))
        practice_name = practice.name if practice else "CoreDent"
        return asyncio.run(
            email_service.send_email(
                to=message.recipient_email,
                subject=message.subject or f"Message from {practice_name}",
                html_content=message.content,
                text_content=message.content,
                idempotency_key=f"patient-message:{message.id}",
            )
        )

    return {
        "success": False,
        "error": f"Unsupported outbound message type: {message.message_type}",
    }


def _retry_or_fail_message(
    task,
    db,
    message: PatientMessage,
    token: str,
    error_message: str,
):
    """Release a failed claim, then use one bounded Celery retry wave."""
    now = _utcnow()
    if task.request.retries < task.max_retries:
        delay = _retry_delay(task.request.retries)
        _finish_message(
            db,
            message,
            token,
            status=MessageStatus.PENDING,
            now=now,
            error_message=error_message,
            next_attempt_at=now + timedelta(seconds=delay),
        )
        raise task.retry(exc=RuntimeError(error_message), countdown=delay)

    attempts_used = getattr(message, "attempt_count", None)
    if isinstance(attempts_used, int) and attempts_used >= _MAX_DELIVERY_ATTEMPTS:
        error_message = (
            f"{error_message} | Permanently failed: delivery budget exhausted "
            f"after {attempts_used} attempts (max {_MAX_DELIVERY_ATTEMPTS})."
        )
    _finish_message(
        db,
        message,
        token,
        status=MessageStatus.FAILED,
        now=now,
        error_message=error_message,
    )
    logger.error(
        "Patient message %s failed after %s retries: %s",
        message.id,
        task.max_retries,
        error_message,
    )
    return {
        "status": "failed",
        "message_id": str(message.id),
        "error": error_message,
    }


def _publish_message(message_id: str) -> bool:
    """Best-effort broker publish; the periodic dispatcher heals failures."""
    try:
        send_message_task.delay(str(message_id))
        return True
    except Exception as exc:
        logger.warning(
            "Could not publish patient message %s; durable dispatcher will recover it: %s",
            message_id,
            exc,
        )
        return False


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
    reject_on_worker_lost=True,
)
def send_message_task(self, message_id: str) -> Dict[str, Any]:
    """Deliver a single persisted patient message using an atomic lease claim."""
    db = get_db_session()
    message = None
    token = None

    try:
        message, token = _claim_message(db, message_id, _utcnow())
        if message is None:
            exists = db.query(PatientMessage).filter(
                PatientMessage.id == message_id
            ).first()
            if exists is None:
                return {"status": "error", "error": "Message not found"}
            return {
                "status": "skipped",
                "reason": "Message is not due, already claimed, or already processed",
            }

        practice = db.query(Practice).filter(
            Practice.id == message.practice_id
        ).first()
        # Keep the tenant relationship lookup explicit: it validates a broken
        # record before a provider call without using any patient data in logs.
        if not db.query(Patient).filter(Patient.id == message.patient_id).first():
            return _retry_or_fail_message(
                self, db, message, token, "Patient not found for message delivery"
            )

        result = _send_message_via_provider(message, practice)
        if _provider_succeeded(result):
            external_id = (
                result.get("provider_message_id")
                or result.get("external_id")
                or result.get("message_id")
            )
            if not _finish_message(
                db,
                message,
                token,
                status=MessageStatus.SENT,
                now=_utcnow(),
                external_id=external_id,
            ):
                return {
                    "status": "skipped",
                    "reason": "Message claim was superseded before completion",
                }
            logger.info("Patient message %s sent via %s", message.id, message.message_type)
            return {
                "status": "sent",
                "message_id": str(message.id),
                "external_id": external_id,
            }

        return _retry_or_fail_message(
            self,
            db,
            message,
            token,
            str(result.get("error") or "Provider did not accept message"),
        )

    except Retry:
        raise
    except Exception as exc:
        logger.error("Error delivering patient message %s: %s", message_id, exc)
        db.rollback()
        if message is not None and token is not None:
            return _retry_or_fail_message(self, db, message, token, str(exc))
        raise self.retry(exc=exc, countdown=_retry_delay(self.request.retries))
    finally:
        db.close()


@shared_task(bind=True, max_retries=5, default_retry_delay=300)
def send_bulk_messages_task(
    self,
    message_ids: List[str],
    channel: str = "sms",
) -> Dict[str, Any]:
    """Dispatch a bounded collection of individual durable deliveries."""
    sent_count = 0
    failed_count = 0
    skipped_count = 0
    results = []

    for message_id in message_ids:
        try:
            result = send_message_task(message_id)
            if result.get("status") == "sent":
                sent_count += 1
            elif result.get("status") == "skipped":
                skipped_count += 1
            else:
                failed_count += 1
            results.append({"message_id": message_id, "result": result})
        except Retry:
            skipped_count += 1
            results.append({"message_id": message_id, "result": {"status": "retrying"}})
        except Exception as exc:
            failed_count += 1
            results.append({"message_id": message_id, "error": str(exc)})
            logger.error("Failed to process message %s in bulk send: %s", message_id, exc)

    logger.info(
        "Bulk send completed: %s sent, %s failed, %s skipped",
        sent_count,
        failed_count,
        skipped_count,
    )
    return {
        "status": "completed",
        "total": len(message_ids),
        "sent": sent_count,
        "failed": failed_count,
        "skipped": skipped_count,
        "results": results,
    }


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def send_template_message_task(
    self,
    patient_id: str,
    template_id: str,
    channel: str,
    practice_id: str,
    context_variables: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Persist a template message once per Celery task before dispatching it."""
    db = get_db_session()

    try:
        # Cross-tenant FIX: prove all three rows belong to the task's practice
        # before rendering — an unscoped fetch could render B's template to
        # A's patient.
        patient = db.query(Patient).filter(
            Patient.id == patient_id,
            Patient.practice_id == practice_id,
        ).first()
        template = db.query(MessageTemplate).filter(
            MessageTemplate.id == template_id,
            MessageTemplate.practice_id == practice_id,
        ).first()
        practice = db.query(Practice).filter(Practice.id == practice_id).first()
        if not all([patient, template, practice]):
            missing = []
            if not patient:
                missing.append("patient")
            if not template:
                missing.append("template")
            if not practice:
                missing.append("practice")
            return {"status": "error", "error": f"Missing: {', '.join(missing)}"}

        task_id = getattr(self.request, "id", None)
        dedupe_key = f"template-task:{task_id}" if task_id else None
        if dedupe_key:
            existing = db.query(PatientMessage).filter(
                PatientMessage.practice_id == practice_id,
                PatientMessage.dedupe_key == dedupe_key,
            ).first()
            if existing:
                _publish_message(str(existing.id))
                return {
                    "status": "queued",
                    "message_id": str(existing.id),
                    "template_id": template_id,
                    "patient_id": patient_id,
                    "duplicate": True,
                }

        context = context_variables or {}
        context.setdefault("patient_name", patient.first_name)
        context.setdefault("practice_name", practice.name)
        content = template.content
        for key, value in context.items():
            content = content.replace(f"[{key}]", str(value))

        message = PatientMessage(
            practice_id=practice_id,
            patient_id=patient_id,
            template_id=template_id,
            message_type=MessageType.SMS if channel == "sms" else MessageType.EMAIL,
            direction=MessageDirection.OUTBOUND,
            status=MessageStatus.PENDING,
            subject=template.subject or None,
            content=content,
            recipient_phone=patient.phone if channel == "sms" else None,
            recipient_email=patient.email if channel == "email" else None,
            dedupe_key=dedupe_key,
            next_attempt_at=_utcnow(),
        )
        db.add(message)
        template.times_used = (template.times_used or 0) + 1
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            if not dedupe_key:
                raise
            existing = db.query(PatientMessage).filter(
                PatientMessage.practice_id == practice_id,
                PatientMessage.dedupe_key == dedupe_key,
            ).first()
            if existing is None:
                raise
            _publish_message(str(existing.id))
            return {
                "status": "queued",
                "message_id": str(existing.id),
                "template_id": template_id,
                "patient_id": patient_id,
                "duplicate": True,
            }

        _publish_message(str(message.id))
        return {
            "status": "queued",
            "message_id": str(message.id),
            "template_id": template_id,
            "patient_id": patient_id,
        }
    except Exception as exc:
        logger.error("Error queueing template message: %s", exc)
        db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_scheduled_messages_task(self) -> Dict[str, Any]:
    """Recover due messages after broker/publisher failures and stale leases."""
    db = get_db_session()
    try:
        now = _utcnow()
        reclaimed = _reclaim_expired_message_claims(db, now)
        if reclaimed:
            db.commit()

        # Fairness FIX (mirror tasks.py per-practice slicing): a global
        # LIMIT(100) lets one noisy tenant starve every other practice.
        # Each practice with due work gets an equal slice (oldest first);
        # claim-lease logic below is unchanged.
        _practice_ids = [
            row[0]
            for row in db.query(PatientMessage.practice_id)
            .filter(
                PatientMessage.status == MessageStatus.PENDING,
                _delivery_due_clause(now),
            )
            .distinct()
            .order_by(PatientMessage.practice_id)
            .all()
        ]
        _per_practice = max(1, _MAX_DISPATCH_BATCH // max(len(_practice_ids), 1))
        messages_to_send: list = []
        for _pid in _practice_ids:
            messages_to_send.extend(
                db.query(PatientMessage)
                .filter(
                    PatientMessage.status == MessageStatus.PENDING,
                    PatientMessage.practice_id == _pid,
                    _delivery_due_clause(now),
                )
                .order_by(PatientMessage.scheduled_at, PatientMessage.id)
                .limit(_per_practice)
                .all()
            )

        queued_count = 0
        for message in messages_to_send:
            if _publish_message(str(message.id)):
                queued_count += 1

        logger.info(
            "Patient-message dispatcher processed %s due rows (%s published, %s reclaimed)",
            len(messages_to_send),
            queued_count,
            reclaimed,
        )
        return {
            "status": "completed",
            "processed": len(messages_to_send),
            "queued": queued_count,
            "reclaimed": reclaimed,
        }
    except Exception as exc:
        logger.error("Error dispatching scheduled messages: %s", exc)
        db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def retry_failed_messages_task(self, older_than_hours: int = 24) -> Dict[str, Any]:
    """Atomically requeue old terminal failures without reviving a live claim.

    Messages that exhausted ``_MAX_DELIVERY_ATTEMPTS`` are permanently
    failed: they stay FAILED and are excluded from the candidate filter, so
    this sweep can no longer revive them forever (e.g. a message with no
    recipient would otherwise retry every day, indefinitely).
    """
    db = get_db_session()
    try:
        now = _utcnow()
        cutoff_time = now - timedelta(hours=older_than_hours)
        candidates = db.query(
            PatientMessage.id, PatientMessage.attempt_count
        ).filter(
            PatientMessage.status == MessageStatus.FAILED,
            PatientMessage.updated_at < cutoff_time,
            PatientMessage.attempt_count < _MAX_DELIVERY_ATTEMPTS,
        ).limit(50).all()

        retried_count = 0
        for candidate in candidates:
            message_id = getattr(candidate, "id", None)
            if message_id is None:
                try:
                    message_id = candidate[0]
                except (TypeError, IndexError):
                    continue
            # Defense in depth on top of the candidate filter: a row whose
            # budget was exhausted between selection and requeue is never
            # revived.
            attempts = getattr(candidate, "attempt_count", None)
            if attempts is None:
                try:
                    attempts = candidate[1]
                except (TypeError, IndexError):
                    attempts = None
            if isinstance(attempts, int) and attempts >= _MAX_DELIVERY_ATTEMPTS:
                logger.warning(
                    "Patient message %s left permanently failed after %s attempts",
                    message_id,
                    attempts,
                )
                continue
            updated = db.query(PatientMessage).filter(
                PatientMessage.id == message_id,
                PatientMessage.status == MessageStatus.FAILED,
                PatientMessage.updated_at < cutoff_time,
            ).update(
                {
                    PatientMessage.status: MessageStatus.PENDING,
                    PatientMessage.error_message: None,
                    PatientMessage.claim_token: None,
                    PatientMessage.claimed_at: None,
                    PatientMessage.claim_expires_at: None,
                    PatientMessage.next_attempt_at: now,
                    PatientMessage.updated_at: now,
                },
                synchronize_session=False,
            )
            db.commit()
            if not updated:
                continue
            # Keep test doubles and an already-loaded ORM candidate coherent.
            if hasattr(candidate, "status"):
                candidate.status = MessageStatus.PENDING
                candidate.error_message = None
                candidate.next_attempt_at = now
            if _publish_message(str(message_id)):
                retried_count += 1

        # Observability: rows the sweep will never revive again.
        try:
            permanently_failed = int(
                db.query(func.count(PatientMessage.id))
                .filter(
                    PatientMessage.status == MessageStatus.FAILED,
                    PatientMessage.attempt_count >= _MAX_DELIVERY_ATTEMPTS,
                )
                .scalar()
                or 0
            )
        except (TypeError, ValueError):
            permanently_failed = 0

        logger.info(
            "Failed message retry requeued %s message(s); %s permanently failed",
            retried_count,
            permanently_failed,
        )
        return {
            "status": "completed",
            "retried": retried_count,
            "total_failed": len(candidates),
            "permanently_failed": permanently_failed,
        }
    except Exception as exc:
        logger.error("Error retrying failed messages: %s", exc)
        db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()


@shared_task(bind=True)
def cleanup_old_messages_task(self, days_old: int = 90) -> Dict[str, Any]:
    """Delete old terminal delivery records, never active claims."""
    db = get_db_session()
    try:
        cutoff_date = _utcnow() - timedelta(days=days_old)
        deleted_count = db.query(PatientMessage).filter(
            PatientMessage.status.in_(
                [MessageStatus.SENT, MessageStatus.DELIVERED, MessageStatus.FAILED]
            ),
            PatientMessage.created_at < cutoff_date,
        ).delete()
        db.commit()
        logger.info("Cleaned up %s old messages", deleted_count)
        return {
            "status": "completed",
            "deleted": deleted_count,
            "cutoff_date": cutoff_date.isoformat(),
        }
    except Exception as exc:
        logger.error("Error cleaning up old messages: %s", exc)
        db.rollback()
        return {"status": "error", "error": str(exc)}
    finally:
        db.close()


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def process_automated_recalls_task(self) -> Dict[str, Any]:
    """Run the tenant-scoped recall engine from the communications queue."""
    db = get_db_session()
    try:
        result = CommunicationsEngine(db).process_automated_recalls()
        return result
    except Exception as exc:
        logger.error("Error processing automated recalls: %s", exc)
        db.rollback()
        raise self.retry(exc=exc, countdown=_retry_delay(self.request.retries))
    finally:
        db.close()
