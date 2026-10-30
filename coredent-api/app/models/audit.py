"""
Audit Models
Audit logs and user sessions for HIPAA compliance
"""

from sqlalchemy import Boolean, Column, String, DateTime, ForeignKey, JSON, Text, event
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.core.base import Base


class AuditLog(Base):
    """Audit log for HIPAA compliance"""
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    action = Column(String(100), nullable=False)  # e.g., "patient_viewed", "record_updated"
    entity_type = Column(String(50), nullable=False)  # e.g., "patient", "appointment"
    # Nullable: list/search actions log no specific entity (e.g., "patient_list_viewed")
    entity_id = Column(UUID(as_uuid=True), nullable=True)

    changes = Column(JSON)  # Before/after values for updates
    # Use string type for IP address for SQLite compatibility
    ip_address = Column(String(45))
    user_agent = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    user = relationship("User", back_populates="audit_logs")

    def __repr__(self):
        return f"<AuditLog {self.action} on {self.entity_type}>"


class Session(Base):
    """User session for JWT refresh tokens"""
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    refresh_token = Column(String(500), unique=True, nullable=True, index=True)  # DEPRECATED: never store plaintext; retained for migration compatibility
    token_hash = Column(String(255), nullable=True, index=True)  # SECURITY FIX: Store hashed refresh token
    previous_token_hash = Column(String(255), nullable=True, index=True)
    previous_token_valid_until = Column(DateTime(timezone=True), nullable=True)
    # H8 FIX: single-use guard for the overlap window. The previous-token leg
    # of the refresh lookup is accepted at most once; a second use within the
    # window is treated as credential replay and revokes every session.
    previous_token_consumed = Column(
        Boolean, nullable=False, server_default="false", default=False
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # Use string type for IP address for SQLite compatibility
    ip_address = Column(String(45))
    user_agent = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="sessions")

    def __repr__(self):
        return f"<Session {self.id} for User {self.user_id}>"


@event.listens_for(AuditLog, 'before_update')
def prevent_audit_log_update(mapper, connection, target):
    raise RuntimeError("HIPAA Compliance: Audit logs are write-once and cannot be modified.")

@event.listens_for(AuditLog, 'before_delete')
def prevent_audit_log_delete(mapper, connection, target):
    raise RuntimeError("HIPAA Compliance: Audit logs are write-once and cannot be deleted.")
