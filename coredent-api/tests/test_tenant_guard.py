"""
Unit tests for app/core/tenant_guard.py.

The middleware enforces that any `practice_id` carried in the URL or body
matches the one in the JWT. These tests exercise the pure-function helpers
and the JSON-rejection paths. End-to-end coverage (real HTTP requests) is
in tests/test_tenant_isolation.py.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.core.config_simple import settings
from app.core.security import create_access_token
from app.core.tenant_guard import (
    TenantGuardMiddleware,
    _decode_practice_id,
    _is_exempt,
    _is_patient_token,
    _looks_like_uuid,
)


def _make_patient_token(sub: str = "p-1") -> str:
    """Build a patient JWT directly — ``create_access_token`` always sets
    type='access', so we encode the patient token by hand."""
    payload = {
        "sub": sub,
        "type": "patient",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


# ---------------------------------------------------------------------------
# _looks_like_uuid
# ---------------------------------------------------------------------------

class TestLooksLikeUuid:
    def test_valid_uuid_returns_true(self):
        assert _looks_like_uuid(str(uuid.uuid4())) is True

    def test_non_string_returns_false(self):
        assert _looks_like_uuid(123) is False
        assert _looks_like_uuid(None) is False
        assert _looks_like_uuid(["not", "a", "uuid"]) is False

    def test_malformed_string_returns_false(self):
        assert _looks_like_uuid("not-a-uuid") is False
        assert _looks_like_uuid("12345") is False
        # Wrong segment lengths
        assert _looks_like_uuid("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee0") is False


# ---------------------------------------------------------------------------
# _is_exempt
# ---------------------------------------------------------------------------

class TestIsExempt:
    def test_login_paths_are_exempt(self):
        for path in (
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/auth/refresh",
            "/api/v1/auth/forgot-password",
            "/api/v1/auth/reset-password",
            "/api/v1/auth/verify-email",
            "/api/v1/auth/resend-verification",
        ):
            assert _is_exempt(path) is True, f"{path} should be exempt"

    def test_patient_portal_access_only_is_exempt(self):
        """Only the public patient-portal/access endpoint is exempt; deeper
        routes like /me, /appointments must pass through the guard. The portal
        router mounts at /api/v1/portal, so the exemption must match that
        prefix (the historical /patient-portal/... prefix never existed in the
        router — a dead regex could never match)."""
        assert _is_exempt("/api/v1/portal/access") is True
        assert _is_exempt("/api/v1/portal/access/") is True
        # Other patient-portal routes are NOT exempt.
        assert _is_exempt("/api/v1/portal/me") is False
        assert _is_exempt("/api/v1/portal/appointments") is False
        assert _is_exempt("/api/v1/portal/billing") is False
        assert _is_exempt("/api/v1/portal/pay") is False

    def test_health_and_metrics_are_exempt(self):
        assert _is_exempt("/health") is True
        assert _is_exempt("/metrics") is True
        assert _is_exempt("/") is True

    def test_business_routes_are_not_exempt(self):
        assert _is_exempt("/api/v1/patients") is False
        assert _is_exempt("/api/v1/appointments") is False
        assert _is_exempt("/api/v1/invoices") is False


# ---------------------------------------------------------------------------
# Token decoding helpers
# ---------------------------------------------------------------------------

class TestDecodePracticeId:
    def test_returns_practice_id_from_valid_token(self):
        pid = str(uuid.uuid4())
        token = create_access_token(
            {"sub": "u-1", "practice_id": pid, "type": "access"}
        )
        request = _make_request(headers={"Authorization": f"Bearer {token}"})
        assert _decode_practice_id(request) == pid

    def test_returns_none_without_token(self):
        request = _make_request()
        assert _decode_practice_id(request) is None

    def test_returns_none_for_patient_token(self):
        """Patient JWTs use type='patient' and carry no practice_id."""
        token = _make_patient_token()
        request = _make_request(headers={"Authorization": f"Bearer {token}"})
        assert _decode_practice_id(request) is None

    def test_returns_none_for_refresh_token(self):
        """Refresh tokens are type='refresh' — not 'access'."""
        pid = str(uuid.uuid4())
        from app.core.security import create_refresh_token
        token = create_refresh_token({"sub": "u-1", "practice_id": pid})
        request = _make_request(headers={"Authorization": f"Bearer {token}"})
        assert _decode_practice_id(request) is None


class TestIsPatientToken:
    def test_true_for_patient_token(self):
        token = _make_patient_token()
        request = _make_request(headers={"Authorization": f"Bearer {token}"})
        assert _is_patient_token(request) is True

    def test_false_for_practice_token(self):
        token = create_access_token(
            {"sub": "u-1", "practice_id": str(uuid.uuid4()), "type": "access"}
        )
        request = _make_request(headers={"Authorization": f"Bearer {token}"})
        assert _is_patient_token(request) is False

    def test_false_without_token(self):
        assert _is_patient_token(_make_request()) is False


# ---------------------------------------------------------------------------
# Middleware: end-to-end JSON rejection
# ---------------------------------------------------------------------------

class TestMiddlewareJsonRejection:
    """Drive TenantGuardMiddleware.dispatch directly with synthetic ASGI
    requests so we can assert on the JSON response shape."""

    @pytest.mark.asyncio
    async def test_query_practice_mismatch_is_rejected(self):
        token_pid = str(uuid.uuid4())
        other_pid = str(uuid.uuid4())
        token = create_access_token(
            {"sub": "u-1", "practice_id": token_pid, "type": "access"}
        )
        request = _make_request(
            method="GET",
            path=f"/api/v1/patients?practice_id={other_pid}",
            headers={"Authorization": f"Bearer {token}"},
        )

        async def call_next(_):
            raise AssertionError("call_next should not be reached on mismatch")

        response = await TenantGuardMiddleware(_dummy_app).dispatch(request, call_next)
        assert response.status_code == 403
        body = json.loads(response.body)
        assert body["type"] == "tenant_mismatch"
        assert "query practice_id" in body["detail"]

    @pytest.mark.asyncio
    async def test_body_practice_mismatch_is_rejected(self):
        token_pid = str(uuid.uuid4())
        other_pid = str(uuid.uuid4())
        token = create_access_token(
            {"sub": "u-1", "practice_id": token_pid, "type": "access"}
        )
        body_bytes = json.dumps({"practice_id": other_pid}).encode()
        request = _make_request(
            method="POST",
            path="/api/v1/patients",
            body=body_bytes,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )

        async def call_next(_):
            raise AssertionError("call_next should not be reached on mismatch")

        response = await TenantGuardMiddleware(_dummy_app).dispatch(request, call_next)
        assert response.status_code == 403
        body = json.loads(response.body)
        assert body["type"] == "tenant_mismatch"
        assert "body practice_id" in body["detail"]

    @pytest.mark.asyncio
    async def test_patient_token_with_practice_in_query_is_rejected(self):
        """Patient JWTs must NEVER reference a practice_id, even in query."""
        token = _make_patient_token()
        other_pid = str(uuid.uuid4())
        request = _make_request(
            method="GET",
            path=f"/api/v1/patient-portal/me?practice_id={other_pid}",
            headers={"Authorization": f"Bearer {token}"},
        )

        async def call_next(_):
            raise AssertionError("call_next should not be reached")

        response = await TenantGuardMiddleware(_dummy_app).dispatch(request, call_next)
        assert response.status_code == 403
        body = json.loads(response.body)
        assert body["type"] == "tenant_mismatch"
        assert "Patient tokens" in body["detail"]

    @pytest.mark.asyncio
    async def test_patient_token_with_practice_in_body_is_rejected(self):
        token = _make_patient_token()
        body_bytes = json.dumps({"practice_id": str(uuid.uuid4())}).encode()
        request = _make_request(
            method="POST",
            path="/api/v1/patient-portal/appointments",
            body=body_bytes,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )

        async def call_next(_):
            raise AssertionError("call_next should not be reached")

        response = await TenantGuardMiddleware(_dummy_app).dispatch(request, call_next)
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_matching_query_passes_through(self):
        pid = str(uuid.uuid4())
        token = create_access_token(
            {"sub": "u-1", "practice_id": pid, "type": "access"}
        )
        request = _make_request(
            method="GET",
            path=f"/api/v1/patients?practice_id={pid}",
            headers={"Authorization": f"Bearer {token}"},
        )
        marker = {"reached": True}

        async def call_next(_):
            marker["reached"] = True
            return _fake_response(200)

        await TenantGuardMiddleware(_dummy_app).dispatch(request, call_next)
        assert marker["reached"] is True

    @pytest.mark.asyncio
    async def test_exempt_path_passes_through(self):
        request = _make_request(method="POST", path="/api/v1/auth/login")
        marker = {"reached": True}

        async def call_next(_):
            marker["reached"] = True
            return _fake_response(200)

        await TenantGuardMiddleware(_dummy_app).dispatch(request, call_next)
        assert marker["reached"] is True

    @pytest.mark.asyncio
    async def test_non_api_path_passes_through(self):
        request = _make_request(method="GET", path="/health")
        marker = {"reached": True}

        async def call_next(_):
            marker["reached"] = True
            return _fake_response(200)

        await TenantGuardMiddleware(_dummy_app).dispatch(request, call_next)
        assert marker["reached"] is True


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _dummy_app(scope):
    """Stub ASGI app — never called in these tests."""
    raise NotImplementedError


def _fake_response(status: int):
    from starlette.responses import Response
    return Response(status_code=status)


def _make_request(method="GET", path="/", body=b"", headers=None):
    """Build a minimal Starlette Request with the given method/path/body."""
    from starlette.requests import Request

    headers = headers or {}
    body = body or b""
    scope = {
        "type": "http",
        "method": method,
        "path": path.split("?")[0],
        "raw_path": path.split("?")[0].encode(),
        "query_string": path.split("?", 1)[1].encode() if "?" in path else b"",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "server": ("testserver", 80),
        "client": ("testclient", 50000),
        "scheme": "http",
        "root_path": "",
    }

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(scope, receive=receive)
