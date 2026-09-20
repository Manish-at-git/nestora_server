"""Pydantic contracts for committee APIs."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.responses import ApiResponse


class CommitteeMemberInput(BaseModel):
    user_id: str = Field(min_length=1)
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def dates_are_ordered(self) -> "CommitteeMemberInput":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("End date cannot be before start date")
        return self


class CommitteeCreateRequest(BaseModel):
    association_id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=5000)
    start_date: date | None = None
    end_date: date | None = None
    members: list[CommitteeMemberInput] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Committee name cannot be blank")
        return value

    @model_validator(mode="after")
    def dates_are_ordered(self) -> "CommitteeCreateRequest":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("End date cannot be before start date")
        return self


class CommitteeUpdateRequest(CommitteeCreateRequest):
    pass


class CommitteeMemberAssignRequest(CommitteeMemberInput):
    committee_id: str = Field(min_length=1)


class CommitteeMemberUpdateRequest(BaseModel):
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def dates_are_ordered(self) -> "CommitteeMemberUpdateRequest":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("End date cannot be before start date")
        return self


class CommitteeMemberInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    name: str
    email: str | None = None
    profile_pic_url: str | None = None
    start_date: date | None = None
    end_date: date | None = None


class CommitteeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    association_id: str
    association_name: str | None = None
    name: str
    description: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    created_at: datetime | None = None
    member_count: int = 0
    members: list[CommitteeMemberInfo] = Field(default_factory=list)


class HomeownerResponse(BaseModel):
    account_id: str
    user_id: str
    name: str
    email: str | None = None
    profile_pic_url: str | None = None
    contact_number: str | None = None
    unit_number: str | None = None
    block_name: str | None = None
    association_id: str
    association_name: str | None = None


class CommitteeMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    committee_member_id: str
    committee_id: str
    user_id: str
    role_start_date: date | None = None
    role_end_date: date | None = None
    created_at: datetime | None = None
    committee_name: str
    association_id: str
    association_name: str | None = None
    name: str
    email: str | None = None
    phone: str | None = None
    profile_pic_url: str | None = None


class IdResponse(BaseModel):
    id: str


class MutationResponse(BaseModel):
    updated: bool = True


class CommitteeChatMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)
    attachment_url: str | None = None

    @field_validator("message")
    @classmethod
    def trim_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message cannot be blank")
        return value


class CommitteeChatMessageResponse(BaseModel):
    id: str
    association_id: str | None = None
    pool_type: str | None = None
    pool_id: str | None = None
    sender_id: str | None = None
    message: str | None = None
    attachment_url: str | None = None
    created_at: datetime | None = None
    email: str | None = None
    sender_name: str | None = None
    profile_pic_url: str | None = None
    is_mine: bool = False


CommitteeListResponse = ApiResponse[list[CommitteeResponse]]
CommitteeMemberListResponse = ApiResponse[list[CommitteeMemberResponse]]
HomeownerListResponse = ApiResponse[list[HomeownerResponse]]
