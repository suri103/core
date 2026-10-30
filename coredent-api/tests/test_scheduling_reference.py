"""Tests for the scheduling-support endpoints and appointment-type coercion.

Covers the reference routes the React scheduling services hit (/providers,
/chairs, /appointment-types, /patients/search, the un-shadowed /export, and
the appointment action routes), plus the display-name->enum coercion for
appointment_type.
"""
import uuid
from datetime import datetime, timedelta, timezone

from app.main import app as fastapi_app
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentUpdate,
    _coerce_appointment_type,
)
from app.models.appointment import AppointmentTypeEnum


def test_display_names_coerce_onto_appointment_type_enum():
    assert _coerce_appointment_type("Checkup") == AppointmentTypeEnum.EXAM
    assert _coerce_appointment_type("root canal") == AppointmentTypeEnum.ROOT_CANAL
    assert _coerce_appointment_type("Follow-up") == AppointmentTypeEnum.OTHER
    assert _coerce_appointment_type("cleaning") == AppointmentTypeEnum.CLEANING
    assert _coerce_appointment_type("unknown_thing") == AppointmentTypeEnum.OTHER
    assert _coerce_appointment_type(AppointmentTypeEnum.CROWN) == AppointmentTypeEnum.CROWN


def _create_kwargs(appointment_type_value):
    start = datetime.now(timezone.utc)
    return dict(
        patient_id=uuid.uuid4(),
        appointment_type=appointment_type_value,
        start_time=start,
        end_time=start + timedelta(minutes=30),
        duration=30,
    )


def test_appointment_create_accepts_human_readable_type_names():
    model = AppointmentCreate(**_create_kwargs("Checkup"))
    assert model.appointment_type == AppointmentTypeEnum.EXAM
    model2 = AppointmentCreate(**_create_kwargs("Root Canal"))
    assert model2.appointment_type == AppointmentTypeEnum.ROOT_CANAL


def test_appointment_update_coerces_only_when_provided():
    update = AppointmentUpdate(status="confirmed")
    assert "appointment_type" not in update.model_dump(exclude_unset=True)

    update2 = AppointmentUpdate(appointment_type="Extraction")
    assert update2.appointment_type == AppointmentTypeEnum.EXTRACTION


def test_scheduling_reference_routes_are_registered():
    paths = fastapi_app.openapi()["paths"]
    for path in (
        "/api/v1/providers",
        "/api/v1/chairs",
        "/api/v1/appointment-types",
        "/api/v1/patients/search",
        "/api/v1/patients/{patient_id}/export",
        "/api/v1/appointments/{appointment_id}/status",
        "/api/v1/appointments/{appointment_id}/cancel",
        "/api/v1/appointments/{appointment_id}/reschedule",
        "/api/v1/patients/{patient_id}/notes",
    ):
        assert path in paths, f"missing route {path}"