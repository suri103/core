"""
EDI Schemas
Insurance eligibility and claims request/response models
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Union
from uuid import UUID
from datetime import date
from decimal import Decimal


class EligibilityCheckRequest(BaseModel):
    """Request to check insurance eligibility"""
    patient_id: UUID
    patient_insurance_id: UUID
    service_date: Optional[date] = None


class EligibilityCheckResponse(BaseModel):
    """Response from eligibility check.

    Fields beyond the core `eligible`/`coverage_status` flags are all optional
    because real-world clearinghouse responses (especially for terminated or
    error states) return partial payloads.
    L-6 FIX: money as Decimal (JSON numbers still coerce; avoids binary float).
    """
    eligible: bool
    coverage_status: str
    plan_name: Optional[str] = None
    effective_date: Optional[str] = None
    termination_date: Optional[str] = None
    copay: Optional[Decimal] = None
    deductible: Optional[Decimal] = None
    deductible_remaining: Optional[Decimal] = None
    coinsurance: Optional[Decimal] = None
    annual_max: Optional[Decimal] = None
    annual_remaining: Optional[Decimal] = None
    message: Optional[str] = None
    error: Optional[str] = None


class ClaimProcedure(BaseModel):
    """Individual procedure in a claim (L-6 FIX: money as Decimal)"""
    procedure_code: str = Field(..., min_length=1, max_length=10)
    tooth: Optional[str] = Field(None, max_length=10)
    surface: Optional[str] = Field(None, max_length=10)
    fee: Decimal = Field(..., ge=0)
    date_of_service: date


class ClaimSubmitRequest(BaseModel):
    """Request to submit a dental claim (L-6 FIX: money as Decimal)"""
    patient_id: UUID
    patient_insurance_id: UUID
    procedures: List[ClaimProcedure] = Field(..., min_length=1, max_length=100)
    total_amount: Decimal = Field(..., ge=0)
    service_date: date
    diagnosis_codes: Optional[List[str]] = Field(None, max_length=50)
    # H-03: clients that already have their own submission identity may supply
    # it, so a retry after a network timeout is recognised even if the request
    # body was rebuilt. When omitted, a content-addressed key is derived.
    idempotency_key: Optional[str] = Field(None, min_length=8, max_length=200)


class ClaimSubmitResponse(BaseModel):
    """Response from claim submission. Supports accept/reject paths."""
    status: str
    claim_id: Optional[Union[UUID, str]] = None
    external_claim_id: Optional[str] = None
    submitted_at: Optional[str] = None
    message: Optional[str] = None


class ClaimStatusResponse(BaseModel):
    """Response for claim status. Tolerant of partial/missing fields. (L-6 FIX: money as Decimal)"""
    status: str
    claim_id: Optional[Union[UUID, str]] = None
    external_claim_id: Optional[str] = None
    paid_amount: Decimal = Decimal("0")
    patient_responsibility: Decimal = Decimal("0")
    denial_code: Optional[str] = None
    denial_reason: Optional[str] = None
    processed_date: Optional[Union[date, str]] = None
    message: Optional[str] = None
