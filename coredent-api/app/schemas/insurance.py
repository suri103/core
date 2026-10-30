"""
Insurance Schemas
Pydantic models for insurance data validation
"""

from datetime import datetime, date
import json
from typing import Literal, Optional, List
from pydantic import BaseModel, Field, field_validator
from uuid import UUID
from decimal import Decimal

from app.models.insurance import (
    ClaimStatus,
    RelationshipToSubscriber,
)


# Insurance Carrier Schemas

class InsuranceCarrierBase(BaseModel):
    """Base insurance carrier schema"""
    name: str = Field(..., min_length=1, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)
    fax: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=255)
    website: Optional[str] = Field(None, max_length=255)
    address_line1: Optional[str] = Field(None, max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=2)
    zip_code: Optional[str] = Field(None, max_length=10)
    payer_id: Optional[str] = Field(None, max_length=50)
    edi_enabled: bool = False
    notes: Optional[str] = None
    is_active: bool = True


class InsuranceCarrierCreate(InsuranceCarrierBase):
    """Schema for creating insurance carrier"""
    pass


class InsuranceCarrierUpdate(BaseModel):
    """Schema for updating insurance carrier"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)
    fax: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=255)
    website: Optional[str] = Field(None, max_length=255)
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    payer_id: Optional[str] = None
    edi_enabled: Optional[bool] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class InsuranceCarrierResponse(InsuranceCarrierBase):
    """Schema for insurance carrier response"""
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InsuranceCarrierListResponse(BaseModel):
    """Schema for list of insurance carriers"""
    carriers: List[InsuranceCarrierResponse]
    count: int


# Patient Insurance Schemas

class PatientInsuranceBase(BaseModel):
    """Writable patient insurance fields backed by PatientInsurance columns."""
    carrier_id: UUID
    subscriber_id: str = Field(..., min_length=1, max_length=100)
    group_number: Optional[str] = Field(None, max_length=100)
    relationship_to_subscriber: RelationshipToSubscriber = RelationshipToSubscriber.SELF
    is_primary: bool = True
    is_active: bool = True
    coverage_type: Optional[str] = Field(None, max_length=50)
    annual_maximum: Optional[Decimal] = Field(None, ge=0)
    annual_deductible: Optional[Decimal] = Field(None, ge=0)
    deductible_met: Decimal = Field(Decimal("0.0"), ge=0)
    benefits_used: Decimal = Field(Decimal("0.0"), ge=0)
    preventive_coverage: int = Field(100, ge=0, le=100)
    basic_coverage: int = Field(80, ge=0, le=100)
    major_coverage: int = Field(50, ge=0, le=100)
    ortho_coverage: int = Field(0, ge=0, le=100)
    effective_date: Optional[date] = None
    expiration_date: Optional[date] = None


class PatientInsuranceCreate(PatientInsuranceBase):
    """Schema for creating patient insurance."""


class PatientInsuranceUpdate(BaseModel):
    """Writable patient insurance fields for partial updates."""
    carrier_id: Optional[UUID] = None
    subscriber_id: Optional[str] = Field(None, min_length=1, max_length=100)
    group_number: Optional[str] = Field(None, max_length=100)
    relationship_to_subscriber: Optional[RelationshipToSubscriber] = None
    is_primary: Optional[bool] = None
    is_active: Optional[bool] = None
    coverage_type: Optional[str] = Field(None, max_length=50)
    annual_maximum: Optional[Decimal] = Field(None, ge=0)
    annual_deductible: Optional[Decimal] = Field(None, ge=0)
    deductible_met: Optional[Decimal] = Field(None, ge=0)
    benefits_used: Optional[Decimal] = Field(None, ge=0)
    preventive_coverage: Optional[int] = Field(None, ge=0, le=100)
    basic_coverage: Optional[int] = Field(None, ge=0, le=100)
    major_coverage: Optional[int] = Field(None, ge=0, le=100)
    ortho_coverage: Optional[int] = Field(None, ge=0, le=100)
    effective_date: Optional[date] = None
    expiration_date: Optional[date] = None

    @field_validator(
        "carrier_id",
        "subscriber_id",
        "relationship_to_subscriber",
        "is_primary",
        "is_active",
        "deductible_met",
        "benefits_used",
        "preventive_coverage",
        "basic_coverage",
        "major_coverage",
        "ortho_coverage",
    )
    @classmethod
    def reject_null_required_columns(cls, value):
        """Omission means unchanged; explicit null cannot clear required policy data."""
        if value is None:
            raise ValueError("field cannot be null")
        return value


class PatientInsuranceResponse(PatientInsuranceBase):
    """Schema for patient insurance response."""
    id: UUID
    patient_id: UUID
    verified: bool
    verified_at: Optional[datetime]
    verified_by: Optional[UUID]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PatientInsuranceListResponse(BaseModel):
    """Schema for list of patient insurance"""
    insurances: List[PatientInsuranceResponse]
    count: int


# Insurance Claim Schemas

class ProcedureCode(BaseModel):
    """Procedure code schema"""
    code: str
    description: str
    fee: Decimal


class InsuranceClaimBase(BaseModel):
    """Base insurance claim schema"""
    patient_insurance_id: UUID
    service_date: date
    billed_amount: Decimal = Field(..., gt=0)
    procedure_codes: List[ProcedureCode]
    diagnosis_codes: Optional[List[str]] = []
    notes: Optional[str] = None


class InsuranceClaimCreate(InsuranceClaimBase):
    """Schema for creating insurance claim"""
    pass


class InsuranceClaimUpdate(BaseModel):
    """Schema for updating insurance claim"""
    status: Optional[ClaimStatus] = None
    submission_date: Optional[date] = None
    received_date: Optional[date] = None
    paid_date: Optional[date] = None
    allowed_amount: Optional[Decimal] = Field(None, ge=0)
    deductible_amount: Optional[Decimal] = Field(None, ge=0)
    copay_amount: Optional[Decimal] = Field(None, ge=0)
    paid_amount: Optional[Decimal] = Field(None, ge=0)
    patient_responsibility: Optional[Decimal] = Field(None, ge=0)
    notes: Optional[str] = None
    denial_reason: Optional[str] = None

    @field_validator(
        "status",
        "deductible_amount",
        "copay_amount",
        "paid_amount",
        "patient_responsibility",
    )
    @classmethod
    def reject_null_required_columns(cls, value):
        """Prevent response-validation failures from nulling required model values."""
        if value is None:
            raise ValueError("field cannot be null")
        return value


class InsuranceClaimResponse(InsuranceClaimBase):
    """Schema for insurance claim response"""
    id: UUID
    practice_id: UUID
    patient_id: UUID
    carrier_id: UUID
    claim_number: str
    status: ClaimStatus
    submission_date: Optional[date]
    received_date: Optional[date]
    paid_date: Optional[date]
    allowed_amount: Optional[Decimal]
    deductible_amount: Decimal
    copay_amount: Decimal
    paid_amount: Decimal
    patient_responsibility: Decimal
    denial_reason: Optional[str]
    edi_transaction_id: Optional[str] = None
    edi_batch_id: Optional[str] = None
    confirmation_number: Optional[str] = None
    outstanding_balance: Decimal
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InsuranceClaimListResponse(BaseModel):
    """Schema for a paginated list of insurance claims."""
    claims: List[InsuranceClaimResponse]
    count: int
    total: int = 0
    limit: int = 50
    offset: int = 0
    next_offset: Optional[int] = None


# Pre-Authorization Schemas

PreAuthorizationStatus = Literal["pending", "approved", "denied"]


class PreAuthorizationBase(BaseModel):
    """Base pre-authorization schema."""
    patient_insurance_id: UUID
    request_date: date
    procedure_codes: List[ProcedureCode]
    estimated_cost: Decimal = Field(..., gt=0)
    notes: Optional[str] = None

    @field_validator("procedure_codes", mode="before")
    @classmethod
    def parse_stored_procedure_codes(cls, value):
        """Normalize the model's legacy Text JSON storage to the API list shape."""
        if value is None:
            return []
        if isinstance(value, str):
            value = json.loads(value)
        if not isinstance(value, list):
            raise ValueError("procedure_codes must be a JSON array")
        return value


class PreAuthorizationCreate(PreAuthorizationBase):
    """Schema for creating a pre-authorization."""


class PreAuthorizationUpdate(BaseModel):
    """Schema for updating a pre-authorization."""
    status: Optional[PreAuthorizationStatus] = None
    approval_date: Optional[date] = None
    expiration_date: Optional[date] = None
    approved_amount: Optional[Decimal] = Field(None, ge=0)
    notes: Optional[str] = None

    @field_validator("status")
    @classmethod
    def reject_null_status(cls, value):
        """Omitted status is unchanged; explicit null is never a valid status."""
        if value is None:
            raise ValueError("field cannot be null")
        return value


class PreAuthorizationResponse(PreAuthorizationBase):
    """Schema for pre-authorization response."""
    id: UUID
    patient_id: UUID
    authorization_number: str
    status: PreAuthorizationStatus
    approval_date: Optional[date]
    expiration_date: Optional[date]
    approved_amount: Optional[Decimal]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PreAuthorizationListResponse(BaseModel):
    """Schema for a paginated list of pre-authorizations."""
    pre_authorizations: List[PreAuthorizationResponse]
    count: int
    total: int = 0
    limit: int = 50
    offset: int = 0
    next_offset: Optional[int] = None

# Eligibility Schemas
class EligibilityResponse(BaseModel):
    """Schema for eligibility verification result"""
    id: UUID
    patient_id: UUID
    patient_insurance_id: UUID
    carrier_id: UUID
    verified_at: datetime
    is_active: bool
    coverage_status: Optional[str]
    remaining_benefits: Optional[Decimal]
    deductible_remaining: Optional[Decimal]
    notes: Optional[str]
    class Config:
        from_attributes = True

class EligibilityListResponse(BaseModel):
    """Schema for a paginated list of eligibility results."""
    eligibilities: List[EligibilityResponse]
    count: int
    total: int = 0
    limit: int = 50
    offset: int = 0
    next_offset: Optional[int] = None

# Explanation of Benefits (EOB) Schemas
class ExplanationOfBenefitsResponse(BaseModel):
    """Schema for EOB"""
    id: UUID
    claim_id: UUID
    generated_at: datetime
    description: Optional[str]
    amount_covered: Optional[Decimal]
    amount_patient_responsibility: Optional[Decimal]
    class Config:
        from_attributes = True

class ExplanationOfBenefitsListResponse(BaseModel):
    """Schema for a paginated list of EOBs."""
    eobs: List[ExplanationOfBenefitsResponse]
    count: int
    total: int = 0
    limit: int = 50
    offset: int = 0
    next_offset: Optional[int] = None


# Insurance Verification Schemas

class InsuranceVerificationRequest(BaseModel):
    """Schema for insurance verification request"""
    patient_insurance_id: UUID
    service_date: date


class InsuranceVerificationResponse(BaseModel):
    """Schema for insurance verification response"""
    is_active: bool
    coverage_status: str
    remaining_benefits: Optional[Decimal]
    deductible_remaining: Optional[Decimal]
    verification_date: datetime
    message: str


# Fee Schedule Schemas

class FeeScheduleEntryBase(BaseModel):
    ada_code: str = Field(..., max_length=10)
    fee: Decimal = Field(..., ge=0)
    is_allowed_amount: bool = True

class FeeScheduleEntryCreate(FeeScheduleEntryBase):
    pass

class FeeScheduleEntryResponse(FeeScheduleEntryBase):
    id: UUID
    fee_schedule_id: UUID
    class Config:
        from_attributes = True

class FeeScheduleBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    is_active: bool = True

class FeeScheduleCreate(FeeScheduleBase):
    entries: Optional[List[FeeScheduleEntryCreate]] = []

class FeeScheduleUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    is_active: Optional[bool] = None

class FeeScheduleResponse(FeeScheduleBase):
    id: UUID
    practice_id: UUID
    created_at: datetime
    updated_at: datetime
    entries: List[FeeScheduleEntryResponse] = []
    class Config:
        from_attributes = True

class FeeScheduleListResponse(BaseModel):
    fee_schedules: List[FeeScheduleResponse]
    count: int