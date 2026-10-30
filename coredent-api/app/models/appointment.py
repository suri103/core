"""
Appointment Models
Appointments, appointment types, and chairs/operatories
SECURITY: Added database indexes for query performance
"""

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum, Boolean, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.core.base import Base


class AppointmentStatus(str, enum.Enum):
    """Appointment status"""
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    CHECKED_IN = "checked_in"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class AppointmentTypeEnum(str, enum.Enum):
    """Common appointment types"""
    CLEANING = "cleaning"
    EXAM = "exam"
    FILLING = "filling"
    ROOT_CANAL = "root_canal"
    CROWN = "crown"
    EXTRACTION = "extraction"
    WHITENING = "whitening"
    CONSULTATION = "consultation"
    EMERGENCY = "emergency"
    OTHER = "other"


class Appointment(Base):
    """Appointment model"""
    __tablename__ = "appointments"

    # PERFORMANCE: Add composite indexes for common query patterns
    __table_args__ = (
        Index('idx_appointment_practice_date', 'practice_id', 'start_time'),
        Index('idx_appointment_patient', 'patient_id', 'start_time'),
        Index('idx_appointment_provider', 'provider_id', 'start_time'),
        Index('idx_appointment_chair', 'chair_id', 'start_time'),
        Index('idx_appointment_status_date', 'status', 'start_time'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    chair_id = Column(UUID(as_uuid=True), ForeignKey("chairs.id"), index=True)

    appointment_type = Column(Enum(AppointmentTypeEnum), nullable=False)
    status = Column(Enum(AppointmentStatus), default=AppointmentStatus.SCHEDULED)

    start_time = Column(DateTime(timezone=True), nullable=False, index=True)
    end_time = Column(DateTime(timezone=True), nullable=False)
    duration = Column(Integer, nullable=False)  # in minutes

    notes = Column(Text)
    # M-6 FIX: dedicated column for the cancellation reason. Previously the
    # reason was appended to ``notes`` (a free-text clinical observation
    # column), mixing which of state-machine metadata with clinical content.
    cancellation_reason = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    practice = relationship("Practice", back_populates="appointments")
    patient = relationship("Patient", back_populates="appointments")
    provider = relationship("User", back_populates="appointments")
    chair = relationship("Chair", back_populates="appointments")
    online_booking = relationship("OnlineBooking", back_populates="appointment", uselist=False)

    def __repr__(self):
        return f"<Appointment {self.id} - {self.appointment_type} - {self.status}>"


class AppointmentType(Base):
    """Appointment type configuration"""
    __tablename__ = "appointment_types"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    name = Column(String(100), nullable=False)
    duration = Column(Integer, nullable=False)  # default duration in minutes
    color = Column(String(7), nullable=False)  # hex color
    description = Column(Text)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    practice = relationship("Practice", back_populates="appointment_types")

    def __repr__(self):
        return f"<AppointmentType {self.name}>"


class Chair(Base):
    """Chair/Operatory model"""
    __tablename__ = "chairs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    name = Column(String(100), nullable=False)
    color = Column(String(7), default="#6B7280")  # hex color
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    practice = relationship("Practice", back_populates="chairs")
    appointments = relationship("Appointment", back_populates="chair")

    def __repr__(self):
        return f"<Chair {self.name}>"
