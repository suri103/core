"""Durable ledger of payment-processor webhook events.

Audit finding C-01: the Stripe webhook marked an event as processed in Redis
*before* invoking the handler, and the payment handler only ever *updated* an
existing ``PaymentTransaction``. When no local row matched the incoming
``payment_intent``, the webhook still answered 200 -- so a real, successful
external payment could be acknowledged with nothing recorded anywhere.

Two things fix that: releasing the dedup marker on handler failure (so
retries are reprocessed), and this table (so an event that can never be
mapped to a tenant is still recorded rather than silently dropped).

The invariant this table enforces: **we only answer 200 to a processor after
the event is durably recorded.** Either it produced a ``PaymentTransaction``,
or it is sitting here as ``UNRECONCILED`` waiting for an operator.

It also provides database-backed idempotency as a second line of defence
behind Redis: ``event_id`` is unique, so a replayed event cannot be applied
twice even if Redis has been flushed.

PHI: the raw processor payload is deliberately NOT stored. Only an
allowlisted set of non-clinical routing fields is persisted (see
``app.services.processor_events.summarize_event``).
"""

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
import uuid

from app.core.base import Base


class ProcessorEventStatus(str, enum.Enum):
    """Terminal state of a processor webhook event."""

    # Handled and reflected in the local ledger.
    PROCESSED = "processed"
    # The processor reports money moved, but we could not map the event to a
    # practice/patient. Requires operator reconciliation. NEVER auto-retried,
    # because a retry cannot supply the missing metadata.
    UNRECONCILED = "unreconciled"
    # Handler raised. The dedup marker was released; the processor will retry.
    FAILED = "failed"
    # Recorded for audit but intentionally not acted on (unhandled type).
    IGNORED = "ignored"


class ProcessorWebhookEvent(Base):
    """One row per payment-processor webhook event we have seen."""

    __tablename__ = "processor_webhook_events"
    __table_args__ = (
        Index("ix_processor_events_status_received", "status", "received_at"),
        Index("ix_processor_events_object", "processor", "processor_object_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # "stripe", "razorpay", ...
    processor = Column(String(30), nullable=False)
    # The processor's own event id. Unique: this is the idempotency key.
    event_id = Column(String(255), nullable=False, unique=True, index=True)
    event_type = Column(String(100), nullable=False)

    status = Column(
        Enum(ProcessorEventStatus), nullable=False, default=ProcessorEventStatus.PROCESSED
    )

    # Nullable: an unreconciled event is precisely one where we could not
    # determine the tenant.
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=True)

    # e.g. the payment_intent / charge id this event concerns.
    processor_object_id = Column(String(255), index=True)

    # Amount exactly as the processor reported it, in minor units (cents /
    # paise). Stored as reported so reconciliation is not confused by our own
    # rounding. BigInteger because minor units overflow Numeric(10,2) framing.
    amount_minor = Column(BigInteger)
    currency = Column(String(3))

    # Link to the ledger row this event produced, when it produced one.
    payment_transaction_id = Column(
        UUID(as_uuid=True), ForeignKey("payment_transactions.id"), nullable=True, index=True
    )

    # Allowlisted, non-PHI routing fields only. See summarize_event().
    summary = Column(JSON)

    error_message = Column(Text)
    resolution_notes = Column(Text)

    received_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resolved_at = Column(DateTime(timezone=True))

    practice = relationship("Practice")
    payment_transaction = relationship("PaymentTransaction")

    def __repr__(self):
        return (
            f"<ProcessorWebhookEvent {self.processor}:{self.event_id} "
            f"{self.event_type} {self.status}>"
        )
