"""
Password Reset Token Model
Separate table for password reset tokens - more secure than storing on User model
"""

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.core.base import Base


class PasswordResetToken(Base):
    """Password reset token model - separate from User for security"""
    __tablename__ = "password_reset_tokens"

    # PERFORMANCE: Add indexes for lookups
    __table_args__ = (
        Index('idx_password_reset_token', 'token', unique=False),
        Index('idx_password_reset_user', 'user_id', 'is_used'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token = Column(String(255), nullable=True, index=True)  # DEPRECATED: never store plaintext; retained for migration compatibility
    token_hash = Column(String(255), nullable=True, index=True)  # SECURITY FIX: Store hashed token
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_used = Column(Boolean, default=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6

    # Relationships
    user = relationship("User", back_populates="password_reset_tokens")

    def __repr__(self):
        return f"<PasswordResetToken user_id={self.user_id} expires={self.expires_at}>"