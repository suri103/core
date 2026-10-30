"""Reference/lookup schemas for scheduling-support endpoints.

These serve the provider/chair/appointment-type/patient-search lookups the React
scheduling UI (schedulingApi) and appointments service resolve against. The
endpoint paths are added to the frontend normalization prefix list, so
responses camelCase into `ScheduleProvider`/`Chair`/`AppointmentTypeConfig`/
`PatientSearchResult` after the case boundary.
"""
from typing import Optional
from pydantic import BaseModel
from uuid import UUID


class ProviderRef(BaseModel):
    """A clinical provider for scheduling (dentist/hygienist)."""
    id: UUID
    name: str
    role: str
    color: Optional[str] = None


class ChairRef(BaseModel):
    """A chair/operatory that appointments can be scheduled in."""
    id: UUID
    name: str
    color: str = "#6B7280"
    description: Optional[str] = None
    is_active: bool = True


class AppointmentTypeConfigRef(BaseModel):
    """An appointment-type lookup entry (DB row or standard fallback)."""
    id: str
    name: str
    code: str = ""
    duration: int
    color: str = "#3B82F6"
    is_active: bool = True
    allow_online_booking: bool = True
    description: Optional[str] = None


class ChairCreate(BaseModel):
    """Create payload for a chair/operatory."""
    name: str
    color: str = "#6B7280"
    is_active: bool = True


class ChairUpdate(BaseModel):
    """Partial update payload for a chair/operatory."""
    name: Optional[str] = None
    color: Optional[str] = None
    is_active: Optional[bool] = None


class AppointmentTypeCreate(BaseModel):
    """Create payload for an appointment type."""
    name: str
    duration: int
    color: str
    description: Optional[str] = None
    is_active: bool = True


class AppointmentTypeUpdate(BaseModel):
    """Partial update payload for an appointment type."""
    name: Optional[str] = None
    duration: Optional[int] = None
    color: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class PatientSearchRef(BaseModel):
    """A lightweight patient hit used by the scheduling type-ahead."""
    id: UUID
    name: str
    phone: str = ""
    email: Optional[str] = None