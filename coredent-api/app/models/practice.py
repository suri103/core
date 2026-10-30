"""
Practice Model
Represents dental practices/clinics
"""

from sqlalchemy import (
    Column,
    String,
    DateTime,
    JSON,
    ForeignKey,
    Boolean,
    Integer,
    Numeric,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.core.base import Base


class PracticeGroup(Base):
    """Enterprise-level practice group/DSO model"""
    __tablename__ = "practice_groups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    address_street = Column(String(255))
    address_city = Column(String(100))
    address_state = Column(String(100))
    address_zip = Column(String(20))
    country = Column(String(2), default="US")
    logo_url = Column(String)
    settings = Column(JSON, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    practices = relationship("Practice", back_populates="group")


class Practice(Base):
    """Practice/Clinic model"""
    __tablename__ = "practices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    public_slug = Column(String(100), unique=True, nullable=False)
    group_id = Column(UUID(as_uuid=True), ForeignKey("practice_groups.id"), nullable=True)
    email = Column(String(255))
    phone = Column(String(20))
    inbound_phone_number = Column(String(20), nullable=True, index=True)
    npi = Column(String(20), nullable=True)  # Service facility NPI (EDI claims)
    address = Column(String(255))  # Combined address field
    address_street = Column(String(255))
    address_city = Column(String(100))
    address_state = Column(String(100)) # Expanded for Global compatibility
    address_zip = Column(String(20))
    city = Column(String(100))  # Alias for address_city
    state = Column(String(100))  # Alias for address_state
    zip_code = Column(String(20))  # Alias for address_zip
    country = Column(String(2), default="US") # Region Switch: US, IN, etc.
    timezone = Column(String(50), default="America/New_York")
    currency = Column(String(3), default="USD")
    website = Column(String(255))
    logo_url = Column(String)
    settings = Column(JSON, default={})

    # Billing preferences
    # Percent, 0..100 (see the units note in billing.py). Numeric(5, 2) to match
    # practices.tax_rate as created by bb372b5f2d4a_baseline_schema.py.
    #
    # This was declared JSON, which no migration ever produced. SQLite tolerates
    # the mismatch, so the whole suite passed locally; PostgreSQL rejects the
    # insert with
    #   DatatypeMismatchError: column "tax_rate" is of type numeric but
    #   expression is of type json
    # and every consumer already treats it as a number - billing.py,
    # settings.py and tasks.py all do Decimal(str(practice.tax_rate)) - and
    # Invoice.tax_rate is Numeric(8, 6). The "float or dict" comment described a
    # capability nothing implemented.
    tax_rate = Column(Numeric(5, 2), default=0.0)
    invoice_prefix = Column(String(10), default="INV")
    payment_terms = Column(JSON, default=30)  # Days
    late_fee_percentage = Column(JSON, default=0.0)
    accepted_payment_methods = Column(JSON, default=["cash", "card", "check"])
    auto_send_invoices = Column(Boolean, default=False)
    auto_send_reminders = Column(Boolean, default=True)
    reminder_days_before = Column(JSON, default=3)

    # Working hours and appointment configuration
    working_hours = Column(JSON, default={})
    appointment_types = Column(JSON, default=[])  # Stored as JSON for flexibility
    chairs = Column(JSON, default=[])  # Stored as JSON for flexibility

    is_active = Column(Boolean, default=True)
    # Data-retention override (docs/DATA_RETENTION_POLICY.md § 1 / § 6).
    # NULL = use the platform default (RETENTION_ANONYMIZED_PURGE_YEARS, 7).
    # A practice in a jurisdiction with a longer statutory minimum (e.g. some
    # US states, or a 10-year country rule) sets a larger value; the hard-purge
    # eligibility check takes max(practice value, platform default) so a
    # practice can only EXTEND retention, never shorten it below the floor.
    retention_years = Column(Integer, nullable=True)
    # Jurisdiction for the retention preset picker (e.g. 'CA', 'USA').
    # NULL = none picked. Purely a UI convenience; purge enforcement only
    # ever reads retention_years (with the platform floor via max()).
    jurisdiction = Column(String(16), nullable=True)
    # Minor-record retention window (docs/DATA_RETENTION_POLICY.md R1).
    # NULL = platform defaults (18 / 7). A minor record is not purged before
    # date_of_birth + majority_age + minor_retention_years.
    majority_age = Column(Integer, nullable=True)
    minor_retention_years = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    group = relationship("PracticeGroup", back_populates="practices")
    users = relationship("User", back_populates="practice")
    patients = relationship("Patient", back_populates="practice")
    appointments = relationship("Appointment", back_populates="practice")
    chairs = relationship("Chair", back_populates="practice")
    appointment_types = relationship("AppointmentType", back_populates="practice")
    invoices = relationship("Invoice", back_populates="practice")
    insurance_claims = relationship("InsuranceClaim", back_populates="practice")
    images = relationship("PatientImage", back_populates="practice")
    treatment_plans = relationship("TreatmentPlan", back_populates="practice")
    booking_pages = relationship("BookingPage", back_populates="practice")
    online_bookings = relationship("OnlineBooking", back_populates="practice")
    waitlist_entries = relationship("WaitlistEntry", back_populates="practice")
    # New relationships for additional modules
    inventory_items = relationship("InventoryItem", back_populates="practice")
    suppliers = relationship("Supplier", back_populates="practice")
    purchase_orders = relationship("PurchaseOrder", back_populates="practice")
    labs = relationship("Lab", back_populates="practice")
    lab_cases = relationship("LabCase", back_populates="practice")
    lab_invoices = relationship("LabInvoice", back_populates="practice")
    referral_sources = relationship("ReferralSource1", back_populates="practice")
    referrals = relationship("Referral", back_populates="practice", foreign_keys="[Referral.practice_id]")
    referral_reports = relationship("ReferralReport", back_populates="practice")
    message_templates = relationship("MessageTemplate", back_populates="practice")
    patient_messages = relationship("PatientMessage", back_populates="practice")
    reminder_schedules = relationship("ReminderSchedule", back_populates="practice")
    conversations = relationship("Conversation", back_populates="practice")
    document_templates = relationship("DocumentTemplate", back_populates="practice")
    documents = relationship("Document", back_populates="practice")
    campaigns = relationship("Campaign", back_populates="practice")
    marketing_templates = relationship("MarketingTemplate", back_populates="practice")
    newsletter_subscriptions = relationship("NewsletterSubscription", back_populates="practice")

    # Payment / Billing Relationships
    payment_cards = relationship("PaymentCard", back_populates="practice")
    payment_transactions = relationship("PaymentTransaction", back_populates="practice")
    recurring_billing = relationship("RecurringBilling", back_populates="practice")
    payment_terminals = relationship("PaymentTerminal", back_populates="practice")
    payment_settings = relationship("PaymentSettings", back_populates="practice")

    # Subscription Relationships
    subscription_plans = relationship("SubscriptionPlan", back_populates="practice")
    subscriptions = relationship("Subscription", back_populates="practice")

    def __repr__(self):
        return f"<Practice {self.name}>"
