"""
Settings Schemas
Pydantic models for settings endpoints
"""

from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class PracticeAddressUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    street: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    zipCode: Optional[str] = Field(None, max_length=20)
    country: Optional[str] = Field(None, min_length=2, max_length=2)


class PracticeSettingsUpdate(BaseModel):
    """Strict general-settings contract; unknown and invalid zones fail 422."""

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(None, min_length=2, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=30)
    website: Optional[str] = Field(None, max_length=500)
    logoUrl: Optional[str] = Field(None, max_length=500)
    timezone: Optional[str] = Field(None, min_length=1, max_length=100)
    currency: Optional[str] = Field(None, min_length=3, max_length=3)
    address: Optional[PracticeAddressUpdate] = None
    workingHours: Optional[Dict[str, Any]] = None
    # Data-retention override: NULL = platform default. Floor of 7 is NOT
    # enforced at the schema level (the service takes max(floor, value)), but
    # the sweep treats values < RETENTION_ANONYMIZED_PURGE_YEARS as no-op.
    retentionYears: Optional[int] = Field(None, ge=0, le=100)
    # Practice jurisdiction code ('CA', 'USA', ...). Validated against the
    # known preset universe server-side only by shape; unknown codes fall back
    # client-side. Max length allows future ISO-alpha-3 + region suffixes.
    jurisdiction: Optional[str] = Field(None, min_length=2, max_length=16)
    # Minor-record retention window (docs/DATA_RETENTION_POLICY.md R1).
    # NULL/absent = platform defaults; values clamped to sane ranges.
    majorityAge: Optional[int] = Field(None, ge=14, le=21)
    minorRetentionYears: Optional[int] = Field(None, ge=0, le=40)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc
        return value

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: Optional[str]) -> Optional[str]:
        return value.upper() if value else value


class BillingPreferencesResponse(BaseModel):
    """Billing preferences response"""
    taxRate: float = Field(default=0.0, ge=0, le=100)
    currency: str = Field(default="USD")
    invoicePrefix: str = Field(default="INV")
    paymentTerms: int = Field(default=30, ge=0)
    lateFeePercentage: float = Field(default=0.0, ge=0, le=100)
    acceptedPaymentMethods: List[str] = Field(default=["cash", "card", "check"])
    autoSendInvoices: bool = Field(default=False)
    autoSendReminders: bool = Field(default=False)
    reminderDaysBefore: int = Field(default=3, ge=0)


class BillingPreferencesUpdate(BaseModel):
    """Billing preferences update"""
    model_config = ConfigDict(extra="forbid")

    taxRate: Optional[float] = Field(None, ge=0, le=100)
    currency: Optional[str] = None
    invoicePrefix: Optional[str] = None
    paymentTerms: Optional[int] = Field(None, ge=0)
    lateFeePercentage: Optional[float] = Field(None, ge=0, le=100)
    acceptedPaymentMethods: Optional[List[str]] = None
    autoSendInvoices: Optional[bool] = None
    autoSendReminders: Optional[bool] = None
    reminderDaysBefore: Optional[int] = Field(None, ge=0)

    @field_validator("acceptedPaymentMethods")
    @classmethod
    def validate_payment_methods(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return value
        allowed = {"cash", "card", "check", "insurance", "upi", "other"}
        normalized = list(dict.fromkeys(method.lower() for method in value))
        invalid = sorted(set(normalized) - allowed)
        if invalid:
            raise ValueError(f"Unsupported payment methods: {', '.join(invalid)}")
        if not normalized:
            raise ValueError("At least one accepted payment method is required")
        return normalized
