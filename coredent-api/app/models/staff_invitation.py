"""
Staff Invitation Model
======================

Pending invitations for new staff members. Onboarding is admin-driven:
an OWNER/ADMIN creates an invitation, the invitee opens the emailed link
and chooses their own password. This replaces hand-distributed temporary
passwords; the invitee never knows a password anyone else chose.

Tokens are stored hashed (SHA-256 of a 256-bit secrets.token_urlsafe
value) — the plaintext token exists only in the email link.
"""

from sqlalchemy import Column, String, DateTime, ForeignKey, Enum, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.core.base import Base
from app.models.user import UserRole


class StaffInvitation(Base):
    """A pending invitation for a not-yet-created staff account."""

    __tablename__ = "staff_invitations"

    __table_args__ = (
        Index("idx_staff_invitation_practice", "practice_id"),
        Index("idx_staff_invitation_email", "email"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)

    email = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    role = Column(Enum(UserRole), nullable=False)

    invited_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Only one live invitation per email: the hash is unique, and the
    # endpoint also rejects a second PENDING invite for the same address.
    token_hash = Column(String(64), nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def __repr__(self):
        return f"<StaffInvitation {self.email} ({self.role})>"
