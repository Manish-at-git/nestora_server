from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.responses import ApiResponse


class BoardMemberCreateRequest(BaseModel):
    association_id: str
    account_id: str
    term_start_date: date
    term_end_date: date

    @field_validator("association_id", "account_id")
    @classmethod
    def trim_identifier(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Identifier is required")
        return value


class BoardMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str | None = None
    account_id: str
    user_id: str | None = None
    name: str
    email: str | None = None
    contact_number: str | None = None
    profile_pic_url: str | None = None
    board_member_since: date | None = None
    term_start_date: date | None = None
    term_end_date: date | None = None
    status: str | None = None
    role: str | None = None
    association_id: str | None = None
    association_name: str | None = None
    created_at: datetime | None = None


class HomeownerResponse(BaseModel):
    account_id: str
    user_id: str | None = None
    name: str
    email: str | None = None
    profile_pic_url: str | None = None


class BoardMemberCreateResponse(BaseModel):
    id: str


class BoardMemberMutationResponse(BaseModel):
    updated: bool = True


BoardMemberListResponse = ApiResponse[list[BoardMemberResponse]]
HomeownerListResponse = ApiResponse[list[HomeownerResponse]]
