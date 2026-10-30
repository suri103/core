"""Cross-tenant reference validation (audit findings H-02, H-04, H-05, M-09..M-12).

These are the regression tests for ``app.services.tenant_refs``. The class of
bug they cover: an endpoint validated the *primary* entity in the request
(usually the patient) and then wrote every other id from the payload straight
into the row, so a caller could attach another practice's provider,
appointment, carrier or insurance policy to their own records.

Every check must fail closed with a generic 404 -- the API must not be usable
as a cross-tenant existence oracle.
"""

from __future__ import annotations

import datetime
import uuid
from datetime import timedelta, timezone

import pytest
from fastapi import HTTPException

from app.core.security import get_password_hash
from app.models.appointment import (
    Appointment,
    AppointmentStatus,
    AppointmentType,
    AppointmentTypeEnum,
)
from app.models.insurance import InsuranceCarrier, PatientInsurance
from app.models.patient import Patient
from app.models.practice import Practice
from app.models.user import User, UserRole
from app.services.tenant_refs import (
    require_appointment,
    require_appointment_type,
    require_carrier,
    require_patient,
    require_patient_insurance,
    require_provider,
)


def _make_patient(practice_id, first_name="Rival", last_name="Patient") -> Patient:
    """Minimal valid patient. ``date_of_birth`` is NOT NULL."""
    return Patient(
        id=uuid.uuid4(),
        practice_id=practice_id,
        first_name=first_name,
        last_name=last_name,
        date_of_birth=datetime.date(1990, 1, 1),
        status="active",
    )


@pytest.fixture
async def other_practice(db_session) -> Practice:
    """A second tenant, entirely unrelated to the fixture practice."""
    practice = Practice(
        id=uuid.uuid4(),
        name="Rival Dental",
        public_slug=f"rival-{uuid.uuid4().hex[:6]}",
        email=f"rival_{uuid.uuid4().hex[:8]}@example.com",
        timezone="UTC",
    )
    db_session.add(practice)
    await db_session.flush()
    await db_session.refresh(practice)
    return practice


@pytest.fixture
async def other_provider(db_session, other_practice) -> User:
    user = User(
        id=uuid.uuid4(),
        practice_id=other_practice.id,
        email=f"rival_dds_{uuid.uuid4().hex[:8]}@example.com",
        password_hash=get_password_hash("Str0ng!Passw0rd"),
        first_name="Rival",
        last_name="Dentist",
        role="DENTIST",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def other_patient(db_session, other_practice) -> Patient:
    patient = _make_patient(other_practice.id)
    db_session.add(patient)
    await db_session.flush()
    await db_session.refresh(patient)
    return patient


class TestRequireProvider:
    async def test_accepts_own_practice_provider(self, db_session, test_user, test_practice):
        result = await require_provider(db_session, test_user.id, test_practice.id)
        assert result.id == test_user.id

    async def test_rejects_other_practice_provider(
        self, db_session, test_practice, other_provider
    ):
        """H-05/M-12: a clinical record must not be attributed to a foreign clinician."""
        with pytest.raises(HTTPException) as exc:
            await require_provider(db_session, other_provider.id, test_practice.id)
        assert exc.value.status_code == 404
        # Generic message: must not disclose that the provider exists elsewhere.
        assert "not found or access denied" in exc.value.detail

    async def test_rejects_nonexistent_provider(self, db_session, test_practice):
        with pytest.raises(HTTPException) as exc:
            await require_provider(db_session, uuid.uuid4(), test_practice.id)
        assert exc.value.status_code == 404

    async def test_nonexistent_and_foreign_are_indistinguishable(
        self, db_session, test_practice, other_provider
    ):
        """The API must not be a cross-tenant existence oracle."""
        with pytest.raises(HTTPException) as foreign:
            await require_provider(db_session, other_provider.id, test_practice.id)
        with pytest.raises(HTTPException) as missing:
            await require_provider(db_session, uuid.uuid4(), test_practice.id)
        assert foreign.value.status_code == missing.value.status_code
        assert foreign.value.detail == missing.value.detail

    async def test_none_is_passthrough(self, db_session, test_practice):
        """An unsupplied optional reference is not an error."""
        assert await require_provider(db_session, None, test_practice.id) is None

    async def test_rejects_inactive_provider(self, db_session, test_practice, test_user):
        test_user.is_active = False
        await db_session.flush()
        with pytest.raises(HTTPException) as exc:
            await require_provider(db_session, test_user.id, test_practice.id)
        assert exc.value.status_code == 404

    async def test_rejects_disallowed_role(self, db_session, test_practice, test_user):
        """H-04: a public booking must not name a non-clinical account as provider."""
        with pytest.raises(HTTPException) as exc:
            await require_provider(
                db_session,
                test_user.id,
                test_practice.id,
                roles=(UserRole.HYGIENIST,),
            )
        assert exc.value.status_code == 422
        assert "must be one of" in exc.value.detail


class TestRequirePatient:
    async def test_rejects_other_practice_patient(
        self, db_session, test_practice, other_patient
    ):
        with pytest.raises(HTTPException) as exc:
            await require_patient(db_session, other_patient.id, test_practice.id)
        assert exc.value.status_code == 404

    async def test_accepts_own_patient(self, db_session, test_practice, test_patient):
        result = await require_patient(db_session, test_patient.id, test_practice.id)
        assert result.id == test_patient.id


class TestRequireAppointment:
    @pytest.fixture
    async def own_appointment(
        self, db_session, test_practice, test_patient, test_user
    ) -> Appointment:
        start = datetime.datetime.now(timezone.utc) + timedelta(days=1)
        appointment = Appointment(
            id=uuid.uuid4(),
            practice_id=test_practice.id,
            patient_id=test_patient.id,
            provider_id=test_user.id,
            appointment_type=AppointmentTypeEnum.OTHER,
            status=AppointmentStatus.SCHEDULED,
            start_time=start,
            end_time=start + timedelta(minutes=30),
            duration=30,
        )
        db_session.add(appointment)
        await db_session.flush()
        await db_session.refresh(appointment)
        return appointment

    async def test_accepts_matching_patient(
        self, db_session, test_practice, test_patient, own_appointment
    ):
        result = await require_appointment(
            db_session, own_appointment.id, test_practice.id, patient_id=test_patient.id
        )
        assert result.id == own_appointment.id

    async def test_rejects_appointment_of_another_patient(
        self, db_session, test_practice, own_appointment
    ):
        """H-05: linking a note to another patient's visit mixes two records."""
        with pytest.raises(HTTPException) as exc:
            await require_appointment(
                db_session,
                own_appointment.id,
                test_practice.id,
                patient_id=uuid.uuid4(),
            )
        assert exc.value.status_code == 404

    async def test_rejects_other_practice_appointment(
        self, db_session, other_practice, own_appointment
    ):
        with pytest.raises(HTTPException) as exc:
            await require_appointment(
                db_session, own_appointment.id, other_practice.id
            )
        assert exc.value.status_code == 404


class TestRequireAppointmentType:
    async def test_rejects_other_practice_type(
        self, db_session, test_practice, other_practice
    ):
        """H-04: a public booking could previously supply any appointment type id."""
        foreign_type = AppointmentType(
            id=uuid.uuid4(),
            practice_id=other_practice.id,
            name="Rival Cleaning",
            duration=30,
            color="#ff0000",
        )
        db_session.add(foreign_type)
        await db_session.flush()

        with pytest.raises(HTTPException) as exc:
            await require_appointment_type(
                db_session, foreign_type.id, test_practice.id
            )
        assert exc.value.status_code == 404

    async def test_accepts_own_type(self, db_session, test_practice):
        own_type = AppointmentType(
            id=uuid.uuid4(),
            practice_id=test_practice.id,
            name="Cleaning",
            duration=30,
            color="#00ff00",
        )
        db_session.add(own_type)
        await db_session.flush()

        result = await require_appointment_type(
            db_session, own_type.id, test_practice.id
        )
        assert result.id == own_type.id


class TestRequireCarrier:
    async def test_accepts_global_carrier(self, db_session, test_practice):
        """practice_id IS NULL means a shared carrier and stays usable."""
        carrier = InsuranceCarrier(
            id=uuid.uuid4(),
            practice_id=None,
            name="Global Payer",
        )
        db_session.add(carrier)
        await db_session.flush()

        result = await require_carrier(db_session, carrier.id, test_practice.id)
        assert result.id == carrier.id

    async def test_accepts_own_carrier(self, db_session, test_practice):
        carrier = InsuranceCarrier(
            id=uuid.uuid4(),
            practice_id=test_practice.id,
            name="Our Payer",
        )
        db_session.add(carrier)
        await db_session.flush()

        result = await require_carrier(db_session, carrier.id, test_practice.id)
        assert result.id == carrier.id

    async def test_rejects_other_practice_carrier(
        self, db_session, test_practice, other_practice
    ):
        """M-10: the FK could previously cross tenants."""
        carrier = InsuranceCarrier(
            id=uuid.uuid4(),
            practice_id=other_practice.id,
            name="Rival Payer",
        )
        db_session.add(carrier)
        await db_session.flush()

        with pytest.raises(HTTPException) as exc:
            await require_carrier(db_session, carrier.id, test_practice.id)
        assert exc.value.status_code == 404


class TestRequirePatientInsurance:
    @pytest.fixture
    async def own_policy(
        self, db_session, test_practice, test_patient
    ) -> PatientInsurance:
        carrier = InsuranceCarrier(
            id=uuid.uuid4(), practice_id=test_practice.id, name="Payer A"
        )
        db_session.add(carrier)
        await db_session.flush()
        policy = PatientInsurance(
            id=uuid.uuid4(),
            patient_id=test_patient.id,
            carrier_id=carrier.id,
            subscriber_id="SUB-1",
        )
        db_session.add(policy)
        await db_session.flush()
        await db_session.refresh(policy)
        return policy

    async def test_accepts_matching_patient(
        self, db_session, test_practice, test_patient, own_policy
    ):
        result = await require_patient_insurance(
            db_session, own_policy.id, test_practice.id, patient_id=test_patient.id
        )
        assert result.id == own_policy.id

    async def test_rejects_policy_of_another_patient(
        self, db_session, test_practice, own_policy
    ):
        """H-02: the exact defect — patient A paired with patient B's policy.

        Both the patient and the policy are inside the caller's practice, so
        every practice-level check passes. Only the patient/policy pairing
        catches it.
        """
        other = _make_patient(test_practice.id, first_name="Second")
        db_session.add(other)
        await db_session.flush()

        with pytest.raises(HTTPException) as exc:
            await require_patient_insurance(
                db_session, own_policy.id, test_practice.id, patient_id=other.id
            )
        assert exc.value.status_code == 404
        assert "does not belong to this patient" in exc.value.detail

    async def test_rejects_other_practice_policy(
        self, db_session, other_practice, own_policy
    ):
        with pytest.raises(HTTPException) as exc:
            await require_patient_insurance(
                db_session, own_policy.id, other_practice.id
            )
        assert exc.value.status_code == 404
