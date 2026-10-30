import logging

import httpx

from app.core.config_simple import settings

logger = logging.getLogger(__name__)

GOOGLE_SITEVERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"


class CaptchaVerificationError(Exception):
    pass


async def verify_recaptcha_v3(token: str, action: str, min_score: float = 0.5) -> None:
    """
    Verify a reCAPTCHA v3 token with Google's siteverify API.

    Raises CaptchaVerificationError on any failure (fail closed).
    In non-production environments without a configured secret key,
    verification is skipped (with a warning) so local dev keeps working.
    """
    secret = getattr(settings, "RECAPTCHA_SECRET_KEY", "") or ""
    if not secret:
        if settings.ENVIRONMENT == "production":
            logger.error("RECAPTCHA_SECRET_KEY is not configured in production")
            raise CaptchaVerificationError("Captcha verification is not configured")
        logger.warning("reCAPTCHA secret not configured; skipping verification (non-production)")
        return

    if not token:
        raise CaptchaVerificationError("Missing captcha token")

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                GOOGLE_SITEVERIFY_URL,
                data={"secret": secret, "response": token},
            )
        data = resp.json()
    except Exception as exc:
        logger.error("reCAPTCHA siteverify request failed: %s", exc)
        # Fail closed: a verification outage must not open the bot gate.
        raise CaptchaVerificationError("Captcha verification unavailable")

    if not data.get("success"):
        logger.warning("reCAPTCHA verification failed: %s", data.get("error-codes"))
        raise CaptchaVerificationError("Captcha verification failed")

    if data.get("action") and data["action"] != action:
        logger.warning(
            "reCAPTCHA action mismatch: expected %s, got %s", action, data["action"]
        )
        raise CaptchaVerificationError("Captcha action mismatch")

    score = data.get("score", 0.0)
    if score < min_score:
        logger.warning("reCAPTCHA score too low: %s < %s", score, min_score)
        raise CaptchaVerificationError("Captcha score too low")
