"""
Communication Schemas
Patient messaging, SMS/email reminders, two-way messaging
"""

import json
from datetime import datetime
from typing import List, Optional
from enum import Enum
from uuid import UUID
from pydantic import BaseModel, Field, field_validator

from app.schemas.common import BaseSchema



def _parse_json_list(value):
    if value is None or isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return None
        return parsed if isinstance(parsed, list) else None
    return value


class MessageType(str, Enum):
    """Message types"""
    SMS = "sms"
    EMAIL = "email"
    VOICE = "voice"
    PUSH = "push"
    IN_APP = "in_app"


class MessageDirection(str, Enum):
    """Message direction"""
    OUTBOUND = "outbound"
    INBOUND = "inbound"


class MessageStatus(str, Enum):
    """Message status"""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    READ = "read"


class ReminderType(str, Enum):
    """Types of reminders"""
    APPOINTMENT = "appointment"
    RECALL = "recall"
    TREATMENT = "treatment"
    PAYMENT = "payment"
    INSURANCE = "insurance"
    CUSTOM = "custom"


# Message Template Schemas
class MessageTemplateBase(BaseSchema):
    """Base template schema"""
    name: str = Field(..., description="Template name")
    message_type: MessageType = Field(..., description="Type of message")
    subject: Optional[str] = Field(None, description="Email subject line")
    content: str = Field(..., description="Template content with variables")
    category: Optional[str] = Field(None, description="Template category")
    variables: Optional[List[str]] = Field(None, description="Available template variables")
    is_active: bool = Field(True, description="Whether template is active")

    @field_validator("variables", mode="before")
    @classmethod
    def parse_variables(cls, value):
        return _parse_json_list(value)
    is_default: bool = Field(False, description="Whether this is the default template")


class MessageTemplateCreate(MessageTemplateBase):
    """Schema for creating a template"""
    pass


class MessageTemplateUpdate(BaseModel):
    """Schema for updating a template"""
    name: Optional[str] = None
    subject: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    variables: Optional[List[str]] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None


class MessageTemplate(MessageTemplateBase):
    """Complete template schema"""
    id: UUID
    practice_id: UUID
    times_used: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Patient Message Schemas
class PatientMessageBase(BaseSchema):
    """Base message schema"""
    patient_id: UUID = Field(..., description="Patient ID")
    message_type: MessageType = Field(..., description="Type of message")
    direction: MessageDirection = Field(default=MessageDirection.OUTBOUND, description="Message direction")
    content: str = Field(..., description="Message content")
    subject: Optional[str] = Field(None, description="Email subject")
    recipient_phone: Optional[str] = Field(None, description="Recipient phone number")
    recipient_email: Optional[str] = Field(None, description="Recipient email")
    from_name: Optional[str] = Field(None, description="Sender name")
    from_email: Optional[str] = Field(None, description="Sender email")
    scheduled_at: Optional[datetime] = Field(None, description="Scheduled send time")
    attachments: Optional[List[str]] = Field(None, description="Message attachments")

    @field_validator("attachments", mode="before")
    @classmethod
    def parse_attachments(cls, value):
        return _parse_json_list(value)

class PatientMessageCreate(PatientMessageBase):
    """Schema for creating a message"""
    template_id: Optional[str] = Field(None, description="Template ID if using template")
    appointment_id: Optional[str] = Field(None, description="Related appointment ID")
    parent_message_id: Optional[str] = Field(None, description="Parent message for conversations")


class PatientMessageUpdate(BaseModel):
    """Schema for updating a message"""
    content: Optional[str] = None
    subject: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    status: Optional[MessageStatus] = None


class PatientMessage(PatientMessageBase):
    """Complete message schema"""
    id: UUID
    practice_id: UUID
    user_id: Optional[UUID] = None
    template_id: Optional[UUID] = None
    appointment_id: Optional[UUID] = None
    parent_message_id: Optional[UUID] = None
    status: MessageStatus = MessageStatus.PENDING
    external_id: Optional[str] = None
    provider_response: Optional[str] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    cost: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Reminder Schedule Schemas
class ReminderScheduleBase(BaseSchema):
    """Base reminder schedule schema"""
    name: str = Field(..., description="Schedule name")
    reminder_type: ReminderType = Field(..., description="Type of reminder")
    days_before: int = Field(0, description="Days before appointment")
    days_after: int = Field(0, description="Days after appointment")
    hours_before: int = Field(0, description="Hours before appointment")
    minutes_before: int = Field(0, description="Minutes before appointment")
    specific_time: Optional[str] = Field(None, description="Specific time (HH:MM format)")
    message_type: MessageType = Field(..., description="Type of message to send")
    is_active: bool = Field(True, description="Whether schedule is active")
    send_on_weekends: bool = Field(False, description="Whether to send on weekends")
    max_reminders: int = Field(3, description="Maximum number of reminders")
    patient_types: Optional[List[str]] = Field(None, description="Patient types to target")

    @field_validator("patient_types", mode="before")
    @classmethod
    def parse_patient_types(cls, value):
        return _parse_json_list(value)

class ReminderScheduleCreate(ReminderScheduleBase):
    """Schema for creating a reminder schedule"""
    template_id: str = Field(..., description="Template ID to use")
    appointment_type_id: Optional[str] = Field(None, description="Appointment type ID")


class ReminderScheduleUpdate(BaseModel):
    """Schema for updating a reminder schedule"""
    name: Optional[str] = None
    reminder_type: Optional[ReminderType] = None
    days_before: Optional[int] = None
    days_after: Optional[int] = None
    hours_before: Optional[int] = None
    minutes_before: Optional[int] = None
    specific_time: Optional[str] = None
    message_type: Optional[MessageType] = None
    is_active: Optional[bool] = None
    send_on_weekends: Optional[bool] = None
    max_reminders: Optional[int] = None
    patient_types: Optional[List[str]] = None


class ReminderSchedule(ReminderScheduleBase):
    """Complete reminder schedule schema"""
    id: UUID
    practice_id: UUID
    template_id: Optional[UUID] = None
    appointment_type_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Conversation Schemas
class ConversationBase(BaseSchema):
    """Base conversation schema"""
    patient_id: UUID = Field(..., description="Patient ID")
    channel: MessageType = Field(..., description="Communication channel")
    subject: Optional[str] = Field(None, description="Conversation subject")
    status: str = Field("active", description="Conversation status")
    auto_responder_enabled: bool = Field(False, description="Whether auto-responder is enabled")


class ConversationCreate(ConversationBase):
    """Schema for creating a conversation"""
    auto_response_template_id: Optional[str] = Field(None, description="Auto-response template ID")


class ConversationUpdate(BaseModel):
    """Schema for updating a conversation"""
    subject: Optional[str] = None
    status: Optional[str] = None
    auto_responder_enabled: Optional[bool] = None
    auto_response_template_id: Optional[str] = None


class Conversation(ConversationBase):
    """Complete conversation schema"""
    id: UUID
    practice_id: UUID
    assigned_user_id: Optional[UUID] = None
    last_message_at: Optional[datetime] = None
    last_message_preview: Optional[str] = None
    unread_count: int = 0
    auto_response_template_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConversationMessageBase(BaseSchema):
    """Base conversation message schema"""
    # The conversation is identified by the request path; the endpoint forces
    # sender_type for staff sends, so neither is required in the body.
    conversation_id: Optional[UUID] = Field(None, description="Conversation ID")
    sender_type: str = Field(default="staff", description="Sender type (patient, staff, system)")
    content: str = Field(..., description="Message content")
    attachments: Optional[List[str]] = Field(None, description="Message attachments")

    @field_validator("attachments", mode="before")
    @classmethod
    def parse_attachments(cls, value):
        return _parse_json_list(value)

class ConversationMessageCreate(ConversationMessageBase):
    """Schema for creating a conversation message"""
    sender_id: Optional[str] = Field(None, description="Sender user ID")


class ConversationMessage(ConversationMessageBase):
    """Complete conversation message schema"""
    id: UUID
    sender_id: Optional[UUID] = None
    is_read: bool = False
    read_at: Optional[datetime] = None
    external_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Communication Settings Schemas
class SMSSettings(BaseModel):
    """SMS provider settings"""
    provider: str = Field(..., description="SMS provider (twilio, etc.)")
    account_sid: Optional[str] = Field(None, description="Account SID")
    auth_token: Optional[str] = Field(None, description="Auth token")
    phone_number: Optional[str] = Field(None, description="Sender phone number")
    is_active: bool = Field(False, description="Whether SMS is active")


class EmailSettings(BaseModel):
    """Email provider settings"""
    provider: str = Field(..., description="Email provider (sendgrid, smtp, etc.)")
    api_key: Optional[str] = Field(None, description="API key")
    smtp_host: Optional[str] = Field(None, description="SMTP host")
    smtp_port: Optional[int] = Field(None, description="SMTP port")
    smtp_username: Optional[str] = Field(None, description="SMTP username")
    smtp_password: Optional[str] = Field(None, description="SMTP password")
    from_email: Optional[str] = Field(None, description="Default from email")
    from_name: Optional[str] = Field(None, description="Default from name")
    is_active: bool = Field(False, description="Whether email is active")


class AutoReminderSettings(BaseModel):
    """Auto reminder settings"""
    enabled: bool = Field(False, description="Whether auto reminders are enabled")
    default_lead_time: int = Field(24, description="Default lead time in hours")
    max_reminders: int = Field(3, description="Maximum number of reminders")
    exclude_weekends: bool = Field(True, description="Whether to exclude weekends")


class CommunicationSettings(BaseModel):
    """Complete communication settings"""
    practice_id: str
    sms: SMSSettings = Field(default_factory=SMSSettings, description="SMS settings")
    email: EmailSettings = Field(default_factory=EmailSettings, description="Email settings")
    auto_reminders: AutoReminderSettings = Field(
        default_factory=AutoReminderSettings, 
        description="Auto reminder settings"
    )
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CommunicationSettingsUpdate(BaseModel):
    """Schema for updating communication settings"""
    sms: Optional[SMSSettings] = None
    email: Optional[EmailSettings] = None
    auto_reminders: Optional[AutoReminderSettings] = None


# Response Schemas
class MessageStats(BaseModel):
    """Message statistics"""
    total_sent: int
    total_delivered: int
    total_failed: int
    delivery_rate: float
    total_cost: str


class ReminderStats(BaseModel):
    """Reminder statistics"""
    total_scheduled: int
    total_sent: int
    total_delivered: int
    pending: int
    failed: int


class CommunicationSummary(BaseModel):
    """Communication summary"""
    messages: MessageStats
    reminders: ReminderStats
    active_conversations: int
    unread_messages: int