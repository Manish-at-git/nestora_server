"""Request and response contracts for financial reports."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FinancialReportRequest(BaseModel):
    association_id: str
    published_month: str = Field(min_length=1, max_length=50)
    report_type: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=255)
    file_url: str = Field(min_length=1)


class FinancialReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    association_id: str
    association_name: str | None = None
    published_month: str
    report_type: str
    title: str
    file_url: str
    uploaded_by: str | None = None
    created_at: datetime | None = None


class FinancialReportMutationResponse(BaseModel):
    ok: bool = True
    id: str | None = None
