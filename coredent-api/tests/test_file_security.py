"""
Tests for app/core/file_security.py.

Exercises the extension / magic-number / size validators, the
sanitize_filename / generate_secure_filename helpers, the
detect_mime_type fallback path, and the comprehensive
validate_file_upload orchestrator.

Virus scanning is tested separately via mocks because it depends on
external services (clamd, VirusTotal).
"""
from __future__ import annotations

import hashlib
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

# ``python-magic`` (libmagic binding) hangs on import in environments
# without libmagic installed. Stub it before any import that pulls in
# file_security so the test module can collect.
if "magic" not in sys.modules:
    _stub = ModuleType("magic")
    _stub.Magic = MagicMock
    sys.modules["magic"] = _stub

from app.core.file_security import (
    FileSecurityError,
    VirusScanner,
    calculate_file_hash,
    detect_mime_type,
    generate_secure_filename,
    sanitize_filename,
    validate_file_extension,
    validate_file_size,
    validate_file_upload,
    validate_magic_number,
)


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

JPEG_BYTES = b"\xFF\xD8\xFF" + b"\x00" * 100
PNG_BYTES = b"\x89\x50\x4E\x47\x0D\x0A\x1A\x0A" + b"\x00" * 100
GIF87A = b"GIF87a" + b"\x00" * 100
GIF89A = b"GIF89a" + b"\x00" * 100
PDF_BYTES = b"%PDF-1.4\n" + b"\x00" * 100
WEBP_BYTES = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 100
DOC_BYTES = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1" + b"\x00" * 100


@pytest.mark.asyncio
async def test_virus_scanner_fails_closed_without_provider_in_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    with patch.object(VirusScanner, "_init_clamav", return_value=None):
        scanner = VirusScanner()

    result = await scanner.scan_file(
        JPEG_BYTES,
        "patient-image.jpg",
        enable_virustotal=False,
    )

    assert result.is_clean is False
    assert result.scanner == "none"


@pytest.mark.asyncio
async def test_virus_scanner_fails_closed_in_staging(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "staging")
    with patch.object(VirusScanner, "_init_clamav", return_value=None):
        scanner = VirusScanner()

    result = await scanner.scan_file(
        JPEG_BYTES,
        "patient-image.jpg",
        enable_virustotal=False,
    )

    assert result.is_clean is False
    assert result.scanner == "none"


@pytest.mark.asyncio
async def test_read_stream_with_size_limit():
    from app.core.file_security import read_stream_with_size_limit
    from unittest.mock import AsyncMock

    mock_file = AsyncMock()
    mock_file.read.side_effect = [b"hello ", b"world", b""]
    data = await read_stream_with_size_limit(mock_file, 100)
    assert data == b"hello world"

    mock_file_large = AsyncMock()
    mock_file_large.read.side_effect = [b"a" * 50, b"b" * 60]
    with pytest.raises(FileSecurityError, match="File too large"):
        await read_stream_with_size_limit(mock_file_large, 100)


DOCX_BYTES = b"PK\x03\x04" + b"\x00" * 100
ZIP_BYTES = b"PK\x03\x04" + b"\x00" * 100


# ---------------------------------------------------------------------------
# validate_file_extension
# ---------------------------------------------------------------------------

class TestValidateFileExtension:
    def test_default_extensions_accept_common_types(self):
        assert validate_file_extension("photo.jpg") is True
        assert validate_file_extension("doc.pdf") is True
        assert validate_file_extension("letter.docx") is True

    def test_case_insensitive(self):
        assert validate_file_extension("photo.JPG") is True
        assert validate_file_extension("photo.JpG") is True

    def test_no_extension_raises(self):
        with pytest.raises(FileSecurityError, match="no extension"):
            validate_file_extension("README")

    def test_disallowed_extension_raises(self):
        with pytest.raises(FileSecurityError, match="not allowed"):
            validate_file_extension("malware.exe")

    def test_custom_allowed_extensions(self):
        # Only allow .csv in addition to defaults
        with pytest.raises(FileSecurityError):
            validate_file_extension("data.csv", allowed_extensions=["jpg"])
        assert validate_file_extension("photo.jpg", allowed_extensions=["jpg"]) is True

    def test_empty_extension_after_dot_raises(self):
        # "photo." -> extension is empty after lstrip(".")
        with pytest.raises(FileSecurityError):
            validate_file_extension("photo.")


# ---------------------------------------------------------------------------
# validate_magic_number
# ---------------------------------------------------------------------------

class TestValidateMagicNumber:
    def test_jpeg_magic_matches(self):
        assert validate_magic_number(JPEG_BYTES, "image/jpeg") is True

    def test_png_magic_matches(self):
        assert validate_magic_number(PNG_BYTES, "image/png") is True

    def test_gif_magic_matches_both_versions(self):
        assert validate_magic_number(GIF87A, "image/gif") is True
        assert validate_magic_number(GIF89A, "image/gif") is True

    def test_webp_magic_matches(self):
        assert validate_magic_number(WEBP_BYTES, "image/webp") is True

    def test_pdf_magic_matches(self):
        assert validate_magic_number(PDF_BYTES, "application/pdf") is True

    def test_text_plain_has_no_magic_returns_true(self):
        # text/plain has an empty magic list → always passes
        assert validate_magic_number(b"hello world", "text/plain") is True

    def test_wrong_magic_for_declared_type_raises(self):
        """JPEG bytes claimed as PNG must be rejected."""
        with pytest.raises(FileSecurityError, match="does not match expected type"):
            validate_magic_number(JPEG_BYTES, "image/png")

    def test_unknown_mime_type_raises(self):
        with pytest.raises(FileSecurityError, match="not allowed"):
            validate_magic_number(b"data", "application/x-evil")


# ---------------------------------------------------------------------------
# validate_file_size
# ---------------------------------------------------------------------------

class TestValidateFileSize:
    def test_within_limit_passes(self):
        # 1KB JPEG, well below 10MB limit
        assert validate_file_size(JPEG_BYTES + b"\x00" * 900, "image/jpeg") is True

    def test_zero_size_raises(self):
        with pytest.raises(FileSecurityError, match="empty"):
            validate_file_size(b"", "image/jpeg")

    def test_exceeds_limit_raises(self):
        # 11MB JPEG exceeds 10MB limit
        big = JPEG_BYTES + b"\x00" * (11 * 1024 * 1024)
        with pytest.raises(FileSecurityError, match="exceeds maximum"):
            validate_file_size(big, "image/jpeg")

    def test_unknown_mime_uses_default(self):
        # A 1MB file is under DEFAULT_MAX_SIZE (10MB)
        one_mb = b"\x00" * (1024 * 1024)
        assert validate_file_size(one_mb, "application/x-unknown") is True

    def test_unknown_mime_over_default_raises(self):
        # 11MB exceeds DEFAULT_MAX_SIZE
        too_big = b"\x00" * (11 * 1024 * 1024)
        with pytest.raises(FileSecurityError, match="exceeds maximum"):
            validate_file_size(too_big, "application/x-unknown")

    def test_pdf_can_be_larger_than_image(self):
        # PDF limit is 20MB; a 15MB PDF is fine
        big_pdf = PDF_BYTES + b"\x00" * (15 * 1024 * 1024)
        assert validate_file_size(big_pdf, "application/pdf") is True


# ---------------------------------------------------------------------------
# sanitize_filename
# ---------------------------------------------------------------------------

class TestSanitizeFilename:
    def test_strips_path_components(self):
        # ``Path(name).name`` removes any directory prefix
        assert sanitize_filename("../../../etc/passwd") == "passwd"

    def test_replaces_dangerous_chars(self):
        assert sanitize_filename("my file (1).pdf") == "my_file__1_.pdf"

    def test_collapses_multiple_dots(self):
        # Two dots collapsed to one (prevents ".." and "....." bypass tricks)
        assert sanitize_filename("file...name.txt") == "file.name.txt"

    def test_strips_leading_trailing_dots_and_dashes(self):
        # Leading dots are stripped; trailing dots+dashes are stripped.
        # Internal dashes are KEPT — they are part of the filename body.
        assert sanitize_filename("..hidden.txt") == "hidden.txt"
        # File ending in a dot gets the dot stripped (no extension).
        assert sanitize_filename("trailing.") == "trailing"

    def test_truncates_long_filenames(self):
        long = "a" * 300 + ".txt"
        result = sanitize_filename(long)
        assert len(result) <= 255
        assert result.endswith(".txt")

    def test_preserves_safe_chars(self):
        assert sanitize_filename("report-2024.pdf") == "report-2024.pdf"


# ---------------------------------------------------------------------------
# generate_secure_filename
# ---------------------------------------------------------------------------

class TestGenerateSecureFilename:
    def test_returns_uuid_hex_with_extension(self):
        result = generate_secure_filename("photo.jpg")
        assert result.endswith(".jpg")
        stem = result[:-4]
        # UUID hex is 32 chars, all hex
        assert len(stem) == 32
        int(stem, 16)  # raises if not valid hex

    def test_extension_is_lowercased(self):
        assert generate_secure_filename("PHOTO.JPG").endswith(".jpg")

    def test_no_extension_returns_no_suffix(self):
        result = generate_secure_filename("README")
        # No dot to split on -> empty extension
        assert "." not in result
        assert len(result) == 32


# ---------------------------------------------------------------------------
# calculate_file_hash
# ---------------------------------------------------------------------------

class TestCalculateFileHash:
    def test_returns_sha256_hex(self):
        data = b"hello"
        expected = hashlib.sha256(data).hexdigest()
        assert calculate_file_hash(data) == expected
        assert len(calculate_file_hash(data)) == 64

    def test_different_inputs_produce_different_hashes(self):
        assert calculate_file_hash(b"a") != calculate_file_hash(b"b")

    def test_empty_input_is_valid(self):
        """Empty input still produces a valid (deterministic) hash."""
        h = calculate_file_hash(b"")
        assert len(h) == 64
        assert h == hashlib.sha256(b"").hexdigest()


# ---------------------------------------------------------------------------
# detect_mime_type
# ---------------------------------------------------------------------------

class TestDetectMimeType:
    def test_returns_detected_type_when_magic_succeeds(self):
        with patch("magic.Magic") as mock_magic:
            mock_magic.return_value.from_buffer.return_value = "image/jpeg"
            assert detect_mime_type(JPEG_BYTES, "anything.bin") == "image/jpeg"

    def test_falls_back_to_extension_when_magic_fails(self):
        with patch("magic.Magic", side_effect=RuntimeError("libmagic missing")):
            assert detect_mime_type(b"\x00", "photo.jpg") == "image/jpeg"
            assert detect_mime_type(b"\x00", "doc.pdf") == "application/pdf"
            assert detect_mime_type(b"\x00", "data.xlsx") == "application/octet-stream"

    def test_unknown_extension_returns_octet_stream(self):
        with patch("magic.Magic", side_effect=RuntimeError("boom")):
            assert detect_mime_type(b"\x00", "weird.xyz") == "application/octet-stream"


# ---------------------------------------------------------------------------
# validate_file_upload (orchestrator)
# ---------------------------------------------------------------------------

class TestValidateFileUpload:
    """The all-in-one validator: extension + magic + size + sanitize + hash."""

    def test_valid_jpeg_passes(self):
        with patch("magic.Magic") as mock_factory:
            mock_factory.return_value.from_buffer.return_value = "image/jpeg"
            result = validate_file_upload(JPEG_BYTES, "photo.jpg")
        assert result["valid"] is True
        assert result["mime_type"] == "image/jpeg"
        assert result["size"] == len(JPEG_BYTES)
        # The secure filename is a UUID4 hex with the original extension
        assert result["secure_filename"].endswith(".jpg")
        assert len(result["secure_filename"]) == 32 + 4
        # The hash is SHA-256 of the bytes
        assert result["hash"] == hashlib.sha256(JPEG_BYTES).hexdigest()
        # safe_filename strips the path
        assert "/" not in result["safe_filename"]

    def test_invalid_extension_raises(self):
        with pytest.raises(FileSecurityError, match="not allowed"):
            validate_file_upload(JPEG_BYTES, "photo.exe")

    def test_magic_mismatch_raises(self):
        """JPEG bytes uploaded with a .png name must be rejected."""
        with patch("magic.Magic") as mock_factory:
            mock_factory.return_value.from_buffer.return_value = "image/png"
            with pytest.raises(FileSecurityError, match="does not match expected type"):
                validate_file_upload(JPEG_BYTES, "photo.png")

    def test_oversize_raises(self):
        # 11MB JPEG exceeds the 10MB JPEG limit
        big = JPEG_BYTES + b"\x00" * (11 * 1024 * 1024)
        with patch("magic.Magic") as mock_factory:
            mock_factory.return_value.from_buffer.return_value = "image/jpeg"
            with pytest.raises(FileSecurityError, match="exceeds maximum"):
                validate_file_upload(big, "photo.jpg")

    def test_custom_max_size_overrides_default(self):
        # 1MB JPEG with a 512KB cap must be rejected
        data = JPEG_BYTES + b"\x00" * (1024 * 1024 - len(JPEG_BYTES))
        with patch("magic.Magic") as mock_factory:
            mock_factory.return_value.from_buffer.return_value = "image/jpeg"
            with pytest.raises(FileSecurityError, match="exceeds maximum"):
                validate_file_upload(data, "photo.jpg", max_size=512 * 1024)

    def test_custom_max_size_allows_under_cap(self):
        data = JPEG_BYTES + b"\x00" * (100 * 1024)
        with patch("magic.Magic") as mock_factory:
            mock_factory.return_value.from_buffer.return_value = "image/jpeg"
            result = validate_file_upload(data, "photo.jpg", max_size=10 * 1024 * 1024)
        assert result["valid"] is True
        assert result["size"] == len(data)

    def test_empty_file_raises(self):
        """Empty bytes fail the magic-number check first (no JPEG signature).
        This is correct order — magic-number validation is cheaper and more
        specific than size, and an empty file with a `.jpg` extension is
        clearly wrong (can't be a valid JPEG)."""
        with patch("magic.Magic") as mock_factory:
            mock_factory.return_value.from_buffer.return_value = "image/jpeg"
            with pytest.raises(FileSecurityError, match="does not match expected type"):
                validate_file_upload(b"", "photo.jpg")

    def test_validate_file_size_rejects_empty_directly(self):
        """validate_file_size has its own empty-check, called directly
        by callers that skip magic-number validation."""
        with pytest.raises(FileSecurityError, match="empty"):
            validate_file_size(b"", "image/jpeg")

    def test_validation_chains_multiple_failures(self):
        """If multiple checks would fail, the FIRST one (extension) wins —
        we never silently accept a file that failed an earlier check."""
        # Empty file with bad extension: extension check fires first.
        with pytest.raises(FileSecurityError, match="not allowed"):
            validate_file_upload(b"", "evil.exe")
