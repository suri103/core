"""
Portal Identity Lockout Model

Persistent brute-force lockout state for the public patient-portal identity
check (email + date-of-birth). The lockout used to live in a module-level
dict that reset on every worker restart; it is now a durable row keyed by
(practice_slug, email) so the 15-minute window and its window-extending
semantics survive restarts and are shared across replicas.

The table is write-only from the portal flow (atomic UPDATE + conditional
INSERT); rows are removed when an identity verifies successfully.
"""

from sqlalchemy import Column, String, Integer, DateTime, func

from app.core.base import Base


class PortalIdentityLockout(Base):
    __tablename__ = "portal_identity_lockouts"

    practice_slug = Column(String(100), primary_key=True)
    email = Column(String(254), primary_key=True)
    failed_attempts = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self):
        return (
            f"<PortalIdentityLockout {self.practice_slug}|{self.email} "
            f"attempts={self.failed_attempts} locked_until={self.locked_until}>"
        )
