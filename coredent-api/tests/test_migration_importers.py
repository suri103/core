"""
Tests for Legacy Migration Importers (Open Dental, Dentrix, Eaglesoft)
"""

from datetime import date
from decimal import Decimal
import io
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.clinical import ClinicalNote
from app.models.patient import Gender, Patient, PatientStatus
from app.services.migration_importers import (
    DentrixAdapter,
    EaglesoftAdapter,
    MigrationImportersService,
    OpenDentalAdapter,
)


class TestMigrationAdapters:
    def test_open_dental_adapter_detection_and_transform(self):
        headers = ["PatNum", "LName", "FName", "Birthdate", "Gender", "WirelessPhone", "Email", "ADACode", "ProcFee", "ProcDescript"]
        assert MigrationImportersService.detect_ehr_system(headers) == "opendental"

        row = {
            "PatNum": "10023",
            "FName": "Arthur",
            "LName": "Dent",
            "Birthdate": "1982-03-11",
            "Gender": "0",  # Male in Open Dental
            "WirelessPhone": "555-123-4567",
            "Email": "arthur.dent@example.com",
            "Address": "42 Galaxy Way",
            "City": "London",
            "State": "UK",
            "Zip": "NW1",
            "ADACode": "0120",  # Will normalize to D0120
            "ProcFee": "75.00",
            "ProcDescript": "Periodic exam",
            "ToothNum": "14",
        }

        record, err = OpenDentalAdapter.transform_row(row, 1)
        assert err is None
        assert record is not None
        assert record.first_name == "Arthur"
        assert record.last_name == "Dent"
        assert record.date_of_birth == date(1982, 3, 11)
        assert record.gender == Gender.MALE
        assert record.email == "arthur.dent@example.com"
        assert "(555) 123-4567" in (record.phone or "")
        assert len(record.procedures) == 1
        assert record.procedures[0].procedure_code == "D0120"
        assert record.procedures[0].fee == Decimal("75.00")

    def test_dentrix_adapter_detection_and_transform(self):
        headers = ["ChartNumber", "FirstName", "LastName", "BirthDate", "Gender", "CellPhone", "EmailAddress", "ProcCode", "Amount"]
        assert MigrationImportersService.detect_ehr_system(headers) == "dentrix"

        row = {
            "ChartNumber": "DX-9901",
            "FirstName": "Ford",
            "LastName": "Prefect",
            "BirthDate": "05/14/1979",
            "Gender": "M",
            "CellPhone": "5559876543",
            "EmailAddress": "ford@betelgeuse.com",
            "Address1": "10 Hitchhiker Blvd",
            "City": "New York",
            "State": "NY",
            "PostalCode": "10001",
            "ProcCode": "D1110",
            "Amount": "120.00",
            "Description": "Prophylaxis - Adult",
        }

        record, err = DentrixAdapter.transform_row(row, 2)
        assert err is None
        assert record is not None
        assert record.first_name == "Ford"
        assert record.last_name == "Prefect"
        assert record.date_of_birth == date(1979, 5, 14)
        assert record.gender == Gender.MALE
        assert record.procedures[0].procedure_code == "D1110"
        assert record.procedures[0].fee == Decimal("120.00")

    def test_eaglesoft_adapter_detection_and_transform(self):
        headers = ["PatientID", "FirstName", "LastName", "Birthdate", "Sex", "HomePhone", "ServiceCode", "Fee"]
        assert MigrationImportersService.detect_ehr_system(headers) == "eaglesoft"

        row = {
            "PatientID": "ES-552",
            "FirstName": "Trillian",
            "LastName": "Astra",
            "Birthdate": "1988-12-01",
            "Sex": "F",
            "HomePhone": "555-444-3322",
            "Email": "trillian@magrathea.org",
            "Street": "88 Star Lane",
            "City": "Austin",
            "State": "TX",
            "Zip": "78701",
            "ServiceCode": "D2391",
            "Fee": "210.00",
            "ToothID": "19",
            "Surface": "MOD",
        }

        record, err = EaglesoftAdapter.transform_row(row, 3)
        assert err is None
        assert record is not None
        assert record.first_name == "Trillian"
        assert record.last_name == "Astra"
        assert record.gender == Gender.FEMALE
        assert record.procedures[0].procedure_code == "D2391"
        assert record.procedures[0].surface == "MOD"


@pytest.mark.asyncio
class TestMigrationEndpoints:
    async def test_analyze_dry_run_endpoint(self, async_client: AsyncClient, auth_headers: dict):
        opendental_rows = [
            {
                "PatNum": "OD-01",
                "FName": "Zaphod",
                "LName": "Beeblebrox",
                "Birthdate": "1975-01-01",
                "Gender": "0",
                "WirelessPhone": "555-000-1111",
                "Email": "president@galaxy.gov",
                "ADACode": "D0150",
                "ProcFee": "150.00",
            },
            {
                "PatNum": "OD-02",
                "FName": "Tricia",
                "LName": "McMillan",
                "Birthdate": "1984-07-20",
                "Gender": "1",
                "Email": "tricia@earth.org",
            },
        ]

        response = await async_client.post(
            "/api/v1/migration/analyze",
            headers=auth_headers,
            json={"rows": opendental_rows},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["detected_ehr"] == "opendental"
        assert data["total_rows"] == 2
        assert data["valid_count"] == 2
        assert data["error_count"] == 0
        assert data["total_fees"] == 150.00
        assert len(data["preview"]) == 2

    async def test_execute_migration_endpoint(
        self, async_client: AsyncClient, auth_headers: dict, db_session, test_practice
    ):
        dentrix_rows = [
            {
                "ChartNumber": "DX-7701",
                "FirstName": "Marvin",
                "LastName": "Paranoid",
                "BirthDate": "1960-06-06",
                "Gender": "M",
                "EmailAddress": "marvin.robot@sirius.com",
                "CellPhone": "555-999-8888",
                "ProcCode": "D0210",
                "Amount": "180.00",
                "Description": "Intraoral comprehensive series",
            }
        ]

        response = await async_client.post(
            "/api/v1/migration/execute",
            headers=auth_headers,
            json={"rows": dentrix_rows},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["source_system"] == "dentrix"
        assert data["imported_patients_count"] == 1
        assert data["imported_clinical_records_count"] == 1

        # Verify patient exists in DB
        res = await db_session.execute(
            select(Patient).where(
                Patient.practice_id == test_practice.id,
                Patient.date_of_birth == date(1960, 6, 6),
            )
        )
        patient = res.scalar_one_or_none()
        assert patient is not None
        assert patient.first_name == "Marvin"
        assert patient.last_name == "Paranoid"
        assert patient.search_index_last_name is not None

        # Verify clinical history note was created
        note_res = await db_session.execute(
            select(ClinicalNote).where(ClinicalNote.patient_id == patient.id)
        )
        note = note_res.scalar_one_or_none()
        assert note is not None
        assert "D0210" in (note.content or "")
