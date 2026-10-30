"""
Imaging Models
Digital images, X-rays, and related data
"""

from sqlalchemy import Column, String, DateTime, ForeignKey, Enum, Integer, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.core.base import Base


class ImageType(str, enum.Enum):
    """Image type"""
    XRAY = "xray"
    PHOTO = "photo"
    SCAN = "scan"
    DOCUMENT = "document"
    OTHER = "other"


class ImageCategory(str, enum.Enum):
    """Image category for X-rays"""
    PERIAPICAL = "periapical"
    BITEWING = "bitewing"
    PANORAMIC = "panoramic"
    CEPHALOMETRIC = "cephalometric"
    CBCT = "cbct"
    INTRAORAL = "intraoral"
    EXTRAORAL = "extraoral"
    OTHER = "other"


class ToothPosition(str, enum.Enum):
    """Tooth numbering system (Universal)"""
    # Adult teeth (1-32)
    TOOTH_1 = "1"   # Upper right third molar
    TOOTH_2 = "2"
    TOOTH_3 = "3"
    TOOTH_4 = "4"
    TOOTH_5 = "5"
    TOOTH_6 = "6"
    TOOTH_7 = "7"
    TOOTH_8 = "8"
    TOOTH_9 = "9"
    TOOTH_10 = "10"
    TOOTH_11 = "11"
    TOOTH_12 = "12"
    TOOTH_13 = "13"
    TOOTH_14 = "14"
    TOOTH_15 = "15"
    TOOTH_16 = "16"  # Lower left third molar
    TOOTH_17 = "17"
    TOOTH_18 = "18"
    TOOTH_19 = "19"
    TOOTH_20 = "20"
    TOOTH_21 = "21"
    TOOTH_22 = "22"
    TOOTH_23 = "23"
    TOOTH_24 = "24"
    TOOTH_25 = "25"
    TOOTH_26 = "26"
    TOOTH_27 = "27"
    TOOTH_28 = "28"
    TOOTH_29 = "29"
    TOOTH_30 = "30"
    TOOTH_31 = "31"
    TOOTH_32 = "32"  # Lower right third molar
    FULL_MOUTH = "full_mouth"


class PatientImage(Base):
    """Patient image model"""
    __tablename__ = "patient_images"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    # Image Information
    image_type = Column(Enum(ImageType), nullable=False)
    category = Column(Enum(ImageCategory))
    tooth_number = Column(String(20))  # Can be multiple teeth: "1,2,3" or "full_mouth"

    # File Information
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)  # S3/storage path
    file_size = Column(Integer)  # in bytes
    mime_type = Column(String(100))

    # Image Metadata
    width = Column(Integer)
    height = Column(Integer)

    # DICOM Metadata (for X-rays)
    dicom_study_id = Column(String(100))
    dicom_series_id = Column(String(100))
    dicom_instance_id = Column(String(100))

    # Acquisition Information
    acquisition_date = Column(DateTime(timezone=True), nullable=False)
    device_name = Column(String(255))
    device_serial = Column(String(100))

    # Clinical Information
    title = Column(String(255))
    description = Column(Text)
    notes = Column(Text)

    # Annotations (stored as JSON)
    # Structure: [{ type: "arrow", x: 100, y: 200, text: "Cavity" }]
    annotations = Column(Text)  # JSON string

    # Sharing and Access
    is_shared_with_patient = Column(Boolean, default=False)
    is_shared_with_referral = Column(Boolean, default=False)
    share_token = Column(String(255))  # Token for secure sharing
    # L1 FIX: share emails promise a 30-day expiry; this column makes the
    # promise real. NULL = legacy share created before enforcement
    # (grandfathered, treated as non-expiring).
    share_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Metadata
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    practice = relationship("Practice", back_populates="images")
    patient = relationship("Patient", back_populates="images")
    provider = relationship("User", back_populates="images")

    def __repr__(self):
        return f"<PatientImage {self.file_name} - {self.image_type}>"


class ImageSeries(Base):
    """Image series for grouping related images (e.g., full mouth series)"""
    __tablename__ = "image_series"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    # Series Information
    series_name = Column(String(255), nullable=False)
    series_type = Column(String(100))  # "FMX" (Full Mouth X-ray), "BWX" (Bitewing), etc.
    description = Column(Text)

    # Dates
    acquisition_date = Column(DateTime(timezone=True), nullable=False)

    # Image count
    image_count = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    practice = relationship("Practice")
    patient = relationship("Patient")
    provider = relationship("User")

    def __repr__(self):
        return f"<ImageSeries {self.series_name}>"


class ImageTemplate(Base):
    """Image templates for standardized image capture"""
    __tablename__ = "image_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)

    # Template Information
    name = Column(String(255), nullable=False)
    description = Column(Text)

    # Template Configuration (stored as JSON)
    # Structure: [{ position: "1", type: "periapical", required: true }]
    configuration = Column(Text, nullable=False)  # JSON string

    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    practice = relationship("Practice")

    def __repr__(self):
        return f"<ImageTemplate {self.name}>"