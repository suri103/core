"""Reminder model for scheduling notifications."""

import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.core.base import Base


class ReminderStatus(str, enum.Enum):
    """Durable state machine for an automated appointment reminder."""

    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"


class Reminder(Base):
    __tablename__ = "reminders"
    # A reminder is a durable delivery record. One scheduled appointment
    # reminder remains the product policy; the delivery lease below prevents
    # concurrent workers from sending that same row twice.
    __table_args__ = (
        UniqueConstraint("appointment_id", name="uq_reminders_appointment_id"),
        Index("ix_reminders_delivery_due", "status", "next_attempt_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    appointment_id = Column(
        UUID(as_uuid=True), ForeignKey("appointments.id"), nullable=False
    )
    reminder_type = Column(String(50), nullable=False)  # sms, email
    status = Column(Enum(ReminderStatus), default=ReminderStatus.PENDING)
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    sent_at = Column(DateTime(timezone=True))
    error_message = Column(String(500))

    # Lease-based delivery claim. A worker commits PROCESSING before provider
    # I/O; an expired lease is safely reclaimed by the periodic dispatcher.
    attempt_count = Column(Integer, nullable=False, default=0, server_default="0")
    next_attempt_at = Column(DateTime(timezone=True))
    claimed_at = Column(DateTime(timezone=True))
    claim_token = Column(String(64))
    claim_expires_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
