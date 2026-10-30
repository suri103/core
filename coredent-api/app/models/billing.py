"""
Billing Models
Invoices and payments
"""

from sqlalchemy import Column, String, DateTime, ForeignKey, Enum, Numeric, Date, JSON, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from decimal import Decimal
import uuid
import enum

from app.core.base import Base


class InvoiceStatus(str, enum.Enum):
    """Invoice status"""
    DRAFT = "draft"
    PENDING = "pending"
    PAID = "paid"
    PARTIALLY_PAID = "partially_paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class PaymentMethod(str, enum.Enum):
    """Payment methods"""
    CASH = "cash"
    CARD = "card"
    CHECK = "check"
    INSURANCE = "insurance"
    UPI = "upi"  # Indian UPI payments
    OTHER = "other"


class PaymentStatus(str, enum.Enum):
    """Payment status"""
    COMPLETED = "completed"
    PENDING = "pending"
    FAILED = "failed"
    REFUNDED = "refunded"
    # 2026-09: partial refunds via POST /billing/payments/{id}/refund. The
    # separate payment-processing enum (payment.py) already had this member;
    # the billing ledger enum now mirrors it so a partially refunded manual
    # payment is representable on the ledger row itself.
    PARTIALLY_REFUNDED = "partially_refunded"


class PaymentPlanStatus(str, enum.Enum):
    """Payment plan status"""
    ACTIVE = "active"
    COMPLETED = "completed"
    DEFAULTED = "defaulted"
    CANCELLED = "cancelled"


class Invoice(Base):
    """Invoice model"""
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint('practice_id', 'invoice_number', name='uq_practice_invoice_number'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)

    invoice_number = Column(String(50), nullable=False, index=True)
    status = Column(Enum(InvoiceStatus), default=InvoiceStatus.PENDING)

    subtotal = Column(Numeric(10, 2), nullable=False)
    tax = Column(Numeric(10, 2), default=0)
    total = Column(Numeric(10, 2), nullable=False)
    # Fractional tax rate used to compute `tax` (e.g. 0.055), persisted so
    # later line-item edits can recompute the tax instead of zeroing it.
    tax_rate = Column(Numeric(8, 6), default=0)

    # GST fields (Indian compliance)
    gstin = Column(String(15))  # GST Identification Number
    gst_rate = Column(Numeric(5, 2), default=18.00)  # Default 18%
    cgst_amount = Column(Numeric(10, 2), default=0)
    sgst_amount = Column(Numeric(10, 2), default=0)
    igst_amount = Column(Numeric(10, 2), default=0)
    is_inter_state = Column(String(1), default="N")  # Y/N for inter-state

    # Line items stored as JSON
    # Structure: [{ description: "", quantity: 1, unit_price: 0, total: 0 }]
    line_items = Column(JSON, nullable=False)

    due_date = Column(Date)
    notes = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    practice = relationship("Practice", back_populates="invoices")
    patient = relationship("Patient", back_populates="invoices")
    payments = relationship("Payment", back_populates="invoice", cascade="all, delete-orphan")
    subscription = relationship("Subscription", back_populates="invoices", overlaps="latest_invoice")

    @property
    def amount_paid(self) -> Decimal:
        """Effective collected amount (Decimal; refunds subtract)."""
        paid = Decimal("0")
        for p in self.payments:
            # PARTIALLY_REFUNDED joined the set in 2026-09: a partial refund
            # still leaves net collected money on the ledger row, so it must
            # keep counting (net of refunded_amount) exactly like REFUNDED.
            if p.status in (
                PaymentStatus.COMPLETED,
                PaymentStatus.REFUNDED,
                PaymentStatus.PARTIALLY_REFUNDED,
            ):
                refunded = p.refunded_amount if p.refunded_amount is not None else Decimal("0")
                paid += Decimal(str(p.amount)) - Decimal(str(refunded))
        return paid

    @property
    def balance_due(self) -> Decimal:
        """Calculate remaining balance"""
        return Decimal(str(self.total)) - self.amount_paid

    @property
    def patient_name(self) -> str:
        """Tenant-authorized patient display name exposed by billing responses."""
        if self.patient is None:
            return ""
        return " ".join(
            part for part in (self.patient.first_name, self.patient.last_name) if part
        )

    @property
    def patient_email(self) -> str | None:
        return self.patient.email if self.patient is not None else None

    @property
    def patient_phone(self) -> str | None:
        return self.patient.phone if self.patient is not None else None

    def __repr__(self):
        return f"<Invoice {self.invoice_number} - {self.status}>"


class Payment(Base):
    """Payment model"""
    __tablename__ = "payments"
    __table_args__ = (
        # L-1 FIX: scope transaction_id per practice. The previous global
        # unique let one tenant probe another's reference (409 vs 200 oracle)
        # and coupled tenants. Replay lookups filter by practice_id.
        UniqueConstraint(
            "practice_id",
            "transaction_id",
            name="uq_payment_practice_transaction",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    # Tenant scoping (added with the payment_transactions FK migration): every
    # payment belongs to exactly one practice, backfilled from its invoice.
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)

    amount = Column(Numeric(10, 2), nullable=False)
    refunded_amount = Column(Numeric(10, 2), default=0)
    payment_method = Column(Enum(PaymentMethod), nullable=False)
    # One row per gateway transaction per practice: the composite unique
    # constraint is the race guard for concurrent webhook deliveries
    # (check-then-insert alone let duplicates through and double-counted
    # invoice.amount_paid).
    transaction_id = Column(String(255), index=True)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.COMPLETED)
    notes = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    invoice = relationship("Invoice", back_populates="payments")
    patient = relationship("Patient", back_populates="payments")

    def __repr__(self):
        return f"<Payment {self.id} - ${self.amount}>"


class PaymentPlan(Base):
    """Installment-based payment plan"""
    __tablename__ = "payment_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=True)

    status = Column(Enum(PaymentPlanStatus), default=PaymentPlanStatus.ACTIVE)
    total_amount = Column(Numeric(10, 2), nullable=False)
    initial_deposit = Column(Numeric(10, 2), default=0)
    interest_rate = Column(Numeric(5, 2), default=0)  # Annual percentage rate

    start_date = Column(Date, nullable=False)
    notes = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    practice = relationship("Practice")
    patient = relationship("Patient")
    invoice = relationship("Invoice")
    installments = relationship("PaymentPlanInstallment", back_populates="plan", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<PaymentPlan {self.id} - {self.status}>"


class InstallmentStatus(str, enum.Enum):
    """Installment status"""
    SCHEDULED = "scheduled"
    PAID = "paid"
    OVERDUE = "overdue"


class PaymentPlanInstallment(Base):
    """Individual installment in a payment plan"""
    __tablename__ = "payment_plan_installments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("payment_plans.id"), nullable=False)

    amount = Column(Numeric(10, 2), nullable=False)
    due_date = Column(Date, nullable=False)
    paid_at = Column(DateTime(timezone=True))
    status = Column(Enum(InstallmentStatus), default=InstallmentStatus.SCHEDULED)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    plan = relationship("PaymentPlan", back_populates="installments")

    def __repr__(self):
        return f"<Installment {self.id} - ${self.amount} - {self.status}>"
