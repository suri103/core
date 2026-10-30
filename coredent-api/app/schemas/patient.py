"""
Patient Schemas
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from uuid import UUID

from app.models.patient import PatientStatus, Gender


class EmergencyContact(BaseModel):
    """Emergency contact schema"""
    name: str
    relationship: str
    phone: str


class PatientBase(BaseModel):
    """Base patient schema"""
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    date_of_birth: date
    gender: Optional[Gender] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address_street: Optional[str] = None
    address_city: Optional[str] = None
    address_state: Optional[str] = Field(None, max_length=100)
    address_zip: Optional[str] = None
    abha_id: Optional[str] = Field(None, max_length=20)


class PatientCreate(PatientBase):
    """Schema for creating a patient"""
    emergency_contact: Optional[EmergencyContact] = None
    medical_alerts: Optional[List[str]] = []
    medical_history: Optional[Dict[str, Any]] = {}
    dental_history: Optional[Dict[str, Any]] = {}
    insurance_info: Optional[Dict[str, Any]] = None


class PatientUpdate(BaseModel):
    """Schema for updating a patient"""
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    date_of_birth: Optional[date] = None
    gender: Optional[Gender] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address_street: Optional[str] = None
    address_city: Optional[str] = None
    address_state: Optional[str] = Field(None, max_length=100)
    address_zip: Optional[str] = None
    abha_id: Optional[str] = Field(None, max_length=20)
    emergency_contact: Optional[EmergencyContact] = None
    medical_alerts: Optional[List[str]] = None
    medical_history: Optional[Dict[str, Any]] = None
    dental_history: Optional[Dict[str, Any]] = None
    insurance_info: Optional[Dict[str, Any]] = None
    status: Optional[PatientStatus] = None

    class Config:
        extra = "forbid"


class PatientInDB(PatientBase):
    """Schema for patient in database"""
    id: UUID
    practice_id: UUID
    emergency_contact: Optional[Dict[str, Any]]
    medical_alerts: List[str]
    medical_history: Dict[str, Any]
    dental_history: Dict[str, Any]
    insurance_info: Optional[Dict[str, Any]]
    abha_id: Optional[str]
    consent_recorded_at: Optional[datetime]
    status: PatientStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PatientAttachmentResponse(BaseModel):
    id: UUID
    name: str
    type: str
    size: int
    url: str
    category: str
    uploaded_at: Optional[datetime] = None
    uploaded_by: Optional[str] = None
    uploaded_by_name: Optional[str] = None

    class Config:
        from_attributes = True


class PatientResponse(PatientInDB):
    """Schema for patient response"""
    full_name: str
    has_medical_alerts: bool
    notes: List[Any] = []
    attachments: List[PatientAttachmentResponse] = []
    appointment_stats: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class PatientListItem(BaseModel):
    """Schema for patient list item"""
    id: UUID
    first_name: str
    last_name: str
    full_name: str
    email: Optional[str]
    phone: Optional[str]
    date_of_birth: date
    status: PatientStatus
    has_medical_alerts: bool
    medical_alerts: List[str]
    last_visit: Optional[date] = None
    next_appointment: Optional[date] = None

    class Config:
        from_attributes = True


class PatientSearchParams(BaseModel):
    """Patient search parameters"""
    query: Optional[str] = None
    status: Optional[PatientStatus] = None
    has_medical_alert: Optional[bool] = None
    sort_by: Optional[str] = "name"
    page: int = Field(1, ge=1)
    limit: int = Field(10, ge=1, le=100)
