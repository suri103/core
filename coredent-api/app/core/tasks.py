"""CoreDent Celery tasks for reminders, summaries, and billing sweeps.

Appointment reminders are durable delivery records. A worker first makes a
short-lived, database-backed claim, commits it, then invokes the provider.
This avoids the old select/send/update race across duplicate Beat instances or
concurrent workers. Expired claims are reclaimed by the next periodic run.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Any, Dict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

# L-4 FIX: single money rounding mode (HALF_UP) matching the billing ledger.
_MONEY_ROUNDING = ROUND_HALF_UP
from uuid import uuid4

from celery import shared_task
from sqlalchemy import and_, func, or_, text
from sqlalchemy.exc import IntegrityError

from app.core.database import AsyncSessionLocal, SessionLocal
from app.core.business_time import (
    DateRangeError,
    business_date,
    day_bounds_utc,
    ensure_utc,
    local_datetime,
    practice_timezone_of,
)
from app.core.email import EmailService
from app.core.sms import SMSService
from app.models.appointment import Appointment, AppointmentStatus
from app.models.billing import Invoice, InvoiceStatus
from app.models.daily_summary import DailySummaryOutbox, DailySummaryStatus
from app.models.patient import Patient
from app.models.practice import Practice
from app.models.reminder import Reminder, ReminderStatus
from app.models.user import User

logger = logging.getLogger(__name__)

_REMINDER_CLAIM_LEASE = timedelta(minutes=5)
_REMINDER_MAX_ATTEMPTS = 4
_REMINDER_BATCH_SIZE = 100
_SCHEDULER_BATCH_SIZE = 500
# Retention for terminal reminder rows (M22): FAILED rows are kept for
# delivery forensics, SENT/SKIPPED rows are retired after this longer window.
_SENT_REMINDER_RETENTION_DAYS = 90


def _run(coro):
    """Run an async provider coroutine from a synchronous Celery task."""
    return asyncio.run(coro)


def _fmt_local(dt, tz, fmt):
    instant = ensure_utc(dt)
    if instant is None:
        return ""
    return instant.astimezone(tz).strftime(fmt)


def _reminder_target_utc(start_time, practice_tz, reminder_days: int) -> datetime:
    """Schedule a reminder on the same local wall time, calendar days earlier.

    When the target lands in a spring-forward gap, schedule at the first valid
    local minute after that gap. Ambiguous fall-back times intentionally use
    fold=0, matching the public booking policy until an offset-aware API is
    introduced.
    """
    appointment_utc = ensure_utc(start_time)
    if appointment_utc is None:
        raise ValueError("appointment start time is required")

    appointment_local = appointment_utc.astimezone(practice_tz)
    target_day = appointment_local.date() - timedelta(days=reminder_days)
    target_wall_time = appointment_local.time().replace(tzinfo=None)
    try:
        return local_datetime(
            practice_tz, target_day, target_wall_time
        ).astimezone(timezone.utc)
    except DateRangeError:
        # A requested wall time inside a DST gap cannot be preserved. Advance
        # to the first existing minute on the same local day rather than
        # silently using an offset-derived instant before the gap.
        candidate = datetime.combine(target_day, target_wall_time)
        for _ in range(24 * 60):
            candidate += timedelta(minutes=1)
            if candidate.date() != target_day:
                break
            try:
                return local_datetime(
                    practice_tz, candidate.date(), candidate.time()
                ).astimezone(timezone.utc)
            except DateRangeError:
                continue
        raise ValueError("no valid local reminder time exists on the target day")


def _send_reminder_email(
    to_email,
    patient_name,
    start_time,
    practice_tz,
    practice_name,
    idempotency_key,
):
    """Send a reminder email and normalize provider output to success/failure."""
    result = _run(
        EmailService().send_appointment_reminder(
            to=to_email,
            patient_name=patient_name,
            appointment_date=_fmt_local(start_time, practice_tz, "%B %d, %Y"),
            appointment_time=_fmt_local(start_time, practice_tz, "%I:%M %p"),
            dentist_name=practice_name,
            idempotency_key=idempotency_key,
        )
    )
    return bool(result.get("success")) or result.get("status") in {
        "sent",
        "queued",
        "accepted",
    }


def _send_sms(to_phone, message):
    """Send an SMS and normalize provider output to success/failure."""
    result = _run(SMSService().send_sms(to=to_phone, message=message))
    return bool(result.get("success")) or result.get("status") in {
        "sent",
        "queued",
        "accepted",
    }


def _reminder_due_clause(now: datetime):
    return and_(
        Reminder.scheduled_at <= now,
        or_(
            Reminder.next_attempt_at.is_(None),
            Reminder.next_attempt_at <= now,
        ),
    )


def _reclaim_expired_reminder_claims(db, now: datetime) -> int:
    """Requeue only work whose committed delivery lease has expired."""
    return db.query(Reminder).filter(
        Reminder.status == ReminderStatus.PROCESSING,
        or_(
            Reminder.claim_expires_at.is_(None),
            Reminder.claim_expires_at <= now,
        ),
    ).update(
        {
            Reminder.status: ReminderStatus.PENDING,
            Reminder.claim_token: None,
            Reminder.claimed_at: None,
            Reminder.claim_expires_at: None,
            Reminder.next_attempt_at: now,
            Reminder.error_message: "Delivery claim expired; requeued for recovery.",
        },
        synchronize_session=False,
    )


def _claim_reminder(db, reminder_id, now: datetime):
    """Atomically claim a due PENDING reminder and return its lease token."""
    token = uuid4().hex
    updated = db.query(Reminder).filter(
        Reminder.id == reminder_id,
        Reminder.status == ReminderStatus.PENDING,
        _reminder_due_clause(now),
    ).update(
        {
            Reminder.status: ReminderStatus.PROCESSING,
            Reminder.claim_token: token,
            Reminder.claimed_at: now,
            Reminder.claim_expires_at: now + _REMINDER_CLAIM_LEASE,
            Reminder.attempt_count: func.coalesce(Reminder.attempt_count, 0) + 1,
        },
        synchronize_session=False,
    )
    db.commit()
    if not updated:
        return None, None
    reminder = db.query(Reminder).filter(
        Reminder.id == reminder_id,
        Reminder.claim_token == token,
    ).first()
    return reminder, token


def _finish_reminder(
    db,
    reminder: Reminder,
    token: str,
    *,
    status: ReminderStatus,
    error_message: str | None = None,
    next_attempt_at: datetime | None = None,
) -> bool:
    """Complete only the claim owned by this worker."""
    now = datetime.now(timezone.utc)
    values = {
        Reminder.status: status,
        Reminder.claim_token: None,
        Reminder.claimed_at: None,
        Reminder.claim_expires_at: None,
        Reminder.next_attempt_at: next_attempt_at,
        Reminder.error_message: error_message[:500] if error_message else None,
    }
    if status == ReminderStatus.SENT:
        values[Reminder.sent_at] = now

    updated = db.query(Reminder).filter(
        Reminder.id == reminder.id,
        Reminder.status == ReminderStatus.PROCESSING,
        Reminder.claim_token == token,
    ).update(values, synchronize_session=False)
    db.commit()
    if not updated:
        return False

    reminder.status = status
    reminder.claim_token = None
    reminder.claimed_at = None
    reminder.claim_expires_at = None
    reminder.next_attempt_at = next_attempt_at
    reminder.error_message = values[Reminder.error_message]
    if status == ReminderStatus.SENT:
        reminder.sent_at = now
    return True


def _retry_or_fail_reminder(db, reminder: Reminder, token: str, error_message: str) -> str:
    """Schedule a bounded retry without relying on a broad task replay."""
    attempts = int(reminder.attempt_count or 1)
    if attempts < _REMINDER_MAX_ATTEMPTS:
        delay = min(3600, 60 * (2 ** min(attempts - 1, 6)))
        _finish_reminder(
            db,
            reminder,
            token,
            status=ReminderStatus.PENDING,
            error_message=error_message,
            next_attempt_at=datetime.now(timezone.utc) + timedelta(seconds=delay),
        )
        return "retrying"

    _finish_reminder(
        db,
        reminder,
        token,
        status=ReminderStatus.FAILED,
        error_message=error_message,
    )
    return "failed"


def _candidate_id(candidate):
    """Extract an ID from an ORM object, SQLAlchemy row, or test double."""
    value = getattr(candidate, "id", None)
    if value is not None:
        return value
    return candidate[0]


def _task_lock_key(name: str) -> int:
    return int.from_bytes(
        hashlib.sha256(name.encode("utf-8")).digest()[:8],
        byteorder="big",
        signed=False,
    ) & 0x7FFFFFFFFFFFFFFF


def _try_acquire_task_lock(db, name: str, session_scope: bool = False) -> bool:
    """Serialize a scheduler run on PostgreSQL without weakening SQLite tests.

    This does not replace individual delivery claims; it protects jobs such as
    the overdue sweep where two workers could calculate and append the same
    late fee from stale state.

    When session_scope=True, pg_try_advisory_lock is used so the lock survives
    across intermediate commits within the task. The caller MUST call _release_task_lock
    in a finally block.
    When session_scope=False, pg_try_advisory_xact_lock is used and automatically
    releases on commit/rollback.
    """
    try:
        bind = db.get_bind()
        if getattr(bind.dialect, "name", None) != "postgresql":
            return True
        lock_key = _task_lock_key(name)
        sql = "SELECT pg_try_advisory_lock(:key)" if session_scope else "SELECT pg_try_advisory_xact_lock(:key)"
        return bool(
            db.execute(
                text(sql), {"key": lock_key}
            ).scalar()
        )
    except Exception as exc:
        logger.error("Could not acquire scheduler lock %s: %s", name, exc)
        return False


def _release_task_lock(db, name: str) -> bool:
    """Release a session-scoped advisory lock on PostgreSQL."""
    try:
        bind = db.get_bind()
        if getattr(bind.dialect, "name", None) != "postgresql":
            return True
        lock_key = _task_lock_key(name)
        return bool(
            db.execute(
                text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key}
            ).scalar()
        )
    except Exception as exc:
        logger.error("Could not release scheduler lock %s: %s", name, exc)
        return False


async def _try_acquire_task_lock_async(db, name: str) -> bool:
    """Serialize an async job run on PostgreSQL without weakening SQLite tests."""
    try:
        bind = db.get_bind()
        if bind.dialect.name != "postgresql":
            return True
        lock_key = int.from_bytes(
            hashlib.sha256(name.encode("utf-8")).digest()[:8],
            byteorder="big",
            signed=False,
        ) & 0x7FFFFFFFFFFFFFFF
        res = await db.execute(
            text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": lock_key}
        )
        return bool(res.scalar())
    except Exception as exc:
        logger.error("Could not acquire async scheduler lock %s: %s", name, exc)
        return False


@shared_task(
    bind=True,
    max_retries=3,
    acks_late=True,
    reject_on_worker_lost=True,
)
def send_appointment_reminders(self):
    """Deliver due reminders with durable row-level claims and bounded retries."""
    db = SessionLocal()
    sent_count = 0
    failed_count = 0
    skipped_count = 0
    retrying_count = 0

    try:
        now = datetime.now(timezone.utc)
        reclaimed = _reclaim_expired_reminder_claims(db, now)
        if reclaimed:
            db.commit()

        # M18 FIX: the batch is gathered per practice instead of globally, so
        # one noisy tenant cannot starve every other practice's reminders.
        # Each practice with due work gets an equal slice of the batch budget
        # (oldest scheduled first); the per-row claim/lease logic below is
        # unchanged.
        practice_ids = [
            row[0]
            for row in db.query(Appointment.practice_id)
            .join(Reminder, Reminder.appointment_id == Appointment.id)
            .filter(
                Reminder.status == ReminderStatus.PENDING,
                _reminder_due_clause(now),
            )
            .distinct()
            .order_by(Appointment.practice_id)
            .all()
        ]
        per_practice_limit = max(
            1, _REMINDER_BATCH_SIZE // max(len(practice_ids), 1)
        )
        candidates = []
        for practice_id in practice_ids:
            candidates.extend(
                db.query(Reminder.id)
                .join(Appointment, Reminder.appointment_id == Appointment.id)
                .filter(
                    Reminder.status == ReminderStatus.PENDING,
                    Appointment.practice_id == practice_id,
                    _reminder_due_clause(now),
                )
                .order_by(Reminder.scheduled_at, Reminder.id)
                .limit(per_practice_limit)
                .all()
            )

        for candidate in candidates:
            reminder = None
            token = None
            reminder_id = _candidate_id(candidate)
            try:
                reminder, token = _claim_reminder(db, reminder_id, datetime.now(timezone.utc))
                if reminder is None:
                    continue

                appointment = db.query(Appointment).filter(
                    Appointment.id == reminder.appointment_id
                ).first()
                if appointment is None:
                    _finish_reminder(
                        db,
                        reminder,
                        token,
                        status=ReminderStatus.FAILED,
                        error_message="Appointment not found",
                    )
                    failed_count += 1
                    continue

                if appointment.status in {
                    AppointmentStatus.CANCELLED,
                    AppointmentStatus.NO_SHOW,
                    AppointmentStatus.COMPLETED,
                }:
                    _finish_reminder(
                        db,
                        reminder,
                        token,
                        status=ReminderStatus.SKIPPED,
                        error_message=f"Appointment {appointment.status.value}; reminder skipped",
                    )
                    skipped_count += 1
                    continue

                patient = appointment.patient
                if patient is None:
                    _finish_reminder(
                        db,
                        reminder,
                        token,
                        status=ReminderStatus.FAILED,
                        error_message="Patient not found",
                    )
                    failed_count += 1
                    continue

                practice = db.query(Practice).filter(
                    Practice.id == appointment.practice_id
                ).first()
                timezone_info = practice_timezone_of(practice)
                local_date = _fmt_local(appointment.start_time, timezone_info, "%B %d, %Y")
                local_time = _fmt_local(appointment.start_time, timezone_info, "%I:%M %p")

                channel = reminder.reminder_type
                if channel == "email" and not patient.email and patient.phone:
                    channel = "sms"
                elif channel == "sms" and not patient.phone and patient.email:
                    channel = "email"

                if channel == "email" and patient.email:
                    success = _send_reminder_email(
                        to_email=patient.email,
                        patient_name=f"{patient.first_name} {patient.last_name}",
                        start_time=appointment.start_time,
                        practice_tz=timezone_info,
                        practice_name=practice.name if practice else "your dental practice",
                        idempotency_key=f"appointment-reminder:{reminder.id}",
                    )
                elif channel == "sms" and patient.phone:
                    success = _send_sms(
                        to_phone=patient.phone,
                        message=(
                            f"Reminder: Your appointment at "
                            f"{practice.name if practice else 'our practice'} is scheduled for "
                            f"{local_date} at {local_time}."
                        ),
                    )
                else:
                    _finish_reminder(
                        db,
                        reminder,
                        token,
                        status=ReminderStatus.FAILED,
                        error_message=f"No contact info for channel {channel}",
                    )
                    failed_count += 1
                    continue

                if success:
                    _finish_reminder(
                        db,
                        reminder,
                        token,
                        status=ReminderStatus.SENT,
                    )
                    sent_count += 1
                    continue

                outcome = _retry_or_fail_reminder(
                    db, reminder, token, "Provider did not accept reminder"
                )
                if outcome == "retrying":
                    retrying_count += 1
                else:
                    failed_count += 1
            except Exception as exc:
                db.rollback()
                logger.error("Error delivering reminder %s: %s", reminder_id, exc)
                if reminder is not None and token is not None:
                    try:
                        outcome = _retry_or_fail_reminder(db, reminder, token, str(exc))
                        if outcome == "retrying":
                            retrying_count += 1
                        else:
                            failed_count += 1
                    except Exception as finish_exc:
                        db.rollback()
                        logger.error(
                            "Could not release failed reminder claim %s: %s",
                            reminder_id,
                            finish_exc,
                        )
                else:
                    failed_count += 1

        logger.info(
            "Reminder task completed: %s sent, %s retrying, %s failed, %s skipped, %s reclaimed",
            sent_count,
            retrying_count,
            failed_count,
            skipped_count,
            reclaimed,
        )
        return {
            "sent": sent_count,
            "retrying": retrying_count,
            "failed": failed_count,
            "skipped": skipped_count,
            "reclaimed": reclaimed,
        }
    except Exception as exc:
        db.rollback()
        logger.error("Error in send_appointment_reminders: %s", exc)
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()



_DAILY_SUMMARY_MAX_ATTEMPTS = 4
_DAILY_SUMMARY_LEASE = timedelta(minutes=10)
_DAILY_SUMMARY_BACKOFF_BASE = timedelta(seconds=300)


def _daily_summary_due_clause(now: datetime):
    """Rows eligible for a new or recovered delivery claim."""
    return or_(
        and_(
            DailySummaryOutbox.status == DailySummaryStatus.PENDING,
            or_(
                DailySummaryOutbox.next_attempt_at.is_(None),
                DailySummaryOutbox.next_attempt_at <= now,
            ),
        ),
        and_(
            DailySummaryOutbox.status == DailySummaryStatus.FAILED,
            DailySummaryOutbox.next_attempt_at <= now,
        ),
        and_(
            DailySummaryOutbox.status == DailySummaryStatus.SENDING,
            or_(
                DailySummaryOutbox.claim_expires_at.is_(None),
                DailySummaryOutbox.claim_expires_at <= now,
            ),
        ),
    )


def _claim_daily_summary(db, row_id, now: datetime):
    """Conditionally claim one summary and commit its lease before email I/O."""
    token = uuid4().hex
    updated = db.query(DailySummaryOutbox).filter(
        DailySummaryOutbox.id == row_id,
        DailySummaryOutbox.attempts < _DAILY_SUMMARY_MAX_ATTEMPTS,
        _daily_summary_due_clause(now),
    ).update(
        {
            DailySummaryOutbox.status: DailySummaryStatus.SENDING,
            DailySummaryOutbox.claim_token: token,
            DailySummaryOutbox.claimed_at: now,
            DailySummaryOutbox.claim_expires_at: now + _DAILY_SUMMARY_LEASE,
            DailySummaryOutbox.last_attempt_at: now,
            DailySummaryOutbox.attempts: func.coalesce(DailySummaryOutbox.attempts, 0) + 1,
        },
        synchronize_session=False,
    )
    db.commit()
    if not updated:
        return None, None
    row = db.query(DailySummaryOutbox).filter(
        DailySummaryOutbox.id == row_id,
        DailySummaryOutbox.claim_token == token,
    ).populate_existing().first()
    return row, token


def _finish_daily_summary(
    db,
    row: DailySummaryOutbox,
    token: str,
    *,
    status: DailySummaryStatus,
    provider_message_id: str | None = None,
    next_attempt_at: datetime | None = None,
    last_error: str | None = None,
) -> bool:
    """Finalize only the lease still owned by this worker."""
    values = {
        DailySummaryOutbox.status: status,
        DailySummaryOutbox.claim_token: None,
        DailySummaryOutbox.claimed_at: None,
        DailySummaryOutbox.claim_expires_at: None,
        DailySummaryOutbox.next_attempt_at: next_attempt_at,
        DailySummaryOutbox.last_error: last_error[:500] if last_error else None,
    }
    if status == DailySummaryStatus.SENT:
        values[DailySummaryOutbox.sent_at] = datetime.now(timezone.utc)
        values[DailySummaryOutbox.provider_message_id] = provider_message_id

    updated = db.query(DailySummaryOutbox).filter(
        DailySummaryOutbox.id == row.id,
        DailySummaryOutbox.status == DailySummaryStatus.SENDING,
        DailySummaryOutbox.claim_token == token,
    ).update(values, synchronize_session=False)
    db.commit()
    return bool(updated)


@shared_task(bind=True, max_retries=3, acks_late=True, reject_on_worker_lost=True)
def send_daily_summary(self):
    """Persist daily intents, then deliver each under a fenced row lease."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        practices = db.query(Practice).all()
        for practice in practices:
            try:
                practice_tz = practice_timezone_of(practice)
                local_day = business_date(practice_tz, now)
                from app.models.user import UserRole

                admin_users = db.query(User).filter(
                    and_(
                        User.practice_id == practice.id,
                        User.role.in_([UserRole.ADMIN, UserRole.OWNER]),
                    )
                ).all()
                # A duplicate recipient rolls back only its savepoint, not
                # newly added recipients in this scheduler run.
                for admin in admin_users:
                    if not admin.email:
                        continue
                    try:
                        with db.begin_nested():
                            db.add(
                                DailySummaryOutbox(
                                    practice_id=practice.id,
                                    user_id=admin.id,
                                    summary_date=local_day,
                                    recipient_email=admin.email,
                                    status=DailySummaryStatus.PENDING,
                                    next_attempt_at=now,
                                )
                            )
                            db.flush()
                    except IntegrityError:
                        # Intentional idempotency: the (user, summary_date)
                        # unique row already exists from a concurrent scheduler
                        # run (or a previous run today) — the recipient is
                        # already queued, so the savepoint rollback above is
                        # exactly the right outcome. Not an error.
                        pass
                db.commit()
            except Exception as exc:
                db.rollback()
                logger.error(
                    "Error preparing daily summary for practice %s: %s",
                    practice.id,
                    exc,
                )

        candidate_ids = db.query(DailySummaryOutbox.id).filter(
            DailySummaryOutbox.attempts < _DAILY_SUMMARY_MAX_ATTEMPTS,
            _daily_summary_due_clause(now),
        ).order_by(
            DailySummaryOutbox.created_at,
            DailySummaryOutbox.id,
        ).limit(200).all()

        emailed_count = 0
        failed_emails = 0
        stats_cache: dict = {}
        service = EmailService()

        def _stats_for(practice_id, summary_date):
            cache_key = (practice_id, summary_date)
            if cache_key in stats_cache:
                return stats_cache[cache_key]
            practice = db.query(Practice).filter(Practice.id == practice_id).first()
            practice_tz = practice_timezone_of(practice)
            day_start_utc, day_end_utc = day_bounds_utc(practice_tz, summary_date)
            appointments_today = db.query(Appointment).filter(
                and_(
                    Appointment.practice_id == practice_id,
                    Appointment.start_time >= day_start_utc,
                    Appointment.start_time < day_end_utc,
                )
            ).count()
            reminder_base = db.query(Reminder).join(
                Appointment, Reminder.appointment_id == Appointment.id
            ).filter(Appointment.practice_id == practice_id)
            pending_reminders = reminder_base.filter(
                and_(
                    Reminder.status.in_([ReminderStatus.PENDING, ReminderStatus.PROCESSING]),
                    Reminder.scheduled_at >= now,
                )
            ).count()
            failed_reminders = reminder_base.filter(
                Reminder.status == ReminderStatus.FAILED
            ).count()
            stats_cache[cache_key] = (
                appointments_today,
                pending_reminders,
                failed_reminders,
            )
            return stats_cache[cache_key]

        from html import escape

        for candidate in candidate_ids:
            row = None
            token = None
            row_id = _candidate_id(candidate)
            try:
                row, token = _claim_daily_summary(
                    db, row_id, datetime.now(timezone.utc)
                )
                if row is None:
                    continue

                practice = db.query(Practice).filter(
                    Practice.id == row.practice_id
                ).first()
                appointments_today, pending_reminders, failed_reminders = _stats_for(
                    row.practice_id, row.summary_date
                )
                practice_name = practice.name if practice else "your practice"
                safe_practice = escape(practice_name)
                subject_practice = practice_name.replace("\r", " ").replace("\n", " ").strip()
                summary_text = (
                    f"Daily summary for {practice_name} - "
                    f"{appointments_today} appointment(s) today, "
                    f"{pending_reminders} pending reminder(s), "
                    f"{failed_reminders} failed reminder(s)."
                )
                summary_html = (
                    "<html><body style='font-family: Arial, sans-serif;'>"
                    f"<h2>Daily Summary &mdash; {safe_practice}</h2><ul>"
                    f"<li><strong>{appointments_today}</strong> appointment(s) today</li>"
                    f"<li><strong>{pending_reminders}</strong> pending reminder(s)</li>"
                    f"<li><strong>{failed_reminders}</strong> failed reminder(s)</li>"
                    "</ul><p style='color:#666;font-size:12px;'>"
                    "CoreDent Dental Practice Management</p></body></html>"
                )
                result = _run(
                    service.send_email(
                        to=row.recipient_email,
                        subject=f"Daily Summary - {subject_practice}",
                        html_content=summary_html,
                        text_content=summary_text,
                        idempotency_key=f"daily-summary:{row.id}",
                    )
                )
                if not (
                    result.get("success")
                    or result.get("status") in {"sent", "queued", "accepted"}
                ):
                    raise RuntimeError(
                        "Email provider did not accept the daily summary"
                    )
                provider_id = result.get("provider_message_id")
                if _finish_daily_summary(
                    db,
                    row,
                    token,
                    status=DailySummaryStatus.SENT,
                    provider_message_id=(str(provider_id) if provider_id else None),
                ):
                    emailed_count += 1
                else:
                    logger.warning(
                        "Daily summary row %s lost its claim before finalization",
                        row.id,
                    )
            except Exception as send_exc:
                db.rollback()
                failed_emails += 1
                if row is not None and token is not None:
                    attempts = int(row.attempts or 1)
                    backoff = _DAILY_SUMMARY_BACKOFF_BASE * (
                        2 ** max(0, attempts - 1)
                    )
                    _finish_daily_summary(
                        db,
                        row,
                        token,
                        status=DailySummaryStatus.FAILED,
                        next_attempt_at=datetime.now(timezone.utc) + backoff,
                        last_error=f"{type(send_exc).__name__}: {send_exc}",
                    )
                logger.error(
                    "Daily summary email error for outbox row %s: %s",
                    row_id,
                    send_exc,
                )

        return {"emailed": emailed_count, "failed": failed_emails}
    except Exception as exc:
        db.rollback()
        logger.error("Error in send_daily_summary: %s", exc)
        raise self.retry(exc=exc, countdown=300)
    finally:
        db.close()

@shared_task(bind=True, max_retries=3, acks_late=True, reject_on_worker_lost=True)
def process_scheduled_reminders(self):
    """Create one durable reminder row per eligible appointment.

    The appointment-level unique index is the final race guard. Each insert
    uses a savepoint, so a single overlapping scheduler insert does not roll
    back unrelated reminders or hide a genuine database outage.
    """
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        horizon_end = now + timedelta(days=7)
        appointments = db.query(Appointment).filter(
            and_(
                Appointment.start_time > now,
                Appointment.start_time <= horizon_end,
                Appointment.status.in_(
                    [AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED]
                ),
            )
        ).limit(_SCHEDULER_BATCH_SIZE).all()

        created_count = 0
        practice_cache = {}
        for appointment in appointments:
            practice = practice_cache.get(appointment.practice_id)
            if appointment.practice_id not in practice_cache:
                practice = db.query(Practice).filter(
                    Practice.id == appointment.practice_id
                ).first()
                practice_cache[appointment.practice_id] = practice
            if practice and practice.auto_send_reminders is False:
                continue

            reminder_days = 1
            raw_days = getattr(practice, "reminder_days_before", None) if practice else None
            try:
                if isinstance(raw_days, (int, float)):
                    reminder_days = max(1, int(raw_days))
                elif isinstance(raw_days, str) and raw_days.isdigit():
                    reminder_days = max(1, int(raw_days))
                elif isinstance(raw_days, list) and raw_days:
                    reminder_days = max(1, int(raw_days[0]))
            except (TypeError, ValueError):
                reminder_days = 1

            try:
                target_time = _reminder_target_utc(
                    appointment.start_time,
                    practice_timezone_of(practice),
                    reminder_days,
                )
            except ValueError as exc:
                logger.error(
                    "Skipping reminder scheduling for appointment %s: %s",
                    appointment.id,
                    exc,
                )
                continue
            if now < target_time - timedelta(hours=12):
                continue

            # Cheap common-case check; the nested transaction below is the
            # authoritative concurrent writer guard.
            if db.query(Reminder.id).filter(
                Reminder.appointment_id == appointment.id
            ).first():
                continue

            reminder_time = max(target_time, now + timedelta(minutes=5))
            try:
                with db.begin_nested():
                    db.add(
                        Reminder(
                            appointment_id=appointment.id,
                            reminder_type="email",
                            scheduled_at=reminder_time,
                            next_attempt_at=reminder_time,
                            status=ReminderStatus.PENDING,
                        )
                    )
                    db.flush()
                created_count += 1
            except IntegrityError:
                logger.info(
                    "Reminder already exists for appointment %s; scheduler race converged",
                    appointment.id,
                )

        if created_count:
            db.commit()
        return {"created": created_count, "scanned": len(appointments)}
    except Exception as exc:
        db.rollback()
        logger.error("Error in process_scheduled_reminders: %s", exc)
        raise self.retry(exc=exc, countdown=120)
    finally:
        db.close()


@shared_task(bind=True, max_retries=3)
def cleanup_old_notifications(self):
    """Remove stale terminal reminders while retaining recent audit history.

    FAILED rows are delivery-forensics and are kept for a short window (7d).
    SENT/SKIPPED rows are no longer actionable once the appointment passed;
    they were previously never cleaned up (M22), so they are now retired
    after a longer retention cutoff (90d).
    """
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        failed_cutoff = now - timedelta(days=7)
        failed_reminders = db.query(Reminder).filter(
            and_(
                Reminder.status == ReminderStatus.FAILED,
                Reminder.created_at < failed_cutoff,
            )
        ).delete()
        sent_cutoff = now - timedelta(days=_SENT_REMINDER_RETENTION_DAYS)
        terminal_reminders = db.query(Reminder).filter(
            and_(
                Reminder.status.in_([ReminderStatus.SENT, ReminderStatus.SKIPPED]),
                Reminder.created_at < sent_cutoff,
            )
        ).delete()
        db.commit()
        logger.info(
            "Cleaned up %s old failed reminders and %s old sent/skipped reminders",
            failed_reminders,
            terminal_reminders,
        )
        return {"cleaned_up_failed": failed_reminders, "cleaned_up_sent_skipped": terminal_reminders}
    except Exception as exc:
        db.rollback()
        logger.error("Error in cleanup_old_notifications: %s", exc)
        raise self.retry(exc=exc, countdown=600)
    finally:
        db.close()


@shared_task(bind=True, max_retries=3, acks_late=True, reject_on_worker_lost=True)
def send_payment_reminder(self, payment_id: str, practice_id: str):
    """Send one serialized payment reminder while the payment is pending."""
    db = SessionLocal()
    try:
        if not _try_acquire_task_lock(db, f"payment-reminder:{payment_id}"):
            return {"status": "skipped", "reason": "Another reminder task is active"}

        from app.models.billing import Payment, PaymentStatus

        # practice_id is required (UUID-guessable id alone). Internal-only
        # task; no HTTP caller today.
        payment = (
            db.query(Payment)
            .filter(
                Payment.id == payment_id,
                Payment.practice_id == practice_id,
            )
            .first()
        )
        if not payment or payment.status != PaymentStatus.PENDING:
            return {"status": "skipped", "reason": "Payment not found or already processed"}
        if not payment.patient or not payment.patient.email:
            return {"status": "skipped", "reason": "No email available"}

        patient_name = f"{payment.patient.first_name} {payment.patient.last_name}"
        result = _run(
            EmailService().send_email(
                to=payment.patient.email,
                subject="Payment Reminder - CoreDent",
                html_content=(
                    f"<p>Dear {patient_name},</p><p>This is a friendly reminder that a "
                    f"payment of ${payment.amount} is outstanding.</p><p>Reference: {payment.id}</p>"
                ),
                text_content=(
                    f"Dear {patient_name}, a payment of ${payment.amount} is outstanding. "
                    f"Reference: {payment.id}"
                ),
                idempotency_key=f"payment-reminder:{payment.id}",
            )
        )
        if result.get("success") or result.get("status") in {"sent", "queued", "accepted"}:
            return {"status": "sent", "payment_id": payment_id}
        return {"status": "failed", "payment_id": payment_id}
    except Exception as exc:
        logger.error("Error in send_payment_reminder: %s", exc)
        raise self.retry(exc=exc, countdown=300)
    finally:
        db.close()


@shared_task(bind=True, max_retries=3, acks_late=True, reject_on_worker_lost=True)
def mark_overdue_invoices(self):
    """Mark invoices overdue against each practice's local business date."""
    db = SessionLocal()
    lock_acquired = False
    try:
        now = datetime.now(timezone.utc)
        if not _try_acquire_task_lock(db, "mark-overdue-invoices", session_scope=True):
            return {"marked_overdue": 0, "skipped": "another sweep is active"}
        lock_acquired = True

        # H-2 FIX: Every real practice's local date is at most one calendar day ahead
        # of UTC. Use (now + 1 day) to avoid skipping practices ahead of UTC.
        candidates = db.query(Invoice).filter(
            and_(
                Invoice.status == InvoiceStatus.PENDING,
                Invoice.due_date.isnot(None),
                Invoice.due_date <= (now + timedelta(days=1)).date(),
            )
        ).all()
        practice_cache = {}
        past_due = []
        for candidate in candidates:
            try:
                # C-2 FIX: Acquire row lock on the invoice to serialize against concurrent payments
                invoice_query = db.query(Invoice).filter(
                    Invoice.id == candidate.id,
                    Invoice.status == InvoiceStatus.PENDING,
                )
                try:
                    invoice = invoice_query.with_for_update().first()
                except Exception as lock_err:
                    try:
                        bind = db.get_bind()
                        is_pg = getattr(bind.dialect, "name", None) == "postgresql"
                    except Exception:
                        is_pg = False
                    if is_pg:
                        logger.warning(
                            "Could not acquire row lock for invoice %s on Postgres: %s. Skipping to prevent unlocked mutation.",
                            candidate.id,
                            lock_err,
                        )
                        continue
                    invoice = candidate
                if invoice is None:
                    continue
                # If mock returns an unconfigured object, use candidate
                if not hasattr(invoice, "due_date") or invoice.due_date is None:
                    invoice = candidate

                practice = practice_cache.get(invoice.practice_id)
                if practice is None and invoice.practice_id not in practice_cache:
                    practice = db.query(Practice).filter(
                        Practice.id == invoice.practice_id
                    ).first()
                    practice_cache[invoice.practice_id] = practice
                if practice is None:
                    logger.warning(
                        "Skipping overdue sweep for invoice %s with no practice", invoice.id
                    )
                    continue

                practice_today = business_date(practice_timezone_of(practice), now)
                if invoice.due_date >= practice_today:
                    continue

                invoice.status = InvoiceStatus.OVERDUE
                past_due.append(invoice)
                if practice.late_fee_percentage is not None:
                    try:
                        late_fee_pct = Decimal(str(practice.late_fee_percentage))
                    except (InvalidOperation, TypeError, ValueError):
                        late_fee_pct = Decimal("0")
                    if late_fee_pct > 0:
                        current_items = list(invoice.line_items or [])
                        # L-8 FIX: structured late-fee marker instead of substring
                        # match. The old "late fee" in description check could be
                        # tripped by a user-typed line (blocking a legitimate
                        # fee) or bypassed by renaming (double-charging).
                        # Legacy rows without "kind" still match by description
                        # for idempotency; new rows always carry kind=late_fee.
                        def _is_late_fee(item: object) -> bool:
                            if not isinstance(item, dict):
                                return False
                            if item.get("kind") == "late_fee":
                                return True
                            return "late fee" in str(item.get("description", "")).lower()

                        has_late_fee = any(_is_late_fee(item) for item in current_items)
                        if not has_late_fee:
                            cent = Decimal("0.01")
                            late_fee = (
                                Decimal(str(invoice.subtotal)) * (late_fee_pct / Decimal("100"))
                            ).quantize(cent, rounding=_MONEY_ROUNDING)
                            if late_fee > 0:
                                current_items.append(
                                    {
                                        # L-3 FIX: money as quantized decimal
                                        # strings, not binary float.
                                        "kind": "late_fee",
                                        "description": f"Late Fee ({late_fee_pct}%)",
                                        "quantity": 1,
                                        "unit_price": str(late_fee),
                                        "total": str(late_fee),
                                    }
                                )
                                invoice.line_items = current_items
                                invoice.subtotal = (Decimal(str(invoice.subtotal)) + late_fee).quantize(cent, rounding=_MONEY_ROUNDING)
                                tax_rate = Decimal(str(invoice.tax_rate or 0))
                                invoice.tax = (invoice.subtotal * tax_rate).quantize(cent, rounding=_MONEY_ROUNDING)
                                invoice.total = invoice.subtotal + invoice.tax
                                # L-5 FIX: keep GST splits consistent when the
                                # late fee changes subtotal/tax.
                                _tax_q = invoice.tax
                                if (getattr(invoice, "is_inter_state", "N") or "N").upper() == "Y":
                                    invoice.cgst_amount = Decimal("0.00")
                                    invoice.sgst_amount = Decimal("0.00")
                                    invoice.igst_amount = _tax_q
                                else:
                                    _cgst = (_tax_q / 2).quantize(cent, rounding=_MONEY_ROUNDING)
                                    invoice.cgst_amount = _cgst
                                    invoice.sgst_amount = _tax_q - _cgst
                                    invoice.igst_amount = Decimal("0.00")
                db.commit()
            except Exception as item_err:
                db.rollback()
                logger.error("Failed to mark invoice %s overdue: %s", candidate.id, item_err)

        if past_due:
            logger.info("Marked %s past-due invoice(s) OVERDUE", len(past_due))
        return {"marked_overdue": len(past_due)}
    except Exception as exc:
        db.rollback()
        logger.error("Error in mark_overdue_invoices: %s", exc)
        raise self.retry(exc=exc, countdown=300)
    finally:
        if lock_acquired:
            _release_task_lock(db, "mark-overdue-invoices")
        db.close()


class _ImmediateBackgroundTasks:
    """FastAPI ``BackgroundTasks`` shim for the Celery dunning run.

    ``process_dunning`` queues dunning emails onto a BackgroundTasks object;
    inside a worker there is no request lifecycle to drain them, so they are
    run inline after the ledger changes are committed.
    """

    def __init__(self):
        self._tasks = []

    def add_task(self, func, *args, **kwargs):
        self._tasks.append((func, args, kwargs))

    async def drain(self):
        for func, args, kwargs in self._tasks:
            try:
                await func(*args, **kwargs)
            except Exception as exc:
                logger.error("Dunning follow-up task failed: %s", exc)


async def _run_dunning_sweep() -> Dict[str, int]:
    from app.services.subscription_billing import SubscriptionBillingService

    background_tasks = _ImmediateBackgroundTasks()
    async with AsyncSessionLocal() as session:
        result = await SubscriptionBillingService.process_dunning(
            session, background_tasks
        )
    await background_tasks.drain()
    return result


@shared_task(bind=True, max_retries=3, acks_late=True, reject_on_worker_lost=True)
def process_dunning_task(self) -> Dict[str, Any]:
    """Hourly dunning sweep for past-due subscriptions (audit finding H2).

    Before this existed, payment retries only happened when an owner manually
    called POST /subscriptions/dunning/process. Concurrency: the sweep and
    that manual endpoint share process_dunning's row-level
    ``with_for_update(skip_locked=True)`` on PostgreSQL, and the advisory
    lock below keeps overlapping Beat runs of the sweep itself apart.
    """
    db = SessionLocal()
    try:
        if not _try_acquire_task_lock(db, "process-dunning"):
            return {"status": "skipped", "reason": "another dunning sweep is active"}
        result = _run(_run_dunning_sweep())
        logger.info("Dunning sweep completed: %s", result)
        return result
    except Exception as exc:
        db.rollback()
        logger.error("Error in process_dunning_task: %s", exc)
        raise self.retry(exc=exc, countdown=300)
    finally:
        db.close()


@shared_task(bind=True, max_retries=3, acks_late=True, reject_on_worker_lost=True)
def purge_expired_anonymized_patients(self) -> Dict[str, Any]:
    """Daily hard purge of anonymized patients past the retention window.

    Implements docs/DATA_RETENTION_POLICY.md § 2 + § 6: once every billing
    disposition for a fully-anonymized patient ([deleted]/[deleted], INACTIVE)
    is older than the EFFECTIVE retention window — max(per-practice
    ``practices.retention_years``, RETENTION_ANONYMIZED_PURGE_YEARS) — the
    orphaned rows + the placeholder row itself are deleted and a write-once
    ``patient_purged`` audit row records the per-table counts (the certificate
    of destruction).

    Batch-bounded (RETENTION_ANONYMIZED_PURGE_BATCH_SIZE, default 50) and
    disabled via RETENTION_ANONYMIZED_PURGE_ENABLED=false.
    """
    from app.core.config_simple import settings
    from app.core.audit import log_audit_event_sync
    from app.services.retention_service import RetentionService

    db = SessionLocal()
    try:
        if not settings.RETENTION_ANONYMIZED_PURGE_ENABLED:
            return {"status": "skipped", "reason": "RETENTION_ANONYMIZED_PURGE_ENABLED=false"}
        if not _try_acquire_task_lock(db, "purge-anonymized-patients"):
            return {"status": "skipped", "reason": "another purge run is active"}

        now = datetime.now(timezone.utc)
        platform_default = max(0, settings.RETENTION_ANONYMIZED_PURGE_YEARS)
        # Marker matching happens in Python (Fernet-encrypted names defeat SQL
        # equality); reuse the service's candidate scan for consistency with
        # the async path.
        candidates = db.query(Patient).filter(
            Patient.status == "INACTIVE",
        ).order_by(Patient.updated_at.asc().nullslast()).limit(
            max(1, settings.RETENTION_ANONYMIZED_PURGE_BATCH_SIZE) * 10
        ).all()
        candidates = [
            p for p in candidates
            if p.first_name == "[deleted]" and p.last_name == "[deleted]"
        ][: max(1, settings.RETENTION_ANONYMIZED_PURGE_BATCH_SIZE)]

        purged: int = 0
        scanned = len(candidates)
        detail: list = []
        for patient in candidates:
            anchor = _retention_anchor_sync(db, patient)
            effective_years = await_retention_years(
                db, patient.practice_id, platform_default=platform_default
            )
            minor_ceiling = getattr(patient, "purge_eligible_at", None)
            if not RetentionService.is_eligible_for_purge(
                anchor,
                now=now,
                retention_years=effective_years,
                purge_eligible_at=minor_ceiling,
            ):
                continue
            try:
                with db.begin_nested():
                    result = RetentionService.purge_patient_hard(db, patient)
                    log_audit_event_sync(
                        db,
                        None,
                        "patient_purged",
                        "patient",
                        patient.id,
                        None,
                        {
                            "anchor": anchor.isoformat() if anchor else None,
                            "retention_years": effective_years,
                            "purge_eligible_at": minor_ceiling.isoformat() if minor_ceiling else None,
                            "deleted": result["deleted"],
                        },
                    )
                    purged += 1
                    detail.append(result)
            except Exception as patient_exc:
                logger.error("Failed to purge patient %s in batch: %s", patient.id, patient_exc)
                continue
        db.commit()
        logger.info("Anonymized-patient purge: purged %s of %s scanned", purged, scanned)
        return {"purged": purged, "scanned": scanned, "detail": detail}
    except Exception as exc:
        db.rollback()
        logger.error("Error in purge_expired_anonymized_patients: %s", exc)
        raise self.retry(exc=exc, countdown=3600)
    finally:
        db.close()


def await_retention_years(db, practice_id, *, platform_default: int) -> int:
    """Sync effective retention window: max(practice, platform default).

    Mirrors RetentionService.effective_retention_years without async, since
    the purge task runs on a sync Celery session.
    """
    from sqlalchemy import func as _func

    from app.models.practice import Practice as _Practice

    value = (
        db.query(_func.max(_Practice.retention_years))
        .filter(_Practice.id == practice_id)
        .scalar()
    )
    if value is None:
        return platform_default
    return max(int(value), int(platform_default))


def _retention_anchor_sync(db, patient):
    from sqlalchemy import func as _func

    from app.models.billing import Invoice as _Invoice
    from app.models.billing import Payment as _Payment
    from app.models.billing import PaymentPlan as _PaymentPlan
    from app.models.insurance import InsuranceClaim as _Claim

    anchors = []
    for model, column in (
        (_Invoice, _Invoice.created_at),
        (_Payment, _Payment.created_at),
        (_PaymentPlan, _PaymentPlan.updated_at),
        (_Claim, _Claim.created_at),
    ):
        value = (
            db.query(_func.max(column)).filter(model.patient_id == patient.id).scalar()
        )
        if value is not None:
            anchors.append(
                value.replace(tzinfo=timezone.utc)
                if value.tzinfo is None
                else value
            )
    if anchors:
        return max(anchors)
    updated = getattr(patient, "updated_at", None)
    if updated is None:
        return None
    return updated.replace(tzinfo=timezone.utc) if updated.tzinfo is None else updated


@shared_task(bind=True, max_retries=3, acks_late=True, reject_on_worker_lost=True)
def purge_expired_token_revocations(self):
    """Daily task to purge expired token revocation rows from the database."""
    db = SessionLocal()
    try:
        from app.core.token_blacklist import purge_expired_revocations_sync
        deleted_count = purge_expired_revocations_sync(db)
        db.commit()
        logger.info("Purged %d expired token revocation rows", deleted_count)
        return {"deleted_count": deleted_count}
    except Exception as exc:
        db.rollback()
        logger.error("Error in purge_expired_token_revocations: %s", exc)
        raise self.retry(exc=exc, countdown=3600)
    finally:
        db.close()

