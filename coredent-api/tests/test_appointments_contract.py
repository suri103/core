"""Contract tests for the AppointmentResponse read-model aliases.

These bridge the frontend `types/api.ts` `Appointment` contract
(`type`, `patientName`, `providerName`, `operatoryId`/`operatoryName`) with the
backend `AppointmentResponse` serializer without needing a live database.
"""
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.api.v1.endpoints.appointments import _serialize_appointment
from app.models.appointment import AppointmentStatus, AppointmentTypeEnum
from app.schemas.appointment import AppointmentResponse


def _person(first: str, last: str) -> SimpleNamespace:
    return SimpleNamespace(first_name=first, last_name=last)


def _fake_appointment(with_relationships: bool = True) -> SimpleNamespace:
    start = datetime.now(timezone.utc)
    appointment = SimpleNamespace(
        id=uuid.uuid4(),
        practice_id=uuid.uuid4(),
        patient_id=uuid.uuid4(),
        provider_id=uuid.uuid4(),
        chair_id=uuid.uuid4() if with_relationships else None,
        appointment_type=AppointmentTypeEnum.CLEANING,
        status=AppointmentStatus.SCHEDULED,
        start_time=start,
        end_time=start + timedelta(minutes=30),
        duration=30,
        notes="Recall",
        created_at=start,
        updated_at=start,
    )
    if with_relationships:
        appointment.patient = _person("Jane", "Doe")
        appointment.provider = _person("Robert", "Smith")
        appointment.chair = SimpleNamespace(id=uuid.uuid4(), name="Chair 1")
        # Simulate the eager-loaded relationships living in __dict__.
        appointment.__dict__.update(
            {
                "patient": appointment.patient,
                "provider": appointment.provider,
                "chair": appointment.chair,
            }
        )
    return appointment


def test_serialize_appointment_emits_read_model_aliases():
    appointment = _fake_appointment(with_relationships=True)
    response: AppointmentResponse = _serialize_appointment(appointment)

    # Canonical fields the React layer already consumed.
    assert response.patient_id == appointment.patient_id
    assert response.provider_id == appointment.provider_id

    # Read-model aliases that complete the types/api.ts Appointment contract.
    assert response.type == "cleaning"
    assert response.patient_name == "Jane Doe"
    assert response.provider_name == "Robert Smith"
    assert response.operatory_id == appointment.chair.id
    assert response.operatory_name == "Chair 1"
    assert response.appointment_type == AppointmentTypeEnum.CLEANING
    assert response.status == AppointmentStatus.SCHEDULED


def test_serialize_appointment_tolerates_unloaded_relationships():
    appointment = _fake_appointment(with_relationships=False)
    response = _serialize_appointment(appointment)

    assert response.type == "cleaning"
    assert response.patient_name == ""
    assert response.provider_name == ""
    assert response.operatory_id is None
    assert response.operatory_name is None