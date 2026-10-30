"""
Tests for enterprise endpoints
"""
from decimal import Decimal
from uuid import uuid4
import pytest
from httpx import AsyncClient


class TestEnterpriseEndpoints:
    """Test enterprise/multi-practice endpoints"""

    @pytest.mark.asyncio
    async def test_group_analytics_unauthorized(self, client: AsyncClient):
        """Test getting group analytics without authentication"""
        response = await client.get("/api/v1/enterprise/group/analytics")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_group_practices_unauthorized(self, client: AsyncClient):
        """Test listing group practices without authentication"""
        response = await client.get("/api/v1/enterprise/group/practices")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_group_analytics_forbidden_regular_user(self, client: AsyncClient, auth_headers):
        """Test that regular users cannot access group analytics"""
        response = await client.get("/api/v1/enterprise/group/analytics", headers=auth_headers)
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_group_practices_forbidden_regular_user(self, client: AsyncClient, auth_headers):
        """Test that regular users cannot list group practices"""
        response = await client.get("/api/v1/enterprise/group/practices", headers=auth_headers)
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_group_analytics_with_date_params(self, client: AsyncClient, auth_headers):
        """Test group analytics with date range parameters"""
        response = await client.get(
            "/api/v1/enterprise/group/analytics?start_date=2026-01-01&end_date=2026-05-01",
            headers=auth_headers,
        )
        assert response.status_code == 403


class TestGroupAnalyticsMoneyDefinitions:
    """M-2 regression: group analytics must use the same money definitions
    as the practice dashboard (reports.py).

    Production counts only billable invoices (no DRAFT/CANCELLED); collections
    are net of refunds over (COMPLETED, REFUNDED). Before the fix, group
    analytics summed ALL invoice totals and gross COMPLETED payments, so the
    same practice showed different production/collections on /enterprise
    than on /reports/dashboard for the same period.
    """

    @pytest.fixture
    async def group_owner_headers(self, client, db_session, test_practice, test_user):
        """Promote the test user to GROUP_OWNER of a group holding the
        test practice, then log in for a role-elevated session."""
        from app.models.practice import PracticeGroup

        group = PracticeGroup(name="Test DSO Group")
        db_session.add(group)
        await db_session.flush()
        test_practice.group_id = group.id
        # Enum member, not a raw string — the column is Enum(UserRole).
        from app.models.user import UserRole

        test_user.role = UserRole.GROUP_OWNER
        db_session.add(test_user)
        await db_session.commit()

        login = await client.post(
            "/api/v1/auth/login",
            json={"email": test_user.email, "password": "testpassword123"},
        )
        assert login.status_code == 200, login.text
        csrf = await client.get("/api/v1/auth/csrf")
        assert csrf.status_code == 200, csrf.text
        return {
            "Authorization": f"Bearer {login.json()['access_token']}",
            "X-CSRF-Token": csrf.json()["csrf_token"],
        }

    @pytest.mark.asyncio
    async def test_production_excludes_draft_and_cancelled(
        self, client, db_session, test_patient, group_owner_headers
    ):
        from app.models.billing import Invoice, InvoiceStatus

        async def _inv(number, total, status):
            inv = Invoice(
                practice_id=test_patient.practice_id,
                patient_id=test_patient.id,
                invoice_number=number,
                status=status,
                subtotal=total,
                tax=Decimal("0.00"),
                total=total,
                line_items=[],
            )
            db_session.add(inv)
            await db_session.flush()
            return inv

        await _inv("INV-GA-001", Decimal("100.00"), InvoiceStatus.PENDING)
        await _inv("INV-GA-002", Decimal("40.00"), InvoiceStatus.PAID)
        # Non-billable: must NOT count toward group production.
        await _inv("INV-GA-003", Decimal("500.00"), InvoiceStatus.DRAFT)
        await _inv("INV-GA-004", Decimal("999.00"), InvoiceStatus.CANCELLED)
        await db_session.commit()

        response = await client.get(
            "/api/v1/enterprise/group/analytics",
            headers=group_owner_headers,
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["consolidated"]["production"] == 140.0  # 100 + 40, not 1639

    @pytest.mark.asyncio
    async def test_collections_subtract_refunds(
        self, client, db_session, test_patient, group_owner_headers
    ):
        from app.models.billing import (
            Invoice,
            InvoiceStatus,
            Payment,
            PaymentMethod,
            PaymentStatus,
        )

        inv = Invoice(
            practice_id=test_patient.practice_id,
            patient_id=test_patient.id,
            invoice_number="INV-GA-005",
            status=InvoiceStatus.PENDING,
            subtotal=Decimal("100.00"),
            tax=Decimal("0.00"),
            total=Decimal("100.00"),
            line_items=[],
        )
        db_session.add(inv)
        await db_session.flush()
        db_session.add(
            Payment(
                invoice_id=inv.id,
                patient_id=test_patient.id,
                practice_id=test_patient.practice_id,
                amount=Decimal("100.00"),
                refunded_amount=Decimal("30.00"),
                payment_method=PaymentMethod.CARD,
                status=PaymentStatus.REFUNDED,
            )
        )
        await db_session.commit()

        response = await client.get(
            "/api/v1/enterprise/group/analytics",
            headers=group_owner_headers,
        )
        assert response.status_code == 200, response.text
        data = response.json()
        # 100 charged, 30 refunded -> 70 collected, not 100.
        assert data["consolidated"]["collections"] == 70.0

    @pytest.fixture
    async def owner_headers(self, client, db_session, test_practice, test_patient):
        """A dedicated plain-OWNER session for the practice dashboard call.

        ``group_owner_headers`` promotes the shared ``test_user`` to
        GROUP_OWNER, and role checks run against the live DB row at request
        time — so re-using ``auth_headers`` for the dashboard would 403 once
        the promotion has happened. This fixture gives the dashboard its own
        un-promoted OWNER.
        """
        from app.core.security import get_password_hash
        from app.models.user import User, UserRole

        owner = User(
            email=f"dashowner_{uuid4().hex[:8]}@example.com",
            password_hash=get_password_hash("testpassword123"),
            first_name="Dash",
            last_name="Owner",
            role=UserRole.OWNER,
            practice_id=test_practice.id,
            is_active=True,
        )
        db_session.add(owner)
        await db_session.commit()

        login = await client.post(
            "/api/v1/auth/login",
            json={"email": owner.email, "password": "testpassword123"},
        )
        assert login.status_code == 200, login.text
        csrf = await client.get("/api/v1/auth/csrf")
        assert csrf.status_code == 200, csrf.text
        return {
            "Authorization": f"Bearer {login.json()['access_token']}",
            "X-CSRF-Token": csrf.json()["csrf_token"],
        }

    @pytest.mark.asyncio
    async def test_group_analytics_agrees_with_practice_dashboard(
        self, client, db_session, test_patient, owner_headers, group_owner_headers
    ):
        """The two money surfaces must agree for the same period — the
        'two surfaces disagree' class of finding the audit rules target."""
        from app.models.billing import (
            Invoice,
            InvoiceStatus,
            Payment,
            PaymentMethod,
            PaymentStatus,
        )

        inv = Invoice(
            practice_id=test_patient.practice_id,
            patient_id=test_patient.id,
            invoice_number="INV-GA-006",
            status=InvoiceStatus.PENDING,
            subtotal=Decimal("80.00"),
            tax=Decimal("0.00"),
            total=Decimal("80.00"),
            line_items=[],
        )
        db_session.add(inv)
        await db_session.flush()
        db_session.add(
            Payment(
                invoice_id=inv.id,
                patient_id=test_patient.id,
                practice_id=test_patient.practice_id,
                amount=Decimal("80.00"),
                refunded_amount=Decimal("10.00"),
                payment_method=PaymentMethod.CARD,
                status=PaymentStatus.REFUNDED,
            )
        )
        # Non-billable invoice that only the old (buggy) production count saw.
        cancelled = Invoice(
            practice_id=test_patient.practice_id,
            patient_id=test_patient.id,
            invoice_number="INV-GA-007",
            status=InvoiceStatus.CANCELLED,
            subtotal=Decimal("700.00"),
            tax=Decimal("0.00"),
            total=Decimal("700.00"),
            line_items=[],
        )
        db_session.add(cancelled)
        await db_session.commit()

        group_resp = await client.get(
            "/api/v1/enterprise/group/analytics",
            headers=group_owner_headers,
        )
        assert group_resp.status_code == 200, group_resp.text
        group = group_resp.json()

        # Same window via the practice dashboard (plain OWNER session).
        # Use the practice's LOCAL business date, not the UTC date: near UTC
        # midnight the two differ and rows created "now" would fall outside
        # a UTC-date window, making this test time-of-day flaky.
        from app.core.business_time import business_date, get_practice_timezone

        tz = await get_practice_timezone(db_session, test_patient.practice_id)
        today = business_date(tz)
        dashboard_resp = await client.get(
            f"/api/v1/reports/dashboard?from={today}&to={today}",
            headers=owner_headers,
        )
        assert dashboard_resp.status_code == 200, dashboard_resp.text
        dashboard = dashboard_resp.json()

        # The two surfaces must agree for the same period (M-2).
        assert group["consolidated"]["production"] == 80.0
        assert dashboard["revenue"]["totalRevenue"] == 80.0
        assert group["consolidated"]["collections"] == 70.0
        assert dashboard["revenue"]["totalCollected"] == 70.0
