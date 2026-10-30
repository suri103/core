"""Communication settings model."""

from sqlalchemy import Column, Boolean, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
from app.core.base import Base
import uuid


class CommunicationSettings(Base):
    __tablename__ = "communication_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), nullable=False)
    sms_enabled = Column(Boolean, default=False)
    email_enabled = Column(Boolean, default=True)
    reminder_hours_before = Column(Integer, default=24)
    provider_config = Column(JSON, default=dict)
