"""Integration tests for the scheduling-support routes added for the frontend.

These exercise the real endpoints through the httpx AsyncClient with seeded
rows: reference lookups (/providers, /chairs, /appointment-types,
/patients/search), the appointment action routes (status/cancel/reschedule)
and the formalised patient export payload.
"""
import uuid

import pytest
from httpx import AsyncClient

from app.models.appointment import AppointmentType, Chair


@pytest.mark.asyncio
async def test_providers_lists_clinical_staff(client: AsyncClient, auth_headers):
    response = await client.get("/api/v1/providers", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list) and len(payload) >= 1
    assert all(item["name"] for item in payload)


@pytest.mark.asyncio
async def test_chairs_returns_practice_chairs(client, auth_headers, test_practice, db_session):
    db_session.add(
        Chair(
            id=uuid.uuid4(),
            practice_id=test_practice.id,
            name="Operatory 1",
            color="#3366FF",
            is_active=True,
        )
    )
    await db_session.flush()

    response = await client.get("/api/v1/chairs", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list) and len(payload) >= 1
    assert payload[0]["name"] == "Operatory 1"
    assert payload[0]["is_active"] is True


@pytest.mark.asyncio
async def test_appointment_types_returns_standard_set(client, auth_headers, db_session, test_practice):
    # No configured rows -> the standard dental type fallback is returned.
    response = await client.get("/api/v1/appointment-types", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list) and len(payload) >= 5
    assert all(item["name"] and item["duration"] for item in payload)

    # With a configured row, the practice's signed config shape is returned.
    db_session.add(
        AppointmentType(
            id=uuid.uuid4(),
            practice_id=test_practice.id,
            name="Custom Exam",
            duration=45,
            color="#102030",
            is_active=True,
        )
    )
    await db_session.flush()
    response2 = await client.get("/api/v1/appointment-types", headers=auth_headers)
    payload2 = response2.json()
    assert any(item["name"] == "Custom Exam" for item in payload2)


@pytest.mark.asyncio
async def test_patient_search_finds_by_name(client, auth_headers, test_patient):
    response = await client.get(
        "/api/v1/patients/search", params={"query": "Doe"}, headers=auth_headers
    )
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert any(item.get("name") == "John Doe" for item in payload)


@pytest.mark.asyncio
async def test_appointment_status_update(client, auth_headers, test_appointment):
    response = await client.put(
        f"/api/v1/appointments/{test_appointment.id}/status",
        json={"status": "confirmed"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"


@pytest.mark.asyncio
async def test_appointment_cancel(client, auth_headers, test_appointment):
    response = await client.post(
        f"/api/v1/appointments/{test_appointment.id}/cancel",
        json={"reason": "patient request"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["id"] == str(test_appointment.id)


@pytest.mark.asyncio
async def test_appointment_reschedule(client, auth_headers, test_appointment):
    response = await client.put(
        f"/api/v1/appointments/{test_appointment.id}/reschedule",
        json={"start_time": "2026-03-18T14:00:00Z"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(test_appointment.id)
    assert data["type"] == "cleaning"
    assert data["patient_name"] == "John Doe"


@pytest.mark.asyncio
async def test_patient_export_returns_schema_payload(client, auth_headers, test_patient):
    response = await client.get(
        f"/api/v1/patients/{test_patient.id}/export", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    for key in (
        "exported_at",
        "exported_by",
        "patient_demographics",
        "appointments",
        "clinical_notes",
        "treatment_plans",
        "invoices",
        "payments",
        "insurances",
        "insurance_claims",
        "patient_images",
        "documents",
    ):
        assert key in data, f"missing export key: {key}"
    assert data["exported_by"]["id"]
    assert data["patient_demographics"]["first_name"] == "John"