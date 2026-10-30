"""
Tests for app/core/kms.py.

Exercises:
- EnvKmsClient: parses ``ENCRYPTION_KEYS`` (and the legacy fallback).
- AwsKmsClient: cache hit/miss/expiry, env-var validation.
- get_kms_client factory: backend dispatch.
- rotate_active_key: clears caches.
"""
from __future__ import annotations

import base64
import importlib
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def kms_module(monkeypatch):
    """Reload kms with a clean module-level cache."""
    monkeypatch.setenv("KMS_BACKEND", "env")
    monkeypatch.setenv("AWS_KMS_KEY_ARN", "")
    monkeypatch.setenv("ENCRYPTION_KEYS", "")
    monkeypatch.setenv("ENCRYPTION_KEY", "")
    from app.core import kms
    importlib.reload(kms)
    kms._client = None
    kms.AwsKmsClient._cache = None
    return kms


# ---------------------------------------------------------------------------
# EnvKmsClient
# ---------------------------------------------------------------------------

class TestEnvKmsClient:
    def test_returns_active_key_from_encryption_keys(self, kms_module, monkeypatch):
        key_b64 = base64.urlsafe_b64encode(b"\x00" * 32).decode()
        monkeypatch.setenv(
            "ENCRYPTION_KEYS", f"primary:{key_b64},retired:abc"
        )
        importlib.reload(kms_module)
        key_id, raw = kms_module.EnvKmsClient().get_active_fernet_key()
        assert key_id == "primary"
        assert raw == key_b64.encode("utf-8")

    def test_falls_back_to_legacy_encryption_key(self, kms_module, monkeypatch):
        """Single ENCRYPTION_KEY (legacy) is wrapped as ``current:<key>``."""
        key_b64 = base64.urlsafe_b64encode(b"\x00" * 32).decode()
        monkeypatch.setenv("ENCRYPTION_KEYS", "")
        monkeypatch.setenv("ENCRYPTION_KEY", key_b64)
        importlib.reload(kms_module)
        key_id, raw = kms_module.EnvKmsClient().get_active_fernet_key()
        assert key_id == "current"
        assert raw == key_b64.encode("utf-8")

    def test_ignores_dev_encryption_key_in_legacy_fallback(
        self, kms_module, monkeypatch
    ):
        """The literal dev key is not a real Fernet key — must NOT be used."""
        monkeypatch.setenv("ENCRYPTION_KEYS", "")
        monkeypatch.setenv("ENCRYPTION_KEY", "dev-encryption-key-CHANGE-ME")
        importlib.reload(kms_module)
        with pytest.raises(kms_module.KmsError, match="ENCRYPTION_KEYS"):
            kms_module.EnvKmsClient().get_active_fernet_key()

    def test_raises_when_no_keys_configured(self, kms_module, monkeypatch):
        monkeypatch.setenv("ENCRYPTION_KEYS", "")
        monkeypatch.setenv("ENCRYPTION_KEY", "")
        importlib.reload(kms_module)
        with pytest.raises(kms_module.KmsError, match="ENCRYPTION_KEYS"):
            kms_module.EnvKmsClient().get_active_fernet_key()

    def test_raises_on_malformed_entry(self, kms_module, monkeypatch):
        monkeypatch.setenv("ENCRYPTION_KEYS", "no-colon-here")
        importlib.reload(kms_module)
        with pytest.raises(kms_module.KmsError, match="Malformed"):
            kms_module.EnvKmsClient().get_active_fernet_key()

    def test_takes_first_entry_as_active(self, kms_module, monkeypatch):
        """When multiple keys are present, the first is the active one."""
        k1 = base64.urlsafe_b64encode(b"\x01" * 32).decode()
        k2 = base64.urlsafe_b64encode(b"\x02" * 32).decode()
        monkeypatch.setenv("ENCRYPTION_KEYS", f"first:{k1},second:{k2}")
        importlib.reload(kms_module)
        key_id, _ = kms_module.EnvKmsClient().get_active_fernet_key()
        assert key_id == "first"

    def test_strips_whitespace(self, kms_module, monkeypatch):
        key_b64 = base64.urlsafe_b64encode(b"\x00" * 32).decode()
        monkeypatch.setenv("ENCRYPTION_KEYS", f"  primary : {key_b64}  ")
        importlib.reload(kms_module)
        key_id, raw = kms_module.EnvKmsClient().get_active_fernet_key()
        assert key_id == "primary"
        assert raw == key_b64.encode("utf-8")


# ---------------------------------------------------------------------------
# AwsKmsClient
# ---------------------------------------------------------------------------

class TestAwsKmsClient:
    def test_raises_when_no_key_arn(self, kms_module, monkeypatch):
        monkeypatch.setenv("AWS_KMS_KEY_ARN", "")
        monkeypatch.setenv(
            "ENCRYPTION_KEYS",
            f"aws:{base64.b64encode(b'ciphertext').decode()}",
        )
        importlib.reload(kms_module)
        with pytest.raises(kms_module.KmsError, match="AWS_KMS_KEY_ARN"):
            kms_module.AwsKmsClient()

    def test_raises_when_no_aws_entry_in_env(self, kms_module, monkeypatch):
        monkeypatch.setenv("AWS_KMS_KEY_ARN", "arn:aws:kms:us-east-1:1:key/abc")
        monkeypatch.setenv("ENCRYPTION_KEYS", "primary:abc,retired:def")
        importlib.reload(kms_module)
        client = kms_module.AwsKmsClient()
        with pytest.raises(kms_module.KmsError, match="aws:"):
            client.get_active_fernet_key()

    def test_decrypts_and_caches(self, kms_module, monkeypatch):
        monkeypatch.setenv("AWS_KMS_KEY_ARN", "arn:aws:kms:us-east-1:1:key/abc")
        plaintext = b"\x00" * 32
        ciphertext = b"ciphertext-blob"
        monkeypatch.setenv(
            "ENCRYPTION_KEYS",
            f"aws:{base64.b64encode(ciphertext).decode()}",
        )
        importlib.reload(kms_module)
        kms_module.AwsKmsClient._cache = None

        client = kms_module.AwsKmsClient()
        # First call -> decrypt + cache
        with patch.object(client, "_kms_decrypt", return_value=plaintext) as dec:
            key_id, raw = client.get_active_fernet_key()
        dec.assert_called_once()
        assert key_id == "aws-active"
        assert raw == plaintext

        # Second call -> cache hit, no further decrypt
        with patch.object(client, "_kms_decrypt") as dec:
            key_id2, raw2 = client.get_active_fernet_key()
        dec.assert_not_called()
        assert (key_id2, raw2) == (key_id, raw)

    def test_cache_expires(self, kms_module, monkeypatch):
        monkeypatch.setenv("AWS_KMS_KEY_ARN", "arn:aws:kms:us-east-1:1:key/abc")
        monkeypatch.setenv(
            "ENCRYPTION_KEYS",
            f"aws:{base64.b64encode(b'cipher').decode()}",
        )
        importlib.reload(kms_module)

        client = kms_module.AwsKmsClient()
        # Manually install an expired cache entry
        import time
        kms_module.AwsKmsClient._cache = (
            "aws-active",
            b"\x00" * 32,
            time.time() - 1,  # already expired
        )
        with patch.object(client, "_kms_decrypt", return_value=b"\x01" * 32) as dec:
            _, raw = client.get_active_fernet_key()
        dec.assert_called_once()
        assert raw == b"\x01" * 32

    def test_kms_decrypt_wraps_boto_errors(self, kms_module, monkeypatch):
        monkeypatch.setenv("AWS_KMS_KEY_ARN", "arn:aws:kms:us-east-1:1:key/abc")
        monkeypatch.setenv(
            "ENCRYPTION_KEYS",
            f"aws:{base64.b64encode(b'cipher').decode()}",
        )
        importlib.reload(kms_module)

        client = kms_module.AwsKmsClient()
        with patch("boto3.client") as boto:
            boto.return_value.decrypt.side_effect = RuntimeError("denied")
            with pytest.raises(kms_module.KmsError, match="AWS KMS decrypt failed"):
                client._kms_decrypt(base64.b64encode(b"cipher").decode())

    def test_kms_decrypt_raises_when_boto_missing(self, kms_module, monkeypatch):
        """If boto3 is not importable, the user gets a clear KmsError."""
        monkeypatch.setenv("AWS_KMS_KEY_ARN", "arn:aws:kms:us-east-1:1:key/abc")
        importlib.reload(kms_module)
        client = kms_module.AwsKmsClient()

        import builtins
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "boto3" or name.startswith("boto3."):
                raise ImportError("boto3 not installed")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        with pytest.raises(kms_module.KmsError, match="boto3 is required"):
            client._kms_decrypt("anything")


# ---------------------------------------------------------------------------
# get_kms_client factory
# ---------------------------------------------------------------------------

class TestGetKmsClient:
    def test_default_backend_is_env(self, kms_module, monkeypatch):
        monkeypatch.delenv("KMS_BACKEND", raising=False)
        importlib.reload(kms_module)
        kms_module._client = None
        client = kms_module.get_kms_client()
        assert isinstance(client, kms_module.EnvKmsClient)

    def test_local_alias_returns_env(self, kms_module, monkeypatch):
        monkeypatch.setenv("KMS_BACKEND", "local")
        importlib.reload(kms_module)
        kms_module._client = None
        client = kms_module.get_kms_client()
        assert isinstance(client, kms_module.EnvKmsClient)

    def test_aws_backend_returns_aws_client(self, kms_module, monkeypatch):
        monkeypatch.setenv("KMS_BACKEND", "aws")
        monkeypatch.setenv("AWS_KMS_KEY_ARN", "arn:aws:kms:us-east-1:1:key/abc")
        importlib.reload(kms_module)
        kms_module._client = None
        client = kms_module.get_kms_client()
        assert isinstance(client, kms_module.AwsKmsClient)

    def test_unknown_backend_raises(self, kms_module, monkeypatch):
        monkeypatch.setenv("KMS_BACKEND", "azure")
        importlib.reload(kms_module)
        kms_module._client = None
        with pytest.raises(kms_module.KmsError, match="Unknown KMS_BACKEND"):
            kms_module.get_kms_client()

    def test_memoizes_client(self, kms_module, monkeypatch):
        monkeypatch.delenv("KMS_BACKEND", raising=False)
        importlib.reload(kms_module)
        kms_module._client = None
        a = kms_module.get_kms_client()
        b = kms_module.get_kms_client()
        assert a is b


# ---------------------------------------------------------------------------
# rotate_active_key
# ---------------------------------------------------------------------------

class TestRotateActiveKey:
    def test_clears_aws_cache_and_factory(self, kms_module, monkeypatch):
        kms_module.AwsKmsClient._cache = ("id", b"x", 9999999999)
        kms_module._client = MagicMock()
        kms_module.rotate_active_key("new-key", base64.urlsafe_b64encode(b"y").decode())
        assert kms_module.AwsKmsClient._cache is None
        assert kms_module._client is None

    def test_swallows_reset_keyring_errors(self, kms_module, monkeypatch):
        """If encryption.reset_keyring_for_tests raises, rotation must not
        crash — the cache still has to be cleared."""
        kms_module.AwsKmsClient._cache = ("id", b"x", 9999999999)
        kms_module._client = MagicMock()
        with patch.dict("sys.modules", {"app.core.encryption": MagicMock(
            reset_keyring_for_tests=MagicMock(side_effect=RuntimeError("boom")),
        )}):
            kms_module.rotate_active_key("k", "x")
        assert kms_module.AwsKmsClient._cache is None
