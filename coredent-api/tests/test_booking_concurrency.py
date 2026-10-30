"""Regression test: Booking slot concurrency and duplicate slot prevention."""
import uuid
from datetime import date, time, timedelta, datetime, timezone
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.api.v1.endpoints import booking
from app.models.practice import Practice
from app.models.user import User, UserRole
from app.models.appointment import AppointmentType
from app.models.booking import BookingPage, BookingPageStatus
from app.schemas.booking import OnlineBookingCreate


def _make_request() -> Request:
    return Request(scope={
        "type": "http",
        "client": ("127.0.0.1", 1234),
        "headers": [],
        "path": "/api/v1/booking/public/test/book",
        "method": "POST",
    })


@pytest.mark.asyncio
async def test_duplicate_slot_booking_rejected_with_409(db_session):
    practice = Practice(
        id=uuid.uuid4(),
        name="Slot Concurrency Clinic",
        public_slug="slot-clinic",
        is_active=True,
    )
    db_session.add(practice)
    await db_session.flush()

    dentist = User(
        id=uuid.uuid4(),
        practice_id=practice.id,
        email="dr.slot@example.com",
        password_hash="dummy_hash",
        first_name="Doctor",
        last_name="Slot",
        role=UserRole.DENTIST,
        is_active=True,
    )
    db_session.add(dentist)
    await db_session.flush()

    apt_type = AppointmentType(
        id=uuid.uuid4(),
        practice_id=practice.id,
        name="General Exam",
        duration=30,
        color="#3B82F6",
        is_active=True,
    )
    db_session.add(apt_type)
    await db_session.flush()

    # Target date: 3 days from today, weekday (Monday-Friday)
    today = datetime.now(timezone.utc).date()
    target_date = today + timedelta(days=3)
    day_name = target_date.strftime("%A").lower()

    page = BookingPage(
        id=uuid.uuid4(),
        practice_id=practice.id,
        page_slug="online",
        page_title="Book Online",
        status=BookingPageStatus.ACTIVE,
        allow_new_patients=True,
        min_notice_hours=1,
        booking_window_days=30,
        allowed_providers=[str(dentist.id)],
        allowed_appointment_types=[str(apt_type.id)],
        business_hours={
            day_name: {
                "enabled": True,
                "slots": [{"start": "09:00", "end": "17:00"}],
            }
        },
    )
    db_session.add(page)
    await db_session.commit()

    slot_time = time(10, 0)

    booking_data_1 = OnlineBookingCreate(
        first_name="Patient",
        last_name="One",
        email="patient.one@example.com",
        phone="555-010-0001",
        date_of_birth=date(1990, 1, 1),
        requested_date=target_date,
        requested_time=slot_time,
        provider_id=dentist.id,
        appointment_type_id=apt_type.id,
        is_new_patient=True,
    )

    booking_data_2 = OnlineBookingCreate(
        first_name="Patient",
        last_name="Two",
        email="patient.two@example.com",
        phone="555-010-0002",
        date_of_birth=date(1992, 2, 2),
        requested_date=target_date,
        requested_time=slot_time,
        provider_id=dentist.id,
        appointment_type_id=apt_type.id,
        is_new_patient=True,
    )

    raw_create = getattr(booking.create_online_booking, "__wrapped__", booking.create_online_booking)
    req = _make_request()

    # First booking must succeed
    res1 = await raw_create(
        request=req,
        practice_slug="slot-clinic",
        page_slug="online",
        booking_data=booking_data_1,
        db=db_session,
    )
    assert res1.confirmation_code is not None

    # Second booking for the exact same provider slot must be rejected with 409
    with pytest.raises(HTTPException) as exc_info:
        await raw_create(
            request=req,
            practice_slug="slot-clinic",
            page_slug="online",
            booking_data=booking_data_2,
            db=db_session,
        )
    assert exc_info.value.status_code == 409
    assert "no longer available" in exc_info.value.detail.lower()
