"""
Advanced Subscription Schemas
Pydantic models for subscription operations
"""

from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from decimal import Decimal


# ======================= Subscription Plan Schemas =======================

class SubscriptionPlanBase(BaseModel):
    """Base subscription plan schema"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    short_description: Optional[str] = Field(None, max_length=100)
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    interval: str  # weekly, monthly, quarterly, semi_annual, annual
    trial_period_days: int = Field(default=0, ge=0)
    features: Optional[List[str]] = None
    limits: Optional[Dict[str, Any]] = None
    is_usage_based: bool = False
    usage_meter_name: Optional[str] = None
    usage_unit_label: Optional[str] = None
    included_usage: Decimal = Field(default=0, ge=0)
    overage_rate: Decimal = Field(default=0, ge=0)
    is_recommended: bool = False
    sort_order: int = 0


class SubscriptionPlanCreate(SubscriptionPlanBase):
    """Schema for creating subscription plans"""
    stripe_price_id: Optional[str] = None
    stripe_product_id: Optional[str] = None
    razorpay_plan_id: Optional[str] = None


class SubscriptionPlanUpdate(BaseModel):
    """Schema for updating subscription plans"""
    name: Optional[str] = None
    description: Optional[str] = None
    short_description: Optional[str] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    interval: Optional[str] = None
    trial_period_days: Optional[int] = None
    features: Optional[List[str]] = None
    limits: Optional[Dict[str, Any]] = None
    is_usage_based: Optional[bool] = None
    usage_meter_name: Optional[str] = None
    usage_unit_label: Optional[str] = None
    included_usage: Optional[Decimal] = None
    overage_rate: Optional[Decimal] = None
    is_active: Optional[bool] = None
    is_recommended: Optional[bool] = None
    sort_order: Optional[int] = None
    stripe_price_id: Optional[str] = None


class SubscriptionPlanResponse(SubscriptionPlanBase):
    """API response for subscription plans"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    is_active: bool
    stripe_price_id: Optional[str] = None
    razorpay_plan_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ======================= Subscription Schemas =======================

class SubscriptionCreate(BaseModel):
    """Schema for creating a subscription"""
    plan_id: UUID
    patient_id: Optional[UUID] = None
    payment_card_id: Optional[UUID] = None
    trial_period_days: Optional[int] = None
    idempotency_key: Optional[str] = Field(None, min_length=16, max_length=255)
    proration_behavior: str = "create_prorations"  # create_prorations, always_invoice, none
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("proration_behavior")
    @classmethod
    def validate_proration(cls, v: str) -> str:
        allowed = ["create_prorations", "always_invoice", "none"]
        if v not in allowed:
            raise ValueError(f"proration_behavior must be one of {allowed}")
        return v


class SubscriptionPause(BaseModel):
    """Schema for pausing a subscription"""
    paused_until: Optional[datetime] = None  # None = indefinitely
    reason: Optional[str] = None


class SubscriptionResume(BaseModel):
    """Schema for resuming a paused subscription"""
    resume_at_period_end: bool = False


class SubscriptionCancellation(BaseModel):
    """Schema for canceling a subscription"""
    cancel_at_period_end: bool = True  # Default: allow access until period ends
    reason: Optional[str] = None
    feedback: Optional[str] = None


class SubscriptionChangePlan(BaseModel):
    """Schema for changing subscription plan"""
    new_plan_id: UUID
    proration_behavior: str = "create_prorations"

    # FIX: A bad proration_behavior previously flowed straight into
    # ProrationBehavior(...) in subscription_service.change_plan and raised an
    # uncaught ValueError -> HTTP 500. Validate it here, mirroring
    # SubscriptionCreate, so the client gets a 422 instead.
    @field_validator("proration_behavior")
    @classmethod
    def validate_proration(cls, v: str) -> str:
        allowed = ["create_prorations", "always_invoice", "none"]
        if v not in allowed:
            raise ValueError(f"proration_behavior must be one of {allowed}")
        return v


class SubscriptionUpdatePayment(BaseModel):
    """Schema for updating payment method"""
    payment_card_id: UUID


class SubscriptionProratePreview(BaseModel):
    """Schema for previewing proration"""
    new_plan_id: UUID
    proration_behavior: str = "create_prorations"


class SubscriptionResponse(BaseModel):
    """API response for subscriptions"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    practice_id: UUID
    patient_id: Optional[UUID] = None
    plan_id: UUID
    status: str
    interval: str
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    next_billing_date: Optional[datetime] = None
    trial_start: Optional[datetime] = None
    trial_end: Optional[datetime] = None
    trial_used: bool = False
    cancel_at_period_end: bool = False
    canceled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    paused_at: Optional[datetime] = None
    paused_until: Optional[datetime] = None
    current_usage: Decimal = 0
    current_overage: Decimal = 0
    dunning_retry_count: int = 0
    last_payment_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ======================= Usage Schemas =======================

class UsageRecordCreate(BaseModel):
    """Schema for recording usage"""
    quantity: Decimal = Field(..., ge=0, decimal_places=2)
    description: Optional[str] = Field(None, max_length=500)
    metadata: Optional[Dict[str, Any]] = None


class UsageRecordResponse(BaseModel):
    """API response for usage records"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    subscription_id: UUID
    quantity: Decimal
    timestamp: datetime
    description: Optional[str] = None


class UsageSummary(BaseModel):
    """Usage summary for current billing period"""
    model_config = ConfigDict(from_attributes=True)

    meter_name: str
    unit_label: str
    included_quantity: Decimal
    used_quantity: Decimal
    overage_quantity: Decimal
    overage_rate: Decimal
    overage_cost: Decimal


class UsageResponse(BaseModel):
    """Usage response with summary"""
    subscription_id: UUID
    period_start: datetime
    period_end: datetime
    records: List[UsageRecordResponse]
    summaries: List[UsageSummary]


# ======================= Dunning Schemas =======================

class DunningConfig(BaseModel):
    """Configure dunning retry settings"""
    max_retries: int = Field(default=4, ge=1, le=10)
    retry_days: List[int] = Field(  # Days to retry after failure
        default=[0, 3, 7, 14],  # Attempt on day 0, 3, 7, 14
        description="Days relative to failed payment to retry"
    )


class DunningEventResponse(BaseModel):
    """API response for dunning events"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    attempt_number: int
    action: str
    result: Optional[str] = None
    error_message: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    created_at: datetime


# ======================= Cancellation Survey Schema =======================

class CancellationSurveyData(BaseModel):
    """Schema for cancellation survey"""
    reason_code: str
    # Reasons: too_expensive, not_using, missing_features,
    #          competitor, customer_service, hard_to_use, other
    additional_feedback: Optional[str] = None
    likelihood_to_return: Optional[int] = Field(None, ge=1, le=10)


# ======================= Subscription Dashboard Schema =======================

class SubscriptionStats(BaseModel):
    """Subscription statistics for dashboard"""
    total_active: int
    total_trials: int
    total_past_due: int
    total_canceled_this_month: int
    mrr: Decimal  # Monthly Recurring Revenue
    mrr_growth_percent: float
    churn_rate: float  # Monthly churn rate
    trial_conversion_rate: float
    average_lifetime_days: float


class SubscriptionRevenue(BaseModel):
    """Subscription revenue breakdown"""
    subscription_revenue: Decimal
    overage_revenue: Decimal
    trial_revenue: Decimal  # Revenue from converted trials
    refunded: Decimal
    net_revenue: Decimal


# ======================= Trial Schema =======================

class TrialResponse(BaseModel):
    """Info about a trial"""
    model_config = ConfigDict(from_attributes=True)

    subscription_id: UUID
    plan_name: str
    trial_start: datetime
    trial_end: datetime
    days_remaining: int
    days_used: int
    used: bool


# ======================= List Response Schemas =======================

class SubscriptionPlanList(BaseModel):
    """List of subscription plans"""
    plans: List[SubscriptionPlanResponse]
    total: int


class SubscriptionList(BaseModel):
    """Paginated subscription list"""
    subscriptions: List[SubscriptionResponse]
    total: int
    page: int
    limit: int


class DunningEventList(BaseModel):
    """List of dunning events"""
    events: List[DunningEventResponse]
    total: int