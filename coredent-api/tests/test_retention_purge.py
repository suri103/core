"""Tests for the scheduled hard purge of anonymized patients.

Covers docs/DATA_RETENTION_POLICY.md § 2: the purge only fires for
fully-anonymized marker rows whose last billing disposition is past the
retention window; explicit deletes (payment cards, plans, portal sessions)
run before the ORM cascade; every purge writes a write-once patient_purged
audit row (certificate of destruction).
"""
import datetime

import pytest

pytestmark = pytest.mark.asyncio


class TestRetentionPurgeEligibility:
    """Pure eligibility logic (no DB needed)."""

    def test_past_window_is_eligible(self):
        from app.services.retention_service import RetentionService

        anchor = datetime.datetime(2010, 1, 1, tzinfo=datetime.timezone.utc)
        now = datetime.datetime(2020, 1, 2, tzinfo=datetime.timezone.utc)
        assert RetentionService.is_eligible_for_purge(
            anchor, now=now, retention_years=7
        )

    def test_recent_anchor_is_not_eligible(self):
        from app.services.retention_service import RetentionService

        now = datetime.datetime(2026, 9, 11, tzinfo=datetime.timezone.utc)
        anchor = now - datetime.timedelta(days=365)
        assert not RetentionService.is_eligible_for_purge(
            anchor, now=now, retention_years=7
        )

    def test_missing_anchor_is_never_eligible(self):
        from app.services.retention_service import RetentionService

        now = datetime.datetime(2026, 9, 11, tzinfo=datetime.timezone.utc)
        assert not RetentionService.is_eligible_for_purge(
            None, now=now, retention_years=7
        )



class TestRetentionPurgeHappyPath:
    """Full purge of an old anonymized patient with billing history."""

    async def test_purges_anonymized_patient_past_window(
        self, async_client, db_session, test_practice, test_user
    ):
        from decimal import Decimal

        from app.models.patient import Patient, PatientStatus
        from app.models.billing import Invoice, InvoiceStatus, Payment, PaymentMethod, PaymentStatus
        from app.services.retention_service import RetentionService
        import uuid as uuid_lib

        # Anonymized marker row (exactly what POST /patients/{id}/anonymize writes).
        patient = Patient(
            id=uuid_lib.uuid4(),
            practice_id=test_practice.id,
            first_name="[deleted]",
            last_name="[deleted]",
            date_of_birth=datetime.date(1970, 1, 1),
            status=PatientStatus.INACTIVE,
        )
        db_session.add(patient)
        await db_session.flush()

        # Old invoice + old payment (8 years ago, past the 7y default).
        old_year = datetime.datetime(2018, 3, 4, tzinfo=datetime.timezone.utc)
        invoice = Invoice(
            id=uuid_lib.uuid4(),
            practice_id=test_practice.id,
            patient_id=patient.id,
            invoice_number="INV-R1",
            status=InvoiceStatus.PAID,
            subtotal=Decimal("100.00"),
            tax=Decimal("0"),
            total=Decimal("100.00"),
            line_items=[{"description": "Cleaning", "quantity": 1, "unit_price": 100.0, "total": 100.0}],
            created_at=old_year,
            updated_at=old_year,
        )
        db_session.add(invoice)
        await db_session.flush()
        payment = Payment(
            id=uuid_lib.uuid4(),
            invoice_id=invoice.id,
            patient_id=patient.id,
            practice_id=test_practice.id,
            amount=Decimal("100.00"),
            refunded_amount=Decimal("0"),
            payment_method=PaymentMethod.CASH,
            transaction_id="TXN-PURGE-1",
            status=PaymentStatus.COMPLETED,
            created_at=old_year,
        )
        db_session.add(payment)
        await db_session.commit()

        anchor = await RetentionService.billing_anchor_async(db_session, patient)
        assert anchor is not None
        now = datetime.datetime(2026, 9, 11, tzinfo=datetime.timezone.utc)
        assert RetentionService.is_eligible_for_purge(anchor, now=now, retention_years=7)

        eligible = await RetentionService.eligible_anonymized_patients(
            db_session, now=now, retention_years=7, limit=1000
        )
        assert any(e["patient_id"] == patient.id for e in eligible)

        result = await RetentionService.purge_patient_hard_async(db_session, patient)
        await db_session.commit()
        assert result["practice_id"] == str(test_practice.id)
        assert result["deleted"]["patients"] == 1

        # Marker row + invoice + payment are gone.
        remaining = await db_session.get(Patient, patient.id)
        assert remaining is None
        inv = await db_session.get(Invoice, invoice.id)
        assert inv is None
        pay = await db_session.get(Payment, payment.id)
        assert pay is None

    async def test_recently_anonymized_patient_is_not_purged(
        self, db_session, test_practice
    ):
        from app.models.patient import Patient, PatientStatus
        from app.services.retention_service import RetentionService
        import uuid as uuid_lib

        patient = Patient(
            id=uuid_lib.uuid4(),
            practice_id=test_practice.id,
            first_name="[deleted]",
            last_name="[deleted]",
            date_of_birth=datetime.date(1970, 1, 1),
            status=PatientStatus.INACTIVE,
            updated_at=datetime.datetime.now(datetime.timezone.utc),
        )
        db_session.add(patient)
        await db_session.commit()

        now = datetime.datetime(2026, 9, 11, tzinfo=datetime.timezone.utc)
        eligible = await RetentionService.eligible_anonymized_patients(
            db_session, now=now, retention_years=7, limit=1000
        )
        assert all(e["patient_id"] != patient.id for e in eligible)


class TestPerPracticeRetentionOverride:
    """practices.retention_years extends (never shortens) the platform floor."""

    async def test_null_practice_uses_platform_default(self, db_session, test_practice):
        from app.services.retention_service import RetentionService

        assert test_practice.retention_years is None
        got = await RetentionService.effective_retention_years(
            db_session, test_practice.id, platform_default=7
        )
        assert got == 7

    async def test_longer_practice_window_extends(self, db_session, test_practice):
        from app.services.retention_service import RetentionService

        test_practice.retention_years = 10
        db_session.add(test_practice)
        await db_session.commit()

        got = await RetentionService.effective_retention_years(
            db_session, test_practice.id, platform_default=7
        )
        assert got == 10

    async def test_shorter_practice_window_cannot_below_floor(
        self, db_session, test_practice
    ):
        from app.services.retention_service import RetentionService

        # A misconfigured practice (3y) must not shorten below the 7y floor.
        test_practice.retention_years = 3
        db_session.add(test_practice)
        await db_session.commit()

        got = await RetentionService.effective_retention_years(
            db_session, test_practice.id, platform_default=7
        )
        assert got == 7

    async def test_extended_window_defers_purge(
        self, db_session, test_practice
    ):
        """An 8y-old anchor with a 10y practice override must NOT purge."""
        import uuid as uuid_lib
        from app.models.patient import Patient, PatientStatus
        from app.services.retention_service import RetentionService

        test_practice.retention_years = 10
        db_session.add(test_practice)
        await db_session.commit()

        patient = Patient(
            id=uuid_lib.uuid4(),
            practice_id=test_practice.id,
            first_name="[deleted]",
            last_name="[deleted]",
            date_of_birth=datetime.date(1970, 1, 1),
            status=PatientStatus.INACTIVE,
            # 8.7 years before "now" (2026-09-11): eligible under the 7y floor
            # but NOT yet under the 10y practice override (window = 2028-01-01).
            updated_at=datetime.datetime(2018, 1, 1, tzinfo=datetime.timezone.utc),
        )
        db_session.add(patient)
        await db_session.commit()

        # 2026-09-11 vs 2016-01-01 anchor: eligible under 7y (default) but NOT
        # under the 10y practice override.
        now = datetime.datetime(2026, 9, 11, tzinfo=datetime.timezone.utc)
        eligible = await RetentionService.eligible_anonymized_patients(
            db_session, now=now, retention_years=7, limit=1000
        )
        assert all(e["patient_id"] != patient.id for e in eligible)


class TestPracticeJurisdictionEndpoint:
    """Settings API exposes + persists the jurisdiction pick for the preset picker."""

    async def test_settings_expose_and_persist_jurisdiction(
        self, async_client, auth_headers
    ):
        headers = auth_headers

        # Default: none picked -> null.
        resp = await async_client.get("/api/v1/settings/", headers=headers)
        assert resp.status_code == 200, resp.text
        assert "jurisdiction" in resp.json()
        assert resp.json()["jurisdiction"] is None

        # PUT a pick plus retention years together.
        put = await async_client.put(
            "/api/v1/settings/",
            headers=headers,
            json={"jurisdiction": "CA", "retentionYears": 7},
        )
        assert put.status_code == 200, put.text
        assert put.json()["jurisdiction"] == "CA"
        assert put.json()["retentionYears"] == 7

        # READ it back.
        re_get = await async_client.get("/api/v1/settings/", headers=headers)
        assert re_get.status_code == 200
        assert re_get.json()["jurisdiction"] == "CA"

        # Explicit null clears the pick.
        clear = await async_client.put(
            "/api/v1/settings/", headers=headers, json={"jurisdiction": None}
        )
        assert clear.status_code == 200, clear.text
        assert clear.json()["jurisdiction"] is None

    async def test_jurisdiction_schema_rejects_too_short(
        self, async_client, auth_headers
    ):
        resp = await async_client.put(
            "/api/v1/settings/", headers=auth_headers, json={"jurisdiction": "C"}
        )
        assert resp.status_code == 422


class TestPracticeRetentionSettingsEndpoint:
    """Settings API exposes + persists the per-practice retention override."""

    async def test_settings_expose_and_persist_retention_years(
        self, async_client, auth_headers
    ):
        """GET /settings returns retentionYears; PUT persists it (owner only)."""
        headers = auth_headers
        resp = await async_client.get("/api/v1/settings/", headers=headers)
        assert resp.status_code == 200, resp.text
        assert "retentionYears" in resp.json()

        # PUT a 10-year override.
        put = await async_client.put(
            "/api/v1/settings/",
            headers=headers,
            json={"retentionYears": 10},
        )
        assert put.status_code == 200, put.text
        assert put.json()["retentionYears"] == 10

        # READ it back.
        re_get = await async_client.get("/api/v1/settings/", headers=headers)
        assert re_get.status_code == 200
        assert re_get.json()["retentionYears"] == 10

        # Explicit null clears the override.
        clear = await async_client.put(
            "/api/v1/settings/", headers=headers, json={"retentionYears": None}
        )
        assert clear.status_code == 200, clear.text
        assert clear.json()["retentionYears"] is None

    async def test_retention_years_schema_rejects_out_of_range(
        self, async_client, auth_headers
    ):
        resp = await async_client.put(
            "/api/v1/settings/",
            headers=auth_headers,
            json={"retentionYears": 250},
        )
        assert resp.status_code == 422


class TestMinorRetentionEndpoints:
    """Settings API exposes + persists majorityAge / minorRetentionYears."""

    async def test_settings_expose_and_persist_minor_window(
        self, async_client, auth_headers
    ):
        headers = auth_headers
        resp = await async_client.get("/api/v1/settings/", headers=headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["majorityAge"] == 18   # platform default
        assert resp.json()["minorRetentionYears"] == 7

        put = await async_client.put(
            "/api/v1/settings/",
            headers=headers,
            json={"majorityAge": 19, "minorRetentionYears": 10},
        )
        assert put.status_code == 200, put.text
        assert put.json()["majorityAge"] == 19
        assert put.json()["minorRetentionYears"] == 10

    async def test_minor_window_schema_validation(
        self, async_client, auth_headers
    ):
        # majorityAge out of range -> 422
        bad = await async_client.put(
            "/api/v1/settings/", headers=auth_headers, json={"majorityAge": 5}
        )
        assert bad.status_code == 422
        # negative minor years -> 422
        bad2 = await async_client.put(
            "/api/v1/settings/",
            headers=auth_headers,
            json={"minorRetentionYears": -1},
        )
        assert bad2.status_code == 422


class TestMinorCeilingLogic:
    """_compute_minor_ceiling_utc (anonymize snapshot helper). Pure logic."""

    async def test_minor_ceiling_far_future_blocks_adult_purge(self):
        from app.api.v1.endpoints.patients import _compute_minor_ceiling_utc
        from app.services.retention_service import RetentionService

        dob = datetime.date(2010, 5, 20)
        ceiling = _compute_minor_ceiling_utc(dob, majority_age=18, minor_retention_years=7)
        assert ceiling is not None
        assert ceiling.year == 2035  # 2010 + 18 + 7

        # Adult window (7y from anchor 2018) has long elapsed by "now", but the
        # minor ceiling (2035) hasn't, so the record must NOT purge.
        now = datetime.datetime(2026, 9, 11, tzinfo=datetime.timezone.utc)
        anchor = datetime.datetime(2018, 3, 4, tzinfo=datetime.timezone.utc)
        assert RetentionService.is_eligible_for_purge(
            anchor, now=now, retention_years=7
        ) is True  # adult alone would allow
        assert RetentionService.is_eligible_for_purge(
            anchor, now=now, retention_years=7, purge_eligible_at=ceiling
        ) is False  # minor ceiling blocks

    async def test_minor_ceiling_past_allows_purge(self):
        from app.api.v1.endpoints.patients import _compute_minor_ceiling_utc
        from app.services.retention_service import RetentionService

        dob = datetime.date(1985, 1, 1)
        ceiling = _compute_minor_ceiling_utc(dob, majority_age=18, minor_retention_years=7)
        # 1985 + 18 + 7 = 2010 -> long past.
        now = datetime.datetime(2026, 9, 11, tzinfo=datetime.timezone.utc)
        anchor = datetime.datetime(2015, 1, 1, tzinfo=datetime.timezone.utc)
        assert RetentionService.is_eligible_for_purge(
            anchor, now=now, retention_years=7, purge_eligible_at=ceiling
        ) is True

    async def test_leap_day_dob_snaps_to_feb_28(self):
        from app.api.v1.endpoints.patients import _compute_minor_ceiling_utc

        dob = datetime.date(2000, 2, 29)
        ceiling = _compute_minor_ceiling_utc(dob, majority_age=18, minor_retention_years=7)
        # 2000+18+7 = 2025 (not a leap year) -> snap to 2025-02-28
        assert ceiling is not None
        assert ceiling.month == 2
        assert ceiling.day == 28
        assert ceiling.year == 2025

    async def test_minor_ceiling_uses_practice_override(self):
        from app.api.v1.endpoints.patients import _compute_minor_ceiling_utc
        from app.services.retention_service import RetentionService

        dob = datetime.date(2010, 5, 20)
        ceiling = _compute_minor_ceiling_utc(dob, majority_age=19, minor_retention_years=10)
        # 2010 + 19 + 10 = 2039
        assert ceiling is not None
        assert ceiling.year == 2039
        now = datetime.datetime(2026, 9, 11, tzinfo=datetime.timezone.utc)
        anchor = datetime.datetime(2018, 3, 4, tzinfo=datetime.timezone.utc)
        assert RetentionService.is_eligible_for_purge(
            anchor, now=now, retention_years=7, purge_eligible_at=ceiling
        ) is False


class TestRetentionPurgeAsyncShape:
    """The async purge path shares sync ordering; exercise it on a fresh marker."""

    async def test_async_purge_removes_marker_patient(
        self, db_session, test_practice
    ):
        from app.models.patient import Patient, PatientStatus
        from app.services.retention_service import RetentionService
        import uuid as uuid_lib

        marker = Patient(
            id=uuid_lib.uuid4(),
            practice_id=test_practice.id,
            first_name="[deleted]",
            last_name="[deleted]",
            date_of_birth=datetime.date(1970, 1, 1),
            status=PatientStatus.INACTIVE,
        )
        db_session.add(marker)
        await db_session.flush()

        result = await RetentionService.purge_patient_hard_async(db_session, marker)
        await db_session.commit()
        assert result["deleted"]["patients"] == 1
        assert await db_session.get(Patient, marker.id) is None


class TestPurgeTaskEntryPoint:
    """The scheduled Celery task itself, not just RetentionService.

    Regression guard: the task body referenced an undefined ``Patient`` name,
    so every scheduled run raised NameError and the nightly purge silently did
    nothing — while every service-level test above stayed green. Only invoking
    the task entry point catches that class of defect.
    """

    async def test_task_purges_eligible_patient(self, db_session, test_practice):
        from decimal import Decimal
        import uuid as uuid_lib

        from app.core.tasks import purge_expired_anonymized_patients
        from app.models.billing import (
            Invoice,
            InvoiceStatus,
            Payment,
            PaymentMethod,
            PaymentStatus,
        )
        from app.models.patient import Patient, PatientStatus

        patient = Patient(
            id=uuid_lib.uuid4(),
            practice_id=test_practice.id,
            first_name="[deleted]",
            last_name="[deleted]",
            date_of_birth=datetime.date(1970, 1, 1),
            status=PatientStatus.INACTIVE,
        )
        old = datetime.datetime(2018, 3, 4, tzinfo=datetime.timezone.utc)
        invoice = Invoice(
            id=uuid_lib.uuid4(),
            practice_id=test_practice.id,
            patient_id=patient.id,
            invoice_number="INV-TASK-1",
            status=InvoiceStatus.PAID,
            subtotal=Decimal("100.00"),
            tax=Decimal("0"),
            total=Decimal("100.00"),
            line_items=[
                {
                    "description": "Cleaning",
                    "quantity": 1,
                    "unit_price": 100.0,
                    "total": 100.0,
                }
            ],
            created_at=old,
            updated_at=old,
        )
        payment = Payment(
            id=uuid_lib.uuid4(),
            invoice_id=invoice.id,
            patient_id=patient.id,
            practice_id=test_practice.id,
            amount=Decimal("100.00"),
            refunded_amount=Decimal("0"),
            payment_method=PaymentMethod.CASH,
            transaction_id="TXN-TASK-1",
            status=PaymentStatus.COMPLETED,
            created_at=old,
        )
        db_session.add_all([patient, invoice, payment])
        await db_session.commit()

        # Capture plain ids: expire_all() below expires the ORM instances, and
        # touching an expired attribute outside a greenlet raises MissingGreenlet.
        patient_id, invoice_id, payment_id = patient.id, invoice.id, payment.id

        # Invoked synchronously; the task opens its own sync session.
        result = purge_expired_anonymized_patients()

        assert result["purged"] >= 1
        assert result["scanned"] >= 1

        # The task committed on a different session, so drop this session's
        # identity map before re-reading.
        db_session.expire_all()
        assert await db_session.get(Patient, patient_id) is None
        assert await db_session.get(Invoice, invoice_id) is None
        assert await db_session.get(Payment, payment_id) is None

    async def test_task_is_disabled_by_setting(self, db_session, monkeypatch):
        """RETENTION_ANONYMIZED_PURGE_ENABLED=false short-circuits the task."""
        from app.core.config_simple import settings
        from app.core.tasks import purge_expired_anonymized_patients

        monkeypatch.setattr(settings, "RETENTION_ANONYMIZED_PURGE_ENABLED", False)
        result = purge_expired_anonymized_patients()
        assert result["status"] == "skipped"

    async def test_task_purges_patient_with_portal_access_code(self, db_session, test_practice):
        """Purge successfully deletes PatientPortalAccessCode rows without FK violation (C5)."""
        from decimal import Decimal
        import uuid as uuid_lib
        from app.core.tasks import purge_expired_anonymized_patients
        from app.models.billing import Invoice, InvoiceStatus, Payment, PaymentMethod, PaymentStatus
        from app.models.patient import Patient, PatientStatus, PatientPortalAccessCode

        patient = Patient(
            id=uuid_lib.uuid4(),
            practice_id=test_practice.id,
            first_name="[deleted]",
            last_name="[deleted]",
            date_of_birth=datetime.date(1970, 1, 1),
            status=PatientStatus.INACTIVE,
        )
        old = datetime.datetime(2018, 3, 4, tzinfo=datetime.timezone.utc)
        invoice = Invoice(
            id=uuid_lib.uuid4(),
            practice_id=test_practice.id,
            patient_id=patient.id,
            invoice_number="INV-PAC-1",
            status=InvoiceStatus.PAID,
            subtotal=Decimal("100.00"),
            tax=Decimal("0"),
            total=Decimal("100.00"),
            line_items=[{"description": "Cleaning", "quantity": 1, "unit_price": 100.0, "total": 100.0}],
            created_at=old,
            updated_at=old,
        )
        payment = Payment(
            id=uuid_lib.uuid4(),
            invoice_id=invoice.id,
            patient_id=patient.id,
            practice_id=test_practice.id,
            amount=Decimal("100.00"),
            refunded_amount=Decimal("0"),
            payment_method=PaymentMethod.CASH,
            transaction_id="TXN-PAC-1",
            status=PaymentStatus.COMPLETED,
            created_at=old,
        )
        access_code = PatientPortalAccessCode(
            id=uuid_lib.uuid4(),
            patient_id=patient.id,
            practice_id=test_practice.id,
            token_hash="pac_hash_test_123",
            expires_at=old,
        )
        db_session.add_all([patient, invoice, payment, access_code])
        await db_session.commit()

        patient_id, access_code_id = patient.id, access_code.id
        result = purge_expired_anonymized_patients()
        assert result["purged"] >= 1

        db_session.expire_all()
        assert await db_session.get(Patient, patient_id) is None
        assert await db_session.get(PatientPortalAccessCode, access_code_id) is None

    async def test_batch_savepoint_resilience(self, db_session, test_practice, monkeypatch):
        """Failure on one patient rolls back via savepoint without aborting the batch."""
        from decimal import Decimal
        import uuid as uuid_lib
        from app.core.tasks import purge_expired_anonymized_patients
        from app.models.billing import Invoice, InvoiceStatus
        from app.models.patient import Patient, PatientStatus
        from app.services.retention_service import RetentionService

        old = datetime.datetime(2018, 3, 4, tzinfo=datetime.timezone.utc)
        p1 = Patient(
            id=uuid_lib.uuid4(),
            practice_id=test_practice.id,
            first_name="[deleted]",
            last_name="[deleted]",
            date_of_birth=datetime.date(1970, 1, 1),
            status=PatientStatus.INACTIVE,
        )
        inv1 = Invoice(
            id=uuid_lib.uuid4(),
            practice_id=test_practice.id,
            patient_id=p1.id,
            invoice_number="INV-FAIL-1",
            status=InvoiceStatus.PAID,
            subtotal=Decimal("50.00"),
            total=Decimal("50.00"),
            tax=Decimal("0"),
            line_items=[{"description": "Exam", "quantity": 1, "unit_price": 50.0, "total": 50.0}],
            created_at=old,
            updated_at=old,
        )
        p2 = Patient(
            id=uuid_lib.uuid4(),
            practice_id=test_practice.id,
            first_name="[deleted]",
            last_name="[deleted]",
            date_of_birth=datetime.date(1970, 1, 1),
            status=PatientStatus.INACTIVE,
        )
        inv2 = Invoice(
            id=uuid_lib.uuid4(),
            practice_id=test_practice.id,
            patient_id=p2.id,
            invoice_number="INV-SUCC-2",
            status=InvoiceStatus.PAID,
            subtotal=Decimal("50.00"),
            total=Decimal("50.00"),
            tax=Decimal("0"),
            line_items=[{"description": "Exam", "quantity": 1, "unit_price": 50.0, "total": 50.0}],
            created_at=old,
            updated_at=old,
        )
        db_session.add_all([p1, inv1, p2, inv2])
        await db_session.commit()

        orig_purge = RetentionService.purge_patient_hard
        def _mock_purge(db, patient):
            if patient.id == p1.id:
                raise RuntimeError("Simulated failure for p1")
            return orig_purge(db, patient)

        monkeypatch.setattr(RetentionService, "purge_patient_hard", _mock_purge)

        p1_id, p2_id = p1.id, p2.id
        result = purge_expired_anonymized_patients()

        assert result["purged"] >= 1
        db_session.expire_all()
        assert await db_session.get(Patient, p1_id) is not None
        assert await db_session.get(Patient, p2_id) is None


