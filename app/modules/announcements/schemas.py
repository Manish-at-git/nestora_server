"""Pydantic contracts for announcement APIs."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.responses import ApiResponse
from app.modules.announcements.constants import AnnouncementCategory, AnnouncementAudience


class AnnouncementCreateRequest(BaseModel):
    association_id: str | None = None
    title: str = Field(min_length=2, max_length=200)
    body: str = Field(min_length=2, max_length=5000)
    category: AnnouncementCategory = AnnouncementCategory.GENERAL
    pinned: bool = False
    audience: str = AnnouncementAudience.ALL
    attachment_url: str | None = None

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, value: str | None) -> AnnouncementCategory:
        normalized = (value or AnnouncementCategory.GENERAL).strip().lower()
        return AnnouncementCategory(normalized)

    @field_validator("title", "body")
    @classmethod
    def trim_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Announcement content cannot be blank")
        return value

    @field_validator("audience")
    @classmethod
    def normalize_audience(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Audience is required")
        return value


class AnnouncementCommentRequest(BaseModel):
    comment: str = Field(min_length=1, max_length=2000)

    @field_validator("comment")
    @classmethod
    def trim_comment(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Comment cannot be blank")
        return value


class AnnouncementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    body: str
    category: str | None = None
    pinned: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
    association_id: str | None = None
    audience: str | None = None
    attachment_url: str | None = None
    author_name: str | None = None
    author_role: str | None = None
    likes_count: int = 0
    comments_count: int = 0
    liked: bool = False


class AnnouncementCommentResponse(BaseModel):
    id: str
    comment: str
    created_at: datetime | None = None
    author_name: str | None = None


class AnnouncementCreateResponse(BaseModel):
    id: str


class AnnouncementLikeResponse(BaseModel):
    liked: bool


class AnnouncementMutationResponse(BaseModel):
    updated: bool = True


class AnnouncementCommentCreateResponse(BaseModel):
    id: str


AnnouncementListResponse = ApiResponse[list[AnnouncementResponse]]
AnnouncementCommentListResponse = ApiResponse[list[AnnouncementCommentResponse]]
