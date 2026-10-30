"""
Treatment Planning Schemas
Pydantic models for treatment planning API
"""

from typing import List, Optional, Dict, Any
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field, model_validator
import uuid as uuid_lib

from app.models.treatment import (
    TreatmentPlanStatus,
    ProcedureType,
    ToothSurface,
)


# Base Schemas
class TreatmentPlanBase(BaseModel):
    """Base treatment plan schema"""
    plan_name: str = Field(..., min_length=1, max_length=255)
    status: TreatmentPlanStatus = TreatmentPlanStatus.DRAFT
    chief_complaint: Optional[str] = None
    diagnosis: Optional[str] = None
    treatment_goals: Optional[str] = None
    target_start_date: Optional[date] = None
    target_completion_date: Optional[date] = None
    notes: Optional[str] = None
    visual_config: Dict[str, Any] = Field(default_factory=dict)


class TreatmentPlanCreate(TreatmentPlanBase):
    """Schema for creating a treatment plan"""
    patient_id: uuid_lib.UUID
    provider_id: uuid_lib.UUID


class TreatmentPlanUpdate(BaseModel):
    """Schema for updating a treatment plan"""
    plan_name: Optional[str] = Field(None, min_length=1, max_length=255)
    status: Optional[TreatmentPlanStatus] = None
    chief_complaint: Optional[str] = None
    diagnosis: Optional[str] = None
    treatment_goals: Optional[str] = None
    target_start_date: Optional[date] = None
    target_completion_date: Optional[date] = None
    acceptance_method: Optional[str] = None
    acceptance_notes: Optional[str] = None
    notes: Optional[str] = None
    visual_config: Optional[Dict[str, Any]] = None


class TreatmentPlanResponse(TreatmentPlanBase):
    """Schema for treatment plan response (L-6 FIX: money as Decimal, not float)"""
    id: uuid_lib.UUID
    practice_id: uuid_lib.UUID
    patient_id: uuid_lib.UUID
    provider_id: uuid_lib.UUID
    total_estimated_cost: Decimal
    total_insurance_estimate: Decimal
    total_patient_responsibility: Decimal
    created_date: date
    presented_date: Optional[date] = None
    accepted_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TreatmentPlanListResponse(BaseModel):
    """Schema for listing treatment plans."""
    plans: List[TreatmentPlanResponse]
    count: int
    total: int = 0
    next_offset: Optional[int] = None


# Treatment Phase Schemas
class TreatmentPhaseBase(BaseModel):
    """Base treatment phase schema"""
    phase_number: int = Field(..., ge=1)
    phase_name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    target_start_date: Optional[date] = None
    target_completion_date: Optional[date] = None
    status: str = "planned"
    display_order: int = 0


class TreatmentPhaseCreate(TreatmentPhaseBase):
    """Schema for creating a treatment phase"""
    pass


class TreatmentPhaseUpdate(BaseModel):
    """Schema for updating a treatment phase"""
    phase_name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    target_start_date: Optional[date] = None
    target_completion_date: Optional[date] = None
    status: Optional[str] = None
    display_order: Optional[int] = None
    actual_start_date: Optional[date] = None
    actual_completion_date: Optional[date] = None


class TreatmentPhaseResponse(TreatmentPhaseBase):
    """Schema for treatment phase response (L-6 FIX: money as Decimal)"""
    id: uuid_lib.UUID
    treatment_plan_id: uuid_lib.UUID
    estimated_cost: Decimal
    insurance_estimate: Decimal
    patient_responsibility: Decimal
    actual_start_date: Optional[date] = None
    actual_completion_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TreatmentPhaseListResponse(BaseModel):
    """Schema for listing treatment phases"""
    phases: List[TreatmentPhaseResponse]
    count: int


# Treatment Procedure Schemas
class ProcedureSurface(BaseModel):
    """Schema for tooth surfaces"""
    surface: ToothSurface
    description: Optional[str] = None


class TreatmentProcedureBase(BaseModel):
    """Base treatment procedure schema (L-6 FIX: money as Decimal)"""
    procedure_type: ProcedureType
    ada_code: str = Field(..., min_length=4, max_length=10)
    description: str = Field(..., min_length=1, max_length=500)
    tooth_number: Optional[str] = None
    surfaces: Optional[str] = None
    quadrant: Optional[int] = Field(None, ge=1, le=4)
    fee: Decimal = Field(..., ge=0)
    insurance_estimate: Decimal = Field(Decimal("0"), ge=0)
    patient_responsibility: Decimal = Field(Decimal("0"), ge=0)
    is_covered: bool = True
    coverage_percentage: int = Field(0, ge=0, le=100)
    requires_pre_auth: bool = False
    priority: int = Field(1, ge=1, le=3)
    complexity: Optional[str] = None
    duration_minutes: int = Field(30, ge=1)
    status: str = "planned"
    is_accepted: bool = False
    acceptance_notes: Optional[str] = None
    display_order: int = 0

    @model_validator(mode="after")
    def _validate_money_splits(self):
        fee = Decimal(str(self.fee))
        ins = Decimal(str(self.insurance_estimate or 0))
        pat = Decimal(str(self.patient_responsibility or 0))
        if ins > fee:
            raise ValueError("insurance_estimate cannot exceed fee")
        if pat > fee:
            raise ValueError("patient_responsibility cannot exceed fee")
        if (ins + pat) > fee:
            raise ValueError("insurance_estimate + patient_responsibility cannot exceed fee")
        return self


class TreatmentProcedureCreate(TreatmentProcedureBase):
    """Schema for creating a treatment procedure"""
    phase_id: Optional[uuid_lib.UUID] = None
    appointment_id: Optional[uuid_lib.UUID] = None
    pre_auth_id: Optional[uuid_lib.UUID] = None


class TreatmentProcedureUpdate(BaseModel):
    """Schema for updating a treatment procedure (L-6 FIX: money as Decimal)"""
    procedure_type: Optional[ProcedureType] = None
    ada_code: Optional[str] = Field(None, min_length=4, max_length=10)
    description: Optional[str] = Field(None, min_length=1, max_length=500)
    tooth_number: Optional[str] = None
    surfaces: Optional[str] = None
    quadrant: Optional[int] = Field(None, ge=1, le=4)
    fee: Optional[Decimal] = Field(None, ge=0)
    insurance_estimate: Optional[Decimal] = Field(None, ge=0)
    patient_responsibility: Optional[Decimal] = Field(None, ge=0)
    is_covered: Optional[bool] = None
    coverage_percentage: Optional[int] = Field(None, ge=0, le=100)
    requires_pre_auth: Optional[bool] = None
    priority: Optional[int] = Field(None, ge=1, le=3)
    complexity: Optional[str] = None
    duration_minutes: Optional[int] = Field(None, ge=1)
    status: Optional[str] = None
    is_accepted: Optional[bool] = None
    acceptance_notes: Optional[str] = None
    display_order: Optional[int] = None
    appointment_id: Optional[uuid_lib.UUID] = None
    pre_auth_id: Optional[uuid_lib.UUID] = None

    @model_validator(mode="after")
    def _validate_money_splits(self):
        if self.fee is not None:
            fee = Decimal(str(self.fee))
            ins = Decimal(str(self.insurance_estimate)) if self.insurance_estimate is not None else None
            pat = Decimal(str(self.patient_responsibility)) if self.patient_responsibility is not None else None
            if ins is not None and ins > fee:
                raise ValueError("insurance_estimate cannot exceed fee")
            if pat is not None and pat > fee:
                raise ValueError("patient_responsibility cannot exceed fee")
            if ins is not None and pat is not None and (ins + pat) > fee:
                raise ValueError("insurance_estimate + patient_responsibility cannot exceed fee")
        return self


class TreatmentProcedureResponse(TreatmentProcedureBase):
    """Schema for treatment procedure response"""
    id: uuid_lib.UUID
    treatment_plan_id: uuid_lib.UUID
    phase_id: Optional[uuid_lib.UUID] = None
    appointment_id: Optional[uuid_lib.UUID] = None
    pre_auth_id: Optional[uuid_lib.UUID] = None
    created_at: datetime
    updated_at: datetime

    @property
    def insurance_coverage_amount(self) -> Decimal:
        if self.insurance_estimate is not None and Decimal(str(self.insurance_estimate)) > 0:
            return Decimal(str(self.insurance_estimate))
        return (Decimal(str(self.fee)) * (Decimal(self.coverage_percentage) / Decimal(100))).quantize(Decimal("0.01"))

    @property
    def patient_amount(self) -> Decimal:
        if self.patient_responsibility is not None and Decimal(str(self.patient_responsibility)) > 0:
            return Decimal(str(self.patient_responsibility))
        return Decimal(str(self.fee)) - self.insurance_coverage_amount

    class Config:
        from_attributes = True


class TreatmentProcedureListResponse(BaseModel):
    """Schema for listing treatment procedures"""
    procedures: List[TreatmentProcedureResponse]
    count: int


# Procedure Library Schemas
class ProcedureLibraryBase(BaseModel):
    """Base procedure library schema (L-6 FIX: money as Decimal)"""
    ada_code: str = Field(..., min_length=4, max_length=10)
    description: str = Field(..., min_length=1, max_length=500)
    long_description: Optional[str] = None
    procedure_type: ProcedureType
    category: Optional[str] = None
    subcategory: Optional[str] = None
    default_fee: Optional[Decimal] = None
    typical_duration_minutes: int = Field(30, ge=1)
    typical_coverage_percentage: Optional[int] = Field(None, ge=0, le=100)
    requires_pre_auth: bool = False
    common_alternatives: Optional[str] = None
    is_active: bool = True


class ProcedureLibraryCreate(ProcedureLibraryBase):
    """Schema for creating a procedure library entry"""
    pass


class ProcedureLibraryUpdate(BaseModel):
    """Schema for updating a procedure library entry (L-6 FIX: money as Decimal)"""
    description: Optional[str] = Field(None, min_length=1, max_length=500)
    long_description: Optional[str] = None
    procedure_type: Optional[ProcedureType] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    default_fee: Optional[Decimal] = None
    typical_duration_minutes: Optional[int] = Field(None, ge=1)
    typical_coverage_percentage: Optional[int] = Field(None, ge=0, le=100)
    requires_pre_auth: Optional[bool] = None
    common_alternatives: Optional[str] = None
    is_active: Optional[bool] = None
    is_archived: Optional[bool] = None


class ProcedureLibraryResponse(ProcedureLibraryBase):
    """Schema for procedure library response"""
    id: uuid_lib.UUID
    practice_id: uuid_lib.UUID
    is_archived: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProcedureLibraryListResponse(BaseModel):
    """Schema for listing procedure library entries"""
    procedures: List[ProcedureLibraryResponse]
    count: int


# Treatment Plan Template Schemas
class TemplateProcedure(BaseModel):
    """Schema for template procedure configuration (L-6 FIX: money as Decimal)"""
    ada_code: str
    description: str
    default_fee: Optional[Decimal] = None
    typical_duration_minutes: Optional[int] = None
    typical_coverage_percentage: Optional[int] = None


class TreatmentPlanTemplateBase(BaseModel):
    """Base treatment plan template schema"""
    template_name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    category: Optional[str] = None
    typical_diagnosis: Optional[str] = None
    typical_goals: Optional[str] = None
    configuration: List[TemplateProcedure] = Field(default_factory=list)
    is_active: bool = True


class TreatmentPlanTemplateCreate(TreatmentPlanTemplateBase):
    """Schema for creating a treatment plan template"""
    pass


class TreatmentPlanTemplateUpdate(BaseModel):
    """Schema for updating a treatment plan template"""
    template_name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    category: Optional[str] = None
    typical_diagnosis: Optional[str] = None
    typical_goals: Optional[str] = None
    configuration: Optional[List[TemplateProcedure]] = None
    is_active: Optional[bool] = None


class TreatmentPlanTemplateResponse(TreatmentPlanTemplateBase):
    """Schema for treatment plan template response"""
    id: uuid_lib.UUID
    practice_id: uuid_lib.UUID
    usage_count: int
    last_used: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TreatmentPlanTemplateListResponse(BaseModel):
    """Schema for listing treatment plan templates"""
    templates: List[TreatmentPlanTemplateResponse]
    count: int


# Treatment Plan Note Schemas
class TreatmentPlanNoteBase(BaseModel):
    """Base treatment plan note schema"""
    note_type: str = "general"
    content: str = Field(..., min_length=1)
    attachments: List[str] = Field(default_factory=list)
    is_internal: bool = True


class TreatmentPlanNoteCreate(TreatmentPlanNoteBase):
    """Schema for creating a treatment plan note"""
    pass


class TreatmentPlanNoteUpdate(BaseModel):
    """Schema for updating a treatment plan note"""
    note_type: Optional[str] = None
    content: Optional[str] = Field(None, min_length=1)
    attachments: Optional[List[str]] = None
    is_internal: Optional[bool] = None


class TreatmentPlanNoteResponse(TreatmentPlanNoteBase):
    """Schema for treatment plan note response"""
    id: uuid_lib.UUID
    treatment_plan_id: uuid_lib.UUID
    author_id: uuid_lib.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TreatmentPlanNoteListResponse(BaseModel):
    """Schema for listing treatment plan notes"""
    notes: List[TreatmentPlanNoteResponse]
    count: int


# Cost Estimate Schemas
class CostEstimateRequest(BaseModel):
    """Schema for cost estimate request"""
    procedures: List[TreatmentProcedureCreate]
    patient_insurance_id: Optional[uuid_lib.UUID] = None


class CostEstimateResponse(BaseModel):
    """Schema for cost estimate response (L-6 FIX: money as Decimal)"""
    total_fee: Decimal
    total_insurance_estimate: Decimal
    total_patient_responsibility: Decimal
    procedure_estimates: List[Dict[str, Any]]
    insurance_details: Optional[Dict[str, Any]] = None


# Acceptance Tracking Schemas
class PlanAcceptanceRequest(BaseModel):
    """Schema for plan acceptance request"""
    acceptance_method: str = Field(..., min_length=1)
    acceptance_notes: Optional[str] = None
    accepted_procedures: Optional[List[uuid_lib.UUID]] = None  # Specific procedures accepted


class PlanAcceptanceResponse(BaseModel):
    """Schema for plan acceptance response (L-6 FIX: money as Decimal)"""
    plan_id: uuid_lib.UUID
    status: TreatmentPlanStatus
    accepted_date: date
    acceptance_method: str
    total_accepted_cost: Decimal
    accepted_procedures: List[uuid_lib.UUID]


# Visual Builder Schemas
class VisualBuilderConfig(BaseModel):
    """Schema for visual builder configuration"""
    layout: str = "grid"  # grid, list, timeline
    show_tooth_chart: bool = True
    show_cost_breakdown: bool = True
    show_insurance_coverage: bool = True
    show_timeline: bool = True
    color_scheme: str = "professional"  # professional, clinical, patient_friendly
    grouping: str = "phase"  # phase, priority, procedure_type


class ToothChartPosition(BaseModel):
    """Schema for tooth chart position"""
    tooth_number: str
    x: int
    y: int
    rotation: int = 0
    scale: float = 1.0


class VisualBuilderResponse(BaseModel):
    """Schema for visual builder response"""
    plan_id: uuid_lib.UUID
    config: VisualBuilderConfig
    tooth_positions: List[ToothChartPosition]
    visual_data: Dict[str, Any]