"""
Booking Validation Service
Validates booking requests and availability
"""

from datetime import datetime, timezone
from typing import Optional

class BookingValidationService:
    """Validates booking requests"""

    @staticmethod
    async def validate_booking_request(
        booking_page_id: str,
        patient_email: str,
        patient_phone: str,
        appointment_date: datetime,
    ) -> tuple[bool, Optional[str]]:
        """Validate a booking request. Returns (is_valid, error_message)."""
        if not patient_email and not patient_phone:
            return False, "Email or phone number is required"
        if appointment_date and appointment_date < datetime.now(timezone.utc):
            return False, "Appointment date must be in the future"
        return True, None

    @staticmethod
    async def validate_email(email: str) -> bool:
        """Basic email validation"""
        return bool(email and "@" in email and "." in email)

    @staticmethod
    async def validate_phone(phone: str) -> bool:
        """Basic phone validation"""
        return bool(phone and len(phone) >= 7)