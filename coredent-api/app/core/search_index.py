"""
Search index helpers for encrypted columns.

Encryption at rest makes substring search impossible on the ciphertext. We
support search by storing a *deterministic HMAC* of the normalized value in a
separate index column. An attacker with the database can do equality lookups
(``WHERE search_index_email = hmac('alice@example.com')``) but cannot invert
the HMAC to recover the plaintext without the secret key.

``SEARCH_INDEX_KEY`` is an independent secret. Non-local deployments must
configure it explicitly; they never derive an index key from a public key ID.
Local development and tests retain a compatibility fallback derived from the
active Fernet secret material, rather than from its public identifier.

This module is intentionally small. Use it in model setters or SQLAlchemy
``@validates`` hooks.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from typing import Optional

from app.core.config_simple import _LOCAL_ENVIRONMENTS, _looks_like_placeholder, settings
from app.core.encryption import keyring


def _development_search_index_secret() -> bytes:
    """Derive a local-only index secret from active Fernet key material.

    The keyring intentionally exposes the active key *identifier* publicly,
    so it must never be used as secret material. The cryptographic key is
    available only inside the active Fernet instance; this fallback exists
    solely to preserve the established development/test setup where an
    explicit search-index key is not configured.
    """
    ciphers = getattr(keyring, "_ciphers", ())
    try:
        _, cipher = ciphers[0]
        signing_key = getattr(cipher, "_signing_key")
        encryption_key = getattr(cipher, "_encryption_key")
    except (AttributeError, IndexError) as exc:
        raise RuntimeError(
            "No active encryption key is available for the local search-index fallback."
        ) from exc

    if not isinstance(signing_key, bytes) or not isinstance(encryption_key, bytes):
        raise RuntimeError(
            "The active encryption key cannot provide safe local search-index material."
        )

    return hmac.new(
        signing_key + encryption_key,
        b"coredent-search-index-development-v1",
        hashlib.sha256,
    ).digest()


def _search_index_secret() -> bytes:
    """Return the configured HMAC key, failing closed outside local use."""
    explicit = (getattr(settings, "SEARCH_INDEX_KEY", "") or "").strip()
    if explicit:
        if settings.ENVIRONMENT not in _LOCAL_ENVIRONMENTS and (
            len(explicit) < 32 or _looks_like_placeholder(explicit)
        ):
            raise RuntimeError(
                "SEARCH_INDEX_KEY must be an independent, non-placeholder secret "
                "of at least 32 characters outside local environments."
            )
        return explicit.encode("utf-8")

    if settings.ENVIRONMENT not in _LOCAL_ENVIRONMENTS:
        raise RuntimeError(
            "SEARCH_INDEX_KEY is required outside local development and test environments."
        )

    return _development_search_index_secret()


def normalize(value: Optional[str]) -> str:
    if not value:
        return ""
    # Lowercase, strip non-alphanumeric (keep + for phone country codes).
    return re.sub(r"[^a-z0-9+]", "", value.lower())


def hmac_index(value: Optional[str]) -> Optional[str]:
    """
    Return a 32-byte hex HMAC-SHA256 of the normalized value, or ``None`` if
    the input is empty.  Storing this in a dedicated index column lets the DB
    do equality lookups without revealing the plaintext.
    """
    n = normalize(value)
    if not n:
        return None
    return hmac.new(
        _search_index_secret(), n.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def update_patient_search_indexes(target, *fields: str) -> None:
    """
    Convenience helper: set ``search_index_email``/``search_index_phone``/
    ``search_index_last_name`` on a Patient instance based on the encrypted
    column values.  Call from a SQLAlchemy ``@validates`` or from the
    endpoint right before commit.
    """
    for field in fields:
        value = getattr(target, field, None)
        h = hmac_index(value)
        if field == "email":
            target.search_index_email = h
        elif field == "phone":
            target.search_index_phone = h
        elif field == "last_name":
            target.search_index_last_name = h
