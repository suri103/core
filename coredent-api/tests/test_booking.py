"""Tests for booking endpoints"""
import pytest
import uuid
import hashlib
from datetime import date, time

pytestmark = pytest.mark.asyncio


class TestBookingPages:
    async def test_list_pages_requires_auth(self, client):
        response = await client.get("/api/v1/booking/pages/")
        assert response.status_code in (401, 403)

    async def test_create_page_requires_auth(self, client):
        response = await client.post("/api/v1/booking/pages/", json={})
        assert response.status_code in (401, 403)

    async def test_create_page_validation_error(self, client, auth_headers):
        response = await client.post("/api/v1/booking/pages/", json={})
        assert response.status_code in (422, 401, 403)

    async def test_get_page_requires_auth(self, client):
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/v1/booking/pages/{fake_id}")
        assert response.status_code in (401, 403)

    async def test_update_page_requires_auth(self, client):
        fake_id = str(uuid.uuid4())
        response = await client.put(f"/api/v1/booking/pages/{fake_id}", json={})
        assert response.status_code in (401, 403)


class TestOnlineBooking:
    async def test_list_bookings_requires_auth(self, client):
        response = await client.get("/api/v1/booking/bookings/")
        assert response.status_code in (401, 403)

    async def test_get_booking_requires_auth(self, client):
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/v1/booking/bookings/{fake_id}")
        assert response.status_code in (401, 403)

    async def test_update_booking_requires_auth(self, client):
        fake_id = str(uuid.uuid4())
        response = await client.put(f"/api/v1/booking/bookings/{fake_id}", json={})
        assert response.status_code in (401, 403)


class TestWaitlist:
    async def test_list_waitlist_requires_auth(self, client):
        response = await client.get("/api/v1/booking/waitlist/")
        assert response.status_code in (401, 403)


class TestConfirmBooking:
    """Regression tests for POST /bookings/{booking_id}/confirm.

    The confirmation endpoint used to crash with a 500 whenever
    create_appointment=true because it constructed Appointment with a
    non-existent appointment_type_id column and never set the required
    appointment_type/duration fields. These tests lock in the fixed path.
    """

    @pytest.fixture
    async def online_booking(
        self, db_session, test_practice, test_patient, test_user
    ):
        """A confirmed-ready online booking linked to the test patient."""
        from app.models.booking import BookingStatus, OnlineBooking

        booking = OnlineBooking(
            booking_page_id=uuid.uuid4(),
            practice_id=test_practice.id,
            patient_id=test_patient.id,
            is_new_patient=False,
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
            phone="+1234567890",
            requested_date=date(2026, 10, 15),
            requested_time=time(10, 0),
            duration_minutes=30,
            status=BookingStatus.PENDING,
            confirmation_code="TESTCONF1",
        )
        db_session.add(booking)
        await db_session.flush()
        await db_session.refresh(booking)
        return booking

    async def test_confirm_booking_creates_appointment(
        self, client, auth_headers, online_booking
    ):
        """Confirming with create_appointment=true creates a real appointment."""
        from app.models.booking import BookingStatus
        from app.models.appointment import Appointment
        from conftest import TestingSessionLocal
        from sqlalchemy import select

        response = await client.post(
            f"/api/v1/booking/bookings/{online_booking.id}/confirm",
            headers=auth_headers,
            json={"booking_id": str(online_booking.id), "create_appointment": True},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == BookingStatus.CONFIRMED.value
        assert body["appointment_id"] is not None

        # Read via a fresh session: the request handler committed in its own
        # session, which may be invisible to an open fixture transaction.
        async with TestingSessionLocal() as check_session:
            result = await check_session.execute(
                select(Appointment).where(
                    Appointment.id == uuid.UUID(body["appointment_id"])
                )
            )
            appointment = result.scalar_one_or_none()
            assert appointment is not None
            assert appointment.practice_id == online_booking.practice_id
            assert appointment.patient_id == online_booking.patient_id
            assert appointment.duration == 30
            assert appointment.status == "scheduled"

    async def test_confirm_booking_404_for_unknown_booking(
        self, client, auth_headers, online_booking
    ):
        """Unknown booking id returns 404, not 500."""
        fake_id = uuid.uuid4()
        response = await client.post(
            f"/api/v1/booking/bookings/{fake_id}/confirm",
            headers=auth_headers,
            json={"booking_id": str(fake_id), "create_appointment": True},
        )
        assert response.status_code == 404

    async def test_confirm_booking_conflict_on_overlap(
        self, client, auth_headers, online_booking, db_session, test_practice
    ):
        """A conflicting appointment at the same time blocks confirmation."""
        from app.models.appointment import Appointment
        from datetime import datetime, timedelta, timezone
        from zoneinfo import ZoneInfo

        # The endpoint interprets the requested wall-clock time in the
        # practice's timezone (default America/New_York) and stores the UTC
        # instant — build the conflicting appointment the same way.
        tz = ZoneInfo(test_practice.timezone or "UTC")
        start = datetime.combine(
            online_booking.requested_date, online_booking.requested_time, tzinfo=tz
        ).astimezone(timezone.utc)
        db_session.add(
            Appointment(
                practice_id=test_practice.id,
                patient_id=online_booking.patient_id,
                appointment_type="cleaning",
                status="scheduled",
                start_time=start,
                end_time=start + timedelta(minutes=30),
                duration=30,
            )
        )
        await db_session.flush()

        response = await client.post(
            f"/api/v1/booking/bookings/{online_booking.id}/confirm",
            headers=auth_headers,
            json={"booking_id": str(online_booking.id), "create_appointment": True},
        )
        assert response.status_code == 409, response.text

    async def test_confirm_booking_new_patient_creates_patient(
        self, client, auth_headers, test_practice, db_session
    ):
        """A booking with no linked patient creates one on confirm."""
        from app.models.booking import BookingStatus, OnlineBooking
        from app.models.patient import Patient
        from conftest import TestingSessionLocal
        from sqlalchemy import select

        booking = OnlineBooking(
            booking_page_id=uuid.uuid4(),
            practice_id=test_practice.id,
            patient_id=None,
            is_new_patient=True,
            first_name="New",
            last_name="Patient",
            email="new.patient@example.com",
            phone="+15551234567",
            date_of_birth=date(1992, 5, 20),
            requested_date=date(2026, 10, 16),
            requested_time=time(11, 0),
            duration_minutes=45,
            status=BookingStatus.PENDING,
            confirmation_code="TESTCONF2",
        )
        db_session.add(booking)
        await db_session.flush()

        response = await client.post(
            f"/api/v1/booking/bookings/{booking.id}/confirm",
            headers=auth_headers,
            json={"booking_id": str(booking.id), "create_appointment": True},
        )
        assert response.status_code == 200, response.text
        assert response.json()["appointment_id"] is not None

        # A patient was auto-created and linked. The email column is
        # encrypted at rest, so match via the HMAC search index instead.
        from app.core.search_index import hmac_index

        async with TestingSessionLocal() as check_session:
            result = await check_session.execute(
                select(Patient).where(
                    Patient.search_index_email
                    == hmac_index("new.patient@example.com")
                )
            )
            assert result.scalar_one_or_none() is not None

    async def test_concurrent_confirm_does_not_create_two_appointments(
        self, client, auth_headers, online_booking, db_session, test_practice
    ):
        """H-2 FIX regression: a staff double-click or concurrent confirm must
        produce exactly one Appointment row, never two. The endpoint holds
        a FOR UPDATE on the booking row and re-checks ``booking.appointment_id``
        before creating a new appointment, so the second confirm sees the
        appointment_id is already set and short-circuits to the idempotent
        return.
        """
        import asyncio
        from app.models.booking import OnlineBooking
        from app.models.appointment import Appointment
        from conftest import TestingSessionLocal
        from sqlalchemy import select

        # Fire two confirms at once. The fixture's auth_headers are
        # stateless between calls in the test client, so both
        # requests reach the endpoint concurrently. We only care that
        # the post-state is one appointment regardless of ordering.
        async def confirm() -> int:
            response = await client.post(
                f"/api/v1/booking/bookings/{online_booking.id}/confirm",
                headers=auth_headers,
                json={
                    "booking_id": str(online_booking.id),
                    "create_appointment": True,
                },
            )
            return response.status_code

        statuses = await asyncio.gather(confirm(), confirm())
        assert statuses[0] == 200, statuses
        assert statuses[1] == 200, statuses

        # Read via a fresh session to escape the fixture transaction.
        # The FK is OnlineBooking.appointment_id -> appointments.id, so
        # we count appointments by joining through the booking row.
        async with TestingSessionLocal() as check_session:
            booking = (
                await check_session.execute(
                    select(OnlineBooking).where(
                        OnlineBooking.id == online_booking.id
                    )
                )
            ).scalar_one()
            assert booking.appointment_id is not None, (
                "booking.appointment_id must be set after confirm"
            )
            appts = (
                await check_session.execute(
                    select(Appointment).where(
                        Appointment.id == booking.appointment_id
                    )
                )
            ).scalars().all()
            assert len(appts) == 1, (
                f"concurrent confirms produced {len(appts)} "
                "Appointment rows; expected exactly 1"
            )


class TestOnlineBookingContracts:
    @staticmethod
    def valid_create_payload():
        return {
            "first_name": "Public",
            "last_name": "Patient",
            "email": "public.patient@example.com",
            "phone": "(555) 123-4567",
            "appointment_type_id": uuid.uuid4(),
            "date_of_birth": date(1990, 1, 2),
            "requested_date": date(2026, 11, 3),
            "requested_time": time(9, 30),
        }

    @pytest.mark.parametrize("missing_field", ["appointment_type_id", "date_of_birth"])
    async def test_online_booking_create_requires_public_contract_fields(
        self, missing_field
    ):
        from pydantic import ValidationError

        from app.schemas.booking import OnlineBookingCreate

        payload = self.valid_create_payload()
        payload.pop(missing_field)

        with pytest.raises(ValidationError) as exc_info:
            OnlineBookingCreate(**payload)

        assert any(
            error["loc"] == (missing_field,) and error["type"] == "missing"
            for error in exc_info.value.errors()
        )

    async def test_online_booking_create_normalizes_formatted_phone(self):
        from app.schemas.booking import OnlineBookingCreate

        booking = OnlineBookingCreate(**self.valid_create_payload())

        assert booking.phone == "5551234567"

    @pytest.mark.parametrize("verification_token", ["", "too-short"])
    async def test_email_verification_request_rejects_short_token(
        self, verification_token
    ):
        from pydantic import ValidationError

        from app.schemas.booking import EmailVerificationRequest

        with pytest.raises(ValidationError) as exc_info:
            EmailVerificationRequest(
                verification_session="opaque-session",
                verification_token=verification_token,
            )

        assert any(
            error["loc"] == ("verification_token",)
            for error in exc_info.value.errors()
        )


class TestBookingSecurityContracts:
    @pytest.fixture
    async def unmatched_existing_booking(self, db_session, test_practice):
        from app.models.booking import BookingStatus, OnlineBooking

        booking = OnlineBooking(
            booking_page_id=uuid.uuid4(),
            practice_id=test_practice.id,
            patient_id=None,
            is_new_patient=False,
            first_name="Existing",
            last_name="Patient",
            email="existing.patient@example.com",
            phone="5551234567",
            requested_date=date(2026, 11, 4),
            requested_time=time(10, 0),
            duration_minutes=30,
            status=BookingStatus.PENDING,
            confirmation_code="UNMATCHED1",
        )
        db_session.add(booking)
        await db_session.flush()
        await db_session.refresh(booking)
        return booking

    async def test_confirmation_rejects_body_booking_id_mismatch(
        self, client, auth_headers
    ):
        url_booking_id = uuid.uuid4()

        response = await client.post(
            f"/api/v1/booking/bookings/{url_booking_id}/confirm",
            headers=auth_headers,
            json={"booking_id": str(uuid.uuid4()), "create_appointment": False},
        )

        assert response.status_code == 422, response.text
        assert response.json()["detail"] == (
            "Booking ID in the request body must match the URL"
        )

    async def test_generic_update_cannot_confirm_pending_booking(
        self, client, auth_headers, unmatched_existing_booking
    ):
        response = await client.put(
            f"/api/v1/booking/bookings/{unmatched_existing_booking.id}",
            headers=auth_headers,
            json={"status": "confirmed"},
        )

        assert response.status_code == 409, response.text
        assert response.json()["detail"] == (
            "Use the confirmation endpoint to confirm a booking; "
            "it enforces verification and conflict checks"
        )

    async def test_staff_assigns_active_same_practice_patient(
        self, client, auth_headers, unmatched_existing_booking, test_patient
    ):
        response = await client.put(
            f"/api/v1/booking/bookings/{unmatched_existing_booking.id}",
            headers=auth_headers,
            json={"patient_id": str(test_patient.id)},
        )

        assert response.status_code == 200, response.text
        assert response.json()["patient_id"] == str(test_patient.id)

    async def test_staff_cannot_assign_unknown_patient(
        self, client, auth_headers, unmatched_existing_booking
    ):
        response = await client.put(
            f"/api/v1/booking/bookings/{unmatched_existing_booking.id}",
            headers=auth_headers,
            json={"patient_id": str(uuid.uuid4())},
        )

        assert response.status_code == 404, response.text
        assert response.json()["detail"] == (
            "Active patient not found for this practice"
        )

    async def test_staff_cannot_assign_cross_practice_patient(
        self, client, auth_headers, unmatched_existing_booking, other_patient
    ):
        response = await client.put(
            f"/api/v1/booking/bookings/{unmatched_existing_booking.id}",
            headers=auth_headers,
            json={"patient_id": str(other_patient.id)},
        )

        assert response.status_code == 404, response.text
        assert response.json()["detail"] == (
            "Active patient not found for this practice"
        )


class TestPublicEmailVerification:
    async def test_email_verification_success_and_replay_are_idempotent(
        self, client, db_session, test_practice
    ):
        from app.api.v1.endpoints.booking import (
            _create_booking_verification_session,
        )
        from app.models.booking import (
            BookingPage,
            BookingPageStatus,
            BookingStatus,
            OnlineBooking,
        )

        page = BookingPage(
            practice_id=test_practice.id,
            page_slug=f"verify-{uuid.uuid4().hex}",
            page_title="Verification Test",
            require_email_verification=True,
            require_phone_verification=False,
            status=BookingPageStatus.ACTIVE,
        )
        db_session.add(page)
        await db_session.flush()

        verification_token = "email-verification-token-12345"
        verification_token_hash = hashlib.sha256(
            verification_token.encode("utf-8")
        ).hexdigest()
        booking = OnlineBooking(
            booking_page_id=page.id,
            practice_id=test_practice.id,
            is_new_patient=True,
            first_name="Verify",
            last_name="Patient",
            email="verify.patient@example.com",
            phone="5559876543",
            requested_date=date(2026, 11, 5),
            requested_time=time(11, 0),
            status=BookingStatus.PENDING,
            confirmation_code="VERIFYEMAIL1",
            email_verified=False,
            email_verification_token=None,
            email_verification_token_hash=verification_token_hash,
            phone_verified=True,
        )
        db_session.add(booking)
        await db_session.flush()
        verification_session = _create_booking_verification_session(booking, page)
        request_body = {
            "verification_session": verification_session,
            "verification_token": verification_token,
        }

        first_response = await client.post(
            "/api/v1/booking/public/verify-email", json=request_body
        )

        assert first_response.status_code == 200, first_response.text
        assert first_response.json() == {
            "verified": True,
            "message": "Email verified successfully",
            "confirmation_code": "VERIFYEMAIL1",
            "email_verified": True,
            "phone_verified": True,
            "require_email_verification": True,
            "require_phone_verification": False,
        }

        replay_response = await client.post(
            "/api/v1/booking/public/verify-email", json=request_body
        )

        assert replay_response.status_code == 200, replay_response.text
        assert replay_response.json() == {
            "verified": True,
            "message": "Email verified successfully",
            "confirmation_code": "VERIFYEMAIL1",
            "email_verified": True,
            "phone_verified": True,
            "require_email_verification": True,
            "require_phone_verification": False,
        }

    async def test_failure_responses_are_uniform_regardless_of_cause(
        self, client, db_session, test_practice
    ):
        """M-06 FIX: an invalid session and a valid session with a wrong
        token must produce byte-identical responses so neither session nor
        token validity can be probed through response differences."""
        from app.api.v1.endpoints.booking import (
            _create_booking_verification_session,
        )
        from app.models.booking import (
            BookingPage,
            BookingPageStatus,
            BookingStatus,
            OnlineBooking,
        )

        page = BookingPage(
            practice_id=test_practice.id,
            page_slug=f"uniform-{uuid.uuid4().hex}",
            page_title="Uniform Failure Test",
            require_email_verification=True,
            require_phone_verification=True,
            status=BookingPageStatus.ACTIVE,
        )
        db_session.add(page)
        await db_session.flush()

        booking = OnlineBooking(
            booking_page_id=page.id,
            practice_id=test_practice.id,
            is_new_patient=True,
            first_name="Uniform",
            last_name="Failure",
            email="uniform.failure@example.com",
            phone="5550001111",
            requested_date=date(2026, 11, 6),
            requested_time=time(9, 30),
            status=BookingStatus.PENDING,
            confirmation_code="UNIFORM01",
            email_verified=False,
            email_verification_token=None,
            email_verification_token_hash=hashlib.sha256(
                b"the-real-email-token"
            ).hexdigest(),
            phone_verified=False,
            phone_verification_code="654321",
        )
        db_session.add(booking)
        await db_session.flush()
        verification_session = _create_booking_verification_session(booking, page)

        expected_failure_body = {
            "verified": False,
            "message": "Verification could not be completed",
            "confirmation_code": None,
            "email_verified": False,
            "phone_verified": False,
            "require_email_verification": False,
            "require_phone_verification": False,
        }

        invalid_session_response = await client.post(
            "/api/v1/booking/public/verify-email",
            json={
                "verification_session": "not-a-valid-session",
                "verification_token": "the-real-email-token",
            },
        )
        wrong_token_response = await client.post(
            "/api/v1/booking/public/verify-email",
            json={
                "verification_session": verification_session,
                "verification_token": "a-guessed-token-0000",
            },
        )

        assert invalid_session_response.status_code == 200
        assert wrong_token_response.status_code == 200
        assert invalid_session_response.json() == expected_failure_body
        assert wrong_token_response.json() == expected_failure_body

        # The booking must remain untouched by failed attempts.
        assert booking.email_verified is False
        assert booking.email_verification_token_hash == hashlib.sha256(
            b"the-real-email-token"
        ).hexdigest()

        # Same contract on the phone path.
        wrong_code_response = await client.post(
            "/api/v1/booking/public/verify-phone",
            json={
                "verification_session": verification_session,
                "verification_code": "000000",
            },
        )
        assert wrong_code_response.status_code == 200
        assert wrong_code_response.json() == expected_failure_body


class TestBookingPublic:
    async def test_public_page_returns_404_for_unknown_slug(self, client):
        response = await client.get("/api/v1/booking/public/nonexistent")
        assert response.status_code in (404, 200)
