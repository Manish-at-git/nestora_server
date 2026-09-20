"""Chart of Accounts API contracts."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChartOfAccountRequest(BaseModel):
    gl_code: str = Field(min_length=1, max_length=255)
    gl_name: str = Field(min_length=1, max_length=255)
    structure: str | None = None
    grouping: str | None = None


class ChartOfAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    association_id: str | None = None
    gl_code: str
    gl_name: str
    structure: str | None = None
    grouping: str | None = None
    mapped_from_global_id: str | None = None
    created_at: datetime | None = None


class ChartMutationResponse(BaseModel):
    ok: bool = True
    id: str | None = None
    message: str | None = None


class ChartStatusResponse(BaseModel):
    status: dict[str, int]
