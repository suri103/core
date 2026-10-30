"""
Insurance Models
Insurance carriers, patient insurance, claims, and payments
"""

from sqlalchemy import Column, String, DateTime, ForeignKey, Enum, Numeric, Date, Boolean, Text, Integer, UniqueConstraint, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from decimal import Decimal
import uuid
import enum

from app.core.base import Base


class InsuranceType(str, enum.Enum):
    """Insurance type"""
    PRIMARY = "primary"
    SECONDARY = "secondary"
    TERTIARY = "tertiary"


class ClaimStatus(str, enum.Enum):
    """Claim status"""
    DRAFT = "draft"
    PENDING = "pending"
    # H-03: reserved locally and committed BEFORE the clearinghouse call, so a
    # crash between "external submit succeeded" and "local commit" leaves an
    # in-flight marker instead of losing the submission. Never a resting state.
    SUBMITTING = "submitting"
    SUBMITTED = "submitted"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    PARTIALLY_APPROVED = "partially_approved"
    DENIED = "denied"
    PAID = "paid"
    APPEALED = "appealed"
    # Terminal failure of the submission attempt itself (transport/rejection),
    # distinct from DENIED which is a payer adjudication outcome.
    SUBMISSION_FAILED = "submission_failed"


class RelationshipToSubscriber(str, enum.Enum):
    """Patient relationship to insurance subscriber"""
    SELF = "self"
    SPOUSE = "spouse"
    CHILD = "child"
    OTHER = "other"


class FeeSchedule(Base):
    """Fee schedule for specific insurance plans or cash prices"""
    __tablename__ = "fee_schedules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    practice = relationship("Practice")
    entries = relationship("FeeScheduleEntry", back_populates="fee_schedule", cascade="all, delete-orphan")
    carriers = relationship("InsuranceCarrier", back_populates="fee_schedule")


class FeeScheduleEntry(Base):
    """Specific fee for an ADA code in a fee schedule"""
    __tablename__ = "fee_schedule_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fee_schedule_id = Column(UUID(as_uuid=True), ForeignKey("fee_schedules.id"), nullable=False)

    # Can link either by ADA code string or by explicit foreign key to procedure_library
    ada_code = Column(String(10), nullable=False, index=True)
    fee = Column(Numeric(10, 2), nullable=False)
    is_allowed_amount = Column(Boolean, default=True)

    __table_args__ = (
        UniqueConstraint('fee_schedule_id', 'ada_code', name='uix_fee_schedule_ada_code'),
    )

    # Relationships
    fee_schedule = relationship("FeeSchedule", back_populates="entries")


class InsuranceCarrier(Base):
    """Insurance carrier/company model"""
    __tablename__ = "insurance_carriers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=True)
    name = Column(String(255), nullable=False, index=True)
    phone = Column(String(20))
    fax = Column(String(20))
    email = Column(String(255))
    website = Column(String(255))

    # Address
    address_line1 = Column(String(255))
    address_line2 = Column(String(255))
    city = Column(String(100))
    state = Column(String(2))
    zip_code = Column(String(10))

    # EDI Information
    payer_id = Column(String(50), index=True)  # Electronic payer ID
    edi_enabled = Column(Boolean, default=False)

    # Fee Schedule Link
    fee_schedule_id = Column(UUID(as_uuid=True), ForeignKey("fee_schedules.id"))

    # Notes
    notes = Column(Text)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    patient_insurances = relationship("PatientInsurance", back_populates="carrier")
    claims = relationship("InsuranceClaim", back_populates="carrier")
    eligibility = relationship("Eligibility", back_populates="carrier")
    fee_schedule = relationship("FeeSchedule", back_populates="carriers")

    def __repr__(self):
        return f"<InsuranceCarrier {self.name}>"


class PatientInsurance(Base):
    """Patient insurance information"""
    __tablename__ = "patient_insurances"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    carrier_id = Column(UUID(as_uuid=True), ForeignKey("insurance_carriers.id"), nullable=False)
    subscriber_id = Column(String(100), nullable=False)
    group_number = Column(String(100))
    relationship_to_subscriber = Column(String(50), default="self")

    # Coverage Details
    is_primary = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    coverage_type = Column(String(50))  # HMO, PPO, EPO, etc.

    # Financial Limits
    annual_maximum = Column(Numeric(10, 2))
    annual_deductible = Column(Numeric(10, 2))
    deductible_met = Column(Numeric(10, 2), default=0)
    benefits_used = Column(Numeric(10, 2), default=0)

    # Coverage Percentages
    preventive_coverage = Column(Integer, default=100)  # Percentage
    basic_coverage = Column(Integer, default=80)
    major_coverage = Column(Integer, default=50)
    ortho_coverage = Column(Integer, default=0)

    # Effective Dates
    effective_date = Column(Date)
    expiration_date = Column(Date)

    # Verification
    verified = Column(Boolean, default=False)
    verified_at = Column(DateTime(timezone=True))
    verified_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    patient = relationship("Patient", back_populates="insurances")
    carrier = relationship("InsuranceCarrier", back_populates="patient_insurances")
    claims = relationship("InsuranceClaim", back_populates="patient_insurance")
    eligibility = relationship("Eligibility", back_populates="patient_insurance", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<PatientInsurance {self.subscriber_id} - {self.carrier_id}>"


class InsuranceClaim(Base):
    """Insurance claim model"""
    __tablename__ = "insurance_claims"
    __table_args__ = (
        UniqueConstraint('practice_id', 'claim_number', name='uq_practice_claim_number'),
        # H-03: durable idempotency for clearinghouse submission. The external
        # POST used to happen before the local commit, so a failed commit
        # meant a retry re-submitted the same claim to the payer. The old
        # guard was a five-minute "any claim for this patient" query, which
        # both let duplicates through after five minutes and blocked
        # legitimate same-day second claims.
        UniqueConstraint(
            'practice_id',
            'submission_idempotency_key',
            name='uq_practice_claim_idempotency_key',
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    patient_insurance_id = Column(UUID(as_uuid=True), ForeignKey("patient_insurances.id"), nullable=False)
    carrier_id = Column(UUID(as_uuid=True), ForeignKey("insurance_carriers.id"), nullable=False)

    # Claim Information
    claim_number = Column(String(50), nullable=False, index=True)
    status = Column(Enum(ClaimStatus), default=ClaimStatus.DRAFT)

    # Dates
    service_date = Column(Date, nullable=False)
    submission_date = Column(Date)
    received_date = Column(Date)
    paid_date = Column(Date)

    # Financial
    billed_amount = Column(Numeric(10, 2), nullable=False)
    allowed_amount = Column(Numeric(10, 2))
    deductible_amount = Column(Numeric(10, 2), default=0)
    copay_amount = Column(Numeric(10, 2), default=0)
    paid_amount = Column(Numeric(10, 2), default=0)
    patient_responsibility = Column(Numeric(10, 2), default=0)

    # Procedure Codes (stored as JSON)
    # Structure: [{ code: "D0120", description: "Periodic oral evaluation", fee: 75.00 }]
    procedure_codes = Column(JSON, default=list)

    # Diagnosis Codes
    diagnosis_codes = Column(JSON, default=list)

    # Notes and Attachments
    notes = Column(Text)
    denial_reason = Column(Text)

    # EDI Information
    edi_transaction_id = Column(String(100))
    edi_batch_id = Column(String(100))
    confirmation_number = Column(String(100))  # From clearinghouse

    # H-03: stable key identifying one submission attempt. Derived from the
    # claim's content (patient + insurance + service date + procedure set) or
    # supplied by the client. Unique per practice, so a retry of the same
    # logical submission cannot produce a second external claim.
    submission_idempotency_key = Column(String(255), index=True)
    submission_attempts = Column(Integer, default=0, nullable=False)
    submission_error = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    practice = relationship("Practice", back_populates="insurance_claims")
    patient = relationship("Patient", back_populates="insurance_claims")
    patient_insurance = relationship("PatientInsurance", back_populates="claims")
    carrier = relationship("InsuranceCarrier", back_populates="claims")
    eob = relationship("ExplanationOfBenefits", back_populates="claim", cascade="all, delete-orphan", uselist=False)

    @property
    def outstanding_balance(self) -> Decimal:
        """Calculate the balance without converting currency through float."""
        return (self.billed_amount or Decimal("0")) - (
            self.paid_amount or Decimal("0")
        )

    def __repr__(self):
        return f"<InsuranceClaim {self.claim_number} - {self.status}>"


class InsurancePreAuthorization(Base):
    """Insurance pre-authorization model"""
    __tablename__ = "insurance_pre_authorizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    patient_insurance_id = Column(UUID(as_uuid=True), ForeignKey("patient_insurances.id"), nullable=False)

    # Authorization Information
    authorization_number = Column(String(50), unique=True, nullable=False, index=True)
    status = Column(String(50), default="pending")  # pending, approved, denied

    # Dates
    request_date = Column(Date, nullable=False)
    approval_date = Column(Date)
    expiration_date = Column(Date)

    # Treatment Information
    procedure_codes = Column(Text)  # JSON string
    estimated_cost = Column(Numeric(10, 2))
    approved_amount = Column(Numeric(10, 2))

    notes = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    patient = relationship("Patient", back_populates="pre_authorizations")
    patient_insurance = relationship("PatientInsurance")

    def __repr__(self):
        return f"<PreAuthorization {self.authorization_number} - {self.status}>"


class Eligibility(Base):
    """Eligibility verification result"""
    __tablename__ = "eligibility"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    patient_insurance_id = Column(UUID(as_uuid=True), ForeignKey("patient_insurances.id"), nullable=False)
    carrier_id = Column(UUID(as_uuid=True), ForeignKey("insurance_carriers.id"), nullable=False)
    verified_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)

    # Coverage details
    coverage_status = Column(String(50))  # e.g., "covered", "not_covered"
    remaining_benefits = Column(Numeric(10, 2))
    deductible_remaining = Column(Numeric(10, 2))
    notes = Column(Text)

    # Relationships
    patient = relationship("Patient", back_populates="eligibility")
    patient_insurance = relationship("PatientInsurance", back_populates="eligibility")
    carrier = relationship("InsuranceCarrier", back_populates="eligibility")

    def __repr__(self):
        return f"<Eligibility {self.id} - {self.coverage_status}>"


class ExplanationOfBenefits(Base):
    """EOB for a claim"""
    __tablename__ = "explanations_of_benefits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id = Column(UUID(as_uuid=True), ForeignKey("insurance_claims.id"), nullable=False)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    description = Column(Text)
    amount_covered = Column(Numeric(10, 2))
    amount_patient_responsibility = Column(Numeric(10, 2))

    # Relationships
    claim = relationship("InsuranceClaim", back_populates="eob")

    def __repr__(self):
        return f"<EOB {self.id} for Claim {self.claim_id}>"