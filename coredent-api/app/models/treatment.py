"""
Treatment Planning Models
Treatment plans, procedures, cost estimates, and acceptance tracking
"""

from sqlalchemy import Column, String, DateTime, ForeignKey, Enum, Numeric, Date, Boolean, Text, Integer, JSON, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from decimal import Decimal
import uuid
import enum

from app.core.base import Base


class TreatmentPlanStatus(str, enum.Enum):
    """Treatment plan status"""
    DRAFT = "draft"
    PRESENTED = "presented"
    ACCEPTED = "accepted"
    PARTIALLY_ACCEPTED = "partially_accepted"
    DECLINED = "declined"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ProcedureType(str, enum.Enum):
    """Procedure type/category"""
    PREVENTIVE = "preventive"
    DIAGNOSTIC = "diagnostic"
    RESTORATIVE = "restorative"
    ENDODONTIC = "endodontic"
    PERIODONTAL = "periodontal"
    PROSTHODONTIC = "prosthodontic"
    ORAL_SURGERY = "oral_surgery"
    ORTHODONTIC = "orthodontic"
    COSMETIC = "cosmetic"
    OTHER = "other"


class ToothSurface(str, enum.Enum):
    """Tooth surfaces for restorations"""
    MESIAL = "mesial"
    DISTAL = "distal"
    OCCLUSAL = "occlusal"
    INCISAL = "incisal"
    BUCCAL = "buccal"
    LINGUAL = "lingual"
    PALATAL = "palatal"
    LABIAL = "labial"
    CERVICAL = "cervical"


class TreatmentPlan(Base):
    """Treatment plan model"""
    __tablename__ = "treatment_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Plan Information
    plan_name = Column(String(255), nullable=False)
    status = Column(Enum(TreatmentPlanStatus), default=TreatmentPlanStatus.DRAFT)

    # Clinical Information
    chief_complaint = Column(Text)
    diagnosis = Column(Text)
    treatment_goals = Column(Text)

    # Financial Information
    total_estimated_cost = Column(Numeric(10, 2), default=0)
    total_insurance_estimate = Column(Numeric(10, 2), default=0)
    total_patient_responsibility = Column(Numeric(10, 2), default=0)

    # Dates
    created_date = Column(Date, nullable=False, default=func.current_date())
    presented_date = Column(Date)
    accepted_date = Column(Date)
    target_start_date = Column(Date)
    target_completion_date = Column(Date)

    # Acceptance Information
    acceptance_method = Column(String(50))  # in_person, electronic, phone
    acceptance_notes = Column(Text)

    # Visual Configuration (stored as JSON)
    # Structure: { layout: "grid", tooth_chart: true, cost_breakdown: true }
    visual_config = Column(JSON, default=dict)

    notes = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    practice = relationship("Practice", back_populates="treatment_plans")
    patient = relationship("Patient", back_populates="treatment_plans")
    provider = relationship("User", back_populates="treatment_plans")
    procedures = relationship("TreatmentProcedure", back_populates="treatment_plan", cascade="all, delete-orphan")
    phases = relationship("TreatmentPhase", back_populates="treatment_plan", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<TreatmentPlan {self.plan_name} - {self.status}>"


class TreatmentPhase(Base):
    """Treatment phase for multi-phase plans"""
    __tablename__ = "treatment_phases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    treatment_plan_id = Column(UUID(as_uuid=True), ForeignKey("treatment_plans.id"), nullable=False)

    # Phase Information
    phase_number = Column(Integer, nullable=False)
    phase_name = Column(String(255), nullable=False)
    description = Column(Text)

    # Financial Information
    estimated_cost = Column(Numeric(10, 2), default=0)
    insurance_estimate = Column(Numeric(10, 2), default=0)
    patient_responsibility = Column(Numeric(10, 2), default=0)

    # Dates
    target_start_date = Column(Date)
    target_completion_date = Column(Date)
    actual_start_date = Column(Date)
    actual_completion_date = Column(Date)

    # Status
    status = Column(String(50), default="planned")  # planned, in_progress, completed, cancelled

    # Ordering
    display_order = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    treatment_plan = relationship("TreatmentPlan", back_populates="phases")
    procedures = relationship("TreatmentProcedure", back_populates="phase", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<TreatmentPhase {self.phase_name} - Phase {self.phase_number}>"


class TreatmentProcedure(Base):
    """Individual procedure within a treatment plan"""
    __tablename__ = "treatment_procedures"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    treatment_plan_id = Column(UUID(as_uuid=True), ForeignKey("treatment_plans.id"), nullable=False)
    phase_id = Column(UUID(as_uuid=True), ForeignKey("treatment_phases.id"))

    # Procedure Information
    procedure_type = Column(Enum(ProcedureType), nullable=False)
    ada_code = Column(String(10), nullable=False)  # ADA Code (D0120, D2750, etc.)
    description = Column(String(500), nullable=False)

    # Tooth Information
    tooth_number = Column(String(20))  # Can be multiple: "1,2,3" or "14-19"
    surfaces = Column(String(100))  # Comma-separated surfaces: "MO,DO"
    quadrant = Column(Integer)  # 1-4 for quadrants

    # Financial Information
    fee = Column(Numeric(10, 2), nullable=False)
    insurance_estimate = Column(Numeric(10, 2), default=0)
    patient_responsibility = Column(Numeric(10, 2), default=0)

    # Insurance Information
    is_covered = Column(Boolean, default=True)
    coverage_percentage = Column(Integer, default=0)  # 0-100%
    requires_pre_auth = Column(Boolean, default=False)
    pre_auth_id = Column(UUID(as_uuid=True), ForeignKey("insurance_pre_authorizations.id"))

    # Clinical Information
    priority = Column(Integer, default=1)  # 1=high, 2=medium, 3=low
    complexity = Column(String(50))  # simple, moderate, complex
    duration_minutes = Column(Integer, default=30)

    # Status
    status = Column(String(50), default="planned")  # planned, scheduled, in_progress, completed, cancelled
    appointment_id = Column(UUID(as_uuid=True), ForeignKey("appointments.id"))

    # Acceptance
    is_accepted = Column(Boolean, default=False)
    acceptance_notes = Column(Text)

    # Ordering
    display_order = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    treatment_plan = relationship("TreatmentPlan", back_populates="procedures")
    phase = relationship("TreatmentPhase", back_populates="procedures")
    pre_authorization = relationship("InsurancePreAuthorization")
    appointment = relationship("Appointment")

    @property
    def insurance_coverage_amount(self) -> Decimal:
        """Calculate insurance coverage amount"""
        from decimal import Decimal, ROUND_HALF_UP
        if self.insurance_estimate is not None and Decimal(str(self.insurance_estimate)) > 0:
            return Decimal(str(self.insurance_estimate))
        fee = Decimal(str(self.fee or 0))
        pct = Decimal(str(self.coverage_percentage or 0))
        return (fee * pct / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @property
    def patient_amount(self) -> Decimal:
        """Calculate patient responsibility amount"""
        from decimal import Decimal
        if self.patient_responsibility is not None and Decimal(str(self.patient_responsibility)) > 0:
            return Decimal(str(self.patient_responsibility))
        return Decimal(str(self.fee or 0)) - self.insurance_coverage_amount

    def __repr__(self):
        return f"<TreatmentProcedure {self.ada_code} - {self.description}>"


class ProcedureLibrary(Base):
    """Library of common dental procedures with ADA codes"""
    __tablename__ = "procedure_library"
    __table_args__ = (
        UniqueConstraint('practice_id', 'ada_code', name='uq_practice_ada_code'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)

    # Procedure Information
    ada_code = Column(String(10), nullable=False, index=True)
    description = Column(String(500), nullable=False)
    long_description = Column(Text)
    procedure_type = Column(Enum(ProcedureType), nullable=False)

    # Category Information
    category = Column(String(100))  # Hygiene, Restorative, Surgery, etc.
    subcategory = Column(String(100))

    # Default Financial Information
    default_fee = Column(Numeric(10, 2))
    typical_duration_minutes = Column(Integer, default=30)

    # Clinical Information
    typical_coverage_percentage = Column(Integer)  # Typical insurance coverage
    requires_pre_auth = Column(Boolean, default=False)
    common_alternatives = Column(Text)  # JSON array of alternative codes

    # Metadata
    is_active = Column(Boolean, default=True)
    is_archived = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    practice = relationship("Practice")

    def __repr__(self):
        return f"<ProcedureLibrary {self.ada_code} - {self.description}>"


class TreatmentPlanTemplate(Base):
    """Templates for common treatment plans"""
    __tablename__ = "treatment_plan_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)

    # Template Information
    template_name = Column(String(255), nullable=False)
    description = Column(Text)
    category = Column(String(100))  # Ortho, Perio, Full Mouth, etc.

    # Clinical Information
    typical_diagnosis = Column(Text)
    typical_goals = Column(Text)

    # Template Configuration (stored as JSON)
    # Structure: { procedures: [{ada_code: "D2750", description: "Crown"}] }
    configuration = Column(JSON, nullable=False)

    # Usage Statistics
    usage_count = Column(Integer, default=0)
    last_used = Column(DateTime(timezone=True))

    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    practice = relationship("Practice")

    def __repr__(self):
        return f"<TreatmentPlanTemplate {self.template_name}>"


class TreatmentPlanNote(Base):
    """Notes and updates for treatment plans"""
    __tablename__ = "treatment_plan_notes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    treatment_plan_id = Column(UUID(as_uuid=True), ForeignKey("treatment_plans.id"), nullable=False)
    author_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Note Content
    note_type = Column(String(50), default="general")  # general, financial, clinical, update
    content = Column(Text, nullable=False)

    # Attachments (stored as JSON array of file paths)
    attachments = Column(JSON, default=list)

    # Visibility
    is_internal = Column(Boolean, default=True)  # Internal note vs patient-visible

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    treatment_plan = relationship("TreatmentPlan")
    author = relationship("User")

    def __repr__(self):
        return f"<TreatmentPlanNote {self.note_type} - {self.created_at}>"