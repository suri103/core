"""
Security Utilities
==================

JWT tokens, password hashing, CSRF protection.

SECURITY HISTORY
----------------
- 2026-02: Migrated from `python-jose` (unmaintained since 2022) to
  `pyjwt[crypto]>=2.9.0` (actively maintained).
- 2026-02: Migrated from `passlib` (unmaintained since 2020) to direct
  `bcrypt>=4.2.0`. Removes the historical `<4.0` pin workaround and a
  transitive dependency on a dead library.
- 2026-02: All JWT operations use HS256 with an explicit
  ``algorithms=["HS256"]`` allow-list on decode (prevents alg-confusion /
  "alg: none" attacks).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import bcrypt
import jwt
import secrets
import re

from app.core.config_simple import settings


# ---------------------------------------------------------------------------
# Password hashing — direct bcrypt (no passlib)
# ---------------------------------------------------------------------------
#
# HIPAA-aligned: 14 rounds is the minimum recommended cost factor for
# healthcare (NIST SP 800-63B).  Each +1 doubles the work; 12 is a common
# baseline, 14 is conservative.

# bcrypt has a 72-byte input limit.  Pre-hashing with SHA-256 lets us
# accept arbitrary-length passwords while keeping the bcrypt cost factor
# effective.  This is the same pattern recommended by the bcrypt author
# (https://github.com/pyca/bcrypt#security).
import hashlib
import base64


def _bcrypt_input(password: str) -> bytes:
    """Hash a password with SHA-256 before bcrypt (handles long passwords
    safely, deterministic per password).

    NOTE: the digest is base64-encoded, not raw. Raw SHA-256 output can
    contain NUL (0x00) bytes (~11.8% of digests), which bcrypt rejects
    with ValueError — previously locking those users out of login.
    """
    return base64.b64encode(hashlib.sha256(password.encode("utf-8")).digest())


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its bcrypt hash.

    Tries the current base64(SHA-256) pre-hash first, then falls back to
    the legacy raw-digest pre-hash so existing password hashes remain
    valid until the user next resets their password.
    """
    hashed = hashed_password.encode("utf-8")
    try:
        if bcrypt.checkpw(_bcrypt_input(plain_password), hashed):
            return True
        # Legacy format: raw SHA-256 digest (may itself contain NUL bytes,
        # which is why it was replaced).
        legacy = hashlib.sha256(plain_password.encode("utf-8")).digest()
        return bcrypt.checkpw(legacy, hashed)
    except (ValueError, TypeError):
        # Malformed hash (e.g. legacy non-bcrypt row): fail closed.
        return False


def get_password_hash(password: str) -> str:
    """Hash a password with bcrypt (14 rounds)."""
    salt = bcrypt.gensalt(rounds=14)
    return bcrypt.hashpw(_bcrypt_input(password), salt).decode("utf-8")


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validate password meets HIPAA-compliant requirements.
    Returns: (is_valid, error_message)
    """
    # F-2 FIX: floor the env-configurable minimum at 8 so an operator cannot
    # silently weaken the policy to PASSWORD_MIN_LENGTH=1 via env.
    effective_min = max(int(settings.PASSWORD_MIN_LENGTH or 0), 8)
    if len(password) < effective_min:
        return False, f"Password must be at least {effective_min} characters"

    if settings.PASSWORD_REQUIRE_UPPERCASE and not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"

    if settings.PASSWORD_REQUIRE_LOWERCASE and not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"

    if settings.PASSWORD_REQUIRE_DIGIT and not re.search(r"\d", password):
        return False, "Password must contain at least one digit"

    if settings.PASSWORD_REQUIRE_SPECIAL and not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must contain at least one special character"

    return True, ""


# ---------------------------------------------------------------------------
# JWT — PyJWT (not python-jose)
# ---------------------------------------------------------------------------
#
# SECURITY: explicit algorithm allow-list on encode AND decode.  This is the
# only correct way to use HMAC JWTs; without the allow-list an attacker who
# flips the token to ``alg: none`` or ``alg: RS256`` (and presents the HMAC
# secret as a public key) can forge tokens.

_JWT_ALG = settings.ALGORITHM  # "HS256"
_JWT_SECRET = settings.SECRET_KEY


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token with a unique ``jti`` for revocation."""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "type": "access",
        "iat": datetime.now(timezone.utc),
        "jti": secrets.token_hex(16),  # unique ID for revocation blacklist
    })
    return jwt.encode(to_encode, _JWT_SECRET, algorithm=_JWT_ALG)


def create_refresh_token(data: Dict[str, Any]) -> str:
    """Create JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh", "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, _JWT_SECRET, algorithm=_JWT_ALG)


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and validate a JWT.

    Returns the payload dict on success, ``None`` on any failure
    (expired, bad signature, wrong algorithm, malformed).

    SECURITY: ``algorithms`` is an explicit allow-list, not a wildcard.
    A token that says ``alg: none`` is rejected.
    """
    try:
        payload = jwt.decode(
            token,
            _JWT_SECRET,
            algorithms=[_JWT_ALG],  # explicit allow-list
            options={"require": ["exp", "type"]},
        )
        return payload
    except jwt.PyJWTError:
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# CSRF
# ---------------------------------------------------------------------------

def generate_csrf_token() -> str:
    """Generate a secure CSRF token."""
    return secrets.token_urlsafe(32)


def verify_csrf_token(token: str, expected_token: str) -> bool:
    """Verify CSRF token (constant-time comparison)."""
    if not token or not expected_token:
        return False
    return secrets.compare_digest(token, expected_token)


# ---------------------------------------------------------------------------
# Random tokens (password reset, invitations, etc.)
# ---------------------------------------------------------------------------

def generate_password_reset_token() -> str:
    """Generate a secure password reset token."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """
    Hash a token for secure storage.

    Uses SHA-256 for fast hashing of high-entropy tokens.  Tokens are
    already cryptographically random, so bcrypt's slow hashing adds no
    security here and only hurts UX (login latency).
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
