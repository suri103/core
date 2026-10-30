"""
Imaging Schemas
Pydantic models for imaging data validation
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from uuid import UUID

from app.models.imaging import ImageType, ImageCategory


# Image Annotation Schema

class ImageAnnotation(BaseModel):
    """Image annotation schema"""
    type: str  # arrow, circle, text, etc.
    x: int
    y: int
    width: Optional[int] = None
    height: Optional[int] = None
    text: Optional[str] = None
    color: Optional[str] = "#FF0000"


# Patient Image Schemas

class PatientImageBase(BaseModel):
    """Base patient image schema"""
    image_type: ImageType
    category: Optional[ImageCategory] = None
    tooth_number: Optional[str] = Field(None, max_length=20)
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    notes: Optional[str] = None
    acquisition_date: datetime
    device_name: Optional[str] = Field(None, max_length=255)
    device_serial: Optional[str] = Field(None, max_length=100)


class PatientImageCreate(PatientImageBase):
    """Schema for creating patient image"""
    provider_id: Optional[UUID] = None


class PatientImageUpdate(BaseModel):
    """Schema for updating patient image"""
    image_type: Optional[ImageType] = None
    category: Optional[ImageCategory] = None
    tooth_number: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    device_name: Optional[str] = None
    device_serial: Optional[str] = None
    is_shared_with_patient: Optional[bool] = None
    is_shared_with_referral: Optional[bool] = None


class PatientImageResponse(PatientImageBase):
    """Schema for patient image response"""
    id: UUID
    practice_id: UUID
    patient_id: UUID
    provider_id: Optional[UUID]
    file_name: str
    file_path: str
    url: Optional[str] = None
    file_size: Optional[int]
    mime_type: Optional[str]
    width: Optional[int]
    height: Optional[int]
    dicom_study_id: Optional[str]
    dicom_series_id: Optional[str]
    dicom_instance_id: Optional[str]
    annotations: Optional[List[ImageAnnotation]] = []
    is_shared_with_patient: bool
    is_shared_with_referral: bool
    is_deleted: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PatientImageListResponse(BaseModel):
    """Schema for list of patient images"""
    images: List[PatientImageResponse]
    count: int


# Image Upload Schemas

class ImageUploadRequest(BaseModel):
    """Schema for image upload request"""
    image_type: ImageType
    category: Optional[ImageCategory] = None
    tooth_number: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    acquisition_date: datetime
    device_name: Optional[str] = None
    device_serial: Optional[str] = None
    provider_id: Optional[UUID] = None


class ImageUploadResponse(BaseModel):
    """Schema for image upload response"""
    upload_url: str
    image_id: UUID
    expires_in: int  # seconds


# Image Annotation Schemas

class ImageAnnotationCreate(BaseModel):
    """Schema for creating image annotation"""
    annotations: List[ImageAnnotation]


class ImageAnnotationResponse(BaseModel):
    """Schema for image annotation response"""
    image_id: UUID
    annotations: List[ImageAnnotation]
    updated_at: datetime


# Image Series Schemas

class ImageSeriesBase(BaseModel):
    """Base image series schema"""
    series_name: str = Field(..., min_length=1, max_length=255)
    series_type: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    acquisition_date: datetime


class ImageSeriesCreate(ImageSeriesBase):
    """Schema for creating image series"""
    provider_id: Optional[UUID] = None


class ImageSeriesUpdate(BaseModel):
    """Schema for updating image series"""
    series_name: Optional[str] = Field(None, min_length=1, max_length=255)
    series_type: Optional[str] = None
    description: Optional[str] = None


class ImageSeriesResponse(ImageSeriesBase):
    """Schema for image series response"""
    id: UUID
    practice_id: UUID
    patient_id: UUID
    provider_id: Optional[UUID]
    image_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ImageSeriesListResponse(BaseModel):
    """Schema for list of image series"""
    series: List[ImageSeriesResponse]
    count: int


# Image Template Schemas

class TemplateConfiguration(BaseModel):
    """Template configuration item"""
    position: str
    type: ImageCategory
    required: bool = True


class ImageTemplateBase(BaseModel):
    """Base image template schema"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    configuration: List[TemplateConfiguration]
    is_active: bool = True


class ImageTemplateCreate(ImageTemplateBase):
    """Schema for creating image template"""
    pass


class ImageTemplateUpdate(BaseModel):
    """Schema for updating image template"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    configuration: Optional[List[TemplateConfiguration]] = None
    is_active: Optional[bool] = None


class ImageTemplateResponse(ImageTemplateBase):
    """Schema for image template response"""
    id: UUID
    practice_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ImageTemplateListResponse(BaseModel):
    """Schema for list of image templates"""
    templates: List[ImageTemplateResponse]
    count: int


# Image Sharing Schemas

class ImageShareRequest(BaseModel):
    """Schema for image sharing request"""
    share_with_patient: bool = False
    share_with_referral: bool = False
    referral_email: Optional[str] = None


class ImageShareResponse(BaseModel):
    """Schema for image sharing response"""
    image_id: UUID
    share_link: Optional[str] = None
    expires_at: Optional[datetime] = None
    message: str