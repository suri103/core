"""
Billing Schemas
Pydantic models for billing data validation
"""

from datetime import datetime, date
from typing import Any, Optional, List
from pydantic import BaseModel, Field, field_validator
from uuid import UUID
from decimal import Decimal

from app.models.billing import InvoiceStatus, PaymentMethod, PaymentStatus, PaymentPlanStatus


# M-02 FIX: money fields are persisted to Numeric(10, 2). The API previously
# accepted an arbitrary-scale Decimal, so a request for 0.004 passed
# validation (it is > 0) and then rounded to 0.00 on write -- a payment that
# validated as non-zero but recorded nothing. Money inputs are now pinned to
# the storage precision and out-of-scale values are rejected, not rounded.
MONEY_MAX_DIGITS = 10
MONEY_DECIMAL_PLACES = 2


def MoneyField(**kwargs) -> Any:  # noqa: N802 - factory reads as a type
    """Decimal field constrained to the Numeric(10, 2) storage precision."""
    kwargs.setdefault("max_digits", MONEY_MAX_DIGITS)
    kwargs.setdefault("decimal_places", MONEY_DECIMAL_PLACES)
    return Field(**kwargs)


# Line Item Schemas

class LineItemBase(BaseModel):
    """Base line item schema"""
    description: str = Field(..., min_length=1, max_length=500)
    quantity: int = Field(..., gt=0, le=100_000)
    unit_price: Decimal = MoneyField(ge=0)
    total: Decimal = MoneyField(ge=0)

    @field_validator('total')
    @classmethod
    def validate_total(cls, v, info):
        # L12 FIX: Pydantic v2 field_validator (the v1 @validator compat
        # shim silently stops validating if v1 support is dropped).
        quantity = info.data.get('quantity')
        unit_price = info.data.get('unit_price')
        if quantity is not None and unit_price is not None:
            expected_total = quantity * unit_price
            if v != expected_total:
                raise ValueError(f'total must equal quantity * unit_price ({expected_total})')
        return v


class LineItemCreate(LineItemBase):
    """Schema for creating line items"""
    pass


# Invoice Schemas

class InvoiceBase(BaseModel):
    """Base invoice schema"""
    patient_id: UUID
    status: Optional[InvoiceStatus] = InvoiceStatus.PENDING
    line_items: List[LineItemCreate] = Field(..., min_length=1, max_length=500)
    tax_rate: Optional[Decimal] = Field(Decimal('0.0'), ge=0, le=1, max_digits=8, decimal_places=6)
    due_date: Optional[date] = None
    notes: Optional[str] = None


class InvoiceCreate(InvoiceBase):
    """Schema for creating invoices"""
    pass


class InvoiceUpdate(BaseModel):
    """Schema for updating invoices"""
    status: Optional[InvoiceStatus] = None
    line_items: Optional[List[LineItemCreate]] = Field(None, min_length=1, max_length=500)
    tax_rate: Optional[Decimal] = Field(None, ge=0, le=1, max_digits=8, decimal_places=6)
    due_date: Optional[date] = None
    notes: Optional[str] = None


class InvoiceResponse(InvoiceBase):
    """Schema for invoice responses"""
    id: UUID
    practice_id: UUID
    patient_name: str
    patient_email: Optional[str] = None
    patient_phone: Optional[str] = None
    invoice_number: str
    subtotal: Decimal
    tax: Decimal
    total: Decimal
    created_at: datetime
    updated_at: datetime
    amount_paid: Decimal
    balance_due: Decimal
    payments: List["PaymentResponse"] = Field(default_factory=list)

    class Config:
        from_attributes = True


class InvoiceListResponse(BaseModel):
    """Schema for a bounded page of invoices."""
    invoices: List[InvoiceResponse]
    # ``count`` retains its historic meaning (items in this response) while
    # the additive fields let clients page without inferring an end state.
    count: int
    total: Optional[int] = None
    limit: Optional[int] = None
    offset: Optional[int] = None
    next_offset: Optional[int] = None


# Payment Schemas

class PaymentBase(BaseModel):
    """Fields shared by payment requests and responses."""
    invoice_id: UUID
    patient_id: UUID
    amount: Decimal = MoneyField(gt=0)
    payment_method: PaymentMethod
    transaction_id: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None


# M-01 FIX: statuses a client may assign when recording a payment.
# REFUNDED is excluded: ``Invoice.amount_paid`` counts REFUNDED rows (net of
# ``refunded_amount``, which defaults to 0), so a client-created REFUNDED
# payment used to increase the invoice's paid total with no refund ledger
# behind it. FAILED is excluded because a failed payment is an outcome
# reported by a processor, not something a user records by hand. Refunds go
# through the refund path, which writes ``refunded_amount`` atomically.
CLIENT_SETTABLE_PAYMENT_STATUSES: frozenset[PaymentStatus] = frozenset(
    {PaymentStatus.COMPLETED, PaymentStatus.PENDING}
)


class PaymentCreate(PaymentBase):
    """Schema for creating payments."""
    status: PaymentStatus = PaymentStatus.COMPLETED

    @field_validator("status")
    @classmethod
    def _reject_derived_status(cls, v: PaymentStatus) -> PaymentStatus:
        if v not in CLIENT_SETTABLE_PAYMENT_STATUSES:
            allowed = ", ".join(sorted(s.value for s in CLIENT_SETTABLE_PAYMENT_STATUSES))
            raise ValueError(
                f"status '{v.value}' cannot be set when recording a payment "
                f"(allowed: {allowed}). Refunds and failures are recorded by "
                "the refund and processor-callback paths."
            )
        return v


class PaymentResponse(PaymentBase):
    """Schema for payment responses"""
    id: UUID
    status: PaymentStatus
    refunded_amount: Decimal = Decimal('0')
    created_at: datetime

    class Config:
        from_attributes = True


# Resolve the embedded payment response after PaymentResponse is declared.
InvoiceResponse.model_rebuild()


class PaymentListResponse(BaseModel):
    """Schema for a bounded page of payments."""
    payments: List[PaymentResponse]
    count: int
    total: Optional[int] = None
    limit: Optional[int] = None
    offset: Optional[int] = None
    next_offset: Optional[int] = None


# Summary Schemas

class StatusBreakdown(BaseModel):
    """Schema for status breakdown"""
    status: InvoiceStatus
    count: int
    amount: float


class BillingSummary(BaseModel):
    """Schema for billing summary"""
    total_invoices: int
    pending_invoices: int = 0
    total_revenue: float
    total_tax: float
    total_payments: int
    total_collected: float
    outstanding_balance: float
    status_breakdown: List[StatusBreakdown]


# Payment Plan Schemas

class PaymentPlanCreate(BaseModel):
    """Schema for creating a payment plan with installment validation"""
    patient_id: UUID
    invoice_id: UUID = Field(..., description="Invoice associated with payment plan")
    total_amount: Decimal = MoneyField(gt=0)
    initial_deposit: Decimal = MoneyField(default=Decimal('0'), ge=0)
    months: int = Field(12, ge=1, le=60)
    notes: Optional[str] = None

    @field_validator('initial_deposit')
    @classmethod
    def _deposit_not_gt_total(cls, v, info):
        # L12 FIX: Pydantic v2 field_validator (see LineItemBase).
        total = info.data.get('total_amount')
        if total is not None and v > total:
            raise ValueError('initial_deposit cannot exceed total_amount')
        return v


class PaymentPlanInstallmentPay(BaseModel):
    """Schema for paying a single installment (M3).

    ``amount`` is retained for client compatibility but, when supplied, must
    equal the stored installment amount exactly. The server always uses the
    deterministic ``PLAN-{installment_id}`` transaction reference; callers
    may only echo that value, never substitute an arbitrary reference.
    """
    payment_method: PaymentMethod
    amount: Optional[Decimal] = MoneyField(default=None, gt=0)
    transaction_id: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None


class PaymentPlanInstallmentResponse(BaseModel):
    """Schema for payment plan installment responses"""
    id: UUID
    plan_id: UUID
    amount: Decimal
    due_date: date
    paid_at: Optional[datetime] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class PaymentPlanResponse(BaseModel):
    """Schema for payment plan responses"""
    id: UUID
    practice_id: UUID
    patient_id: UUID
    invoice_id: Optional[UUID] = None
    status: PaymentPlanStatus
    total_amount: Decimal
    initial_deposit: Decimal
    interest_rate: Decimal = Decimal('0')
    start_date: date
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    installments: List[PaymentPlanInstallmentResponse] = []

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Refunds
# ---------------------------------------------------------------------------


class RefundCreate(BaseModel):
    """Request body for refunding a recorded payment."""
    amount: Decimal = MoneyField(gt=0, description="Amount to refund, in currency units")
    reason: Optional[str] = Field(None, max_length=500)


class RefundResponse(BaseModel):
    """Result of a refund: the updated payment ledger row."""
    payment_id: UUID
    invoice_id: UUID
    refunded_amount: Decimal
    remaining_refundable: Decimal
    payment_status: PaymentStatus
    invoice_status: InvoiceStatus
    message: str


class PaymentRefundDialogState(BaseModel):
    """Echoed server-side contract used by the frontend refund dialog."""
    max_refundable: Decimal
    payment_method: PaymentMethod
    currency: str = "USD"


class PaymentPlanListResponse(BaseModel):
    """Schema for a bounded page of payment plans."""
    payment_plans: List[PaymentPlanResponse]
    count: int
    total: Optional[int] = None
    limit: Optional[int] = None
    offset: Optional[int] = None
    next_offset: Optional[int] = None
