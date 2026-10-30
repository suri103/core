"""
Appointment Schemas
Pydantic models for appointment data validation
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, validator
from uuid import UUID

from app.models.appointment import AppointmentStatus, AppointmentTypeEnum


# Display-name -> enum coercion for the appointment_type field. The React
# scheduling/demo form sends human-readable type names (e.g. "Checkup",
# "Root Canal", "Follow-up"); map them onto the validated enum, defaulting to
# OTHER so an unknown type never rejects a booking.
_TYPE_ALIASES = {
    "checkup": AppointmentTypeEnum.EXAM,
    "exam": AppointmentTypeEnum.EXAM,
    "cleaning": AppointmentTypeEnum.CLEANING,
    "filling": AppointmentTypeEnum.FILLING,
    "crown": AppointmentTypeEnum.CROWN,
    "root_canal": AppointmentTypeEnum.ROOT_CANAL,
    "extraction": AppointmentTypeEnum.EXTRACTION,
    "whitening": AppointmentTypeEnum.WHITENING,
    "consultation": AppointmentTypeEnum.CONSULTATION,
    "emergency": AppointmentTypeEnum.EMERGENCY,
    "follow_up": AppointmentTypeEnum.OTHER,
    "follow-up": AppointmentTypeEnum.OTHER,
    "other": AppointmentTypeEnum.OTHER,
}


def _coerce_appointment_type(raw: object) -> AppointmentTypeEnum:
    if isinstance(raw, AppointmentTypeEnum):
        return raw
    key = str(raw or "").strip().lower().replace(" ", "_")
    return _TYPE_ALIASES.get(key, AppointmentTypeEnum.OTHER)


class AppointmentBase(BaseModel):
    """Base appointment schema"""
    patient_id: UUID
    provider_id: Optional[UUID] = None
    chair_id: Optional[UUID] = None
    appointment_type: AppointmentTypeEnum
    status: Optional[AppointmentStatus] = AppointmentStatus.SCHEDULED
    start_time: datetime
    end_time: datetime
    duration: int = Field(..., gt=0, description="Duration in minutes")
    notes: Optional[str] = None

    @validator('end_time')
    def validate_end_time(cls, v, values):
        if 'start_time' in values and v <= values['start_time']:
            raise ValueError('end_time must be after start_time')
        return v

    @validator('duration')
    def validate_duration(cls, v, values):
        if 'start_time' in values and 'end_time' in values:
            expected_duration = int((values['end_time'] - values['start_time']).total_seconds() / 60)
            if v != expected_duration:
                raise ValueError(f'duration must match time difference ({expected_duration} minutes)')
        return v


class AppointmentCreate(AppointmentBase):
    """Schema for creating appointments"""

    @validator("appointment_type", pre=True)
    def coerce_appointment_type(cls, v):
        return _coerce_appointment_type(v)


class AppointmentUpdate(BaseModel):
    """Schema for updating appointments"""
    provider_id: Optional[UUID] = None
    chair_id: Optional[UUID] = None
    appointment_type: Optional[AppointmentTypeEnum] = None
    status: Optional[AppointmentStatus] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration: Optional[int] = Field(None, gt=0)
    notes: Optional[str] = None

    @validator("appointment_type", pre=True)
    def coerce_appointment_type(cls, v):
        if v is None:
            return v
        return _coerce_appointment_type(v)


class AppointmentResponse(AppointmentBase):
    """Schema for appointment responses.

    Emits the canonical snake_case fields plus the read-model aliases the React
    `types/api.ts` `Appointment` contract expects after case normalization:
    `type` (the appointment_type value), `patient_name`/`provider_name`,
    `operatory_id`/`operatory_name` (the chair). The aliases are additive and
    non-breaking for existing consumers (scheduling, booking, availability).
    """
    id: UUID
    practice_id: UUID
    created_at: datetime
    updated_at: datetime
    # M-6 FIX: surface the dedicated cancellation reason column. The
    # response is additive and non-breaking; old clients can ignore it.
    cancellation_reason: Optional[str] = None

    # Read-model aliases (populated by the appointments endpoints' serializer)
    type: Optional[str] = None
    patient_name: Optional[str] = None
    provider_name: Optional[str] = None
    operatory_id: Optional[UUID] = None
    operatory_name: Optional[str] = None

    class Config:
        from_attributes = True


class AppointmentListResponse(BaseModel):
    """A page of appointments with additive cursor-free pagination metadata."""

    appointments: List[AppointmentResponse]
    count: int
    total: Optional[int] = None
    limit: Optional[int] = None
    offset: Optional[int] = None
    next_offset: Optional[int] = None


class AppointmentSlot(BaseModel):
    """Schema for available appointment slots"""
    start_time: datetime
    end_time: datetime
    duration: int
    is_available: bool


class AppointmentStatusUpdate(BaseModel):
    """Schema for updating an appointment's status from the scheduling UI"""
    status: AppointmentStatus


class AppointmentCancelRequest(BaseModel):
    """Schema for cancelling an appointment (soft delete + reason)"""
    reason: Optional[str] = None


class AppointmentRescheduleRequest(BaseModel):
    """Schema for rescheduling an appointment (chair + start time)"""
    chair_id: Optional[UUID] = None
    start_time: Optional[datetime] = None