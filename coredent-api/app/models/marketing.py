"""
Marketing Models
Campaign and marketing automation tracking

Column types match the migrations. These models previously declared String for
id/practice_id/campaign_id/patient_id while the migrations created UUID, and the
database enforces what the migration created: SQLite accepts a varchar against a
uuid column, PostgreSQL rejects it with DatatypeMismatchError on the first
insert. Caught by scripts/check_schema_drift.py, which now runs in CI.
"""

from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey, JSON, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
import enum

from app.core.base import Base


class CampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CampaignType(str, enum.Enum):
    EMAIL = "email"
    SMS = "sms"


class AudienceType(str, enum.Enum):
    ALL_PATIENTS = "all_patients"
    TARGETED = "targeted"
    NEW_PATIENTS = "new_patients"
    RETURNING = "returning"
    CUSTOM = "custom"


class Campaign(Base):
    __tablename__ = "marketing_campaigns"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    campaign_type = Column(String(50), nullable=False, default="email")
    status = Column(String(50), nullable=False, default="draft")
    audience_type = Column(String(50), nullable=False, default="all_patients")
    target_criteria = Column(JSON, nullable=True)
    scheduled_date = Column(DateTime(timezone=True), nullable=True)
    sent_date = Column(DateTime(timezone=True), nullable=True)
    total_recipients = Column(Integer, default=0)
    sent_count = Column(Integer, default=0)
    opened_count = Column(Integer, default=0)
    clicked_count = Column(Integer, default=0)
    bounced_count = Column(Integer, default=0)
    unsubscribed_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    practice = relationship("Practice", back_populates="campaigns")


class MarketingTemplate(Base):
    __tablename__ = "marketing_templates"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    name = Column(String(255), nullable=False)
    subject = Column(String(255), nullable=True)
    body_content = Column(Text, nullable=True)
    template_type = Column(String(50), nullable=False, default="email")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    practice = relationship("Practice", back_populates="marketing_templates")


class CampaignSegment(Base):
    __tablename__ = "marketing_campaign_segments"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("marketing_campaigns.id"), nullable=False)
    name = Column(String(255), nullable=False)
    criteria = Column(JSON, nullable=True)
    patient_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    campaign = relationship("Campaign", backref="segments")


class MarketingEmail(Base):
    __tablename__ = "marketing_emails"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("marketing_campaigns.id"), nullable=False)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    email_address = Column(String(255), nullable=False)
    subject = Column(String(255), nullable=True)
    status = Column(String(50), default="pending")
    opened_at = Column(DateTime(timezone=True), nullable=True)
    clicked_at = Column(DateTime(timezone=True), nullable=True)
    bounced = Column(Boolean, default=False)
    unsubscribed = Column(Boolean, default=False)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    campaign = relationship("Campaign", backref="emails")
    patient = relationship("Patient", backref="marketing_emails")


class NewsletterSubscription(Base):
    __tablename__ = "newsletter_subscriptions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=True)
    email = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    subscribed_at = Column(DateTime(timezone=True), server_default=func.now())
    unsubscribed_at = Column(DateTime(timezone=True), nullable=True)
    practice = relationship("Practice", back_populates="newsletter_subscriptions")
    patient = relationship("Patient", backref="newsletter_subscription")