"""Durable outbox for practice daily-summary emails.

B7-9: ``send_daily_summary`` used to email admins directly under only an
advisory lock. If the process died between the provider call and any local
bookkeeping there was no record a summary was due or sent; conversely two
overlapping runs could both send. External email remains at-least-once at the
provider boundary (none of the configured providers accept idempotency keys),
but this table makes *our* side exactly-once:

* one row per (practice, local summary date, recipient user) — enforced by a
  database unique constraint, so concurrent schedulers converge on one intent;
* a claim/lease state machine like reminders: PENDING -> SENDING -> SENT,
  with FAILED + exponential backoff for retryable provider errors;
* expired SENDING leases are reclaimed by later runs.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, Enum, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.core.base import Base


class DailySummaryStatus(str, enum.Enum):
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"


class DailySummaryOutbox(Base):
    __tablename__ = "daily_summary_outbox"

    __table_args__ = (
        UniqueConstraint(
            "practice_id",
            "summary_date",
            "user_id",
            name="uq_daily_summary_practice_date_user",
        ),
        Index("ix_daily_summary_delivery_due", "status", "next_attempt_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(
        UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False
    )
    # The recipient is an admin/owner USER — deliberately not a patient, so
    # PatientMessage semantics do not apply.
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    # The practice-LOCAL business day the summary describes.
    summary_date = Column(Date, nullable=False)
    recipient_email = Column(String(255), nullable=False)

    status = Column(
        Enum(DailySummaryStatus, name="dailysummarystatus"),
        nullable=False,
        default=DailySummaryStatus.PENDING,
    )
    attempts = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(DateTime(timezone=True), nullable=True)
    last_attempt_at = Column(DateTime(timezone=True), nullable=True)
    # Lease ownership fields fence stale workers from finalizing a reclaimed
    # delivery after provider I/O.
    claim_token = Column(String(64), nullable=True)
    claimed_at = Column(DateTime(timezone=True), nullable=True)
    claim_expires_at = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    provider_message_id = Column(String(255), nullable=True)
    last_error = Column(String(500), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
