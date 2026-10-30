"""Tests for encryption module"""
import os

import pytest
from cryptography.fernet import Fernet


class TestFernetEncryption:
    """Test Fernet encryption/decryption"""

    def test_fernet_key_generation(self):
        """Verify Fernet key can be generated"""
        key = Fernet.generate_key()
        assert len(key) == 44  # Fernet keys are 44 bytes base64-encoded
        assert key.endswith(b"=")  # Base64 padding

    def test_fernet_encrypt_decrypt(self):
        """Verify encryption and decryption roundtrip"""
        key = Fernet.generate_key()
        f = Fernet(key)
        data = b"test sensitive data"
        token = f.encrypt(data)
        assert token != data
        assert f.decrypt(token) == data

    def test_fernet_invalid_key(self):
        """Verify invalid Fernet key is rejected"""
        with pytest.raises((ValueError, TypeError)):
            Fernet(b"not-a-valid-fernet-key")

    def test_fernet_tamper_detection(self):
        """Verify tampered ciphertext is detected"""
        key = Fernet.generate_key()
        f = Fernet(key)
        token = f.encrypt(b"test")
        tampered = bytearray(token)
        tampered[10] ^= 0xFF  # Flip a bit
        with pytest.raises(Exception):
            f.decrypt(bytes(tampered))


class TestEncryptionModule:
    """Test the app.core.encryption helpers."""

    def test_encrypt_decrypt_roundtrip(self):
        """encrypt_value / decrypt_value should roundtrip correctly."""
        from app.core.encryption import encrypt_value, decrypt_value

        # In test environment the cipher may be absent (plaintext passthrough)
        # or configured; either way the value must survive the roundtrip.
        original = "secret-phi-value"
        ciphertext = encrypt_value(original)
        assert ciphertext is not None
        assert decrypt_value(ciphertext) == original

    def test_encrypt_none_returns_none(self):
        from app.core.encryption import encrypt_value, decrypt_value

        assert encrypt_value(None) is None
        assert decrypt_value(None) is None


class TestEncryptionSettings:
    """Verify the hardened production key guards."""

    def test_encryption_key_default_is_invalid_in_production(self):
        """Missing ENCRYPTION_KEY must fail config load in production."""
        os.environ["ENVIRONMENT"] = "production"
        os.environ.pop("ENCRYPTION_KEY", None)
        os.environ.pop("SECRET_KEY", None)
        os.environ["DEBUG"] = "false"
        try:
            from app.core.config_simple import SimpleSettings
            with pytest.raises(RuntimeError, match="ENCRYPTION_KEY|SECRET_KEY"):
                SimpleSettings()
        finally:
            os.environ["ENVIRONMENT"] = "development"
            os.environ.pop("DEBUG", None)
