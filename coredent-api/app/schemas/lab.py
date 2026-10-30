"""
Lab Management Schemas
Pydantic models for lab invoice creation and payment recording.

Money fields are Decimal (never float) so totals and payments are exact to
the cent, matching the Numeric(10,2) columns on LabInvoice.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class LabInvoiceCreate(BaseModel):
    """Create a lab invoice.

    The backend computes ``total`` from the line totals (never trusts a
    client-supplied total) so the stored invoice always satisfies
    total = round(subtotal + tax + shipping - discount).
    """

    lab_id: UUID
    lab_case_id: Optional[UUID] = None
    due_date: Optional[datetime] = None
    subtotal: Decimal = Field(..., ge=0)
    tax: Decimal = Field(Decimal("0"), ge=0)
    shipping: Decimal = Field(Decimal("0"), ge=0)
    discount: Decimal = Field(Decimal("0"), ge=0)
    notes: Optional[str] = None
    terms: Optional[str] = None

    @model_validator(mode="after")
    def _discount_not_gt_chargeable(self) -> "LabInvoiceCreate":
        """Discount must never exceed the pre-discount base (subtotal + shipping)."""
        if self.discount > self.subtotal + self.shipping:
            raise ValueError("discount cannot exceed subtotal + shipping")
        return self


class LabInvoicePayRequest(BaseModel):
    """Record one idempotent payment against a lab invoice."""

    amount: Decimal = Field(..., gt=0, max_digits=10, decimal_places=2)
    transaction_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        pattern=r".*\S.*",
        description="Caller-stable idempotency key for this payment attempt",
    )
    payment_date: Optional[datetime] = None
    notes: Optional[str] = None
