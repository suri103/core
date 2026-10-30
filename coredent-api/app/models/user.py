"""
User Model
Represents staff members and system users
SECURITY: Added database indexes for query performance
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.core.base import Base


class UserRole(str, enum.Enum):
    """User roles for RBAC"""
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    DENTIST = "DENTIST"
    HYGIENIST = "HYGIENIST"
    FRONT_DESK = "FRONT_DESK"
    GROUP_OWNER = "GROUP_OWNER"
    GROUP_ADMIN = "GROUP_ADMIN"
    # 2026-09: production-readiness additions.
    # ACCOUNTANT — finance-only staff (billing/payments/reports). The frontend
    #   "front_desk" role previously carried all money handling; clinics that
    #   hire bookkeepers need a least-privilege role for it.
    # SUPER_ADMIN — the SaaS operator's own staff (platform-level, not a
    #   clinic role). Super admins live in their own bootstrap practice and
    #   are authorized via /platform/* endpoints, never clinic routes.
    ACCOUNTANT = "ACCOUNTANT"
    SUPER_ADMIN = "SUPER_ADMIN"


class User(Base):
    """User/Staff member model"""
    __tablename__ = "users"

    # PERFORMANCE: Add composite indexes
    __table_args__ = (
        Index('idx_user_practice_role', 'practice_id', 'role'),
        Index('idx_user_practice_active', 'practice_id', 'is_active'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    npi = Column(String(20), nullable=True)  # National Provider Identifier (EDI claims)
    role = Column(Enum(UserRole), nullable=False)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime(timezone=True), nullable=True)

    # SECURITY: Account lockout fields for brute force protection
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    last_failed_login = Column(DateTime(timezone=True), nullable=True)

    # SECURITY: Email verification
    is_email_verified = Column(Boolean, default=False, nullable=False)
    email_verification_token = Column(String(255), nullable=True)
    # Expiry for the hashed verification token above (NULL = legacy rows)
    email_verification_token_expires_at = Column(DateTime(timezone=True), nullable=True)
    # M1 FIX: accounts created through the staff-invitation accept flow must
    # verify their inbox before they can sign in (the 72h invite token is not
    # proof of email ownership). Self-registered accounts keep the documented
    # grace period; this flag makes the gate immediate instead.
    email_verification_required = Column(
        Boolean, default=False, nullable=False, server_default="false"
    )

    # Password reset tokens are now stored in separate table for security
    # See PasswordResetToken model
    password_changed_at = Column(DateTime(timezone=True), nullable=True)

    # First-login security: admin-provisioned accounts start with True
    # (the admin hands out the temporary password). API access is gated
    # to the password-change endpoints until the user rotates it; a
    # self-service change clears it, an admin password reset re-arms it.
    # Invitation-accepted accounts set their own password and start False.
    must_change_password = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    practice = relationship("Practice", back_populates="users")
    appointments = relationship("Appointment", back_populates="provider")
    clinical_notes = relationship("ClinicalNote", back_populates="provider")
    treatment_plans = relationship("TreatmentPlan", back_populates="provider")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    password_reset_tokens = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user")
    images = relationship("PatientImage", back_populates="provider")
    online_bookings = relationship("OnlineBooking", back_populates="provider")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"
