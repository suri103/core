"""Patient data-portability (GDPR/HIPAA export) schema.

Formalises the `/patients/{patient_id}/export` payload with a Pydantic
response model so the hand-rolled row dump is validated/serialised by the
framework and the `/patients` normalization boundary can camelCase it for the
React layer. Each section keeps full-column rows (a portable snapshot), while
the envelope, actor and timestamps are typed.
"""
from typing import Any, Dict, List
from datetime import datetime
from pydantic import BaseModel
from uuid import UUID


class PatientExportActor(BaseModel):
    """Who triggered the export."""
    id: UUID
    name: str
    role: str


class PatientExportResponse(BaseModel):
    """Complete patient export envelope (PHI data-portability payload)."""
    exported_at: datetime
    exported_by: PatientExportActor
    patient_demographics: Dict[str, Any]
    appointments: List[Dict[str, Any]]
    clinical_notes: List[Dict[str, Any]]
    treatment_plans: List[Dict[str, Any]]
    invoices: List[Dict[str, Any]]
    payments: List[Dict[str, Any]]
    insurances: List[Dict[str, Any]]
    insurance_claims: List[Dict[str, Any]]
    patient_images: List[Dict[str, Any]]
    documents: List[Dict[str, Any]]