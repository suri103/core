"""Phase 2 regression tests.

These tests are designed to FAIL on the prior code and PASS after the
Phase 2 fixes. They cover:

  * H-7 login status-code uniformity (no email enumeration via status)
  * H-1 / H-9 audit-log email is not leaked to the audit log on failure
  * M-10 booking email-verification token is stored hashed only
"""
import hashlib

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update


class TestLoginStatusUniformity:
    """H-7: every post-lookup login failure returns 401 + same detail."""

    @pytest.mark.asyncio
    async def test_wrong_password_401(self, client, test_user):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": test_user.email, "password": "definitely-wrong"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Incorrect email or password"

    @pytest.mark.asyncio
    async def test_missing_user_401(self, client):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "no-such-user@example.com", "password": "x"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Incorrect email or password"

    @pytest.mark.asyncio
    async def test_locked_account_returns_401_not_429(
        self, client, test_user, db_session
    ):
        """Lockout no longer reveals itself through a 429 status code."""
        from uuid import uuid4

        from httpx import ASGITransport

        from app.main import app as fastapi_app
        from app.models.user import User

        # Force a lockout via five failed attempts. Each attempt comes from a
        # distinct client IP: the per-IP login limiter (5/minute, auth.login)
        # would otherwise answer the sixth same-IP request with 429 before the
        # account-lockout branch is reached — and this regression is about the
        # *account* lockout status, not IP throttling.
        for _ in range(5):
            probe = AsyncClient(
                transport=ASGITransport(
                    app=fastapi_app, client=(f"lockout-{uuid4().hex}", 0)
                ),
                base_url="http://test",
            )
            try:
                await probe.post(
                    "/api/v1/auth/login",
                    json={"email": test_user.email, "password": "wrong"},
                )
            finally:
                await probe.aclose()
        locked = await client.post(
            "/api/v1/auth/login",
            json={"email": test_user.email, "password": "testpassword123"},
        )
        assert locked.status_code == 401, locked.text
        assert locked.json()["detail"] == "Incorrect email or password"
        # Reset for the rest of the suite.
        await db_session.execute(
            update(User)
            .where(User.id == test_user.id)
            .values(
                failed_login_attempts=0,
                locked_until=None,
                is_active=True,
                is_email_verified=True,
            )
        )
        await db_session.commit()


class TestLoginAuditLogDoesNotLeakEmail:
    """H-1 / H-9: the submitted email must not appear in audit log."""

    @pytest.mark.asyncio
    async def test_missing_user_audit_log_omits_email(
        self, client, db_session
    ):
        from app.models.audit import AuditLog

        unknown_email = "no-such-user-1234@example.com"
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": unknown_email, "password": "x"},
        )
        assert response.status_code == 401
        result = await db_session.execute(
            select(AuditLog)
            .where(AuditLog.action == "login_failed")
            .order_by(AuditLog.created_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        assert row is not None
        changes_str = str(row.changes or {})
        assert unknown_email not in changes_str
        assert (row.changes or {}).get("email_present") is False


class TestBookingEmailVerificationTokenHash:
    """M-10: booking email-verification tokens are stored hashed."""

    def test_model_has_token_hash_column(self):
        from app.models.booking import OnlineBooking
        columns = {c.name for c in OnlineBooking.__table__.columns}
        assert "email_verification_token_hash" in columns
        # Legacy plaintext column retained for the migration window.
        assert "email_verification_token" in columns

    @pytest.mark.asyncio
    async def test_booking_stores_hash_not_plaintext(
        self, test_practice, db_session
    ):
        from app.models.booking import (
            BookingPage,
            BookingPageStatus,
            OnlineBooking,
        )

        page = BookingPage(
            practice_id=test_practice.id,
            page_slug=f"v-{hashlib.md5(b'm10').hexdigest()[:8]}",
            page_title="Token Hash",
            require_email_verification=True,
            status=BookingPageStatus.ACTIVE,
        )
        db_session.add(page)
        await db_session.commit()

        plaintext = "abc123"
        expected_hash = hashlib.sha256(plaintext.encode("utf-8")).hexdigest()
        booking = OnlineBooking(
            booking_page_id=page.id,
            practice_id=test_practice.id,
            is_new_patient=True,
            first_name="X",
            last_name="Y",
            email="xy@example.com",
            phone="1",
            requested_date=__import__("datetime").date(2026, 12, 1),
            requested_time=__import__("datetime").time(10, 0),
            status="pending",
            confirmation_code="TOK01",
            email_verified=False,
            email_verification_token=None,
            email_verification_token_hash=expected_hash,
            phone_verification_code="000000",
        )
        db_session.add(booking)
        await db_session.commit()
        await db_session.refresh(booking)

        # Plaintext column is empty.
        assert booking.email_verification_token in (None, "")
        # Hash column equals SHA-256(plaintext).
        assert booking.email_verification_token_hash == expected_hash
        # The stored hash is NOT equal to the plaintext token.
        assert booking.email_verification_token_hash != plaintext