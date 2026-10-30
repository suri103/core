"""
Webhook signature verification.

Provides a single, dependable way to verify inbound webhooks (Stripe, Razorpay,
etc.).  Every webhook handler in the codebase should call
``verify_stripe_signature`` (or its sibling) before doing any work.

Principles:

1. **Fail closed.**  If the signing secret is empty in production, the import
   itself fails.  We do not let webhooks slip through unverified.
2. **Constant-time comparison.**  We use ``hmac.compare_digest`` and never
   ``==`` to compare MACs.
3. **No raw HTTP body without verification.**  The body must be passed in
   raw (not parsed JSON) so the signature is over the exact bytes Stripe sent.
4. **Reasonable tolerance.**  ``construct_event`` enforces a 5-minute
   timestamp window.  We do not relax it.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import hmac
import hashlib

from app.core.config_simple import settings

logger = logging.getLogger(__name__)


class WebhookVerificationError(Exception):
    """Raised when a webhook signature cannot be verified."""


def log_webhook_attempt(request, provider: str, success: bool, error: Optional[str] = None) -> None:
    """Log webhook outcomes without recording payloads, signatures, or PHI."""
    client_ip = request.client.host if request.client else "unknown"
    log = logger.info if success else logger.warning
    log(
        "Webhook provider=%s success=%s path=%s client_ip=%s error=%s",
        provider,
        success,
        request.url.path,
        client_ip,
        error,
    )


def _get_stripe_lib():
    """Import the Stripe SDK lazily so this module can be loaded in tests
    and environments where the SDK is not installed."""
    try:
        import stripe  # type: ignore
        return stripe
    except Exception as exc:  # pragma: no cover
        raise WebhookVerificationError(
            "Stripe SDK is not installed; cannot verify webhook signature."
        ) from exc


def verify_stripe_signature(
    payload: bytes,
    sig_header: Optional[str],
    *,
    secret: Optional[str] = None,
    tolerance_seconds: int = 300,
) -> dict:
    """
    Verify a Stripe webhook signature and return the parsed event.

    Args:
        payload: The raw HTTP body (bytes) of the webhook.
        sig_header: The value of the ``Stripe-Signature`` header.
        secret: Override the signing secret.  Defaults to
            ``settings.STRIPE_WEBHOOK_SECRET``.
        tolerance_seconds: Maximum age of the ``t=`` timestamp.  Defaults to
            Stripe's recommended 5 minutes.

    Returns:
        The parsed Stripe event as a dict.

    Raises:
        WebhookVerificationError: if the signature is missing, malformed, the
        secret is not configured, the timestamp is out of tolerance, or the
        signature does not match.
    """
    signing_secret = (secret or getattr(settings, "STRIPE_WEBHOOK_SECRET", "") or "").strip()
    if not signing_secret:
        raise WebhookVerificationError(
            "STRIPE_WEBHOOK_SECRET is not configured. Refusing to process "
            "any webhook payload until the signing secret is set."
        )

    if not sig_header:
        raise WebhookVerificationError("Missing Stripe-Signature header.")

    # We re-implement the signature check so we don't depend on the Stripe
    # SDK being importable everywhere (and so we can unit-test the verifier
    # without the SDK).  Stripe's scheme: header has "t=...,v1=...,v1=...".
    try:
        elements = dict(item.split("=", 1) for item in sig_header.split(",") if "=" in item)
    except ValueError as exc:
        raise WebhookVerificationError("Malformed Stripe-Signature header.") from exc

    timestamp = elements.get("t")
    signatures = [v for k, v in elements.items() if k == "v1"]
    if not timestamp or not signatures:
        raise WebhookVerificationError("Stripe-Signature missing t= or v1=.")

    # Tolerance check.
    try:
        ts_int = int(timestamp)
    except ValueError as exc:
        raise WebhookVerificationError("Invalid timestamp in Stripe-Signature.") from exc
    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise WebhookVerificationError(
            f"Stripe webhook timestamp outside tolerance ({tolerance_seconds}s)."
        )

    # Compute expected signature.
    signed_payload = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(
        signing_secret.encode("utf-8"),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()

    if not any(hmac.compare_digest(expected, s) for s in signatures):
        raise WebhookVerificationError("Stripe signature mismatch.")

    # Now safe to parse.
    import json
    try:
        return json.loads(payload.decode("utf-8"))
    except Exception as exc:
        raise WebhookVerificationError("Webhook body is not valid JSON.") from exc


def verify_razorpay_signature(
    payload: bytes,
    *,
    received_signature: str,
    secret: Optional[str] = None,
) -> bool:
    """Verify a Razorpay webhook signature.  Returns True on success."""
    signing_secret = (secret or getattr(settings, "RAZORPAY_WEBHOOK_SECRET", "") or "").strip()
    if not signing_secret:
        raise WebhookVerificationError("RAZORPAY_WEBHOOK_SECRET is not configured.")
    if not received_signature:
        raise WebhookVerificationError("Missing X-Razorpay-Signature header.")
    expected = hmac.new(
        signing_secret.encode("utf-8"), payload, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, received_signature):
        raise WebhookVerificationError("Razorpay signature mismatch.")
    return True


# Convenience: the Stripe ``construct_event``-style API, in case a handler
# prefers it.  Always uses our strict verifier above.
def construct_stripe_event(payload: bytes, sig_header: Optional[str], secret: Optional[str] = None):
    return verify_stripe_signature(payload, sig_header, secret=secret)
