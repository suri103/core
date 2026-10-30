"""Tests for Phase-1 production gaps: refunds, ACCOUNTANT role, platform console.

Covers:
- POST /billing/payments/{id}/refund â€” happy path (full + partial), over-refund
  rejection, cross-tenant 404, role gating.
- ACCOUNTANT role access to billing + reports, denial on clinic-scoped reads.
- /platform/* super-admin console â€” SUPER_ADMIN access, OWNER denial (403),
  clinic suspend/reactivate + login block for suspended clinics.
"""
import datetime
from decimal import Decimal

import pytest

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_invoice(client, headers, patient_id, total="100.00"):
    resp = await client.post(
        "/api/v1/billing/invoices/",
        headers=headers,
        json={
            "patient_id": str(patient_id),
            "line_items": [
                {
                    "description": "Cleaning",
                    "quantity": 1,
                    "unit_price": float(total),
                    "total": float(total),
                }
            ],
            "status": "pending",
        },
    )
    # POST /invoices/ returns 200 (not 201) in this API's contract.
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _pay_invoice(client, headers, invoice, amount):
    resp = await client.post(
        "/api/v1/billing/payments/",
        headers=headers,
        json={
            "invoice_id": invoice["id"],
            "patient_id": invoice["patient_id"],
            "amount": float(amount),
            "payment_method": "cash",
            "transaction_id": f"TXN-{invoice['id'][:8]}-{amount}",
        },
    )
    assert resp.status_code == 200, resp.text  # payments POST also returns 200
    return resp.json()


class TestPaymentRefund:
    """POST /billing/payments/{payment_id}/refund"""

    async def test_full_refund_returns_payment_to_pending(
        self, async_client, auth_headers, test_patient
    ):
        invoice = await _create_invoice(async_client, auth_headers, test_patient.id)
        payment = await _pay_invoice(async_client, auth_headers, invoice, "100.00")

        resp = await async_client.post(
            f"/api/v1/billing/payments/{payment['id']}/refund",
            headers=auth_headers,
            json={"amount": 100.00, "reason": "Patient overcharged"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert Decimal(data["refunded_amount"]) == Decimal("100.00")
        assert Decimal(data["remaining_refundable"]) == Decimal("0.00")
        assert data["payment_status"] == "refunded"
        assert data["invoice_status"] == "pending"

    async def test_partial_refund_marks_invoice_partially_paid(
        self, async_client, auth_headers, test_patient
    ):
        invoice = await _create_invoice(async_client, auth_headers, test_patient.id)
        payment = await _pay_invoice(async_client, auth_headers, invoice, "100.00")

        resp = await async_client.post(
            f"/api/v1/billing/payments/{payment['id']}/refund",
            headers=auth_headers,
            json={"amount": 40.00},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert Decimal(data["refunded_amount"]) == Decimal("40.00")
        assert Decimal(data["remaining_refundable"]) == Decimal("60.00")
        assert data["payment_status"] == "partially_refunded"
        assert data["invoice_status"] == "partially_paid"

    async def test_over_refund_rejected(
        self, async_client, auth_headers, test_patient
    ):
        invoice = await _create_invoice(async_client, auth_headers, test_patient.id)
        payment = await _pay_invoice(async_client, auth_headers, invoice, "100.00")

        resp = await async_client.post(
            f"/api/v1/billing/payments/{payment['id']}/refund",
            headers=auth_headers,
            json={"amount": 150.00},
        )
        assert resp.status_code == 422
        assert "refundable" in resp.json()["detail"].lower()

    async def test_double_full_refund_rejected(
        self, async_client, auth_headers, test_patient
    ):
        invoice = await _create_invoice(async_client, auth_headers, test_patient.id)
        payment = await _pay_invoice(async_client, auth_headers, invoice, "100.00")

        first = await async_client.post(
            f"/api/v1/billing/payments/{payment['id']}/refund",
            headers=auth_headers,
            json={"amount": 100.00},
        )
        assert first.status_code == 200
        second = await async_client.post(
            f"/api/v1/billing/payments/{payment['id']}/refund",
            headers=auth_headers,
            json={"amount": 10.00},
        )
        assert second.status_code == 422

    async def test_refund_unknown_payment_404(self, async_client, auth_headers):
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await async_client.post(
            f"/api/v1/billing/payments/{fake_id}/refund",
            headers=auth_headers,
            json={"amount": 10.00},
        )
        assert resp.status_code == 404

    async def test_refund_requires_auth(self, async_client):
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await async_client.post(
            f"/api/v1/billing/payments/{fake_id}/refund",
            json={"amount": 10.00},
        )
        assert resp.status_code == 401


async def _make_user(db_session, practice_id, role, password="testpassword123"):
    from app.core.security import get_password_hash
    from app.models.user import User
    import uuid as uuid_lib

    user = User(
        id=uuid_lib.uuid4(),
        email=f"{role.lower()}_{uuid_lib.uuid4().hex[:8]}@example.com",
        password_hash=get_password_hash(password),
        first_name="Test",
        last_name=role.title(),
        role=role,
        practice_id=practice_id,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def _login_headers(client, email, password="testpassword123"):
    login = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert login.status_code == 200, login.text
    csrf = await client.get("/api/v1/auth/csrf")
    return {
        "Authorization": f"Bearer {login.json()['access_token']}",
        "X-CSRF-Token": csrf.json()["csrf_token"],
    }


class TestAccountantRole:
    """ACCOUNTANT has billing/reports access; no clinic-management access."""

    async def test_accountant_can_record_and_refund(
        self, async_client, db_session, test_practice, test_patient
    ):
        user = await _make_user(db_session, test_practice.id, "ACCOUNTANT")
        headers = await _login_headers(async_client, user.email)

        resp = await async_client.post(
            "/api/v1/billing/invoices/",
            headers=headers,
            json={
                "patient_id": str(test_patient.id),
                "line_items": [
                    {
                        "description": "Filling",
                        "quantity": 1,
                        "unit_price": 50.0,
                        "total": 50.0,
                    }
                ],
                "status": "pending",
            },
        )
        assert resp.status_code == 200, resp.text
        invoice = resp.json()
        payment = await _pay_invoice(async_client, headers, invoice, "50.00")
        refund = await async_client.post(
            f"/api/v1/billing/payments/{payment['id']}/refund",
            headers=headers,
            json={"amount": 25.00},
        )
        assert refund.status_code == 200, refund.text
        assert refund.json()["payment_status"] == "partially_refunded"

    async def test_accountant_can_view_reports(
        self, async_client, db_session, test_practice
    ):
        user = await _make_user(db_session, test_practice.id, "ACCOUNTANT")
        headers = await _login_headers(async_client, user.email)
        today = datetime.date.today()
        resp = await async_client.get(
            f"/api/v1/reports/dashboard?from={today}&to={today}",
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        assert "appointments" in resp.json()

    async def test_accountant_cannot_delete_patient(
        self, async_client, db_session, test_practice, test_patient
    ):
        user = await _make_user(db_session, test_practice.id, "ACCOUNTANT")
        headers = await _login_headers(async_client, user.email)
        resp = await async_client.delete(
            f"/api/v1/patients/{test_patient.id}", headers=headers
        )
        assert resp.status_code == 403


class TestPlatformConsole:
    """Platform (super-admin) endpoints: access control + core flows."""

    async def _super_admin_headers(self, client, db_session):
        # Super admins live in their own bootstrap practice.
        import uuid as uuid_lib
        from app.models.practice import Practice

        boot = Practice(
            id=uuid_lib.uuid4(),
            name="Platform HQ",
            public_slug=f"platform-hq-{uuid_lib.uuid4().hex[:6]}",
            email="ops@coredent.example",
        )
        db_session.add(boot)
        await db_session.flush()
        user = await _make_user(db_session, boot.id, "SUPER_ADMIN")
        headers = await _login_headers(client, user.email)
        return headers, boot, user

    async def test_owner_cannot_access_platform(
        self, async_client, auth_headers
    ):
        """A clinic OWNER (tenant user) must be denied the platform console."""
        for path in (
            "/api/v1/platform/metrics",
            "/api/v1/platform/clinics",
            "/api/v1/platform/users",
            "/api/v1/platform/subscriptions",
            "/api/v1/platform/audit-events",
        ):
            resp = await async_client.get(path, headers=auth_headers)
            assert resp.status_code == 403, f"{path} -> {resp.status_code}"

    async def test_metrics_shape(
        self, async_client, db_session
    ):
        headers, _, _ = await self._super_admin_headers(async_client, db_session)
        resp = await async_client.get("/api/v1/platform/metrics", headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        for key in (
            "total_clinics",
            "active_clinics",
            "suspended_clinics",
            "total_users",
            "active_subscriptions",
            "mrr",
            "churn_rate_percent",
            "new_registrations_this_month",
        ):
            assert key in data, f"missing {key}"

    async def test_list_clinics_and_detail(
        self, async_client, db_session, test_practice, test_patient
    ):
        headers, _, _ = await self._super_admin_headers(async_client, db_session)
        resp = await async_client.get("/api/v1/platform/clinics", headers=headers)
        assert resp.status_code == 200
        clinics = resp.json()["clinics"]
        listed = next((c for c in clinics if c["id"] == str(test_practice.id)), None)
        assert listed is not None
        # Regression guard: the grouped patient-count query was described in a
        # comment but never written, so patient_count was always 0.
        assert listed["patient_count"] >= 1

        detail = await async_client.get(
            f"/api/v1/platform/clinics/{test_practice.id}", headers=headers
        )
        assert detail.status_code == 200, detail.text
        body = detail.json()
        assert body["clinic"]["id"] == str(test_practice.id)
        assert isinstance(body["users"], list)

    async def test_suspend_and_reactivate_clinic(
        self, async_client, db_session, test_practice, test_user
    ):
        headers, _, _ = await self._super_admin_headers(async_client, db_session)

        suspended = await async_client.put(
            f"/api/v1/platform/clinics/{test_practice.id}/suspend",
            headers=headers,
            json={"reason": "Non-payment"},
        )
        assert suspended.status_code == 200, suspended.text
        assert suspended.json()["is_active"] is False

        # Login for a user of the suspended clinic is now blocked.
        login = await async_client.post(
            "/api/v1/auth/login",
            json={"email": test_user.email, "password": "testpassword123"},
        )
        assert login.status_code == 403
        assert "suspended" in login.json()["detail"].lower()

        reactivated = await async_client.put(
            f"/api/v1/platform/clinics/{test_practice.id}/reactivate",
            headers=headers,
            json={},
        )
        assert reactivated.status_code == 200, reactivated.text
        assert reactivated.json()["is_active"] is True

        # Login works again.
        login2 = await async_client.post(
            "/api/v1/auth/login",
            json={"email": test_user.email, "password": "testpassword123"},
        )
        assert login2.status_code == 200, login2.text

    async def test_list_users_includes_clinic_name(
        self, async_client, db_session, test_practice, test_user
    ):
        headers, _, _ = await self._super_admin_headers(async_client, db_session)
        resp = await async_client.get("/api/v1/platform/users", headers=headers)
        assert resp.status_code == 200
        users = resp.json()["users"]
        row = next(u for u in users if u["email"] == test_user.email)
        assert row["practice_name"] == "Test Practice"

    async def test_list_subscriptions_and_audit_events(
        self, async_client, db_session
    ):
        headers, _, _ = await self._super_admin_headers(async_client, db_session)
        subs = await async_client.get(
            "/api/v1/platform/subscriptions", headers=headers
        )
        assert subs.status_code == 200
        assert "subscriptions" in subs.json()

        events = await async_client.get(
            "/api/v1/platform/audit-events", headers=headers
        )
        assert events.status_code == 200
        assert "events" in events.json()
        # The console view itself must be audited.
        actions = [e["action"] for e in events.json()["events"]]
        assert "platform_audit_console_viewed" in actions

    async def test_platform_requires_csrf_for_actions(
        self, async_client, db_session, test_practice
    ):
        """Suspend without CSRF token must fail even for a super admin."""
        headers, _, _ = await self._super_admin_headers(async_client, db_session)
        no_csrf = {k: v for k, v in headers.items() if k != "X-CSRF-Token"}
        resp = await async_client.put(
            f"/api/v1/platform/clinics/{test_practice.id}/suspend",
            headers=no_csrf,
            json={},
        )
        assert resp.status_code == 403
