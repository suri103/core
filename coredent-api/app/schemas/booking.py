"""
Online Booking Schemas
Pydantic models for online booking API
"""

from typing import List, Optional, Dict, Any
from datetime import date, datetime, time
from pydantic import BaseModel, Field, EmailStr, field_validator, model_validator
import uuid as uuid_lib

from app.models.booking import (
    BookingPageStatus,
    BookingStatus,
    WaitlistStatus,
)


# Booking Page Schemas
class BusinessHours(BaseModel):
    """Business hours for a day"""
    enabled: bool = True
    slots: List[Dict[str, str]] = Field(default_factory=list)  # [{"start": "09:00", "end": "17:00"}]


class IntakeFormField(BaseModel):
    """Custom intake form field"""
    field_id: str
    field_type: str  # text, textarea, select, checkbox, radio, date
    label: str
    required: bool = False
    options: Optional[List[str]] = None  # For select, checkbox, radio
    placeholder: Optional[str] = None


class BookingPageBase(BaseModel):
    """Base booking page schema"""
    page_slug: str = Field(..., min_length=3, max_length=100)
    page_title: str = Field(..., min_length=1, max_length=255)
    welcome_message: Optional[str] = None
    logo_url: Optional[str] = None
    primary_color: str = "#3B82F6"
    background_image_url: Optional[str] = None
    allow_new_patients: bool = True
    allow_existing_patients: bool = True
    require_phone_verification: bool = False
    require_email_verification: bool = True
    booking_window_days: int = Field(30, ge=1, le=365)
    min_notice_hours: int = Field(24, ge=0, le=168)
    max_bookings_per_day: int = Field(10, ge=1, le=100)
    allowed_appointment_types: List[uuid_lib.UUID] = Field(default_factory=list)
    allowed_providers: List[uuid_lib.UUID] = Field(default_factory=list)
    business_hours: Dict[str, BusinessHours] = Field(default_factory=dict)
    blocked_dates: List[date] = Field(default_factory=list)
    intake_form_fields: List[IntakeFormField] = Field(default_factory=list)
    require_insurance_info: bool = False
    require_medical_history: bool = False
    send_confirmation_email: bool = True
    send_confirmation_sms: bool = False
    send_reminder_email: bool = True
    send_reminder_sms: bool = False
    reminder_hours_before: int = Field(24, ge=1, le=168)
    status: BookingPageStatus = BookingPageStatus.ACTIVE
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    meta_keywords: Optional[str] = None


class BookingPageCreate(BookingPageBase):
    """Schema for creating a booking page"""
    pass


class BookingPageUpdate(BaseModel):
    """Schema for updating a booking page"""
    page_title: Optional[str] = Field(None, min_length=1, max_length=255)
    welcome_message: Optional[str] = None
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None
    background_image_url: Optional[str] = None
    allow_new_patients: Optional[bool] = None
    allow_existing_patients: Optional[bool] = None
    require_phone_verification: Optional[bool] = None
    require_email_verification: Optional[bool] = None
    booking_window_days: Optional[int] = Field(None, ge=1, le=365)
    min_notice_hours: Optional[int] = Field(None, ge=0, le=168)
    max_bookings_per_day: Optional[int] = Field(None, ge=1, le=100)
    allowed_appointment_types: Optional[List[uuid_lib.UUID]] = None
    allowed_providers: Optional[List[uuid_lib.UUID]] = None
    business_hours: Optional[Dict[str, BusinessHours]] = None
    blocked_dates: Optional[List[date]] = None
    intake_form_fields: Optional[List[IntakeFormField]] = None
    require_insurance_info: Optional[bool] = None
    require_medical_history: Optional[bool] = None
    send_confirmation_email: Optional[bool] = None
    send_confirmation_sms: Optional[bool] = None
    send_reminder_email: Optional[bool] = None
    send_reminder_sms: Optional[bool] = None
    reminder_hours_before: Optional[int] = Field(None, ge=1, le=168)
    status: Optional[BookingPageStatus] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    meta_keywords: Optional[str] = None


class BookingPageResponse(BookingPageBase):
    """Schema for booking page response"""
    id: uuid_lib.UUID
    practice_id: uuid_lib.UUID
    practice_public_slug: str
    total_bookings: int
    total_views: int
    conversion_rate: int
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def _load_practice_slug(cls, data):
        """Inject practice_public_slug from the loaded practice relationship."""
        practice = getattr(data, "practice", None)
        slug = getattr(practice, "public_slug", None) if practice else None
        d = dict(data.__dict__) if hasattr(data, "__dict__") else dict(data)
        d["practice_public_slug"] = slug
        return d

    class Config:
        from_attributes = True


class BookingPageListResponse(BaseModel):
    """Schema for a bounded page of booking pages."""
    pages: List[BookingPageResponse]
    count: int
    total: Optional[int] = None
    limit: Optional[int] = None
    offset: Optional[int] = None
    next_offset: Optional[int] = None


class AppointmentTypePublicInfo(BaseModel):
    id: uuid_lib.UUID
    name: str
    duration_minutes: int = 30
    description: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None

    class Config:
        from_attributes = True


class BookingPagePublicResponse(BaseModel):
    """Public-facing booking page response (no sensitive data)"""
    practice_public_slug: str
    page_slug: str
    page_title: str
    welcome_message: Optional[str]
    logo_url: Optional[str]
    primary_color: str
    background_image_url: Optional[str]
    allow_new_patients: bool
    allow_existing_patients: bool
    require_phone_verification: bool
    require_email_verification: bool
    booking_window_days: int
    min_notice_hours: int
    practice_timezone: str
    business_hours: Dict[str, BusinessHours]
    blocked_dates: List[date]
    intake_form_fields: List[IntakeFormField]
    require_insurance_info: bool
    require_medical_history: bool
    allowed_appointment_types: List[str] = Field(default_factory=list)
    appointment_types: List[AppointmentTypePublicInfo] = Field(default_factory=list)


# Online Booking Schemas
class OnlineBookingBase(BaseModel):
    """Base online booking schema"""
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone: str = Field(..., min_length=10, max_length=32)
    date_of_birth: Optional[date] = None

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        raw = value.strip()
        digits = "".join(character for character in raw if character.isdigit())
        if not 10 <= len(digits) <= 15:
            raise ValueError("phone must contain between 10 and 15 digits")
        return f"+{digits}" if raw.startswith("+") else digits
    is_new_patient: bool = True
    appointment_type_id: Optional[uuid_lib.UUID] = None
    provider_id: Optional[uuid_lib.UUID] = None
    requested_date: date
    requested_time: time
    reason: Optional[str] = None
    chief_complaint: Optional[str] = None
    has_insurance: bool = False
    insurance_carrier_name: Optional[str] = None
    insurance_member_id: Optional[str] = None
    insurance_group_number: Optional[str] = None
    medical_history: Dict[str, Any] = Field(default_factory=dict)
    intake_form_responses: Dict[str, Any] = Field(default_factory=dict)
    patient_notes: Optional[str] = None
    referral_source: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None


class OnlineBookingCreate(OnlineBookingBase):
    """Schema for creating a complete, confirmable online booking."""
    appointment_type_id: uuid_lib.UUID
    date_of_birth: date
    honeypot: Optional[str] = None
    captcha_token: Optional[str] = None


class OnlineBookingUpdate(BaseModel):
    """Schema for staff-managed online booking updates."""
    status: Optional[BookingStatus] = None
    appointment_id: Optional[uuid_lib.UUID] = None
    patient_id: Optional[uuid_lib.UUID] = None
    staff_notes: Optional[str] = None
    cancellation_reason: Optional[str] = None


class OnlineBookingResponse(OnlineBookingBase):
    """Schema for online booking response (Admin/Staff only)"""
    id: uuid_lib.UUID
    booking_page_id: uuid_lib.UUID
    practice_id: uuid_lib.UUID
    patient_id: Optional[uuid_lib.UUID]
    status: BookingStatus
    confirmation_code: str
    email_verified: bool
    phone_verified: bool
    appointment_id: Optional[uuid_lib.UUID]
    staff_notes: Optional[str]
    submitted_at: datetime
    confirmed_at: Optional[datetime]
    declined_at: Optional[datetime]
    cancelled_at: Optional[datetime]
    cancellation_reason: Optional[str]
    cancelled_by: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OnlineBookingPublicResponse(BaseModel):
    """Public booking result with an opaque, short-lived verification session."""
    confirmation_code: str
    status: BookingStatus
    first_name: str
    last_name: str
    requested_date: date
    requested_time: time
    verification_session: str
    require_email_verification: bool
    require_phone_verification: bool
    email_verified: bool = False
    phone_verified: bool = False
    message: str = "Booking request submitted successfully"

    class Config:
        from_attributes = True


class OnlineBookingListResponse(BaseModel):
    """Schema for a bounded page of online bookings."""
    bookings: List[OnlineBookingResponse]
    count: int
    total: Optional[int] = None
    limit: Optional[int] = None
    offset: Optional[int] = None
    next_offset: Optional[int] = None


# Waitlist Schemas
class WaitlistEntryBase(BaseModel):
    """Base waitlist entry schema"""
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone: str = Field(..., min_length=10, max_length=20)
    preferred_dates: List[date] = Field(default_factory=list)
    preferred_times: List[str] = Field(default_factory=list)  # ["morning", "afternoon", "evening"]
    preferred_providers: List[uuid_lib.UUID] = Field(default_factory=list)
    appointment_type_id: Optional[uuid_lib.UUID] = None
    reason: Optional[str] = None
    priority: int = Field(2, ge=1, le=3)


class WaitlistEntryCreate(WaitlistEntryBase):
    """Schema for creating a waitlist entry"""
    pass


class WaitlistEntryUpdate(BaseModel):
    """Schema for updating a waitlist entry"""
    status: Optional[WaitlistStatus] = None
    priority: Optional[int] = Field(None, ge=1, le=3)
    booking_id: Optional[uuid_lib.UUID] = None


class WaitlistEntryResponse(WaitlistEntryBase):
    """Schema for waitlist entry response"""
    id: uuid_lib.UUID
    booking_page_id: uuid_lib.UUID
    practice_id: uuid_lib.UUID
    patient_id: Optional[uuid_lib.UUID]
    status: WaitlistStatus
    notified_count: int
    last_notified_at: Optional[datetime]
    expires_at: Optional[datetime]
    booking_id: Optional[uuid_lib.UUID]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WaitlistEntryListResponse(BaseModel):
    """Schema for a bounded page of waitlist entries."""
    entries: List[WaitlistEntryResponse]
    count: int
    total: Optional[int] = None
    limit: Optional[int] = None
    offset: Optional[int] = None
    next_offset: Optional[int] = None


# Availability Schemas
class TimeSlot(BaseModel):
    """Available time slot"""
    start_time: time
    end_time: time
    duration_minutes: int
    is_available: bool
    provider_id: Optional[uuid_lib.UUID]
    provider_name: Optional[str]


class DayAvailability(BaseModel):
    """Availability for a specific day"""
    date: date
    day_of_week: str
    is_available: bool
    slots: List[TimeSlot]


class AvailabilityRequest(BaseModel):
    """Request for availability."""
    start_date: date
    end_date: date
    appointment_type_id: Optional[uuid_lib.UUID] = None
    provider_id: Optional[uuid_lib.UUID] = None
    duration_minutes: int = Field(30, ge=5, le=480)


class AvailabilityResponse(BaseModel):
    """Response with available slots"""
    days: List[DayAvailability]
    total_slots: int


# Verification Schemas
class EmailVerificationRequest(BaseModel):
    """Verify email through an opaque, short-lived booking session."""
    verification_session: str = Field(..., min_length=1, max_length=4096)
    verification_token: str = Field(..., min_length=16, max_length=256)


class PhoneVerificationRequest(BaseModel):
    """Verify phone through an opaque, short-lived booking session."""
    verification_session: str
    verification_code: str = Field(..., pattern=r"^\d{6}$")


class VerificationResponse(BaseModel):
    """Public verification state without exposing an internal booking UUID."""
    verified: bool
    message: str
    confirmation_code: Optional[str] = None
    email_verified: bool = False
    phone_verified: bool = False
    require_email_verification: bool = False
    require_phone_verification: bool = False


# Confirmation Schemas
class BookingConfirmationRequest(BaseModel):
    """Request to confirm a booking"""
    booking_id: uuid_lib.UUID
    create_appointment: bool = True
    send_confirmation: bool = True


class BookingConfirmationResponse(BaseModel):
    """Booking confirmation response"""
    booking_id: uuid_lib.UUID
    appointment_id: Optional[uuid_lib.UUID]
    confirmation_code: str
    status: BookingStatus
    message: str


# Analytics Schemas
class BookingAnalytics(BaseModel):
    """Booking analytics"""
    total_bookings: int
    total_views: int
    conversion_rate: float
    confirmed_bookings: int
    pending_bookings: int
    declined_bookings: int
    cancelled_bookings: int
    new_patients: int
    existing_patients: int
    average_response_time_hours: float
    popular_times: Dict[str, int]
    popular_appointment_types: Dict[str, int]
    referral_sources: Dict[str, int]