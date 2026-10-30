"""
Tenant isolation middleware.

Every authenticated request carries a ``practice_id`` claim in its JWT.
This middleware enforces that any ``practice_id`` the client tries to use —
in a path parameter, query string, or JSON body — matches the one in the
JWT.  Without this, a single forgotten ``WHERE practice_id = :practice_id``
clause in one endpoint would leak data across tenants.

The middleware is intentionally conservative: it only validates the *presence*
and *equality* of practice ids.  It does not run any business logic.  The
endpoint still must include the practice_id in its query.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Awaitable, Callable, Optional
from uuid import UUID

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


# Endpoints that legitimately operate across tenants (signup, login, health,
# internal super-admin tasks).  Anything not in this list AND authenticated
# is checked.
EXEMPT_PATH_PATTERNS = (
    re.compile(r"^/api/v1/auth/(login|register|refresh|forgot-password|reset-password|verify-email|resend-verification)/?$"),
    # Only the public patient-portal entry point is exempt (it is
    # unauthenticated and resolves its tenant from the practice_slug body/. It
    # mounts at /api/v1/portal/access — the /patient-portal/... prefix never
    # existed in the router and could never match here. Authenticated
    # patient-portal routes (`/me`, `/appointments`, `/billing`, `/pay`, …)
    # still pass through the guard: their opaque bearer token carries no
    # practice_id claim, so sending one is rejected.

    re.compile(r"^/api/v1/portal/access/?$"),
    re.compile(r"^/health/?$"),
    re.compile(r"^/metrics/?$"),
    re.compile(r"^/$"),
)


def _is_exempt(path: str) -> bool:
    return any(p.match(path) for p in EXEMPT_PATH_PATTERNS)


def _decode_token_payload(request: Request) -> Optional[dict]:
    """Return the decoded JWT payload, or None when the request is unauthenticated."""
    # Bearer-header only: no endpoint sets an access-token cookie, and a
    # cookie fallback would re-open CSRF exposure.
    auth = request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    token = auth.split(" ", 1)[1].strip()
    if not token:
        return None
    # Local import to avoid a circular import at module load.
    from app.core.security import decode_token
    try:
        payload = decode_token(token)
    except Exception:
        return None
    return payload or None


def _decode_practice_id(request: Request) -> Optional[str]:
    """Return the practice_id claim from a practice JWT, or None for patient JWTs."""
    payload = _decode_token_payload(request)
    if not payload or payload.get("type") != "access":
        return None
    pid = payload.get("practice_id")
    return str(pid) if pid else None


def _is_patient_token(request: Request) -> bool:
    """Patient-portal tokens carry type='patient' (not 'access')."""
    payload = _decode_token_payload(request)
    return bool(payload and payload.get("type") == "patient")


def _looks_like_uuid(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        UUID(value)
        return True
    except (ValueError, TypeError):
        return False


def _uuid_matches(value: str, token_pid: Optional[str]) -> bool:
    """Compare UUIDs canonically so case/format differences don't false-403."""
    if not token_pid:
        return False
    try:
        return UUID(value) == UUID(str(token_pid))
    except (ValueError, TypeError):
        return value == token_pid


TENANT_ID_KEYS = {"practice_id", "practice_ids", "practice_uuid", "practice_uuids"}

def _is_tenant_key(key: Any) -> bool:
    """Recognize only tenant identifiers, not fields like practice_name."""
    if not isinstance(key, str):
        return False
    normalized = re.sub(r"[^a-z0-9]", "", key.lower())
    return normalized in {"practiceid", "practiceids", "practiceuuid", "practiceuuids"}


def _iter_practice_keys(obj: Any):
    """Yield explicit tenant-id fields from nested JSON objects."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if _is_tenant_key(key) and value:
                yield key, value
            yield from _iter_practice_keys(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _iter_practice_keys(item)


def _tenant_value_matches(value: Any, token_pid: Optional[str]) -> bool:
    if isinstance(value, list):
        return bool(value) and all(_tenant_value_matches(item, token_pid) for item in value)
    if not isinstance(value, (str, UUID)) or not str(value):
        return False
    value_str = str(value)
    return _looks_like_uuid(value_str) and _uuid_matches(value_str, token_pid)



class TenantGuardMiddleware(BaseHTTPMiddleware):
    """
    Reject any authenticated request that names a practice_id in the URL or
    body other than the one in the JWT.

    Bypass for exempt paths (login, signup, health, etc.).
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable],
    ):
        path = request.url.path
        if _is_exempt(path) or not path.startswith("/api/"):
            return await call_next(request)

        # Decode the JWT practice_id.  If the request is unauthenticated, the
        # downstream ``get_current_user`` dependency will reject it; we don't
        # need to short-circuit here.
        # NOTE (explicit): patient-portal opaque tokens (secrets.token_urlsafe
        # 48, hashed at rest) are not JWTs, so decode fails and both helpers
        # return None/False here. Portal isolation rests on _get_portal_patient
        # token->patient binding + per-endpoint patient_id/practice_id filters,
        # not on this guard. The 48-byte bearer is unguessable; theft is
        # bounded by 30-min expiry + per-route 30/min limits.
        token_pid = _decode_practice_id(request)
        is_patient = _is_patient_token(request)
        if token_pid is None and not is_patient:
            return await call_next(request)

        # Patient-portal tokens must NEVER carry a practice_id in URL or body.
        # If one is present we reject immediately: this is the missing piece
        # the blanket `/patient-portal/.*` exempt list used to hide.
        if is_patient and token_pid is None:
            for key, value in request.query_params.multi_items():
                if _is_tenant_key(key) and value:
                    logger.warning(
                        "Tenant guard: patient token sent %s=%s; rejecting",
                        key, value,
                    )
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={
                            "detail": "Patient tokens must not reference a practice_id.",
                            "type": "tenant_mismatch",
                        },
                    )

        # Path parameters are checked before query/body values.
        for key, value in request.path_params.items():
            if not _is_tenant_key(key) or not value:
                continue
            if is_patient or not _tenant_value_matches(value, token_pid):
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "Tenant mismatch: practice identifier is not allowed.", "type": "tenant_mismatch"},
                )

        # Query string check. Any non-empty tenant-id value must match the JWT.
        for key, value in request.query_params.multi_items():
            if not _is_tenant_key(key) or not value:
                continue
            if not _looks_like_uuid(value) or not _uuid_matches(value, token_pid):
                logger.warning(
                    "Tenant guard: query %s=%s does not match JWT practice_id %s",
                    key, value, token_pid,
                )
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={
                        "detail": "Tenant mismatch: query practice_id does not match the authenticated practice.",
                        "type": "tenant_mismatch",
                    },
                )

        # Body check.  We only inspect JSON; for non-JSON / streaming bodies we
        # let the endpoint handle it.  We buffer the body so the endpoint can
        # still read it.
        if request.method in {"POST", "PUT", "PATCH"}:
            ctype = request.headers.get("content-type", "").lower()
            if "application/json" in ctype:
                body_bytes = await request.body()
                # Re-attach the body for downstream readers.
                async def receive():
                    return {"type": "http.request", "body": body_bytes, "more_body": False}
                request._receive = receive  # type: ignore[attr-defined]
                try:
                    payload = json.loads(body_bytes.decode("utf-8") or "null") if body_bytes else None
                except Exception:
                    payload = None
                if isinstance(payload, (dict, list)):
                    for key, value in _iter_practice_keys(payload):
                        # Patient tokens may not reference any practice id at all
                        if is_patient and token_pid is None:
                            logger.warning(
                                "Tenant guard: patient token sent body %s=%s; rejecting",
                                key, value,
                            )
                            return JSONResponse(
                                status_code=status.HTTP_403_FORBIDDEN,
                                content={
                                    "detail": "Patient tokens must not reference a practice_id.",
                                    "type": "tenant_mismatch",
                                },
                            )
                        if not _tenant_value_matches(value, token_pid):
                            logger.warning(
                                "Tenant guard: body %s=%s does not match JWT practice_id %s",
                                key, value, token_pid,
                            )
                            return JSONResponse(
                                status_code=status.HTTP_403_FORBIDDEN,
                                content={
                                    "detail": "Tenant mismatch: body practice_id does not match the authenticated practice.",
                                    "type": "tenant_mismatch",
                                },
                            )

        return await call_next(request)
