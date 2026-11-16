"""Request and response contracts for the violations module."""

from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.violations.constants import ViolationAction, ViolationStatus, ViolatorResponse


class _TrimmedModel(BaseModel):
    @field_validator("*", mode="before")
    @classmethod
    def trim_strings(cls, value):
        return value.strip() or None if isinstance(value, str) else value


class ViolationCreateRequest(_TrimmedModel):
    knows_violator: bool = True
    violator_user_id: str | None = Field(default=None, max_length=36)
    title: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=100)
    incident_at: datetime | None = None
    description: str = Field(min_length=1, max_length=5000)
    proof_url: str = Field(min_length=1, max_length=2048)
    audio_url: str | None = Field(default=None, max_length=2048)

    @field_validator("incident_at")
    @classmethod
    def incident_cannot_be_in_the_future(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        incident_at = value if value.tzinfo else value.replace(tzinfo=UTC)
        if incident_at > datetime.now(UTC):
            raise ValueError("Incident date and time cannot be in the future")
        return value

    @model_validator(mode="after")
    def require_target_when_known(self):
        if self.knows_violator and not self.violator_user_id:
            raise ValueError("Select the homeowner when the violator is known")
        if not self.knows_violator and self.violator_user_id:
            raise ValueError("An unidentified violator cannot include a homeowner")
        return self


class ViolationAdminReviewRequest(_TrimmedModel):
    offense_count: int = Field(ge=1, le=999)
    action: ViolationAction
    fine_amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    admin_notes: str | None = Field(default=None, max_length=5000)
    outcome: ViolationStatus

    @model_validator(mode="after")
    def validate_outcome(self):
        if self.outcome not in {ViolationStatus.PENDING_BOARD, ViolationStatus.REJECTED, ViolationStatus.DISMISSED}:
            raise ValueError("Admin review must send a violation to the board, reject it, or dismiss it")
        if self.action == ViolationAction.FINE and self.outcome != ViolationStatus.PENDING_BOARD:
            raise ValueError("A fine can only be set when sending a violation to the board")
        if self.action != ViolationAction.FINE and self.fine_amount is not None:
            raise ValueError("Only a Fine action may include a fine amount")
        return self


class ViolationBoardDecisionRequest(_TrimmedModel):
    outcome: ViolationStatus
    board_notes: str | None = Field(default=None, max_length=5000)

    @field_validator("outcome")
    @classmethod
    def only_board_outcomes(cls, value: ViolationStatus) -> ViolationStatus:
        if value not in {ViolationStatus.APPROVED, ViolationStatus.REJECTED}:
            raise ValueError("Board review must approve or reject a violation")
        return value


class ViolatorResponseRequest(BaseModel):
    response: ViolatorResponse


class ViolationMessageRequest(_TrimmedModel):
    body: str | None = Field(default=None, max_length=5000)
    attachment_url: str | None = Field(default=None, max_length=2048)

    @model_validator(mode="after")
    def require_content(self):
        if not self.body and not self.attachment_url:
            raise ValueError("A message or attachment is required")
        return self


class EligibleResidentResponse(BaseModel):
    user_id: str
    account_id: str | None = None
    unit_id: str
    role_code: str
    name: str
    unit_number: str | None = None
    block_name: str | None = None


class ViolationResponse(BaseModel):
    id: str
    display_id: str
    association_id: str
    title: str
    category: str
    incident_at: datetime | None = None
    description: str
    proof_url: str | None = None
    audio_url: str | None = None
    knows_violator: bool
    status: str
    offense_count: int | None = None
    action: str | None = None
    fine_amount: Decimal | None = None
    fine_applied: bool
    admin_notes: str | None = None
    board_notes: str | None = None
    violator_response: str | None = None
    responded_at: datetime | None = None
    reporter_name: str | None = None
    reporter_unit_number: str | None = None
    violator_name: str | None = None
    violator_unit_number: str | None = None
    is_current_user_violator: bool = False
    created_at: datetime
    updated_at: datetime | None = None


class ViolationFineDefaultResponse(BaseModel):
    amount: Decimal | None = None


class ActiveViolationFineResponse(BaseModel):
    id: str
    display_id: str
    title: str
    category: str
    fine_amount: Decimal


class ViolationMessageResponse(BaseModel):
    id: str
    violation_id: str
    sender_account_id: str
    sender_name: str | None = None
    body: str | None = None
    attachment_url: str | None = None
    created_at: datetime


class IdResponse(BaseModel):
    id: str
