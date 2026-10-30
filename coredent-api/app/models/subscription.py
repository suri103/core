"""
Advanced Subscription Models
Supports: Auto-billing, Dunning, Proration, Trials, Cancellations, Usage-Based Billing
"""

from sqlalchemy import (
    Column, String, DateTime, ForeignKey, Enum, Text, Boolean, Numeric,
    Integer, JSON, Index, text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.core.base import Base


class SubscriptionInterval(str, enum.Enum):
    """Billing intervals"""
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"
    ANNUAL = "annual"


class SubscriptionStatus(str, enum.Enum):
    """Subscription lifecycle states"""
    TRIALING = "trialing"           # Active trial period
    ACTIVE = "active"               # Normal active subscription
    PAST_DUE = "past_due"           # Payment failed, grace period
    CANCELED = "canceled"           # Canceled but still accessible until period end
    PAUSED = "paused"               # Temporarily paused (user-initiated)
    EXPIRED = "expired"             # Period ended after cancellation
    INCOMPLETE = "incomplete"       # Payment pending (3D Secure, etc)
    UNPAID = "unpaid"               # Payment failed multiple times, access revoked


class ProrationBehavior(str, enum.Enum):
    """How to handle mid-cycle changes"""
    CREATE_PRORATIONS = "create_prorations"     # Generate credit/debit invoice items
    ALWAYS_INVOICE = "always_invoice"           # Immediately invoice the difference
    NONE = "none"                               # No proration, charge full amount


class UsageAggregationPeriod(str, enum.Enum):
    """Usage billing aggregation periods"""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class DunningAction(str, enum.Enum):
    """Actions in the dunning (retry) process"""
    RETRY_PAYMENT = "retry_payment"
    SEND_EMAIL = "send_email"
    SUSPEND_SUBSCRIPTION = "suspend_subscription"
    CANCEL_SUBSCRIPTION = "cancel_subscription"


class SubscriptionPlan(Base):
    """
    Subscription plan template
    Defines what features/services are included and billing schedule
    """
    __tablename__ = "subscription_plans"
    __table_args__ = (
        Index('idx_plan_practice_active', 'practice_id', 'is_active'),
        Index('idx_plan_stripe_id', 'stripe_price_id'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=True)  # NULL = global plan

    # Plan Details
    name = Column(String(255), nullable=False)
    description = Column(Text)
    short_description = Column(String(100))

    # Pricing
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="USD")
    interval = Column(Enum(SubscriptionInterval), nullable=False)

    # Trial
    trial_period_days = Column(Integer, default=0)

    # Features (stored as JSON)
    features = Column(JSON)  # ["feature_1", "feature_2", ...]

    # Limits (stored as JSON)
    limits = Column(JSON)  # {"patients": 1000, "users": 10, "storage_gb": 50}

    # Processor IDs
    stripe_price_id = Column(String(255))
    stripe_product_id = Column(String(255))
    razorpay_plan_id = Column(String(255))

    # Visibility
    is_active = Column(Boolean, default=True)
    is_recommended = Column(Boolean, default=False)
    sort_order = Column(Integer, default=0)

    # Usage-based billing settings
    is_usage_based = Column(Boolean, default=False)
    usage_meter_name = Column(String(255))  # What is being metered
    usage_unit_label = Column(String(50))   # What unit to display
    included_usage = Column(Numeric(10, 2), default=0)  # Included in base price
    overage_rate = Column(Numeric(10, 4), default=0)  # Price per unit over included

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    practice = relationship("Practice", back_populates="subscription_plans")
    subscriptions = relationship("Subscription", back_populates="plan")
    usage_meters = relationship("UsageMeter", back_populates="plan", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<SubscriptionPlan {self.name} - ${self.amount}/{self.interval}>"


class Subscription(Base):
    """
    Patient or Practice subscription instance
    Tracks the lifecycle from trial through active, past-due, and cancellation
    """
    __tablename__ = "subscriptions"
    __table_args__ = (
        Index('idx_sub_practice_status', 'practice_id', 'status'),
        Index('idx_sub_patient_status', 'patient_id', 'status'),
        Index('idx_sub_stripe_id', 'stripe_subscription_id'),
        Index(
            'uq_subscriptions_stripe_subscription_id',
            'stripe_subscription_id',
            unique=True,
            postgresql_where=text('stripe_subscription_id IS NOT NULL'),
            sqlite_where=text('stripe_subscription_id IS NOT NULL'),
        ),
        Index('idx_sub_next_billing', 'next_billing_date'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=True)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("subscription_plans.id"), nullable=False)
    payment_card_id = Column(UUID(as_uuid=True), ForeignKey("payment_cards.id"), nullable=True)

    # Status
    status = Column(Enum(SubscriptionStatus), default=SubscriptionStatus.INCOMPLETE)

    # Billing Schedule
    interval = Column(Enum(SubscriptionInterval), nullable=False)
    current_period_start = Column(DateTime(timezone=True))
    current_period_end = Column(DateTime(timezone=True))
    next_billing_date = Column(DateTime(timezone=True))
    billing_day = Column(Integer, default=1)  # Day of month to bill

    # Trial
    trial_start = Column(DateTime(timezone=True))
    trial_end = Column(DateTime(timezone=True))
    trial_used = Column(Boolean, default=False)

    # Cancellation
    cancel_at_period_end = Column(Boolean, default=False)
    canceled_at = Column(DateTime(timezone=True))
    cancellation_reason = Column(Text)
    cancellation_feedback = Column(String(255))  # Why they canceled

    # Paused
    paused_at = Column(DateTime(timezone=True))
    paused_until = Column(DateTime(timezone=True))

    # Proration
    proration_behavior = Column(Enum(ProrationBehavior), default=ProrationBehavior.CREATE_PRORATIONS)
    proration_date = Column(DateTime(timezone=True))

    # Processor
    stripe_subscription_id = Column(String(255))
    stripe_customer_id = Column(String(255))
    latest_invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=True)

    # Dunning
    dunning_retry_count = Column(Integer, default=0)
    dunning_max_retries = Column(Integer, default=4)  # Default 4 retry attempts
    last_payment_error = Column(Text)
    next_retry_at = Column(DateTime(timezone=True))

    # Usage tracking (for usage-based billing)
    current_usage = Column(Numeric(10, 2), default=0)
    current_overage = Column(Numeric(10, 2), default=0)

    # Metadata
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    practice = relationship("Practice", back_populates="subscriptions")
    patient = relationship("Patient", back_populates="subscriptions")
    plan = relationship("SubscriptionPlan", back_populates="subscriptions")
    payment_card = relationship("PaymentCard")
    latest_invoice = relationship("Invoice", overlaps="invoices")
    usage_records = relationship("UsageRecord", back_populates="subscription", cascade="all, delete-orphan")
    dunning_events = relationship("DunningEvent", back_populates="subscription", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="subscription", overlaps="latest_invoice")

    def __repr__(self):
        return f"<Subscription {self.id} - {self.status}>"


class UsageMeter(Base):
    """
    Defines what is tracked for usage-based billing
    """
    __tablename__ = "usage_meters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("subscription_plans.id"), nullable=False)
    meter_name = Column(String(255), nullable=False)
    unit_label = Column(String(50), nullable=False)
    aggregation = Column(String(50), default="sum")  # sum, max, latest
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    plan = relationship("SubscriptionPlan", back_populates="usage_meters")

    def __repr__(self):
        return f"<UsageMeter {self.meter_name}>"


class UsageRecord(Base):
    """
    Records usage events for usage-based billing
    """
    __tablename__ = "usage_records"
    __table_args__ = (
        Index('idx_usage_sub_period', 'subscription_id', 'timestamp'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=False)
    meter_id = Column(UUID(as_uuid=True), ForeignKey("usage_meters.id"), nullable=True)

    # Usage data
    quantity = Column(Numeric(10, 2), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    # Metadata (renamed from 'metadata' to avoid SQLAlchemy reserved word)
    description = Column(String(500))
    usage_metadata = Column(JSON)

    # Relationships
    subscription = relationship("Subscription", back_populates="usage_records")

    def __repr__(self):
        return f"<UsageRecord {self.quantity} {self.subscription_id}>"


class DunningEvent(Base):
    """
    Records dunning (payment retry) attempts and actions taken
    """
    __tablename__ = "dunning_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=False)
    attempt_number = Column(Integer, nullable=False)
    action = Column(Enum(DunningAction), nullable=False)
    result = Column(String(100))  # success, failed, skipped
    error_message = Column(Text)
    scheduled_at = Column(DateTime(timezone=True))
    executed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    subscription = relationship("Subscription", back_populates="dunning_events")

    def __repr__(self):
        return f"<DunningEvent attempt={self.attempt_number} action={self.action}>"


class CancellationSurvey(Base):
    """
    Tracks why customers canceled (for churn analysis)
    """
    __tablename__ = "cancellation_surveys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=False)

    # Cancellation reason codes
    reason_code = Column(String(50), nullable=False)
    # common_reasons: too_expensive, not_using, missing_features, competitor, other

    additional_feedback = Column(Text)
    likelihood_to_return = Column(Integer)  # 1-10 scale
    used_trial = Column(Boolean, default=False)
    sub_duration_days = Column(Integer)
    total_amount_paid = Column(Numeric(10, 2), default=0)

    # Save offered to try to win back
    save_offer_type = Column(String(50))  # discount, pause, feature_upgrade
    save_offer_accepted = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    subscription = relationship("Subscription")

    def __repr__(self):
        return f"<CancellationSurvey reason={self.reason_code}>"