"""Pydantic contracts for meeting APIs."""

from datetime import date, datetime, time

from pydantic import BaseModel, Field, field_validator

from app.core.responses import ApiResponse
from app.modules.meetings.constants import MeetingAudience


class MeetingCreateRequest(BaseModel):
    association_id: str | None = None
    title: str = Field(min_length=1, max_length=100)
    meeting_type: str = Field(min_length=1, max_length=100)
    priority: str = Field(min_length=1, max_length=50)
    audience: str = Field(min_length=1, max_length=100)
    agenda: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=5000)
    meeting_date: date
    meeting_time: time
    duration: str = Field(min_length=1, max_length=50)
    venue: str = Field(min_length=1, max_length=100)
    meeting_link: str | None = None
    organizer: str = Field(min_length=1)
    attachment_url: str | None = None
    target_block_id: str | None = None

    @field_validator("title", "meeting_type", "priority", "audience", "agenda", "description", "duration", "venue")
    @classmethod
    def trim_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("audience")
    @classmethod
    def validate_audience(cls, value: str) -> str:
        if value not in {audience.value for audience in MeetingAudience}:
            raise ValueError("Invalid meeting audience")
        return value


class MeetingDetailsRequest(MeetingCreateRequest):
    association_id: str | None = None
    target_block_id: str | None = None


class MeetingMinutesRequest(BaseModel):
    meeting_minutes: str = Field(min_length=1, max_length=10000)
    discussed_topic: str = Field(min_length=1, max_length=200)

    @field_validator("meeting_minutes", "discussed_topic")
    @classmethod
    def trim_text(cls, value: str) -> str:
        return value.strip()


class MeetingAttendanceRequest(BaseModel):
    status: str


class AttendanceStats(BaseModel):
    yes_count: int = 0
    no_count: int = 0
    maybe_count: int = 0
    no_response_count: int = 0


class MeetingResponse(BaseModel):
    id: str
    association_id: str
    association_name: str | None = None
    created_by: str
    created_by_name: str | None = None
    title: str
    meeting_type: str
    priority: str
    audience: str
    agenda: str
    description: str | None = None
    meeting_date: date | None = None
    meeting_time: time | None = None
    duration: str
    venue: str
    meeting_link: str | None = None
    organizer: str
    organizer_name: str | None = None
    attachment_url: str | None = None
    target_block_id: str | None = None
    target_block_name: str | None = None
    status: str
    meeting_minutes: str | None = None
    discussed_topic: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
    my_attendance_status: str | None = None
    attendance_stats: AttendanceStats = AttendanceStats()


class MeetingMutationResponse(BaseModel):
    updated: bool = True


class AssociationBlockResponse(BaseModel):
    id: str
    name: str


class OrganizerResponse(BaseModel):
    account_id: str
    name: str
    email: str


MeetingsResponse = ApiResponse[list[MeetingResponse]]
