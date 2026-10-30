"""
Automations & Webhooks Endpoints
Handles outbound practice automation webhooks and trigger dispatches

SECURITY HISTORY
----------------
- 2026-08: ``POST /automations/test`` previously issued an outbound POST to
  any client-supplied URL with no role gate and no CSRF dependency — a
  first-party SSRF primitive. Both outbound paths (/test and /trigger) now
  share one SSRF guard: HTTPS-only outside local environments, and the
  resolved address may not be private/loopback/link-local/reserved.
"""

import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Dict, Any
from uuid import uuid4
import httpx
import logging
from datetime import datetime, timezone

from app.core.config_simple import settings, _LOCAL_ENVIRONMENTS
from app.core.database import get_db
from app.api.deps import get_current_user, require_role, verify_csrf
from app.models.user import User, UserRole
from app.models.practice import Practice
from app.core.audit import log_audit_event

router = APIRouter()
logger = logging.getLogger(__name__)

_WEBHOOK_TIMEOUT_SECONDS = 5.0

# H-14: fields inside a stored webhook that are credentials, not configuration.
# These are write-only: they may be set, but are never returned by the API.
_SECRET_WEBHOOK_FIELDS = ("secretToken", "headers")

# Roles permitted to read webhook configuration or manage it. Reading the list
# used to require only authentication, and the list carried the outbound secret
# token and custom headers verbatim — so any authenticated staff account could
# harvest the practice's integration credentials.
_AUTOMATION_ADMIN_ROLES = (UserRole.OWNER, UserRole.ADMIN)

# H-14: events a client may trigger. ``/trigger`` is deliberately available to
# all staff (the clinical and billing screens fire these as side effects of
# normal work), so the blast radius is limited by constraining *what* can be
# fired rather than *who* can fire it. An unknown event is rejected instead of
# being forwarded to whatever wildcard subscribers exist.
_TRIGGERABLE_EVENTS = frozenset(
    {
        "appointment_booked",
        "appointment_cancelled",
        "appointment_completed",
        "appointment_confirmed",
        "appointment_no_show",
        "patient_created",
        "patient_registered",
        "invoice_created",
        "invoice_overdue",
        "payment_received",
        "review_request",
        "treatment_plan_approved",
        "treatment_plan_created",
    }
)

# Bound on the client-supplied event payload forwarded to a third party.
_MAX_TRIGGER_PAYLOAD_BYTES = 16 * 1024


def _redact_webhook(hook: Dict[str, Any]) -> Dict[str, Any]:
    """Return a webhook safe to serialize to a client.

    H-14: ``secretToken`` and custom ``headers`` are outbound credentials. The
    API reports only *whether* they are configured, never their values. A
    client that needs to change a secret sends a new one; it never needs to
    read the old one back.
    """
    safe = {k: v for k, v in hook.items() if k not in _SECRET_WEBHOOK_FIELDS}
    safe["hasSecretToken"] = bool(hook.get("secretToken"))
    safe["customHeaderNames"] = sorted(
        k for k in (hook.get("headers") or {}) if isinstance(k, str)
    )
    return safe


async def _load_practice_for_update(db: AsyncSession, practice_id) -> Practice:
    """Load the practice row with a write lock.

    M-24: webhook configuration lives inside the ``practices.settings`` JSON
    document and is edited read-modify-write. Two concurrent updates each read
    the whole document, mutate their own copy and write it back, so the second
    write silently discards the first (a webhook added concurrently just
    disappears). Locking the row serializes the read-modify-write.
    """
    from app.core.database import row_locks_supported

    stmt = select(Practice).where(Practice.id == practice_id)
    if row_locks_supported():
        stmt = stmt.with_for_update()
    practice = (await db.execute(stmt)).scalar_one_or_none()
    if not practice:
        raise HTTPException(status_code=404, detail="Practice not found")
    return practice


def _validate_webhook_url_sync(raw_url: str) -> None:
    """Reject webhook targets that would let the API server probe internal
    networks. Raises HTTPException(400) on any disallowed target."""
    parsed = urlparse(raw_url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise HTTPException(status_code=400, detail="Webhook URL must be an absolute http(s) URL")
    if parsed.scheme != "https" and settings.ENVIRONMENT not in _LOCAL_ENVIRONMENTS:
        raise HTTPException(status_code=400, detail="Webhook URLs must use HTTPS")
    default_port = 443 if parsed.scheme == "https" else 80
    try:
        infos = socket.getaddrinfo(
            parsed.hostname, parsed.port or default_port, proto=socket.IPPROTO_TCP
        )
    except (socket.gaierror, OSError) as exc:
        raise HTTPException(status_code=400, detail=f"Webhook host could not be resolved: {exc}") from exc
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise HTTPException(
                status_code=400,
                detail="Webhook URLs may not target private or reserved network addresses",
            )


async def validate_webhook_url(raw_url: str) -> None:
    """Async wrapper — DNS resolution runs off the event loop."""
    await asyncio.to_thread(_validate_webhook_url_sync, raw_url)


def _webhook_headers(hook: Dict[str, Any]) -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    secret = hook.get("secretToken")
    if secret:
        headers["X-Webhook-Secret"] = str(secret)
    # Owner-configured custom headers, minus hop-by-hop/unsafe ones.
    blocked = {"host", "content-length", "connection", "transfer-encoding", "authorization"}
    for key, value in (hook.get("headers") or {}).items():
        if isinstance(key, str) and isinstance(value, str) and key.lower() not in blocked:
            headers[key] = value
    return headers


@router.get("/webhooks")
async def list_webhooks(
    event: Optional[str] = None,
    current_user: User = Depends(require_role(*_AUTOMATION_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List configured automation webhooks for the practice.

    H-14 FIX: owner/admin only, and secrets are redacted. This route used to
    require only authentication and returned each webhook's ``secretToken`` and
    custom headers verbatim, so any authenticated staff account could read the
    practice's outbound integration credentials.
    """
    stmt = select(Practice).where(Practice.id == current_user.practice_id)
    result = await db.execute(stmt)
    practice = result.scalar_one_or_none()
    if not practice:
        raise HTTPException(status_code=404, detail="Practice not found")

    settings_dict = practice.settings or {}
    webhooks = settings_dict.get("webhooks", [])

    if event:
        webhooks = [w for w in webhooks if w.get("event") == event or w.get("event") == "*"]

    return [_redact_webhook(hook) for hook in webhooks]


@router.post("/webhooks")
async def create_webhook(
    webhook_data: Dict[str, Any],
    request: Request = None,
    current_user: User = Depends(require_role(*_AUTOMATION_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> Dict[str, Any]:
    """Create a new automation webhook."""
    practice = await _load_practice_for_update(db, current_user.practice_id)

    settings_dict = dict(practice.settings or {})
    webhooks = list(settings_dict.get("webhooks", []))

    url = webhook_data.get("url", "")
    # Validate the target before storing it: a stored URL that fails the SSRF
    # guard is a configuration trap that only surfaces at dispatch time.
    if url:
        await validate_webhook_url(url)

    now_iso = datetime.now(timezone.utc).isoformat()
    new_hook = {
        "id": str(uuid4()),
        "name": webhook_data.get("name", "Webhook"),
        "url": url,
        "event": webhook_data.get("event", "*"),
        "isActive": webhook_data.get("isActive", True),
        "secretToken": webhook_data.get("secretToken"),
        "headers": webhook_data.get("headers", {}),
        "createdAt": now_iso,
        "updatedAt": now_iso,
    }
    webhooks.append(new_hook)
    settings_dict["webhooks"] = webhooks
    practice.settings = settings_dict

    await log_audit_event(db, current_user, "create_automation_webhook", "webhook", new_hook["id"], request)
    await db.commit()

    return _redact_webhook(new_hook)


@router.put("/webhooks/{webhook_id}")
async def update_webhook(
    webhook_id: str,
    update_data: Dict[str, Any],
    request: Request = None,
    current_user: User = Depends(require_role(*_AUTOMATION_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> Dict[str, Any]:
    """Update an existing automation webhook."""
    practice = await _load_practice_for_update(db, current_user.practice_id)

    settings_dict = dict(practice.settings or {})
    webhooks = list(settings_dict.get("webhooks", []))

    target = None
    for hook in webhooks:
        if hook.get("id") == webhook_id:
            target = hook
            break

    if not target:
        raise HTTPException(status_code=404, detail="Webhook not found")

    if update_data.get("url"):
        await validate_webhook_url(update_data["url"])

    for k, v in update_data.items():
        if k in ("id", "createdAt"):
            continue
        # A redacted read round-tripped back through an update must not wipe
        # the stored secret: the client never received it, so it cannot resend
        # it. Only an explicit non-empty value replaces it.
        if k in _SECRET_WEBHOOK_FIELDS and not v:
            continue
        if k in ("hasSecretToken", "customHeaderNames"):
            continue
        target[k] = v
    target["updatedAt"] = datetime.now(timezone.utc).isoformat()

    settings_dict["webhooks"] = webhooks
    practice.settings = settings_dict
    await log_audit_event(db, current_user, "update_automation_webhook", "webhook", webhook_id, request)
    await db.commit()

    return _redact_webhook(target)


@router.delete("/webhooks/{webhook_id}")
async def delete_webhook(
    webhook_id: str,
    request: Request = None,
    current_user: User = Depends(require_role(*_AUTOMATION_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> dict:
    """Delete an automation webhook."""
    practice = await _load_practice_for_update(db, current_user.practice_id)

    settings_dict = dict(practice.settings or {})
    webhooks = [w for w in settings_dict.get("webhooks", []) if w.get("id") != webhook_id]
    settings_dict["webhooks"] = webhooks
    practice.settings = settings_dict

    await log_audit_event(db, current_user, "delete_automation_webhook", "webhook", webhook_id, request)
    await db.commit()

    return {"status": "success"}


@router.post("/webhooks/{webhook_id}/toggle")
async def toggle_webhook(
    webhook_id: str,
    request: Request = None,
    current_user: User = Depends(require_role(*_AUTOMATION_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> Dict[str, Any]:
    """Toggle active state of a webhook."""
    practice = await _load_practice_for_update(db, current_user.practice_id)

    settings_dict = dict(practice.settings or {})
    webhooks = list(settings_dict.get("webhooks", []))

    target = None
    for hook in webhooks:
        if hook.get("id") == webhook_id:
            target = hook
            break

    if not target:
        raise HTTPException(status_code=404, detail="Webhook not found")

    target["isActive"] = not target.get("isActive", True)
    target["updatedAt"] = datetime.now(timezone.utc).isoformat()

    settings_dict["webhooks"] = webhooks
    practice.settings = settings_dict
    await log_audit_event(
        db, current_user, "toggle_automation_webhook", "webhook", webhook_id, request
    )
    await db.commit()

    return _redact_webhook(target)


@router.post("/trigger")
async def trigger_automation(
    trigger_data: Dict[str, Any],
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: bool = Depends(verify_csrf),
) -> Dict[str, Any]:
    """
    Trigger practice automations and matching webhook dispatches.

    M2 FIX: this endpoint previously only *counted* matching webhooks and
    returned success — nothing was ever sent. It now actually POSTs the
    event payload to each active matching webhook (fire-and-forget with a
    per-request timeout; delivery failures are logged, not raised, so a
    dead consumer cannot fail the clinical/billing flow that triggered it).

    H-14 FIX: this route stays open to all authenticated staff on purpose —
    the scheduling, billing and treatment screens fire these events as a side
    effect of ordinary work, so an owner/admin gate would break the product.
    The blast radius is bounded differently: the event name must be one we
    recognise, and the forwarded payload is size-capped. The destination URL
    and secret are never client-supplied; they come from the practice's own
    stored configuration.
    """
    event = trigger_data.get("event")

    if event not in _TRIGGERABLE_EVENTS:
        raise HTTPException(
            status_code=422,
            detail=(
                "Unknown automation event. Allowed events: "
                + ", ".join(sorted(_TRIGGERABLE_EVENTS))
            ),
        )

    # The frontend sends the body under "payload"; older callers used "data".
    raw_payload = trigger_data.get("payload")
    if raw_payload is None:
        raw_payload = trigger_data.get("data", {})
    if not isinstance(raw_payload, dict):
        raise HTTPException(
            status_code=422, detail="Automation payload must be an object"
        )

    import json as _json

    try:
        encoded_size = len(_json.dumps(raw_payload, default=str).encode("utf-8"))
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=422, detail="Automation payload is not JSON-serializable"
        )
    if encoded_size > _MAX_TRIGGER_PAYLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Automation payload is too large ({encoded_size} bytes; "
                f"limit {_MAX_TRIGGER_PAYLOAD_BYTES})"
            ),
        )

    stmt = select(Practice).where(Practice.id == current_user.practice_id)
    result = await db.execute(stmt)
    practice = result.scalar_one_or_none()

    triggered = 0
    delivered = 0
    failed = 0
    if practice:
        settings_dict = practice.settings or {}
        webhooks = [
            w for w in settings_dict.get("webhooks", [])
            if w.get("isActive", True) and (w.get("event") == event or w.get("event") == "*")
        ]
        triggered = len(webhooks)

        if webhooks:
            payload = {
                "event": event,
                "practice_id": str(practice.id),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": raw_payload,
            }

            async def _dispatch(hook: Dict[str, Any]) -> bool:
                url = hook.get("url") or ""
                try:
                    await validate_webhook_url(url)
                    async with httpx.AsyncClient(timeout=_WEBHOOK_TIMEOUT_SECONDS) as client:
                        resp = await client.post(url, json=payload, headers=_webhook_headers(hook))
                    return resp.is_success
                except HTTPException as guard_exc:
                    # A stored URL that now fails the SSRF guard (DNS rebind,
                    # reconfigured host) must not fail the caller's clinical
                    # flow — record it and treat the delivery as failed.
                    logger.warning(
                        "Webhook target rejected by SSRF guard: hook=%s detail=%s",
                        hook.get("id"),
                        guard_exc.detail,
                    )
                    return False
                except Exception as exc:
                    logger.warning(
                        "Webhook dispatch failed: event=%s hook=%s error=%s",
                        event, hook.get("id"), type(exc).__name__,
                    )
                    return False

            results = await asyncio.gather(*(_dispatch(hook) for hook in webhooks))
            delivered = sum(1 for ok in results if ok)
            failed = len(results) - delivered

    logger.info(
        f"Automation triggered: event={event}, practice={current_user.practice_id}, "
        f"targets={triggered}, delivered={delivered}, failed={failed}"
    )
    return {
        "success": True,
        "triggeredCount": triggered,
        "deliveredCount": delivered,
        "failedCount": failed,
    }


@router.post("/test")
async def test_webhook(
    test_data: Dict[str, Any],
    request: Request = None,
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
    _csrf: bool = Depends(verify_csrf),
) -> Dict[str, Any]:
    """Test webhook endpoint with a ping payload.

    SECURITY (H3): owner/admin-only + CSRF + SSRF guard — this used to let
    any authenticated user make the server POST to an arbitrary URL.
    """
    url = test_data.get("webhookUrl")
    if not url:
        raise HTTPException(status_code=400, detail="Missing webhookUrl")

    await validate_webhook_url(url)

    try:
        headers = {"Content-Type": "application/json"}
        if test_data.get("secretToken"):
            headers["X-Webhook-Secret"] = test_data["secretToken"]
        async with httpx.AsyncClient(timeout=_WEBHOOK_TIMEOUT_SECONDS) as client:
            resp = await client.post(url, json={"event": "ping", "test": True}, headers=headers)
            return {"success": resp.is_success, "status_code": resp.status_code}
    except Exception as e:
        logger.warning("Webhook test failed: %s", type(e).__name__)
        return {"success": False, "error": "Webhook test request failed"}
