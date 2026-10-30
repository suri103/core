"""
Communication Models
Patient messaging, SMS/email reminders, two-way messaging
"""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.core.base import Base


class MessageType(str, enum.Enum):
    """Message types"""
    SMS = "sms"
    EMAIL = "email"
    VOICE = "voice"
    PUSH = "push"
    IN_APP = "in_app"


class MessageDirection(str, enum.Enum):
    """Message direction"""
    OUTBOUND = "outbound"
    INBOUND = "inbound"


class MessageStatus(str, enum.Enum):
    """Message status"""
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    READ = "read"


class ReminderType(str, enum.Enum):
    """Types of reminders"""
    APPOINTMENT = "appointment"
    RECALL = "recall"
    TREATMENT = "treatment"
    PAYMENT = "payment"
    INSURANCE = "insurance"
    CUSTOM = "custom"


class MessageTemplate(Base):
    """Message template model"""
    __tablename__ = "message_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)

    # Template Information
    name = Column(String(255), nullable=False)
    message_type = Column(Enum(MessageType), nullable=False)
    subject = Column(String(255))  # For email
    content = Column(Text, nullable=False)

    # Category
    category = Column(String(50))  # appointment, recall, billing, marketing, etc.

    # Variables
    variables = Column(Text)  # JSON array of available variables

    # Status
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)

    # Usage
    times_used = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    practice = relationship("Practice", back_populates="message_templates")
    messages = relationship("PatientMessage", back_populates="template")

    def __repr__(self):
        return f"<MessageTemplate {self.name}>"


class PatientMessage(Base):
    """Persisted outbound/inbound patient communication and delivery state."""

    __tablename__ = "patient_messages"
    __table_args__ = (
        # A caller-supplied or system-derived key turns a retried business
        # event into the same durable delivery rather than a second message.
        Index(
            "uq_patient_messages_practice_dedupe_key",
            "practice_id",
            "dedupe_key",
            unique=True,
            postgresql_where=text("dedupe_key IS NOT NULL"),
            sqlite_where=text("dedupe_key IS NOT NULL"),
        ),
        Index("ix_patient_messages_delivery_due", "status", "next_attempt_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))  # Who sent/received
    template_id = Column(UUID(as_uuid=True), ForeignKey("message_templates.id"))
    appointment_id = Column(UUID(as_uuid=True), ForeignKey("appointments.id"))

    # Message Details
    message_type = Column(Enum(MessageType), nullable=False)
    direction = Column(Enum(MessageDirection), nullable=False)
    status = Column(Enum(MessageStatus), default=MessageStatus.PENDING)

    # Content
    subject = Column(String(255))
    content = Column(Text, nullable=False)

    # Recipient Info
    recipient_phone = Column(String(20))
    recipient_email = Column(String(255))

    # Provider Info
    from_name = Column(String(100))
    from_email = Column(String(255))

    # External IDs (for SMS/Email providers)
    external_id = Column(String(100))
    provider_response = Column(Text)

    # Timestamps
    scheduled_at = Column(DateTime(timezone=True))
    sent_at = Column(DateTime(timezone=True))
    delivered_at = Column(DateTime(timezone=True))
    read_at = Column(DateTime(timezone=True))

    # A durable, lease-based delivery claim. The task commits SENDING before
    # network I/O and a periodic dispatcher reclaims only expired leases.
    dedupe_key = Column(String(255))
    attempt_count = Column(Integer, nullable=False, default=0, server_default="0")
    next_attempt_at = Column(DateTime(timezone=True))
    claimed_at = Column(DateTime(timezone=True))
    claim_token = Column(String(64))
    claim_expires_at = Column(DateTime(timezone=True))

    # Error Info
    error_message = Column(Text)
    error_code = Column(String(20))

    # Two-way conversation
    parent_message_id = Column(UUID(as_uuid=True), ForeignKey("patient_messages.id"))

    # Attachments
    attachments = Column(Text)  # JSON array of file URLs

    # Cost
    cost = Column(String(10))  # e.g., "0.01" for SMS

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    practice = relationship("Practice", back_populates="patient_messages")
    patient = relationship("Patient", back_populates="messages")
    user = relationship("User")
    template = relationship("MessageTemplate", back_populates="messages")
    appointment = relationship("Appointment")
    parent_message = relationship("PatientMessage", remote_side=[id])
    replies = relationship("PatientMessage", back_populates="parent_message")

    def __repr__(self):
        return f"<PatientMessage {self.id} - {self.message_type} - {self.direction}>"


class ReminderSchedule(Base):
    """Reminder schedule for automated messages"""
    __tablename__ = "reminder_schedules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    template_id = Column(UUID(as_uuid=True), ForeignKey("message_templates.id"))
    appointment_type_id = Column(UUID(as_uuid=True), ForeignKey("appointment_types.id"))

    # Schedule Details
    name = Column(String(255), nullable=False)
    reminder_type = Column(Enum(ReminderType), nullable=False)

    # Timing (in days before/after)
    days_before = Column(Integer, default=0)  # Negative for before, positive for after
    days_after = Column(Integer, default=0)
    hours_before = Column(Integer, default=0)
    minutes_before = Column(Integer, default=0)

    # Specific Time
    specific_time = Column(String(10))  # e.g., "09:00" for 9 AM

    # Message Type to Send
    message_type = Column(Enum(MessageType), nullable=False)

    # Status
    is_active = Column(Boolean, default=True)
    send_on_weekends = Column(Boolean, default=False)

    # Limit
    max_reminders = Column(Integer, default=3)

    # Patient Selection
    patient_types = Column(Text)  # JSON array: ["new", "existing", "recall"]

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    practice = relationship("Practice", back_populates="reminder_schedules")
    template = relationship("MessageTemplate")
    appointment_type = relationship("AppointmentType")

    def __repr__(self):
        return f"<ReminderSchedule {self.name}>"


class Conversation(Base):
    """Two-way messaging conversation"""
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    assigned_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    # Conversation Details
    subject = Column(String(255))
    channel = Column(Enum(MessageType), nullable=False)  # sms, email, in_app

    # Status
    status = Column(String(20), default="active")  # active, closed, archived

    # Last Message
    last_message_at = Column(DateTime(timezone=True))
    last_message_preview = Column(String(255))
    unread_count = Column(Integer, default=0)

    # Auto-Response
    auto_responder_enabled = Column(Boolean, default=False)
    auto_response_template_id = Column(UUID(as_uuid=True), ForeignKey("message_templates.id"))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    practice = relationship("Practice", back_populates="conversations")
    patient = relationship("Patient", back_populates="conversations")
    assigned_user = relationship("User")
    messages = relationship("ConversationMessage", back_populates="conversation", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Conversation {self.id} - {self.patient_id}>"


class ConversationMessage(Base):
    """Individual message in a conversation"""
    __tablename__ = "conversation_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)
    sender_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))  # If from staff
    sender_type = Column(String(20))  # patient, staff, system

    # Message Content
    content = Column(Text, nullable=False)
    attachments = Column(Text)  # JSON array

    # Status
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime(timezone=True))

    # Provider Info
    external_id = Column(String(100))

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    sender = relationship("User")

    def __repr__(self):
        return f"<ConversationMessage {self.id}>"
