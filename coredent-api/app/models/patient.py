"""
Patient Model
Represents dental patients
SECURITY: Added database indexes for query performance

PHI columns are stored as EncryptedString / EncryptedJSON so the database
itself never holds plaintext PHI.  The application is the only place plaintext
exists in memory, and only for the lifetime of a request.

Search columns (``first_name``, ``last_name``, ``email``, ``phone``) are kept
*both* encrypted (the source of truth) and as a deterministic hash
(``search_hash_*``) for equality lookups.  Substring search is performed on a
trigram index of the plaintext at write-time, written to ``search_index_*``
columns.  ``search_index_*`` is itself low-sensitivity (it is not the value)
but should still be considered personal data under most privacy regimes.
"""

from sqlalchemy import (
    Column,
    String,
    Date,
    DateTime,
    ForeignKey,
    Enum,
    Index,
    Integer,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func, text
import enum
import uuid

from app.core.base import Base
from app.core.encryption import EncryptedString, EncryptedJSON


class PatientStatus(str, enum.Enum):
    """Patient status"""
    ACTIVE = "active"
    INACTIVE = "inactive"


class Gender(str, enum.Enum):
    """Gender options"""
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class Patient(Base):
    """Patient model"""
    __tablename__ = "patients"

    # PERFORMANCE: Add composite indexes for common query patterns
    # M16 FIX: unique per-practice contact indexes (active rows only) make
    # the DB the final arbiter for the check-then-insert duplicate race.
    __table_args__ = (
        Index("idx_patient_practice_status", "practice_id", "status"),
        Index("idx_patient_name", "last_name", "first_name"),
        Index("idx_patient_practice_email", "practice_id", "email"),
        Index(
            "uq_patient_practice_email_idx",
            "practice_id", "search_index_email",
            unique=True,
            postgresql_where=text("search_index_email IS NOT NULL AND status <> 'INACTIVE'"),
            sqlite_where=text("search_index_email IS NOT NULL AND status <> 'INACTIVE'"),
        ),
        Index(
            "uq_patient_practice_phone_idx",
            "practice_id", "search_index_phone",
            unique=True,
            postgresql_where=text("search_index_phone IS NOT NULL AND status <> 'INACTIVE'"),
            sqlite_where=text("search_index_phone IS NOT NULL AND status <> 'INACTIVE'"),
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)

    # ---- Encrypted PHI columns ----
    # ``column_name=`` is used as AAD so swapping ciphertext between columns
    # is detected on decrypt.
    first_name = Column(EncryptedString(100, column_name="patient.first_name"), nullable=False)
    last_name = Column(EncryptedString(100, column_name="patient.last_name"), nullable=False)
    date_of_birth = Column(Date, nullable=False)
    gender = Column(Enum(Gender))
    email = Column(EncryptedString(255, column_name="patient.email"))
    phone = Column(EncryptedString(20, column_name="patient.phone"))

    # Address
    address_street = Column(EncryptedString(255, column_name="patient.address_street"))
    address_city = Column(EncryptedString(100, column_name="patient.address_city"))
    address_state = Column(EncryptedString(100, column_name="patient.address_state"))
    address_zip = Column(EncryptedString(20, column_name="patient.address_zip"))

    # Global identifiers
    abha_id = Column(EncryptedString(20, column_name="patient.abha_id"))
    ssn_last_four = Column(EncryptedString(4, column_name="patient.ssn_last_four"))

    # Emergency contact
    emergency_contact = Column(
        EncryptedJSON(column_name="patient.emergency_contact")
    )  # {name, relationship, phone}

    # Medical information (all sensitive PHI)
    medical_alerts = Column(EncryptedJSON(column_name="patient.medical_alerts"), default=dict)
    medical_history = Column(EncryptedJSON(column_name="patient.medical_history"), default=dict)
    dental_history = Column(EncryptedJSON(column_name="patient.dental_history"), default=dict)
    insurance_info = Column(EncryptedJSON(column_name="patient.insurance_info"))

    # ---- Search indexes (low-sensitivity, allow exact + prefix lookup) ----
    # These store HMACs of the lowercased/normalized values.  They are *not*
    # plaintext; they let the DB do equality/prefix matching without
    # revealing the original value.  See ``app.core.search_index`` for the
    # HMAC computation.  These columns are *not* a substitute for the
    # encrypted columns — they are an index on them.
    search_index_email = Column(String(64), index=True)
    search_index_phone = Column(String(64), index=True)
    search_index_last_name = Column(String(64), index=True)

    # Status
    status = Column(Enum(PatientStatus), default=PatientStatus.ACTIVE)

    # Minor-record retention snapshot (docs/DATA_RETENTION_POLICY.md R1). Set at
    # ANONYMIZE TIME from DOB + practice minor config, BEFORE DOB is scrubbed,
    # so the minor ceiling survives erasure without keeping PHI. NULL for rows
    # anonymized before this column existed (adult rule only applies).
    purge_eligible_at = Column(DateTime(timezone=True), nullable=True)

    # Global Compliance (India DPDP / US HIPAA)
    consent_recorded_at = Column(DateTime(timezone=True))

    # Patient Portal Access
    portal_access_token = Column(String(128))  # Hashed token for patient self-service portal
    portal_token_expires = Column(DateTime(timezone=True))

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    practice = relationship("Practice", back_populates="patients")
    appointments = relationship("Appointment", back_populates="patient", cascade="all, delete-orphan")
    clinical_notes = relationship("ClinicalNote", back_populates="patient", cascade="all, delete-orphan")
    dental_chart = relationship("DentalChart", back_populates="patient", uselist=False, cascade="all, delete-orphan")
    perio_charts = relationship("PerioChart", back_populates="patient", cascade="all, delete-orphan")
    treatment_plans = relationship("TreatmentPlan", back_populates="patient", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="patient", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="patient", cascade="all, delete-orphan")
    insurances = relationship("PatientInsurance", back_populates="patient", cascade="all, delete-orphan")
    insurance_claims = relationship("InsuranceClaim", back_populates="patient", cascade="all, delete-orphan")
    pre_authorizations = relationship("InsurancePreAuthorization", back_populates="patient", cascade="all, delete-orphan")
    eligibility = relationship("Eligibility", back_populates="patient", cascade="all, delete-orphan")
    images = relationship("PatientImage", back_populates="patient", cascade="all, delete-orphan")
    online_bookings = relationship("OnlineBooking", back_populates="patient", cascade="all, delete-orphan")
    waitlist_entries = relationship("WaitlistEntry", back_populates="patient", cascade="all, delete-orphan")
    lab_cases = relationship("LabCase", back_populates="patient", cascade="all, delete-orphan")
    referrals = relationship("Referral", back_populates="patient", cascade="all, delete-orphan")
    messages = relationship("PatientMessage", back_populates="patient", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="patient", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="patient", cascade="all, delete-orphan")
    payment_cards = relationship("PaymentCard", back_populates="patient")
    subscriptions = relationship("Subscription", back_populates="patient")

    @property
    def full_name(self) -> str:
        # Both fields are already decrypted by the EncryptedString type.
        return f"{self.first_name or ''} {self.last_name or ''}".strip()

    @property
    def has_medical_alerts(self) -> bool:
        return bool(self.medical_alerts)

    def __repr__(self):
        return f"<Patient {self.id}>"


class PatientPortalSession(Base):
    """One row per active patient-portal login.

    H-5 FIX: the prior design stored a single ``Patient.portal_access_token``
    column, so a second login in a different browser would silently
    overwrite the first session. This table records every issued token
    (hashed) so multiple concurrent sessions work and the patient (or
    an operator) can revoke them all atomically.

    Tokens are stored hashed (SHA-256 hex); the plaintext is only ever
    returned to the caller at issue time. Expired / revoked rows are
    kept for a short retention window so audit can correlate them with
    the access log; a periodic Celery task purges them.
    """

    __tablename__ = "patient_portal_sessions"
    __table_args__ = (
        Index("ix_pps_patient_active", "patient_id", "revoked_at", "expires_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False, index=True)

    token_hash = Column(String(128), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    # User-agent and IP at issue time. Best-effort, useful for the
    # patient to see which devices are logged in.
    user_agent = Column(String(500), nullable=True)
    ip_address = Column(String(45), nullable=True)

    def __repr__(self) -> str:
        return f"<PatientPortalSession {self.id} patient={self.patient_id}>"


class PatientPortalAccessCode(Base):
    """Single-use magic-link code proving inbox control (Option A).

    POST /portal/access creates one row and emails a link containing the raw
    code; POST /portal/access/verify consumes it and issues the bearer. Codes
    are SHA-256 hashed at rest, expire in 15 minutes, allow 5 guesses, and
    are single-use. Login links, not the bearer, are what travel by email.
    """

    __tablename__ = "patient_portal_access_codes"
    __table_args__ = (
        Index("ix_ppac_patient_active", "patient_id", "used_at", "expires_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False, index=True)

    token_hash = Column(String(128), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    attempts = Column(Integer, nullable=False, default=0)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ip_address = Column(String(45), nullable=True)

    def __repr__(self) -> str:
        return f"<PatientPortalAccessCode {self.id} patient={self.patient_id}>"
