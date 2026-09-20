"""Request and response DTOs; these validate API input without exposing database models directly."""

import re

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.access_codes import normalize_access_code
from app.core.constants import RoleCode


class PasswordRequest(BaseModel):
    """Shared password validation for account provisioning and password resets."""

    password: str = Field(min_length=12, max_length=256)

    @field_validator("password")
    @classmethod
    def require_strong_password(cls, value: str) -> str:
        """Reject common weak patterns before bcrypt work or database writes begin."""
        if not all(
            (
                re.search(r"[a-z]", value),
                re.search(r"[A-Z]", value),
                re.search(r"\d", value),
                re.search(r"[^\w\s]", value),
            )
        ):
            raise ValueError("Password must include upper-case, lower-case, number, and symbol characters")
        return value


class LoginRequest(BaseModel):
    """Credentials accepted by the legacy-compatible login path."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=256)


class ValidateCodeRequest(BaseModel):
    code: str = Field(min_length=8, max_length=8)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return normalize_access_code(value)


class ValidateCodeResponse(BaseModel):
    valid: bool = True
    code_id: str
    already_registered: bool = False


class AccessCodeRequest(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    contact_number: str = Field(min_length=6, max_length=30)


class AccessCodeRequestResponse(BaseModel):
    accepted: bool = True


class CreateMemberAccountRequest(PasswordRequest):
    # The public onboarding form documents an 8-character minimum. Keep the
    # stronger character-class validation inherited from PasswordRequest.
    password: str = Field(min_length=8, max_length=256)
    code: str = Field(min_length=8, max_length=8)
    email: EmailStr
    confirm_password: str

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return normalize_access_code(value)


class UpdateDetailsRequest(BaseModel):
    code: str = Field(min_length=8, max_length=8)
    requested_name: str | None = None
    requested_address: str | None = None
    requested_email: EmailStr | None = None
    requested_contact: str | None = None
    note: str | None = None

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return normalize_access_code(value)

    @field_validator("requested_email", mode="before")
    @classmethod
    def empty_email_is_optional(cls, value: str | None) -> str | None:
        return None if value is None or not str(value).strip() else value


class CodeRequestResponse(BaseModel):
    id: str
    name: str
    email: EmailStr
    contact_number: str
    status: str
    issued_code: str | None = None
    created_at: str | None = None


class IssueCodeRequest(BaseModel):
    request_id: str


class UpdateRequestResponse(BaseModel):
    id: str
    status: str
    requested_name: str | None = None
    requested_address: str | None = None
    requested_email: EmailStr | None = None
    requested_contact: str | None = None
    note: str | None = None
    created_at: str | None = None
    login_code: str | None = None


class AccessCodeStatsResponse(BaseModel):
    total_codes: int = 0
    used_codes: int = 0
    pending_requests: int = 0
    members: int = 0
    open_update_requests: int = 0


class UserDetailsResponse(BaseModel):
    user_id: str
    code_id: str | None = None
    name: str
    email: str
    contact_number: str
    address: str
    association_name: str | None = None
    address_line_1: str | None = None
    address_line_2: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None
    block_name: str | None = None
    unit_number: str | None = None


class CreateAccountRequest(PasswordRequest):
    """A privileged account-provisioning request; public registration is intentionally not allowed."""

    email: EmailStr
    role_code: RoleCode


class PasswordResetRequest(BaseModel):
    """Public request for reset instructions; response never reveals whether the email exists."""

    email: EmailStr


class PasswordResetVerifyRequest(BaseModel):
    """Bearer reset token supplied from the link delivered through the configured email provider."""

    token: str = Field(min_length=32, max_length=256)


class PasswordResetConfirmRequest(PasswordRequest):
    """One-time reset token and replacement password for the final password-change operation."""

    token: str = Field(min_length=32, max_length=256)


class RolePermissionResponse(BaseModel):
    """One role's database-backed access rule for a visible application feature."""

    feature_id: str
    feature_name: str
    feature_code: str | None = None
    parent_id: str | None = None
    icon: str | None = None
    url: str | None = None
    order_index: int = 0
    sidebar_order: int = 0
    can_create: bool = False
    can_view: bool = False
    can_update: bool = False
    can_delete: bool = False


class AccountResponse(BaseModel):
    """Safe account information that may be returned to a browser after authentication."""

    account_id: str
    email: EmailStr
    name: str | None = None
    role: str
    role_code: str
    association_id: str | None = None
    role_permissions: list[RolePermissionResponse] = Field(default_factory=list)


class LoginResponseData(BaseModel):
    """Login response data; the session itself remains exclusively inside an HttpOnly cookie."""

    account: AccountResponse


class LogoutResponseData(BaseModel):
    """Small explicit data object for a completed logout operation."""

    logged_out: bool = True


class PasswordResetRequestResponse(BaseModel):
    """Generic response that avoids disclosing whether a given email belongs to an account."""

    accepted: bool = True
    # Only populated by the development diagnostics in the password-reset
    # routes. Production responses remain generic to avoid account probing.
    email_sent: bool | None = None
    email_provider: str | None = None
    email_message_id: str | None = None
    email_error: str | None = None


class PasswordResetVerifyResponse(BaseModel):
    """A valid token can be used once by the subsequent password-reset confirmation endpoint."""

    valid: bool = True


class PasswordResetConfirmResponse(BaseModel):
    """Password reset completion response that exposes no account or session secret."""

    password_updated: bool = True


class LegacyPasswordResetRequest(BaseModel):
    """Email payload kept for the OTP-based recovery screen from the legacy client."""

    email: EmailStr


class PasswordResetOtpRequest(BaseModel):
    """A six-digit, short-lived recovery code scoped to the requested email."""

    email: EmailStr
    otp: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class LegacyPasswordResetConfirmRequest(BaseModel):
    """OTP and replacement password accepted by the legacy-compatible endpoint."""

    email: EmailStr
    otp: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    new_password: str = Field(min_length=8, max_length=256)

    @field_validator("new_password")
    @classmethod
    def require_strong_new_password(cls, value: str) -> str:
        if not all((re.search(r"[a-z]", value), re.search(r"[A-Z]", value), re.search(r"\d", value), re.search(r"[^\w\s]", value))):
            raise ValueError("Password must include upper-case, lower-case, number, and symbol characters")
        return value
