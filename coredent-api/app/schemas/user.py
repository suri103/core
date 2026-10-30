"""
User Schemas
Pydantic models for request/response validation
"""

from pydantic import BaseModel, EmailStr, Field, validator, field_validator
from typing import Optional
from datetime import datetime
from uuid import UUID

from app.models.user import UserRole


class UserBase(BaseModel):
    """Base user schema"""
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    role: UserRole


class UserCreate(UserBase):
    """Schema for creating a user"""
    # Keep the schema minimum aligned with the enforced policy
    # (PASSWORD_MIN_LENGTH) so validation errors are consistent.
    password: str = Field(..., min_length=12)
    practice_id: UUID


class UserUpdate(BaseModel):
    """Schema for updating a user"""
    email: Optional[EmailStr] = None
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserInDB(UserBase):
    """Schema for user in database"""
    id: UUID
    practice_id: UUID
    is_active: bool
    last_login: Optional[datetime]
    # First-login security flag: admin-provisioned accounts must rotate the
    # temporary password before the API gate lets them past /auth.
    must_change_password: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserResponse(UserInDB):
    """Schema for user response, including tenant display metadata."""
    full_name: str
    practice_name: Optional[str] = None
    practice_country: Optional[str] = None
    # Practice-configured ISO currency (e.g. "INR"); drives money display
    # in the frontend. Falls back to country-derived currency when null.
    practice_currency: Optional[str] = None

    class Config:
        from_attributes = True

    @validator('role', pre=False)
    def lowercase_role(cls, v):
        """Convert role enum to lowercase string for frontend compatibility"""
        if isinstance(v, UserRole):
            return v.value.lower()
        return str(v).lower() if v else v


class PasswordChange(BaseModel):
    """Schema for password change"""
    current_password: str
    new_password: str = Field(..., min_length=12)

    @validator('new_password')
    def passwords_must_differ(cls, v, values):
        if 'current_password' in values and v == values['current_password']:
            raise ValueError('New password must be different from current password')
        return v


# ---------------------------------------------------------------------------
# Staff invitation onboarding
# ---------------------------------------------------------------------------

class StaffInvitationCreate(BaseModel):
    """Invite a new staff member to the practice."""
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    role: UserRole

    @field_validator("role", mode="before")
    @classmethod
    def uppercase_role(cls, v):
        # Frontend sends lowercase role slugs ("dentist"); accept both
        # dialects at this boundary.
        return v.upper() if isinstance(v, str) else v


class StaffInvitationResponse(BaseModel):
    """A staff invitation as surfaced to the admin UI."""
    id: UUID
    email: EmailStr
    first_name: str
    last_name: str
    role: UserRole
    invited_by_name: str
    expires_at: datetime
    created_at: Optional[datetime] = None

    @validator("role", pre=False)
    def lowercase_role(cls, v):
        """Match the lowercase role convention used elsewhere in the API."""
        if isinstance(v, UserRole):
            return v.value.lower()
        return str(v).lower() if v else v

    class Config:
        from_attributes = True


class StaffInvitationValidateResponse(BaseModel):
    """Public (token-holder-visible) invitation details."""
    email: EmailStr
    first_name: str
    last_name: str
    role: UserRole
    practice_name: str
    invited_by_name: str
    is_valid: bool

    @validator("role", pre=False)
    def lowercase_role(cls, v):
        if isinstance(v, UserRole):
            return v.value.lower()
        return str(v).lower() if v else v

    class Config:
        from_attributes = True


class StaffInvitationAccept(BaseModel):
    """Accept an invitation by choosing the account password."""
    token: str = Field(..., min_length=1)
    password: str = Field(..., min_length=12)
