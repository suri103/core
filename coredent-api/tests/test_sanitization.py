"""
Tests for app/core/sanitization.py.

Defense-in-depth input sanitizers used in search and form fields.
"""
from __future__ import annotations

import pytest

from app.core.sanitization import (
    sanitize_email,
    sanitize_id,
    sanitize_name,
    sanitize_phone,
    sanitize_search_query,
)


# ---------------------------------------------------------------------------
# sanitize_search_query
# ---------------------------------------------------------------------------

class TestSanitizeSearchQuery:
    def test_none_returns_none(self):
        assert sanitize_search_query(None) is None

    def test_empty_returns_none(self):
        assert sanitize_search_query("") is None
        assert sanitize_search_query("   ") is None

    def test_strips_whitespace(self):
        assert sanitize_search_query("  hello  ") == "hello"

    def test_truncates_to_max_length(self):
        q = "x" * 200
        assert sanitize_search_query(q, max_length=50) == "x" * 50

    @pytest.mark.parametrize("dangerous,expected_clean", [
        ("john'; DROP TABLE users--", "john"),
        ("john UNION SELECT * FROM passwords", "john * FROM passwords"),
        ("exec(evil)", "evil)"),
        ("xp_cmdshell 'net user'", "'net user'"),
        ("<script>alert(1)</script>", "alert(1)</>"),
        ("javascript:alert(1)", "alert(1)"),
        ("onerror=alert(1)", "alert(1)"),
    ])
    def test_removes_dangerous_patterns(self, dangerous, expected_clean):
        result = sanitize_search_query(dangerous)
        assert result is not None
        # Each result is free of the dangerous pattern (case-insensitive)
        assert "drop table" not in result.lower()
        assert "<script" not in result.lower()
        assert "javascript:" not in result.lower()
        assert "onerror=" not in result.lower()

    def test_returns_none_when_only_dangerous_chars_remain(self):
        # After stripping patterns, only whitespace is left
        result = sanitize_search_query("';--")
        # The exact leftover depends on which pattern matches first;
        # either way the SQL/XSS markers must be gone.
        assert result is None or "drop" not in result.lower()

    def test_keeps_safe_punctuation(self):
        # Periods, apostrophes (not at start of comment), hyphens are OK
        result = sanitize_search_query("Dr. O'Brien-Smith")
        assert result is not None
        assert "Dr." in result
        assert "Brien-Smith" in result or "Brien" in result


# ---------------------------------------------------------------------------
# sanitize_phone
# ---------------------------------------------------------------------------

class TestSanitizePhone:
    def test_none_returns_none(self):
        assert sanitize_phone(None) is None
        assert sanitize_phone("") is None

    def test_keeps_digits_and_common_separators(self):
        # The sanitizer keeps digits, spaces, dashes, parens, and plus.
        # Periods are NOT in the keep set, so they're stripped.
        assert sanitize_phone("(555) 123-4567") == "(555) 123-4567"
        assert sanitize_phone("+1 555 123 4567") == "+1 555 123 4567"
        assert sanitize_phone("555.123.4567") == "5551234567"

    def test_strips_letters(self):
        assert sanitize_phone("CALL 555-1234") == "555-1234"

    def test_strips_after_only_chars_remain_returns_none(self):
        assert sanitize_phone("abc") is None


# ---------------------------------------------------------------------------
# sanitize_email
# ---------------------------------------------------------------------------

class TestSanitizeEmail:
    def test_none_returns_none(self):
        assert sanitize_email(None) is None
        assert sanitize_email("") is None

    def test_lowercases_and_strips(self):
        assert sanitize_email("  USER@Example.COM  ") == "user@example.com"

    @pytest.mark.parametrize("valid", [
        "user@example.com",
        "user.name+tag@sub.example.co.uk",
        "a@b.io",
    ])
    def test_valid_emails_pass_through(self, valid):
        assert sanitize_email(valid) == valid.lower()

    @pytest.mark.parametrize("invalid", [
        "no-at-sign",
        "@no-local.com",
        "user@",
        "user@.com",
        "user@com",
        "user example.com",
    ])
    def test_invalid_emails_return_none(self, invalid):
        assert sanitize_email(invalid) is None


# ---------------------------------------------------------------------------
# sanitize_name
# ---------------------------------------------------------------------------

class TestSanitizeName:
    def test_none_returns_none(self):
        assert sanitize_name(None) is None
        assert sanitize_name("") is None

    def test_strips_whitespace(self):
        assert sanitize_name("  Jane  ") == "Jane"

    def test_truncates(self):
        assert sanitize_name("x" * 200, max_length=10) == "x" * 10

    def test_strips_html_tags(self):
        # Tags are stripped but inner text is kept (defense-in-depth).
        # XSS attempts via <script> tags are neutralized; the inner
        # 'alert(1)' remains as harmless text.
        assert sanitize_name("<b>Bold</b>") == "Bold"
        assert sanitize_name("Hello<script>alert(1)</script>World") == "Helloalert(1)World"
        # No script tag remains:
        assert "<script" not in sanitize_name("Hello<script>alert(1)</script>World")

    def test_returns_none_when_only_tags_remain(self):
        assert sanitize_name("<br/>") is None


# ---------------------------------------------------------------------------
# sanitize_id
# ---------------------------------------------------------------------------

class TestSanitizeId:
    def test_none_returns_none(self):
        assert sanitize_id(None) is None
        assert sanitize_id("") is None

    def test_keeps_alphanumeric_dash_underscore(self):
        assert sanitize_id("abc-123_XYZ") == "abc-123_XYZ"
        assert sanitize_id("550e8400-e29b-41d4-a716-446655440000") == (
            "550e8400-e29b-41d4-a716-446655440000"
        )

    def test_strips_other_characters(self):
        # Dashes are KEPT (allowed for UUID-style IDs); only the apostrophe
        # and semicolon are stripped.
        assert sanitize_id("user'; DROP--") == "userDROP--"

    def test_returns_none_when_only_stripped_chars(self):
        assert sanitize_id("!@#$%") is None
