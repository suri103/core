"""
Booking Service
===============

The booking endpoints implement their flows inline (see
app/api/v1/endpoints/booking.py). The only pieces shared with the endpoint
layer are the three token/code generators below. Everything else the old
BookingService carried (page CRUD, booking CRUD, waitlist, stats) was dead
code duplicating the endpoint implementations — it was removed with the
dead booking_availability module.
"""

import secrets
import string


class BookingService:
    """Shared helpers for the public booking flow."""

    @staticmethod
    def generate_confirmation_code() -> str:
        """Generate a unique confirmation code"""
        chars = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(chars) for _ in range(8))

    @staticmethod
    def generate_verification_token() -> str:
        """Generate a verification token for email confirmation"""
        return secrets.token_urlsafe(32)

    @staticmethod
    def generate_verification_code() -> str:
        """Generate a verification code for SMS confirmation"""
        return ''.join(secrets.choice(string.digits) for _ in range(6))
