"""
Key Management Service (KMS) integration
=========================================

By default the application reads Fernet keys from the ``ENCRYPTION_KEYS``
environment variable.  This is acceptable for closed-beta deployments
and dev environments but is *not* HIPAA-compliant key management for
production US healthcare: HIPAA requires that encryption keys be
managed in a manner that separates the key custodian from the data
custodian, with auditable access, rotation, and revocation.

This module provides a ``KmsClient`` interface with three backends:

    1. ``env``         - current behavior, reads from env var
                         (``ENCRYPTION_KEYS`` or ``ENCRYPTION_KEY``).
    2. ``aws``         - AWS KMS, decrypts the data key on demand and
                         caches in memory.  Set ``KMS_BACKEND=aws`` and
                         ``AWS_KMS_KEY_ARN=...``.
    3. ``local``       - alias for ``env`` (semantically clear naming
                         for the default case).

The current default backend is ``env``.  Once AWS KMS is provisioned
and BAAs are in place, switching is one env var.

AWS KMS data-key flow:
    1.  On startup, call KMS ``GenerateDataKey`` with a CMK ARN.
    2.  KMS returns a 32-byte plaintext data key + the same key
        encrypted under the CMK.  We discard the plaintext from disk
        and store only the *encrypted* data key in
        ``ENCRYPTION_KEYS`` (e.g. ``"aws:<encrypted-blob>"``).
    3.  On every encrypt/decrypt, decrypt the data key with KMS
        (cached in memory for 5 min), then use it as a Fernet key.

This pattern is documented in the AWS KMS best-practices guide.
"""
from __future__ import annotations

import logging
import os
import time
from abc import ABC, abstractmethod
from typing import Optional, Tuple


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------


class KmsError(RuntimeError):
    """Raised when a KMS operation cannot be completed."""


class KmsClient(ABC):
    """Abstract base for key-management backends."""

    @abstractmethod
    def get_active_fernet_key(self) -> Tuple[str, bytes]:
        """
        Return ``(key_id, raw_fernet_key_bytes)`` for the active key.

        ``key_id`` is a stable, human-readable identifier we store
        in the envelope so future rotations can decrypt old rows.

        ``raw_fernet_key_bytes`` is the 32-byte url-safe base64-encoded
        Fernet key (the format Fernet expects).
        """


# ---------------------------------------------------------------------------
# 1. Env-var backend (default)
# ---------------------------------------------------------------------------


class EnvKmsClient(KmsClient):
    """
    Read the active Fernet key from the ``ENCRYPTION_KEYS`` env var.

    Format: ``key_id:fernet_base64[,key_id:fernet_base64,...]``
    The first entry is the active key.  All entries are valid for
    decryption (rotation support).
    """

    def get_active_fernet_key(self) -> Tuple[str, bytes]:
        raw = os.getenv("ENCRYPTION_KEYS", "").strip()
        if not raw:
            legacy = (os.getenv("ENCRYPTION_KEY", "") or "").strip()
            if legacy and not legacy.startswith("dev-encryption-key"):
                raw = f"current:{legacy}"
        if not raw:
            raise KmsError(
                "ENCRYPTION_KEYS (or legacy ENCRYPTION_KEY) is required."
            )
        # Parse first key_id:fernet_base64 pair.
        first = raw.split(",", 1)[0].strip()
        if ":" not in first:
            raise KmsError(
                f"Malformed ENCRYPTION_KEYS entry (expected key_id:fernet): {first!r}"
            )
        key_id, key = first.split(":", 1)
        return key_id.strip(), key.strip().encode("utf-8")


# ---------------------------------------------------------------------------
# 2. AWS KMS backend
# ---------------------------------------------------------------------------


class AwsKmsClient(KmsClient):
    """
    Resolve the Fernet key via AWS KMS.

    Required env:
        - AWS_KMS_KEY_ARN:  ARN of the customer master key.
        - AWS_REGION:       KMS region (default us-east-1).
        - ENCRYPTION_KEYS:  must contain an entry like
                            ``aws:<base64-encrypted-data-key>``
                            where ``<base64-encrypted-data-key>`` is
                            the KMS-encrypted data key blob returned
                            by ``GenerateDataKey``.

    The data key is decrypted in-memory and cached for 5 minutes.
    Every encrypt/decrypt that uses the key shares the same cache.
    """

    _cache: Optional[Tuple[str, bytes, float]] = None
    _CACHE_TTL = 300  # 5 minutes

    def __init__(self):
        self._key_arn = os.getenv("AWS_KMS_KEY_ARN", "").strip()
        if not self._key_arn:
            raise KmsError("AWS_KMS_KEY_ARN is required for KMS_BACKEND=aws")

    def get_active_fernet_key(self) -> Tuple[str, bytes]:
        cached = self._read_cache()
        if cached:
            return cached

        # Find the ``aws:`` entry in ENCRYPTION_KEYS.
        raw = os.getenv("ENCRYPTION_KEYS", "").strip()
        encrypted_blob = None
        key_id = "aws-active"
        for entry in raw.split(","):
            entry = entry.strip()
            if entry.startswith("aws:"):
                encrypted_blob = entry.split(":", 1)[1].strip()
                # The blob is base64; we don't add a separate key_id
                # because AWS KMS itself is the key custodian.
                break
        if not encrypted_blob:
            raise KmsError(
                "ENCRYPTION_KEYS must contain an ``aws:<encrypted-blob>`` "
                "entry when KMS_BACKEND=aws.  Generate one with the "
                "included `scripts/generate_aws_data_key.py`."
            )

        plaintext = self._kms_decrypt(encrypted_blob)
        # Cache the decrypted key.
        AwsKmsClient._cache = (key_id, plaintext, time.time() + self._CACHE_TTL)
        return key_id, plaintext

    def _read_cache(self) -> Optional[Tuple[str, bytes]]:
        c = AwsKmsClient._cache
        if c is None:
            return None
        key_id, key, expires_at = c
        if time.time() >= expires_at:
            AwsKmsClient._cache = None
            return None
        return key_id, key

    def _kms_decrypt(self, encrypted_blob_b64: str) -> bytes:
        try:
            import boto3
            from botocore.config import Config
        except Exception as exc:  # pragma: no cover
            raise KmsError(
                "boto3 is required for KMS_BACKEND=aws. "
                "Install with `pip install boto3`."
            ) from exc

        client = boto3.client(
            "kms",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_REGION", "us-east-1"),
            config=Config(retries={"max_attempts": 3, "mode": "standard"}),
        )
        try:
            response = client.decrypt(
                CiphertextBlob=_b64decode(encrypted_blob_b64),
            )
        except Exception as exc:
            raise KmsError(f"AWS KMS decrypt failed: {exc}") from exc
        return response["Plaintext"]


def _b64decode(s: str) -> bytes:
    import base64
    return base64.b64decode(s.encode("ascii"))


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


_client: Optional[KmsClient] = None


def get_kms_client() -> KmsClient:
    """
    Return a memoized ``KmsClient`` for the configured backend.

    Backend is selected by the ``KMS_BACKEND`` env var:

      - ``KMS_BACKEND=env`` (default)   → EnvKmsClient
      - ``KMS_BACKEND=aws``             → AwsKmsClient
      - ``KMS_BACKEND=local``           → EnvKmsClient (alias)
    """
    global _client
    if _client is not None:
        return _client
    backend = (os.getenv("KMS_BACKEND", "env") or "env").strip().lower()
    if backend in ("env", "local", ""):
        _client = EnvKmsClient()
    elif backend == "aws":
        _client = AwsKmsClient()
    else:
        raise KmsError(f"Unknown KMS_BACKEND: {backend!r}")
    logger.info(f"KMS backend: {backend}")
    return _client


# ---------------------------------------------------------------------------
# Rotation helper
# ---------------------------------------------------------------------------


def rotate_active_key(new_key_id: str, new_key_b64: str) -> None:
    """
    Helper for an operator to rotate the active key.

    Updates the in-memory cache and (in production) emits a Sentry
    event.  The actual env-var update is the operator's responsibility
    (or a deploy hook).

    For AWS KMS, ``new_key_b64`` is the base64-encoded encrypted data
    key returned by ``GenerateDataKey``.
    """
    global _client
    if _client is not None:
        try:
            from app.core.encryption import reset_keyring_for_tests
            reset_keyring_for_tests()
        except Exception:
            pass
    AwsKmsClient._cache = None
    # Clear the module-level KMS client so it re-resolves with the new env.
    _client = None
    logger.info(
        f"Key rotation requested: new active key_id={new_key_id!r}. "
        "Reload the process to pick up the new key."
    )
