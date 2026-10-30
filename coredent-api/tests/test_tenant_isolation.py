"""
Cross-Tenant Isolation Tests
=============================

These tests exist to enforce the security invariant that **a user
belonging to practice A can never read, modify, or delete any resource
belonging to practice B** via any HTTP endpoint.

The ``TenantGuardMiddleware`` provides defense in depth, but the
per-endpoint ``WHERE practice_id = :practice_id`` clauses are the
primary control.  This test suite creates two real practices with
overlapping data (same patient name, same email) and exercises every
endpoint, asserting that the cross-tenant request is rejected with
404 / 403 and never returns the other practice's data.

If a future PR adds a new endpoint without proper tenant scoping, this
file must be extended to cover it.  CI runs this file as a required
job (see ``.github/workflows/ci.yml``).

Run locally:
    cd coredent-api && pytest tests/test_tenant_isolation.py -v
"""
import pytest


pytestmark = pytest.mark.asyncio


# Endpoints we exercise.  We list (method, path_template, payload).  The
# path template is rendered with the other practice's IDs; the body may
# reference the cross-tenant resource.  If the server returns 2xx the
# test fails loudly with the response body attached.
#
# For routes that legitimately accept arbitrary IDs (e.g. ``GET
# /api/v1/patients/{id}``) we substitute the *other* practice's patient
# id and expect 404.  For routes that must NEVER accept a cross-tenant
# id (e.g. ``PUT /api/v1/patients/{id}``), we expect 404 *or* 403.

class TestPatientTenantIsolation:
    async def test_cannot_read_other_practice_patient(
        self, async_client, auth_headers, other_patient
    ):
        """GET /patients/{b_patient_id} as user from practice A → 404."""
        response = await async_client.get(
            f"/api/v1/patients/{other_patient.id}",
            headers=auth_headers,
        )
        assert response.status_code == 404, response.text
        assert other_patient.first_name not in response.text

    async def test_cannot_update_other_practice_patient(
        self, async_client, auth_headers, other_patient
    ):
        """PUT /patients/{b_patient_id} as user from practice A → 404."""
        response = await async_client.put(
            f"/api/v1/patients/{other_patient.id}",
            headers=auth_headers,
            json={
                "first_name": "HACKED",
                "last_name": "INTRUDER",
            },
        )
        assert response.status_code == 404, response.text

    async def test_cannot_delete_other_practice_patient(
        self, async_client, auth_headers, other_patient
    ):
        """DELETE /patients/{b_patient_id} as user from practice A → 404."""
        response = await async_client.delete(
            f"/api/v1/patients/{other_patient.id}",
            headers=auth_headers,
        )
        assert response.status_code == 404, response.text

    async def test_list_does_not_include_other_practice_patients(
        self, async_client, auth_headers, other_patient
    ):
        """GET /patients must not return other_practice's patients."""
        response = await async_client.get(
            "/api/v1/patients",
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        # The response is paginated; look at items.
        body = response.json()
        items = body.get("items", body if isinstance(body, list) else [])
        ids = {p.get("id") for p in items}
        assert str(other_patient.id) not in ids
        # Defensive: name should not appear either.
        body_text = response.text
        assert "Jane" not in body_text or "Smith" not in body_text

    async def test_search_does_not_leak_other_practice(
        self, async_client, auth_headers, other_patient
    ):
        """Searching for a name owned by the other practice returns no hits."""
        response = await async_client.get(
            "/api/v1/patients",
            params={"query": other_patient.last_name},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        items = body.get("items", body if isinstance(body, list) else [])
        ids = {p.get("id") for p in items}
        assert str(other_patient.id) not in ids

    async def test_query_practice_id_mismatch_is_rejected(
        self, async_client, auth_headers, other_practice
    ):
        """Querying ?practice_id={b_practice_id} must be rejected by the tenant guard."""
        response = await async_client.get(
            "/api/v1/patients",
            params={"practice_id": str(other_practice.id)},
            headers=auth_headers,
        )
        # TenantGuardMiddleware should reject with 403, or the endpoint
        # should ignore the param and return only A's data.  Either is
        # acceptable; returning B's data is not.
        assert response.status_code in (200, 403), response.text
        if response.status_code == 200:
            body = response.json()
            items = body.get("items", body if isinstance(body, list) else [])
            # B's patients (created in fixtures) must not appear.
            assert all(
                p.get("practice_id") != str(other_practice.id) for p in items
            )


class TestAppointmentTenantIsolation:
    async def test_cannot_read_other_practice_appointment(
        self, async_client, auth_headers, other_appointment
    ):
        response = await async_client.get(
            f"/api/v1/appointments/{other_appointment.id}",
            headers=auth_headers,
        )
        assert response.status_code == 404, response.text


class TestBillingTenantIsolation:
    async def test_cannot_list_other_practice_invoices(
        self, async_client, auth_headers, other_practice
    ):
        response = await async_client.get(
            "/api/v1/billing/invoices/",
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        items = body.get("invoices", body if isinstance(body, list) else [])
        for inv in items:
            assert inv.get("practice_id") != str(other_practice.id), (
                f"Invoice from other practice leaked: {inv}"
            )

    async def test_cannot_read_other_practice_invoice(
        self, async_client, auth_headers, other_practice, other_patient, db_session
    ):
        """Create an invoice in the other practice directly, then try to read it."""
        from app.models.billing import Invoice, InvoiceStatus
        from decimal import Decimal
        import uuid as uuid_lib
        import datetime

        inv = Invoice(
            id=uuid_lib.uuid4(),
            practice_id=other_practice.id,
            # Must be a real patient. This was uuid_lib.uuid4() with the comment
            # "arbitrary", which SQLite accepts because it does not enforce
            # foreign keys by default and PostgreSQL rejects with
            # ForeignKeyViolationError on invoices_patient_id_fkey.
            patient_id=other_patient.id,
            invoice_number=f"INV-X-{uuid_lib.uuid4().hex[:6]}",
            status=InvoiceStatus.PENDING,
            subtotal=Decimal("10.00"),
            tax=Decimal("0"),
            total=Decimal("10.00"),
            line_items=[],
            created_at=datetime.datetime.utcnow(),
        )
        db_session.add(inv)
        await db_session.commit()

        response = await async_client.get(
            f"/api/v1/billing/invoices/{inv.id}",
            headers=auth_headers,
        )
        assert response.status_code == 404, response.text

    async def test_cannot_create_invoice_for_other_practice_patient(
        self, async_client, auth_headers, other_patient
    ):
        """POST /billing/invoices/ against the other practice's patient → 404.

        Invoices are tenant-scoped by the patient's practice; the patient
        existence check must not resolve across practices.
        """
        response = await async_client.post(
            "/api/v1/billing/invoices/",
            headers=auth_headers,
            json={
                "patient_id": str(other_patient.id),
                "line_items": [
                    {
                        "description": "X-Ray",
                        "quantity": 1,
                        "unit_price": "100.00",
                        "total": "100.00",
                    }
                ],
                "tax_rate": "0.0",
            },
        )
        assert response.status_code == 404, response.text


class TestStaffTenantIsolation:
    async def test_cannot_list_other_practice_staff(
        self, async_client, auth_headers, other_user
    ):
        response = await async_client.get(
            "/api/v1/staff/",
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        items = body if isinstance(body, list) else body.get("items", [])
        ids = {u.get("id") for u in items}
        assert str(other_user.id) not in ids

    async def test_cannot_update_other_practice_staff(
        self, async_client, auth_headers, other_user
    ):
        response = await async_client.put(
            f"/api/v1/staff/{other_user.id}",
            headers=auth_headers,
            json={"first_name": "HACKED"},
        )
        assert response.status_code == 404, response.text

    async def test_cannot_inactivate_other_practice_staff(
        self, async_client, auth_headers, other_user
    ):
        response = await async_client.delete(
            f"/api/v1/staff/{other_user.id}",
            headers=auth_headers,
        )
        assert response.status_code == 404, response.text


class TestUnauthenticatedIsolation:
    """Without any auth header, no PHI should leak regardless of practice."""

    async def test_unauthenticated_patient_get_is_401(self, async_client, test_patient):
        response = await async_client.get(f"/api/v1/patients/{test_patient.id}")
        assert response.status_code == 401

    async def test_unauthenticated_patient_list_is_401(self, async_client):
        response = await async_client.get("/api/v1/patients")
        assert response.status_code == 401
