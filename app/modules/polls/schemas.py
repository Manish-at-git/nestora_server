from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.responses import ApiResponse


class PollOptionRequest(BaseModel):
    text: str = Field(min_length=1, max_length=255)

    @field_validator("text")
    @classmethod
    def trim(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Option cannot be blank")
        return value


class PollCreateRequest(BaseModel):
    question: str = Field(min_length=2, max_length=255)
    description: str | None = None
    visibility: str = "All"
    status: str = "Published"
    is_multiple_choice: bool = False
    end_date: datetime | None = None
    association_id: str | None = None
    options: list[PollOptionRequest] = Field(min_length=2, max_length=50)

    @field_validator("question")
    @classmethod
    def trim_question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Question cannot be blank")
        return value


class PollVoteRequest(BaseModel):
    option_ids: list[str] = Field(min_length=1, max_length=50)


class PollCommentRequest(BaseModel):
    comment: str = Field(min_length=1, max_length=2000)

    @field_validator("comment")
    @classmethod
    def trim_comment(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Comment cannot be blank")
        return value


class PollOptionResponse(BaseModel):
    id: str
    text: str
    option_text: str
    vote_count: int = 0
    vote_percentage: int = 0


class PollResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    association_id: str | None = None
    question: str
    description: str | None = None
    visibility: str | None = None
    status: str | None = None
    is_multiple_choice: bool = False
    end_date: datetime | None = None
    created_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    author_name: str | None = None
    options: list[PollOptionResponse] = []
    total_votes: int = 0
    my_votes: list[str] = []
    like_count: int = 0
    user_has_liked: bool = False
    comment_count: int = 0


class PollMutationResponse(BaseModel):
    updated: bool = True


class PollCreateResponse(BaseModel):
    id: str


class PollLikeResponse(BaseModel):
    liked: bool


class PollCommentResponse(BaseModel):
    id: str
    poll_id: str
    account_id: str
    content: str
    comment: str
    author_name: str | None = None
    created_at: datetime | None = None


class PollCommentCreateResponse(BaseModel):
    id: str


PollListResponse = ApiResponse[list[PollResponse]]
PollCommentListResponse = ApiResponse[list[PollCommentResponse]]
