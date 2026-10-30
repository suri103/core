"""
Authentication Schemas
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from uuid import UUID

from app.models.user import UserRole


class LoginRequest(BaseModel):
    """Login request schema"""
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    """Self-serve practice registration request.

    Creates a new Practice (tenant) and its first OWNER user atomically.
    """
    practice_name: str = Field(..., min_length=2, max_length=255)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=12)
    country: str = Field(default="US", min_length=2, max_length=2)
    phone: Optional[str] = Field(default=None, max_length=20)


class TokenResponse(BaseModel):
    """Access-token response; refresh credentials are cookie-only."""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int  # seconds
    # First-login force-change flag: admin-provisioned accounts must rotate
    # the temporary password before they get full API access.
    must_change_password: bool = False


class LoginResponse(TokenResponse):
    """Login response schema"""
    csrf_token: str


class TokenRefreshRequest(BaseModel):
    """Token refresh request; cookie-backed browser sessions may omit the body."""
    refresh_token: Optional[str] = None


class TokenData(BaseModel):
    """Token payload data (Hardened: No PHI)"""
    sub: str  # user_id
    role: UserRole
    practice_id: UUID
    type: str  # "access" or "refresh"
    email: Optional[str] = None # No longer stored in JWT


class ForgotPasswordRequest(BaseModel):
    """Forgot password request"""
    email: EmailStr


class VerifyEmailRequest(BaseModel):
    """Email verification request (token in body, not the URL)."""
    token: str = Field(..., min_length=1)


class InvitationValidateRequest(BaseModel):
    """Invitation validation token carried in a POST body."""
    token: str = Field(..., min_length=1)


class ResetPasswordRequest(BaseModel):
    """Reset password request"""
    token: str
    # Aligned with the enforced policy (PASSWORD_MIN_LENGTH)
    new_password: str = Field(..., min_length=12)


# NOTE: the invitation flow (InvitationValidateResponse /
# AcceptInvitationRequest) was removed — it had no endpoints. Staff
# onboarding uses admin-provisioned accounts + /auth/change-password.
