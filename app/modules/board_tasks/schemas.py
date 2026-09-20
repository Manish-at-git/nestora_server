"""Pydantic contracts for board-task APIs."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.responses import ApiResponse
from app.modules.board_tasks.constants import BoardTaskStatus


class BoardTaskCreateRequest(BaseModel):
    association_id: str | None = None
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=5000)
    supervised_by: str = Field(min_length=1)
    image_url: str | None = None

    @field_validator("title", "description")
    @classmethod
    def trim_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value cannot be blank")
        return value


class BoardTaskStatusRequest(BaseModel):
    status: BoardTaskStatus


class BoardTaskMessageRequest(BaseModel):
    message: str | None = Field(default=None, max_length=10000)
    attachment_url: str | None = None

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str | None) -> str | None:
        value = value.strip() if value else None
        return value or None

    @model_validator(mode="after")
    def require_content(self) -> "BoardTaskMessageRequest":
        if not self.message and not self.attachment_url:
            raise ValueError("Message or attachment is required")
        return self


class BoardTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    association_id: str
    created_by: str
    title: str
    description: str | None = None
    supervised_by: str
    image_url: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime | None = None
    association_name: str | None = None
    supervised_by_name: str | None = None
    created_by_name: str | None = None


class BoardTaskMessageResponse(BaseModel):
    id: str
    board_task_id: str
    sender_id: str
    message: str | None = None
    attachment_url: str | None = None
    created_at: datetime
    email: str | None = None
    role_id: str | None = None
    sender_name: str | None = None


class BoardTaskCreateResponse(BaseModel):
    id: str


class BoardTaskMutationResponse(BaseModel):
    updated: bool = True


class BoardTaskMessageCreateResponse(BaseModel):
    id: str


class BoardMemberResponse(BaseModel):
    account_id: str
    name: str
    email: str
    contact_number: str | None = None
    profile_pic_url: str | None = None
    board_member_since: datetime | None = None


BoardTaskListResponse = ApiResponse[list[BoardTaskResponse]]
