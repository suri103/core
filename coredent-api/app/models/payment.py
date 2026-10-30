"""
Payment Processing Models
Credit card processing, recurring billing, payment terminals
SECURITY: API keys are encrypted using Fernet encryption
"""

from sqlalchemy import Column, String, DateTime, ForeignKey, Enum, Text, Boolean, Numeric, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.core.base import Base
from app.core.encryption import encrypt_value, decrypt_value


class PaymentMethod(str, enum.Enum):
    """Payment methods"""
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    CASH = "cash"
    CHECK = "check"
    BANK_TRANSFER = "bank_transfer"
    INSURANCE = "insurance"
    OTHER = "other"


class PaymentStatus(str, enum.Enum):
    """Payment status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"
    VOIDED = "voided"
    CANCELLED = "cancelled"


class CardType(str, enum.Enum):
    """Card types"""
    VISA = "visa"
    MASTERCARD = "mastercard"
    AMEX = "amex"
    DISCOVER = "discover"
    OTHER = "other"


class RecurringBillingStatus(str, enum.Enum):
    """Recurring billing status"""
    ACTIVE = "active"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"


class PaymentCard(Base):
    """Saved payment card model"""
    __tablename__ = "payment_cards"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)

    # Card Information (encrypted in production)
    card_last_four = Column(String(4), nullable=False)  # Last 4 digits
    card_type = Column(Enum(CardType))
    expiration_month = Column(String(2))
    expiration_year = Column(String(4))

    # Token from payment processor
    processor_token = Column(String(255))  # Token from Stripe, etc.
    processor_customer_id = Column(String(255))

    # Cardholder Info
    cardholder_name = Column(String(255))

    # Status
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    # Metadata
    nickname = Column(String(100))  # e.g., "Personal Visa", "Business Card"
    brand = Column(String(50))  # Card brand

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    practice = relationship("Practice", back_populates="payment_cards")
    patient = relationship("Patient", back_populates="payment_cards")

    def __repr__(self):
        return f"<PaymentCard {self.card_type} ending in {self.card_last_four}>"


class RecurringBilling(Base):
    """Recurring billing/subscription model"""
    __tablename__ = "recurring_billing"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    payment_card_id = Column(UUID(as_uuid=True), ForeignKey("payment_cards.id"))

    # Subscription Details
    subscription_name = Column(String(255), nullable=False)
    description = Column(Text)

    # Billing Schedule
    billing_frequency = Column(String(20), nullable=False)  # weekly, monthly, quarterly, yearly
    billing_day = Column(Integer)  # Day of month for billing

    # Amount
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="USD")

    # Status
    status = Column(Enum(RecurringBillingStatus), default=RecurringBillingStatus.ACTIVE)

    # Dates
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True))
    next_billing_date = Column(DateTime(timezone=True))
    last_billing_date = Column(DateTime(timezone=True))

    # Processor Info
    processor_subscription_id = Column(String(255))

    # Counters
    total_billed = Column(Integer, default=0)
    failed_attempts = Column(Integer, default=0)

    # Auto-charge
    auto_retry = Column(Boolean, default=True)
    retry_attempts = Column(Integer, default=3)

    # Cancel Info
    cancelled_at = Column(DateTime(timezone=True))
    cancellation_reason = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    practice = relationship("Practice", back_populates="recurring_billing")
    patient = relationship("Patient")
    payment_card = relationship("PaymentCard")
    payments = relationship("PaymentTransaction", back_populates="recurring_billing")

    def __repr__(self):
        return f"<RecurringBilling {self.subscription_name} - {self.status}>"


class PaymentTransaction(Base):
    """Payment transaction model"""
    __tablename__ = "payment_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id"))
    payment_card_id = Column(UUID(as_uuid=True), ForeignKey("payment_cards.id"))
    recurring_billing_id = Column(UUID(as_uuid=True), ForeignKey("recurring_billing.id"))
    # M5 FIX: link to the invoice-ledger Payment this processor transaction
    # corresponds to. Nullable: manual ledger entries (cash/check/UPI) have no
    # processor transaction, and legacy rows predate the link. The link is
    # resolved from Payment.transaction_id == processor_transaction_id.
    payment_id = Column(
        UUID(as_uuid=True), ForeignKey("payments.id", name="fk_payment_transactions_payment_id"), nullable=True, index=True
    )

    # Transaction Details
    transaction_type = Column(String(20), nullable=False)  # charge, refund, void, capture
    payment_method = Column(Enum(PaymentMethod), nullable=False)

    # Amount
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="USD")
    tip_amount = Column(Numeric(10, 2), default=0)
    total_amount = Column(Numeric(10, 2), nullable=False)

    # Status
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)

    # Processor Info
    # C-01 FIX: unique. This column is the idempotency key for processor
    # callbacks; without uniqueness a webhook lookup could match — and then
    # mutate — the wrong ledger row, and concurrent deliveries could each
    # insert their own row for one real payment.
    processor_transaction_id = Column(String(255), unique=True, index=True)
    processor_response_code = Column(String(20))
    processor_response_message = Column(Text)
    authorization_code = Column(String(50))

    # Card Info (for record)
    card_last_four = Column(String(4))
    card_type = Column(Enum(CardType))

    # Terminal Info
    terminal_id = Column(String(100))
    terminal_name = Column(String(255))
    terminal_location = Column(String(255))

    # IP Address
    ip_address = Column(String(45))

    # Timestamps
    processed_at = Column(DateTime(timezone=True))

    # Error Info
    error_code = Column(String(20))
    error_message = Column(Text)

    # Refund Info
    refunded_amount = Column(Numeric(10, 2), default=0)
    refund_reason = Column(Text)

    # Notes
    notes = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    practice = relationship("Practice", back_populates="payment_transactions")
    patient = relationship("Patient")
    invoice = relationship("Invoice")
    payment_card = relationship("PaymentCard")
    recurring_billing = relationship("RecurringBilling", back_populates="payments")
    payment = relationship("Payment")

    def __repr__(self):
        return f"<PaymentTransaction {self.id} - {self.status}>"


class PaymentTerminal(Base):
    """Payment terminal model"""
    __tablename__ = "payment_terminals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False)

    # Terminal Info
    name = Column(String(255), nullable=False)
    terminal_type = Column(String(50))  # card_present, card_not_present
    provider = Column(String(50))  # stripe, square, clover, etc.

    # Connection
    is_connected = Column(Boolean, default=False)
    last_connected_at = Column(DateTime(timezone=True))

    # Settings
    is_default = Column(Boolean, default=False)
    is_enabled = Column(Boolean, default=True)

    # Location
    location = Column(String(255))  # Front desk, Operatory 1, etc.

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    practice = relationship("Practice", back_populates="payment_terminals")

    def __repr__(self):
        return f"<PaymentTerminal {self.name}>"


class PaymentSettings(Base):
    """Payment settings for practice - with encrypted API keys"""
    __tablename__ = "payment_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    practice_id = Column(UUID(as_uuid=True), ForeignKey("practices.id"), nullable=False, unique=True)

    # Processor Settings
    stripe_enabled = Column(Boolean, default=False)
    stripe_publishable_key = Column(String(255))

    # SECURITY: Encrypted fields - stored with underscore prefix, accessed via properties
    _stripe_secret_key = Column(String(255), name="stripe_secret_key")
    _stripe_webhook_secret = Column(String(255), name="stripe_webhook_secret")
    _square_access_token = Column(String(255), name="square_access_token")
    _clover_api_key = Column(String(255), name="clover_api_key")

    square_enabled = Column(Boolean, default=False)
    square_location_id = Column(String(100))

    clover_enabled = Column(Boolean, default=False)
    clover_merchant_id = Column(String(100))

    # Default Settings
    default_payment_terminal_id = Column(UUID(as_uuid=True), ForeignKey("payment_terminals.id"))
    auto_capture = Column(Boolean, default=True)
    require_zip_code = Column(Boolean, default=True)

    # Receipt Settings
    send_receipt_email = Column(Boolean, default=True)
    send_receipt_sms = Column(Boolean, default=False)

    # Tip Settings
    enable_tips = Column(Boolean, default=True)
    suggested_tip_percentages = Column(String(50))  # JSON array

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    practice = relationship("Practice", back_populates="payment_settings")
    default_terminal = relationship("PaymentTerminal")

    # Encrypted field accessors
    @property
    def stripe_secret_key(self) -> str:
        """Get decrypted stripe secret key"""
        return decrypt_value(self._stripe_secret_key) if self._stripe_secret_key else ""

    @stripe_secret_key.setter
    def stripe_secret_key(self, value: str):
        """Set stripe secret key (encrypts automatically)"""
        self._stripe_secret_key = encrypt_value(value) if value else None

    @property
    def stripe_webhook_secret(self) -> str:
        """Get decrypted stripe webhook secret"""
        return decrypt_value(self._stripe_webhook_secret) if self._stripe_webhook_secret else ""

    @stripe_webhook_secret.setter
    def stripe_webhook_secret(self, value: str):
        """Set stripe webhook secret (encrypts automatically)"""
        self._stripe_webhook_secret = encrypt_value(value) if value else None

    @property
    def square_access_token(self) -> str:
        """Get decrypted square access token"""
        return decrypt_value(self._square_access_token) if self._square_access_token else ""

    @square_access_token.setter
    def square_access_token(self, value: str):
        """Set square access token (encrypts automatically)"""
        self._square_access_token = encrypt_value(value) if value else None

    @property
    def clover_api_key(self) -> str:
        """Get decrypted clover API key"""
        return decrypt_value(self._clover_api_key) if self._clover_api_key else ""

    @clover_api_key.setter
    def clover_api_key(self, value: str):
        """Set clover API key (encrypts automatically)"""
        self._clover_api_key = encrypt_value(value) if value else None

    def __repr__(self):
        return f"<PaymentSettings for Practice {self.practice_id}>"
