"""
Referral Management Models
Patient referrals, specialist communication, and tracking
"""

from sqlalchemy import Column, String, DateTime, ForeignKey, Enum, Text, Numeric, Boolean, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.core.base import Base


class ReferralStatus(str, enum.Enum):
    """Referral status"""
    PENDING = "pending"
    SENT = "sent"
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class ReferralType(str, enum.Enum):
    """Types of referrals"""
    ORAL_SURGERY = "oral_surgery"
    ENDODONTICS = "endodontics"
    PERIODONTICS = "periodontics"
    ORTHODONTICS = "orthodontics"
    PROSTHODONTICS = "prosthodontics"
    PEDIATRIC = "pediatric"
    IMPLANT = "implant"
    COSMETIC = "cosmetic"
    EMERGENCY = "emergency"
    CONSULTATION = "consultation"
    OTHER = "other"


class ReferralSource(str, enum.Enum):
    """Referral sources"""
    PATIENT = "patient"
    INSURANCE = "insurance"
    FRIEND = "friend"
    PHYSICIAN = "physician"
    OTHER_DENTIST = "other_dentist"
    MARKETING = "marketing"
    OTHER = "other"


class ReferralSource1(Base):
    """Referral source/tracking model"""
    __tablename__ = "referral_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)

    # Source Information
    name = Column(String(255), nullable=False)
    source_type = Column(Enum(ReferralSource), nullable=False)

    # Contact Information
    contact_name = Column(String(100))
    email = Column(String(255))
    phone = Column(String(20))
    address = Column(String(255))

    # Professional Info (for doctors/referring dentists)
    specialty = Column(String(100))
    license_number = Column(String(50))

    # Status
    is_active = Column(Boolean, default=True)
    is_track_referrals = Column(Boolean, default=True)
    notes = Column(Text)

    # Deletion (HIPAA: soft delete to preserve referral attribution)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime(timezone=True))

    # Stats
    total_referrals = Column(String(20), default="0")
    successful_referrals = Column(String(20), default="0")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    practice = relationship("Practice", back_populates="referral_sources")
    referrals = relationship("Referral", back_populates="referral_source_obj")

    def __repr__(self):
        return f"<ReferralSource {self.name} - {self.source_type}>"


class Referral(Base):
    """Patient referral model"""
    __tablename__ = "referrals"
    __table_args__ = (
        UniqueConstraint('practice_id', 'referral_number', name='uq_practice_referral_number'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    referring_provider_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    referral_source_id = Column(UUID(as_uuid=True), ForeignKey("referral_sources.id"))

    # Internal Enterprise Referrals
    target_practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=True)
    is_internal = Column(Boolean, default=False)

    # Referral Information
    referral_number = Column(String(50), nullable=True, index=True)
    referral_type = Column(Enum(ReferralType), nullable=False)
    status = Column(Enum(ReferralStatus), default=ReferralStatus.PENDING)

    # Reason for Referral
    reason = Column(Text, nullable=False)
    clinical_notes = Column(Text)

    # Specialist Info
    specialist_name = Column(String(255))
    specialist_address = Column(String(255))
    specialist_phone = Column(String(20))
    specialist_fax = Column(String(20))

    # Dates
    referral_date = Column(DateTime(timezone=True), server_default=func.now())
    appointment_date = Column(DateTime(timezone=True))
    completed_date = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))

    # Soft delete (HIPAA audit-trail preservation). FIX: delete_referral
    # previously set these attributes without the columns existing — the
    # values were silently discarded and nothing was ever deleted.
    is_deleted = Column(Boolean, nullable=False, default=False, server_default="0")
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Results
    outcome = Column(Text)
    follow_up_required = Column(Boolean, default=False)
    follow_up_notes = Column(Text)

    # Financial
    referral_fee = Column(Numeric(10, 2))
    referral_received = Column(Boolean, default=False)
    payment_date = Column(DateTime(timezone=True))

    # Urgent
    is_urgent = Column(Boolean, default=False)
    urgent_reason = Column(Text)

    # Attachments
    attachments = Column(Text)  # JSON array of file URLs

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    practice = relationship("Practice", back_populates="referrals", foreign_keys=[practice_id])
    patient = relationship("Patient", back_populates="referrals")
    referring_provider = relationship("User", foreign_keys=[referring_provider_id])
    target_practice = relationship("Practice", foreign_keys=[target_practice_id], viewonly=True)
    referral_source_obj = relationship("ReferralSource1", back_populates="referrals")
    communications = relationship("ReferralCommunication", back_populates="referral", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Referral {self.id} - {self.referral_type} - {self.status}>"


class ReferralCommunication(Base):
    """Referral communication log"""
    __tablename__ = "referral_communications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    referral_id = Column(UUID(as_uuid=True), ForeignKey("referrals.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    # Communication Details
    communication_type = Column(String(20), nullable=False)  # note, email, phone, fax
    subject = Column(String(255))
    content = Column(Text)
    direction = Column(String(10))  # inbound, outbound

    # Related To
    related_to = Column(String(50))  # scheduling, result, complaint, etc.

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    referral = relationship("Referral", back_populates="communications")
    user = relationship("User")

    def __repr__(self):
        return f"<ReferralCommunication {self.communication_type} for Referral {self.referral_id}>"


class ReferralReport(Base):
    """Referral reporting and analytics"""
    __tablename__ = "referral_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)

    # Report Details
    report_name = Column(String(255), nullable=False)
    report_type = Column(String(50))  # monthly, quarterly, annual

    # Date Range
    start_date = Column(DateTime(timezone=True))
    end_date = Column(DateTime(timezone=True))

    # Metrics
    total_referrals = Column(String(20), default="0")
    completed_referrals = Column(String(20), default="0")
    pending_referrals = Column(String(20), default="0")
    cancelled_referrals = Column(String(20), default="0")
    no_shows = Column(String(20), default="0")

    # Revenue
    total_referral_fees = Column(Numeric(10, 2), default=0)
    collected_fees = Column(Numeric(10, 2), default=0)

    # By Type
    by_type = Column(Text)  # JSON of referral type counts

    # By Source
    by_source = Column(Text)  # JSON of source counts

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    practice = relationship("Practice", back_populates="referral_reports")

    def __repr__(self):
        return f"<ReferralReport {self.report_name}>"
