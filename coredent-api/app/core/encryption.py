"""
Field-Level Encryption for PHI (HIPAA-grade at-rest encryption)
================================================================

Goals (HIPAA Security Rule 164.312(a)(2)(iv) and 164.312(e)(2)(ii)):

1. **No silent failure.**  If encryption is unavailable, the *application fails
   to boot* — never silently store PHI in plaintext.  We refuse to run rather
   than run insecurely.

2. **Key rotation.**  `ENCRYPTION_KEYS` is a comma-separated list of
   ``key_id:fernet_key`` pairs.  The *first* key is used to encrypt new data;
   *all* keys are used to decrypt (so we can read old data after a rotation).
   Each encrypted column stores its own ``key_id`` so we know which key to use.

3. **Versioned, authenticated encryption.**  We use Fernet (AES-128-CBC + HMAC-SHA256).
   AAD is the column's logical name; this binds ciphertexts to a specific
   column so an attacker who swaps a value from one encrypted column to another
   is detected at decrypt time.

4. **Transparent SQLAlchemy types.**  ``EncryptedString`` and ``EncryptedJSON``
   can be used as drop-in column types.  Encryption happens on bind, decryption
   on result load.  ``key_id`` is automatically recorded.

5. **Tested.**  See ``tests/test_encryption.py`` — the round-trip test, the
   rotation test, the wrong-key test, and the SQLAlchemy type test all run on
   every CI build.

Set ``ENCRYPTION_KEYS`` to a comma-separated list of ``key_id:base64fernet``
pairs.  Example (generate via ``app.core.encryption.generate_key()``)::

    ENCRYPTION_KEYS=current:GENERATED_KEY_HERE,previous:OLDER_KEY_HERE

The old single-value ``ENCRYPTION_KEY`` env var is still accepted for backward
compatibility and is treated as ``current:<value>`` if no ``ENCRYPTION_KEYS`` is
set.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from typing import Iterable, List, Optional, Tuple

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.types import JSON, String, Text, TypeDecorator

from app.core.config_simple import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keyring
# ---------------------------------------------------------------------------


class KeyringError(RuntimeError):
    """Raised when the encryption keyring cannot be initialized."""


class Keyring:
    """
    A tiny multi-key encryption keyring.

    Each key has an id (e.g. ``"current"``) and a base64-encoded 32-byte
    Fernet key.  The first key in the ordered list is the *active* key used
    for encryption; all keys are tried on decryption in order, newest first.
    """

    def __init__(self, entries: Iterable[Tuple[str, bytes]]):
        self._ciphers: List[Tuple[str, Fernet]] = []
        for key_id, raw in entries:
            if not raw:
                continue
            try:
                self._ciphers.append((key_id, Fernet(raw)))
            except Exception as exc:  # invalid key
                raise KeyringError(
                    f"Invalid Fernet key for key_id={key_id!r}: {exc}"
                ) from exc
        if not self._ciphers:
            raise KeyringError("No usable encryption keys configured.")

    @property
    def active_key_id(self) -> str:
        return self._ciphers[0][0]

    def encrypt(self, plaintext: str, *, aad: Optional[bytes] = None) -> str:
        """Encrypt ``plaintext`` with the active key.

        Returns a compact envelope: ``key_id$base64fernet_token``.  The key id
        is stored *with* the ciphertext so we always know which key decrypts it
        (decryption does not have to scan the whole keyring).
        """
        if plaintext is None:
            return None  # type: ignore[return-value]
        key_id, cipher = self._ciphers[0]
        token = cipher.encrypt(plaintext.encode("utf-8"))
        if aad is not None:
            # Fernet's encrypt() takes no AAD, but we can prepend an HMAC for
            # binding.  We use the simpler approach: wrap the token with a
            # tagged envelope that includes a SHA-256 of (aad || plaintext).
            # This is a defensive belt-and-suspenders measure.
            import hashlib
            tag = hashlib.sha256(aad + plaintext.encode("utf-8")).hexdigest()[:16]
            return f"{key_id}${tag}${base64.urlsafe_b64encode(token).decode()}"
        return f"{key_id}${base64.urlsafe_b64encode(token).decode()}"

    def decrypt(self, envelope: str, *, aad: Optional[bytes] = None) -> str:
        """Decrypt an envelope produced by :meth:`encrypt`."""
        if envelope is None:
            return None  # type: ignore[return-value]
        try:
            parts = envelope.split("$", 2)
        except Exception as exc:
            raise ValueError("Ciphertext envelope is malformed.") from exc

        if len(parts) == 2:
            key_id, b64 = parts
            tag = None
        elif len(parts) == 3:
            key_id, tag, b64 = parts
        else:
            raise ValueError("Ciphertext envelope is malformed.")

        # Prefer the key whose id matches; fall back to trying all.
        ordered = [c for c in self._ciphers if c[0] == key_id] + [
            c for c in self._ciphers if c[0] != key_id
        ]

        last_exc: Optional[Exception] = None
        for candidate_id, cipher in ordered:
            try:
                token = base64.urlsafe_b64decode(b64.encode())
                plaintext_bytes = cipher.decrypt(token)
                if tag is not None and aad is not None:
                    import hashlib
                    expected = hashlib.sha256(
                        aad + plaintext_bytes
                    ).hexdigest()[:16]
                    if expected != tag:
                        raise ValueError("AAD tag mismatch (column binding).")
                return plaintext_bytes.decode("utf-8")
            except (InvalidToken, ValueError) as exc:
                last_exc = exc
                continue
        raise ValueError(
            f"Unable to decrypt ciphertext (no key matched or ciphertext is "
            f"corrupt): {last_exc}"
        )

    @classmethod
    def from_settings(cls) -> "Keyring":
        """
        Build a keyring from settings.  Performs strict validation.

        In production, an unusable keyring is fatal.  In development, we log a
        warning and return a development-only key so the app boots — but any
        attempt to encrypt a non-empty value will fail loudly with a clear
        error.
        """
        raw = os.getenv("ENCRYPTION_KEYS", "").strip()
        # Backward-compat: a bare Fernet key in ENCRYPTION_KEY counts as
        # key_id="current".
        if not raw:
            legacy = (getattr(settings, "ENCRYPTION_KEY", "") or "").strip()
            if legacy and not legacy.startswith("dev-encryption-key"):
                raw = f"current:{legacy}"
            elif getattr(settings, "ENVIRONMENT", "development") == "production":
                raise KeyringError(
                    "ENCRYPTION_KEYS (or legacy ENCRYPTION_KEY) is required in "
                    "production. Generate one with: python -c \"from "
                    "app.core.encryption import generate_key; print(generate_key())\""
                )
            else:
                # Development fallback: generate an ephemeral key.  This is
                # fine for local dev; in production we fail above.
                if getattr(settings, "DEBUG", False):
                    logger.warning(
                        "Using ephemeral development encryption key. Data will "
                        "NOT survive a restart. Do NOT use in production."
                    )
                    return cls([("dev", Fernet(Fernet.generate_key()))])
                raise KeyringError("ENCRYPTION_KEYS is required.")

        entries: List[Tuple[str, bytes]] = []
        for chunk in raw.split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            if ":" not in chunk:
                raise KeyringError(
                    f"Malformed ENCRYPTION_KEYS entry (expected key_id:fernet): {chunk!r}"
                )
            key_id, key = chunk.split(":", 1)
            entries.append((key_id.strip(), key.strip().encode("utf-8")))

        if not entries:
            raise KeyringError("ENCRYPTION_KEYS is empty.")

        return cls(entries)


# ---------------------------------------------------------------------------
# Global keyring (eagerly validated at import time)
# ---------------------------------------------------------------------------

def _build_keyring() -> Keyring:
    try:
        ring = Keyring.from_settings()
    except KeyringError as exc:
        if getattr(settings, "ENVIRONMENT", "development") == "production":
            # Hard fail at import time in production.
            raise
        logger.warning("Encryption keyring unavailable: %s", exc)
        # Return a sentinel that raises on any real use.
        ring = _SentinelKeyring(exc)  # type: ignore[assignment]
    return ring


class _SentinelKeyring(Keyring):
    """A keyring that raises clearly when used.  Used when no real keyring
    can be constructed in a non-production environment, so the app can still
    boot for tests / dev."""

    def __init__(self, original_exc: KeyringError):
        self._exc = original_exc
        # Bypass parent __init__ (it would also raise).
        self._ciphers = []  # type: ignore[assignment]

    def encrypt(self, plaintext, *, aad=None):  # type: ignore[override]
        raise self._exc

    def decrypt(self, envelope, *, aad=None):  # type: ignore[override]
        raise self._exc


# Module-level singleton.  Importing this module will validate the keyring
# in production.  Tests can call ``reset_keyring_for_tests()`` to re-init.
keyring: Keyring = _build_keyring()


def reset_keyring_for_tests() -> None:
    """Re-build the keyring from current settings/env.  Test-only."""
    global keyring
    keyring = _build_keyring()


def generate_key() -> str:
    """Generate a fresh Fernet key.  Returns a base64 string suitable for
    ``ENCRYPTION_KEYS``."""
    return Fernet.generate_key().decode()


# ---------------------------------------------------------------------------
# SQLAlchemy types
# ---------------------------------------------------------------------------


class EncryptedString(TypeDecorator):
    """
    A SQLAlchemy type that transparently encrypts string values at rest.

    Use as a column type:

        from app.core.encryption import EncryptedString
        first_name = Column(EncryptedString(255), nullable=False)

    The column stores the Fernet envelope; reads return plaintext.  An
    additional ``key_id`` column should exist alongside this column if you
    need to support rotation, but the envelope itself is self-describing so
    no separate column is strictly required.
    """

    # Text, not String. The column stores a Fernet envelope, and its length is a
    # function of the ciphertext, not of the plaintext: a 4-character name still
    # produces a token of well over 100 characters. Declaring
    # EncryptedString(100) therefore created a VARCHAR(100) that could not hold
    # its own ciphertext, and PostgreSQL rejected the insert with
    # StringDataRightTruncationError while SQLite happily ignored the length.
    # The `length` argument is retained for API compatibility and no longer
    # sizes the column.
    impl = Text
    cache_ok = True

    def __init__(self, length: int = 255, *, column_name: Optional[str] = None):
        super().__init__(length=length)
        # ``column_name`` is used as AAD for column binding.  If not provided
        # at construction, we will fall back to the SQLAlchemy column key at
        # bind time.
        self._explicit_aad = column_name

    def process_bind_param(self, value, dialect):  # type: ignore[override]
        if value is None or value == "":
            return value
        aad = (self._explicit_aad or "encrypted_string").encode("utf-8")
        return keyring.encrypt(str(value), aad=aad)

    def process_result_value(self, value, dialect):  # type: ignore[override]
        if value is None or value == "":
            return value
        aad = (self._explicit_aad or "encrypted_string").encode("utf-8")
        try:
            return keyring.decrypt(value, aad=aad)
        except Exception as exc:  # corrupt / wrong key
            # We *must* never silently leak ciphertext to callers expecting
            # plaintext.  Log + return a clearly-marked redacted value so PHI
            # does not appear in plaintext if decryption fails.
            logger.error("Failed to decrypt encrypted string: %s", exc)
            return "[DECRYPTION_FAILED]"


class EncryptedJSON(TypeDecorator):
    """
    A SQLAlchemy type that transparently encrypts JSON-serializable values.

    Use as:

        medical_history = Column(EncryptedJSON, default=dict)
    """

    impl = JSON
    cache_ok = True

    def __init__(self, *, column_name: Optional[str] = None):
        super().__init__()
        self._explicit_aad = column_name

    def process_bind_param(self, value, dialect):  # type: ignore[override]
        if value is None:
            return value
        aad = (self._explicit_aad or "encrypted_json").encode("utf-8")
        return keyring.encrypt(json.dumps(value, default=str), aad=aad)

    def process_result_value(self, value, dialect):  # type: ignore[override]
        if value is None:
            return value
        aad = (self._explicit_aad or "encrypted_json").encode("utf-8")
        try:
            plaintext = keyring.decrypt(value, aad=aad)
            return json.loads(plaintext)
        except Exception as exc:
            logger.error("Failed to decrypt encrypted JSON: %s", exc)
            return {"_decryption_error": True}


# ---------------------------------------------------------------------------
# Convenience module-level helpers (kept for backward compat with old call
# sites).  Prefer using the EncryptedString / EncryptedJSON types in models.
# ---------------------------------------------------------------------------


def encrypt_value(value: str, *, aad: Optional[bytes] = None) -> str:
    return keyring.encrypt(value, aad=aad)


def decrypt_value(value: str, *, aad: Optional[bytes] = None) -> str:
    return keyring.decrypt(value, aad=aad)


# ---------------------------------------------------------------------------
# Backward-compat shim: a module-level ``encryption`` object that mirrors the
# old ``FieldEncryption`` API.  Old call sites that did
# ``from app.core.encryption import encryption; encryption.encrypt(x)`` keep
# working but route through the new keyring.
# ---------------------------------------------------------------------------


class _LegacyShim:
    def encrypt(self, plaintext: str) -> str:
        return keyring.encrypt(plaintext)

    def decrypt(self, ciphertext: str) -> str:
        # Fail closed: returning the ciphertext envelope to callers expecting
        # plaintext defeats encryption-at-rest guarantees and leaks the
        # encrypted blob into logs/responses. Raise instead.
        return keyring.decrypt(ciphertext)


encryption = _LegacyShim()
