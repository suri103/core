"""
Clinical Models
Clinical notes, dental charts, and treatment plans
"""

from sqlalchemy import Column, String, DateTime, ForeignKey, Enum, Text, JSON, Numeric, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.core.base import Base


class NoteType(str, enum.Enum):
    """Clinical note types"""
    SOAP = "soap"
    PROGRESS = "progress"
    TREATMENT = "treatment"
    CONSULTATION = "consultation"
    FOLLOW_UP = "follow_up"
    PROCEDURE = "procedure"
    GENERAL = "general"


class ClinicalNote(Base):
    """Clinical note model"""
    __tablename__ = "clinical_notes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    appointment_id = Column(UUID(as_uuid=True), ForeignKey("appointments.id"))

    note_type = Column(Enum(NoteType), nullable=False)
    content = Column(Text, nullable=True)
    # SOAP breakdown (used when note_type == SOAP); content stores the free-text
    # body for non-SOAP note types. All are nullable so both shapes round-trip.
    subjective = Column(Text, nullable=True)
    objective = Column(Text, nullable=True)
    assessment = Column(Text, nullable=True)
    plan = Column(Text, nullable=True)
    signed_at = Column(DateTime(timezone=True), nullable=True)
    signed_by = Column(String(255), nullable=True)
    attachments = Column(JSON, default=[])  # Array of file URLs

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    patient = relationship("Patient", back_populates="clinical_notes")
    provider = relationship("User", back_populates="clinical_notes")

    def __repr__(self):
        return f"<ClinicalNote {self.id} - {self.note_type}>"


class DentalChart(Base):
    """Dental chart model"""
    __tablename__ = "dental_charts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), unique=True, nullable=False)

    # Chart data stored as JSON
    # Structure: { tooth_number: { conditions: [], procedures: [], notes: "" } }
    chart_data = Column(JSON, nullable=False, default={})

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    patient = relationship("Patient", back_populates="dental_chart")

    def __repr__(self):
        return f"<DentalChart for Patient {self.patient_id}>"


class PerioChart(Base):
    """Periodontal charting model - records probing depths, bleeding points, mobility"""
    __tablename__ = "perio_charts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    examination_date = Column(DateTime(timezone=True), server_default=func.now())

    # Legacy/Flexible storage
    perio_data = Column(JSON, nullable=False, default={})

    # Overall assessment
    overall_bleeding_index = Column(Numeric(5, 2))  # 0-100%
    plaque_index = Column(Numeric(5, 2))  # 0-100%
    calculus_index = Column(Numeric(5, 2))  # 0-100%
    diagnosis = Column(String(255))  # e.g., "Healthy", "Gingivitis", "Periodontitis"
    notes = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    patient = relationship("Patient", back_populates="perio_charts")
    provider = relationship("User")
    entries = relationship("PerioChartEntry", back_populates="perio_chart", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<PerioChart for Patient {self.patient_id} on {self.examination_date}>"


class PerioChartEntry(Base):
    """Detailed highly structured entry for a specific tooth in a PerioChart"""
    __tablename__ = "perio_chart_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    perio_chart_id = Column(UUID(as_uuid=True), ForeignKey("perio_charts.id"), nullable=False)
    tooth_number = Column(Integer, nullable=False)

    # 6-Point Pocket Depths (PD)
    pd_distobuccal = Column(Integer)
    pd_buccal = Column(Integer)
    pd_mesiobuccal = Column(Integer)
    pd_distolingual = Column(Integer)
    pd_lingual = Column(Integer)
    pd_mesiolingual = Column(Integer)

    # 6-Point Bleeding on Probing (BOP)
    bop_distobuccal = Column(Boolean, default=False)
    bop_buccal = Column(Boolean, default=False)
    bop_mesiobuccal = Column(Boolean, default=False)
    bop_distolingual = Column(Boolean, default=False)
    bop_lingual = Column(Boolean, default=False)
    bop_mesiolingual = Column(Boolean, default=False)

    # 6-Point Clinical Attachment Level (CAL) - Optional calculated or stored
    cal_distobuccal = Column(Integer)
    cal_buccal = Column(Integer)
    cal_mesiobuccal = Column(Integer)
    cal_distolingual = Column(Integer)
    cal_lingual = Column(Integer)
    cal_mesiolingual = Column(Integer)

    # Advanced clinical metrics
    mobility = Column(Integer)  # 0, 1, 2, 3
    furcation_class = Column(String(10))  # I, II, III, IV
    mucogingival_defect = Column(Boolean, default=False)

    # Position
    display_order = Column(Integer, default=0)

    # Relationships
    perio_chart = relationship("PerioChart", back_populates="entries")

    def __repr__(self):
        return f"<PerioChartEntry Tooth {self.tooth_number}>"
