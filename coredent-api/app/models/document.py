"""
Document Management Models
Templates, e-signatures, and document storage
"""

from sqlalchemy import Column, String, DateTime, ForeignKey, Enum, Text, Boolean, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.core.base import Base


class DocumentCategory(str, enum.Enum):
    """Document categories"""
    CONSENT = "consent"
    FINANCIAL = "financial"
    CLINICAL = "clinical"
    ADMINISTRATIVE = "administrative"
    POLICY = "policy"
    MARKETING = "marketing"
    OTHER = "other"


class DocumentStatus(str, enum.Enum):
    """Document status"""
    DRAFT = "draft"
    PENDING = "pending"
    SIGNED = "signed"
    EXPIRED = "expired"
    VOIDED = "voided"


class SignatureStatus(str, enum.Enum):
    """E-signature status"""
    PENDING = "pending"
    SENT = "sent"
    VIEWED = "viewed"
    SIGNED = "signed"
    DECLINED = "declined"
    EXPIRED = "expired"


class DocumentTemplate(Base):
    """Document template model"""
    __tablename__ = "document_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)

    # Template Information
    name = Column(String(255), nullable=False)
    description = Column(Text)
    category = Column(Enum(DocumentCategory), default=DocumentCategory.OTHER)

    # Content
    template_content = Column(Text, nullable=False)  # HTML or Markdown
    template_variables = Column(JSON)  # JSON object of available variables

    # Settings
    requires_signature = Column(Boolean, default=False)
    requires_witness = Column(Boolean, default=False)
    requires_date = Column(Boolean, default=True)

    # Signing Options
    signature_type = Column(String(20), default="electronic")  # electronic, digital, handwritten

    # Status
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)

    # Version
    version = Column(Integer, default=1)

    # Usage Stats
    times_used = Column(Integer, default=0)
    completion_rate = Column(String(10))  # Percentage

    # Related
    related_template_id = Column(UUID(as_uuid=True), ForeignKey("document_templates.id"))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    practice = relationship("Practice", back_populates="document_templates")
    documents = relationship("Document", back_populates="template")

    def __repr__(self):
        return f"<DocumentTemplate {self.name}>"


class Document(Base):
    """Document model - generated from templates or uploaded"""
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"))
    template_id = Column(UUID(as_uuid=True), ForeignKey("document_templates.id"))
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    # Document Information
    name = Column(String(255), nullable=False)
    description = Column(Text)
    category = Column(Enum(DocumentCategory), default=DocumentCategory.OTHER)

    # Content
    content = Column(Text)
    file_url = Column(String(500))  # URL to stored file
    file_type = Column(String(20))  # pdf, html, doc

    # Status
    status = Column(Enum(DocumentStatus), default=DocumentStatus.DRAFT)

    # Completion
    is_completed = Column(Boolean, default=False)
    completed_at = Column(DateTime(timezone=True))

    # Expiration
    expires_at = Column(DateTime(timezone=True))

    # Related
    appointment_id = Column(UUID(as_uuid=True), ForeignKey("appointments.id"))
    treatment_plan_id = Column(UUID(as_uuid=True), ForeignKey("treatment_plans.id"))

    # Notes
    notes = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    practice = relationship("Practice", back_populates="documents")
    patient = relationship("Patient", back_populates="documents")
    template = relationship("DocumentTemplate", back_populates="documents")
    creator = relationship("User")
    signatures = relationship("DocumentSignature", back_populates="document", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Document {self.name} - {self.status}>"


class DocumentSignature(Base):
    """E-signature model"""
    __tablename__ = "document_signatures"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    signer_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"))
    signed_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    # Signer Information
    signer_name = Column(String(255))
    signer_email = Column(String(255))
    signer_role = Column(String(50))  # patient, guardian, witness, provider

    # Signature Status
    status = Column(Enum(SignatureStatus), default=SignatureStatus.PENDING)

    # Signature Data
    signature_data = Column(Text)  # Base64 encoded signature image or hash
    signature_ip = Column(String(45))  # IP address
    signature_user_agent = Column(String(500))

    # Timestamps
    sent_at = Column(DateTime(timezone=True))
    viewed_at = Column(DateTime(timezone=True))
    signed_at = Column(DateTime(timezone=True))

    # External Provider
    provider = Column(String(50))  # docusign, hellosign, internal
    provider_signature_id = Column(String(100))

    # Decline Info
    decline_reason = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    document = relationship("Document", back_populates="signatures")
    signer = relationship("Patient")
    signer_user = relationship("User")

    def __repr__(self):
        return f"<DocumentSignature {self.id} - {self.status}>"


class SignatureField(Base):
    """Signature field positions on a document"""
    __tablename__ = "signature_fields"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)

    # Field Information
    field_name = Column(String(100), nullable=False)
    field_type = Column(String(20), nullable=False)  # signature, initials, date, text
    required = Column(Boolean, default=True)

    # Position (percentage based for PDF)
    page_number = Column(Integer, nullable=False)
    x_position = Column(String(10))  # Percentage
    y_position = Column(String(10))  # Percentage
    width = Column(String(10))  # Percentage
    height = Column(String(10))  # Percentage

    # Assignee
    assignee_type = Column(String(20))  # patient, provider, witness
    assignee_label = Column(String(100))

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    document = relationship("Document")

    def __repr__(self):
        return f"<SignatureField {self.field_name}>"
