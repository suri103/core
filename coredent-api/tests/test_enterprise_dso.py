"""
Tests for DSO Multi-Location View (Pillar 4)
Consolidated roll-up reporting, AR aging, provider productivity,
context switcher, and cross-clinic patient lookup.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.search_index import update_patient_search_indexes
from app.core.security import create_access_token
from app.models.appointment import Appointment, AppointmentStatus, AppointmentTypeEnum, Chair
from app.models.billing import Invoice, InvoiceStatus, Payment, PaymentMethod, PaymentStatus
from app.models.patient import Gender, Patient, PatientStatus
from app.models.practice import Practice, PracticeGroup
from app.models.user import User, UserRole


@pytest.mark.asyncio
class TestDsoMultiLocationView:
    async def test_dso_full_lifecycle(
        self, async_client: AsyncClient, db_session
    ):
        # 1. Setup Practice Group & Practices
        group = PracticeGroup(
            name="Apex Dental Partners DSO",
            address_city="Austin",
            address_state="TX",
        )
        db_session.add(group)
        await db_session.flush()

        clinic_a = Practice(
            name="Apex Downtown Dental",
            public_slug="apex-downtown",
            group_id=group.id,
            address_city="Austin",
            address_state="TX",
        )
        clinic_b = Practice(
            name="Apex North Hills Dental",
            public_slug="apex-north-hills",
            group_id=group.id,
            address_city="Round Rock",
            address_state="TX",
        )
        db_session.add_all([clinic_a, clinic_b])
        await db_session.flush()

        chair_a1 = Chair(practice_id=clinic_a.id, name="Op 1")
        chair_a2 = Chair(practice_id=clinic_a.id, name="Op 2")
        chair_b1 = Chair(practice_id=clinic_b.id, name="Op 1")
        chair_b2 = Chair(practice_id=clinic_b.id, name="Op 2")
        chair_b3 = Chair(practice_id=clinic_b.id, name="Op 3")
        db_session.add_all([chair_a1, chair_a2, chair_b1, chair_b2, chair_b3])
        await db_session.flush()

        # 2. Setup Group Owner & Providers
        group_owner = User(
            email="owner@apexdental.com",
            first_name="Victoria",
            last_name="Sterling",
            role=UserRole.GROUP_OWNER,
            practice_id=clinic_a.id,
            password_hash="fakehash",
            is_active=True,
        )
        dentist_a = User(
            email="dentist.a@apexdental.com",
            first_name="Marcus",
            last_name="Brody",
            role=UserRole.DENTIST,
            practice_id=clinic_a.id,
            password_hash="fakehash",
            is_active=True,
        )
        dentist_b = User(
            email="dentist.b@apexdental.com",
            first_name="Elena",
            last_name="Rostova",
            role=UserRole.DENTIST,
            practice_id=clinic_b.id,
            password_hash="fakehash",
            is_active=True,
        )
        db_session.add_all([group_owner, dentist_a, dentist_b])
        await db_session.flush()

        # 3. Setup Patients
        patient_a = Patient(
            practice_id=clinic_a.id,
            first_name="John",
            last_name="Connor",
            date_of_birth=date(1985, 2, 28),
            gender=Gender.MALE,
            email="john.connor@resistance.net",
            phone="555-019-2831",
            status=PatientStatus.ACTIVE,
        )
        patient_b = Patient(
            practice_id=clinic_b.id,
            first_name="Sarah",
            last_name="Connor",
            date_of_birth=date(1965, 11, 10),
            gender=Gender.FEMALE,
            email="sarah.connor@resistance.net",
            phone="555-019-9999",
            status=PatientStatus.ACTIVE,
        )
        update_patient_search_indexes(patient_a, "email", "phone", "last_name")
        update_patient_search_indexes(patient_b, "email", "phone", "last_name")
        db_session.add_all([patient_a, patient_b])
        await db_session.flush()

        # 4. Invoices & Payments (Clinic A: $500 total, $300 paid -> $200 AR; Clinic B: $800 total, $800 paid -> $0 AR)
        inv_a = Invoice(
            practice_id=clinic_a.id,
            patient_id=patient_a.id,
            invoice_number="INV-A-101",
            subtotal=Decimal("500.00"),
            total=Decimal("500.00"),
            line_items=[{"description": "Crown", "quantity": 1, "unit_price": 500, "total": 500}],
            status=InvoiceStatus.PARTIALLY_PAID,
            due_date=date.today() - timedelta(days=45),  # 31-60 aging bucket
        )
        db_session.add(inv_a)
        await db_session.flush()

        pay_a = Payment(
            practice_id=clinic_a.id,
            invoice_id=inv_a.id,
            patient_id=patient_a.id,
            amount=Decimal("300.00"),
            payment_method=PaymentMethod.CARD,
            status=PaymentStatus.COMPLETED,
            transaction_id="TX-A-300",
        )
        db_session.add(pay_a)

        inv_b = Invoice(
            practice_id=clinic_b.id,
            patient_id=patient_b.id,
            invoice_number="INV-B-201",
            subtotal=Decimal("800.00"),
            total=Decimal("800.00"),
            line_items=[{"description": "Root Canal", "quantity": 1, "unit_price": 800, "total": 800}],
            status=InvoiceStatus.PAID,
            due_date=date.today() - timedelta(days=10),
        )
        db_session.add(inv_b)
        await db_session.flush()

        pay_b = Payment(
            practice_id=clinic_b.id,
            invoice_id=inv_b.id,
            patient_id=patient_b.id,
            amount=Decimal("800.00"),
            payment_method=PaymentMethod.INSURANCE,
            status=PaymentStatus.COMPLETED,
            transaction_id="TX-B-800",
        )
        db_session.add(pay_b)

        # 5. Completed Appointments for Provider Leaderboard
        appt_a = Appointment(
            practice_id=clinic_a.id,
            patient_id=patient_a.id,
            provider_id=dentist_a.id,
            appointment_type=AppointmentTypeEnum.CROWN,
            status=AppointmentStatus.COMPLETED,
            start_time=datetime.now(timezone.utc) - timedelta(days=2),
            end_time=datetime.now(timezone.utc) - timedelta(days=2, hours=-1),
            duration=60,
        )
        appt_b = Appointment(
            practice_id=clinic_b.id,
            patient_id=patient_b.id,
            provider_id=dentist_b.id,
            appointment_type=AppointmentTypeEnum.ROOT_CANAL,
            status=AppointmentStatus.COMPLETED,
            start_time=datetime.now(timezone.utc) - timedelta(days=1),
            end_time=datetime.now(timezone.utc) - timedelta(days=1, hours=-1),
            duration=60,
        )
        db_session.add_all([appt_a, appt_b])
        await db_session.commit()

        # Build JWT auth headers for GROUP_OWNER
        owner_token = create_access_token({
            "sub": str(group_owner.id),
            "role": UserRole.GROUP_OWNER.value,
            "practice_id": str(clinic_a.id),
        })
        auth_headers = {
            "Authorization": f"Bearer {owner_token}",
            "X-CSRF-Token": "test-csrf",
        }
        async_client.cookies.set("csrf_token", "test-csrf")

        # ── Test 1: GET /api/v1/enterprise/dso/overview ──
        res_overview = await async_client.get("/api/v1/enterprise/dso/overview", headers=auth_headers)
        assert res_overview.status_code == 200
        overview = res_overview.json()
        assert overview["group_id"] == str(group.id)
        assert overview["total_clinics"] == 2
        # Financials: Total Production = 500 + 800 = 1300; Collections = 300 + 800 = 1100; AR = 200
        assert overview["financials"]["total_production"] == 1300.00
        assert overview["financials"]["total_collections"] == 1100.00
        assert overview["financials"]["total_outstanding_ar"] == 200.00
        assert overview["ar_aging"]["days_31_60"] == 200.00
        assert len(overview["locations"]) == 2
        assert len(overview["provider_leaderboard"]) >= 2

        # ── Test 2: GET /api/v1/enterprise/dso/clinics ──
        res_clinics = await async_client.get("/api/v1/enterprise/dso/clinics", headers=auth_headers)
        assert res_clinics.status_code == 200
        clinics = res_clinics.json()
        assert len(clinics) == 2
        clinic_names = [c["name"] for c in clinics]
        assert "Apex Downtown Dental" in clinic_names
        assert "Apex North Hills Dental" in clinic_names

        # ── Test 3: POST /api/v1/enterprise/dso/switch-context ──
        res_switch = await async_client.post(
            "/api/v1/enterprise/dso/switch-context",
            headers=auth_headers,
            json={"target_practice_id": str(clinic_b.id)},
        )
        assert res_switch.status_code == 200
        switched = res_switch.json()
        assert switched["success"] is True
        assert switched["active_practice_id"] == str(clinic_b.id)
        assert switched["active_practice_name"] == "Apex North Hills Dental"
        assert "access_token" in switched

        # ── Test 4: GET /api/v1/enterprise/dso/patients/search ──
        # Search for "Connor" across clinics
        res_search = await async_client.get(
            "/api/v1/enterprise/dso/patients/search?q=Connor",
            headers=auth_headers,
        )
        assert res_search.status_code == 200
        patients_found = res_search.json()
        assert len(patients_found) >= 2
        found_pids = {p["practice_id"] for p in patients_found}
        assert str(clinic_a.id) in found_pids
        assert str(clinic_b.id) in found_pids
