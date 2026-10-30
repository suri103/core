"""
Online Booking Models
Public booking pages, availability, waitlist, and intake forms
"""

from sqlalchemy import Column, String, DateTime, ForeignKey, Enum, Boolean, Text, Integer, Date, Time, JSON, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.core.base import Base


class BookingPageStatus(str, enum.Enum):
    """Booking page status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PAUSED = "paused"


class BookingStatus(str, enum.Enum):
    """Booking request status"""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    DECLINED = "declined"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class WaitlistStatus(str, enum.Enum):
    """Waitlist entry status"""
    ACTIVE = "active"
    NOTIFIED = "notified"
    BOOKED = "booked"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class BookingPage(Base):
    """Public booking page configuration"""
    __tablename__ = "booking_pages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)

    # Page Configuration
    # page_slug is unique PER PRACTICE (public URLs are
    # /book/{practice_slug}/{page_slug}, so two practices may use the same
    # page slug). The composite unique constraint below is the authoritative
    # guard; the index serves lookups.
    page_slug = Column(String(100), nullable=False, index=True)  # URL slug
    page_title = Column(String(255), nullable=False)
    welcome_message = Column(Text)

    # Branding
    logo_url = Column(String(500))
    primary_color = Column(String(7), default="#3B82F6")  # Hex color
    background_image_url = Column(String(500))

    # Booking Settings
    allow_new_patients = Column(Boolean, default=True)
    allow_existing_patients = Column(Boolean, default=True)
    require_phone_verification = Column(Boolean, default=False)
    require_email_verification = Column(Boolean, default=True)

    # Availability Settings
    booking_window_days = Column(Integer, default=30)  # How far ahead can book
    min_notice_hours = Column(Integer, default=24)  # Minimum notice required
    max_bookings_per_day = Column(Integer, default=10)

    # Appointment Types (stored as JSON array of appointment_type_ids)
    allowed_appointment_types = Column(JSON, default=list)

    # Providers (stored as JSON array of provider_ids)
    allowed_providers = Column(JSON, default=list)

    # Business Hours (stored as JSON)
    # Structure: { "monday": { "enabled": true, "slots": [{"start": "09:00", "end": "17:00"}] } }
    business_hours = Column(JSON, default=dict)

    # Blocked Dates (stored as JSON array of dates)
    blocked_dates = Column(JSON, default=list)

    # Intake Form Configuration
    intake_form_fields = Column(JSON, default=list)  # Custom fields
    require_insurance_info = Column(Boolean, default=False)
    require_medical_history = Column(Boolean, default=False)

    # Notifications
    send_confirmation_email = Column(Boolean, default=True)
    send_confirmation_sms = Column(Boolean, default=False)
    send_reminder_email = Column(Boolean, default=True)
    send_reminder_sms = Column(Boolean, default=False)
    reminder_hours_before = Column(Integer, default=24)

    # Analytics
    total_bookings = Column(Integer, default=0)
    total_views = Column(Integer, default=0)
    conversion_rate = Column(Integer, default=0)  # Percentage

    # Status
    status = Column(Enum(BookingPageStatus), default=BookingPageStatus.ACTIVE)

    # SEO
    meta_title = Column(String(255))
    meta_description = Column(Text)
    meta_keywords = Column(String(500))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        # Two practices may use the same page slug; one practice may not.
        UniqueConstraint(
            "practice_id", "page_slug", name="uq_booking_pages_practice_page_slug"
        ),
    )

    # Relationships
    practice = relationship("Practice", back_populates="booking_pages")
    bookings = relationship("OnlineBooking", back_populates="booking_page", cascade="all, delete-orphan")
    waitlist_entries = relationship("WaitlistEntry", back_populates="booking_page", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<BookingPage {self.page_slug} - {self.status}>"


class OnlineBooking(Base):
    """Online booking request"""
    __tablename__ = "online_bookings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_page_id = Column(UUID(as_uuid=True), ForeignKey("booking_pages.id"), nullable=False)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)

    # Patient Information
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"))  # Null for new patients
    is_new_patient = Column(Boolean, default=True)

    # Contact Information
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=False)
    date_of_birth = Column(Date)

    # Appointment Details
    appointment_type_id = Column(UUID(as_uuid=True), ForeignKey("appointment_types.id"))
    provider_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    requested_date = Column(Date, nullable=False)
    requested_time = Column(Time, nullable=False)
    duration_minutes = Column(Integer, default=30)

    # Reason for Visit
    reason = Column(Text)
    chief_complaint = Column(Text)

    # Insurance Information
    has_insurance = Column(Boolean, default=False)
    insurance_carrier_name = Column(String(255))
    insurance_member_id = Column(String(100))
    insurance_group_number = Column(String(100))

    # Medical History (stored as JSON)
    medical_history = Column(JSON, default=dict)

    # Intake Form Responses (stored as JSON)
    intake_form_responses = Column(JSON, default=dict)

    # Status and Tracking
    status = Column(Enum(BookingStatus), default=BookingStatus.PENDING)
    confirmation_code = Column(String(20), unique=True, index=True)

    # Verification
    email_verified = Column(Boolean, default=False)
    # M-10 FIX: the plaintext token column is retained for the migration
    # window (so we can hash legacy rows in a data migration) but is no
    # longer written by the application. All new tokens go into
    # ``email_verification_token_hash``; the comparison in
    # ``verify_email`` uses ``hmac.compare_digest`` on the hash.
    email_verification_token = Column(String(100))
    email_verification_token_hash = Column(String(128), index=True)
    phone_verified = Column(Boolean, default=False)
    phone_verification_code = Column(String(6))

    # Linked Appointment
    appointment_id = Column(UUID(as_uuid=True), ForeignKey("appointments.id"))

    # Notes
    patient_notes = Column(Text)  # Notes from patient
    staff_notes = Column(Text)  # Internal notes

    # Timestamps
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
    confirmed_at = Column(DateTime(timezone=True))
    declined_at = Column(DateTime(timezone=True))
    cancelled_at = Column(DateTime(timezone=True))

    # Cancellation
    cancellation_reason = Column(Text)
    cancelled_by = Column(String(50))  # patient, staff, system

    # Source Tracking
    referral_source = Column(String(100))  # google, facebook, website, etc.
    utm_source = Column(String(100))
    utm_medium = Column(String(100))
    utm_campaign = Column(String(100))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    booking_page = relationship("BookingPage", back_populates="bookings")
    practice = relationship("Practice", back_populates="online_bookings")
    patient = relationship("Patient", back_populates="online_bookings")
    appointment_type = relationship("AppointmentType")
    provider = relationship("User", back_populates="online_bookings")
    appointment = relationship("Appointment", back_populates="online_booking", uselist=False)

    def __repr__(self):
        return f"<OnlineBooking {self.first_name} {self.last_name} - {self.status}>"


class WaitlistEntry(Base):
    """Waitlist for fully booked time slots"""
    __tablename__ = "waitlist_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_page_id = Column(UUID(as_uuid=True), ForeignKey("booking_pages.id"), nullable=False)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)

    # Patient Information
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"))
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=False)

    # Preferences
    preferred_dates = Column(JSON, default=list)  # Array of dates
    preferred_times = Column(JSON, default=list)  # Array of time ranges
    preferred_providers = Column(JSON, default=list)  # Array of provider_ids
    appointment_type_id = Column(UUID(as_uuid=True), ForeignKey("appointment_types.id"))

    # Reason
    reason = Column(Text)

    # Status
    status = Column(Enum(WaitlistStatus), default=WaitlistStatus.ACTIVE)

    # Notifications
    notified_count = Column(Integer, default=0)
    last_notified_at = Column(DateTime(timezone=True))

    # Expiration
    expires_at = Column(DateTime(timezone=True))

    # Priority (1=high, 2=medium, 3=low)
    priority = Column(Integer, default=2)

    # Linked Booking
    booking_id = Column(UUID(as_uuid=True), ForeignKey("online_bookings.id"))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    booking_page = relationship("BookingPage", back_populates="waitlist_entries")
    practice = relationship("Practice", back_populates="waitlist_entries")
    patient = relationship("Patient", back_populates="waitlist_entries")
    appointment_type = relationship("AppointmentType")
    booking = relationship("OnlineBooking")

    def __repr__(self):
        return f"<WaitlistEntry {self.first_name} {self.last_name} - {self.status}>"


class BookingAvailability(Base):
    """Cached availability slots for faster booking"""
    __tablename__ = "booking_availability"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    # Slot Information
    date = Column(Date, nullable=False, index=True)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    duration_minutes = Column(Integer, nullable=False)

    # Availability
    is_available = Column(Boolean, default=True)
    is_blocked = Column(Boolean, default=False)
    block_reason = Column(String(255))

    # Capacity
    max_bookings = Column(Integer, default=1)
    current_bookings = Column(Integer, default=0)

    # Appointment Types (stored as JSON array)
    allowed_appointment_types = Column(JSON, default=list)

    # Cache Metadata
    cached_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    practice = relationship("Practice")
    provider = relationship("User")

    def __repr__(self):
        return f"<BookingAvailability {self.date} {self.start_time}-{self.end_time}>"


class BookingNotification(Base):
    """Notification log for bookings"""
    __tablename__ = "booking_notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id = Column(UUID(as_uuid=True), ForeignKey("online_bookings.id"), nullable=False)

    # Notification Details
    notification_type = Column(String(50), nullable=False)  # confirmation, reminder, cancellation
    channel = Column(String(20), nullable=False)  # email, sms, push

    # Recipient
    recipient_email = Column(String(255))
    recipient_phone = Column(String(20))

    # Content
    subject = Column(String(255))
    message = Column(Text)

    # Status
    sent_at = Column(DateTime(timezone=True))
    delivered_at = Column(DateTime(timezone=True))
    opened_at = Column(DateTime(timezone=True))
    clicked_at = Column(DateTime(timezone=True))
    failed_at = Column(DateTime(timezone=True))
    failure_reason = Column(Text)

    # Provider Response
    provider_message_id = Column(String(255))  # External provider ID

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    booking = relationship("OnlineBooking")

    def __repr__(self):
        return f"<BookingNotification {self.notification_type} - {self.channel}>"