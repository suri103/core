"""Tests for the booking generators still used by the booking endpoints.

The old BookingService page/booking/waitlist/stats CRUD methods were dead
code duplicating the inline endpoint implementations and were removed with
booking_availability.py. Only the three generators remain.
"""

from app.services.booking_service import BookingService


class TestBookingGenerators:
    def test_generate_confirmation_code(self):
        code = BookingService.generate_confirmation_code()
        assert len(code) == 8
        assert code.isalnum()

    def test_generate_verification_token(self):
        token = BookingService.generate_verification_token()
        assert len(token) > 20

    def test_generate_verification_code(self):
        code = BookingService.generate_verification_code()
        assert len(code) == 6
        assert code.isdigit()
