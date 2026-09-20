"""Request and response contracts for document workflows."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentRequest(BaseModel):
    association_id: str
    title: str = Field(min_length=1, max_length=100)
    document_number: str | None = None
    document_type: str | None = None
    category: str | None = None
    file_name: str | None = None
    file_url: str | None = None
    file_type: str | None = None
    file_size_kb: int | None = None
    department: str | None = None
    related_module: str | None = None
    visibility: str | None = None
    allow_download: bool = True
    issue_date: date | None = None
    expiry_date: date | None = None
    reminder_before_expiry_days: int | None = None
    status: str = "Active"
    keywords: str | None = None
    remarks: str | None = None


class DocumentUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    document_number: str | None = None
    document_type: str | None = None
    category: str | None = None
    department: str | None = None
    related_module: str | None = None
    visibility: str | None = None
    allow_download: bool = True
    issue_date: date | None = None
    expiry_date: date | None = None
    reminder_before_expiry_days: int | None = None
    status: str = "Active"
    keywords: str | None = None
    remarks: str | None = None


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    association_id: str
    association_name: str | None = None
    title: str
    document_number: str | None = None
    document_type: str | None = None
    category: str | None = None
    file_name: str | None = None
    file_url: str | None = None
    file_type: str | None = None
    file_size_kb: int | None = None
    department: str | None = None
    related_module: str | None = None
    visibility: str | None = None
    allow_download: bool | None = True
    issue_date: date | None = None
    expiry_date: date | None = None
    reminder_before_expiry_days: int | None = None
    status: str | None = None
    keywords: str | None = None
    remarks: str | None = None
    created_at: datetime | None = None


class UnitDocumentRequest(BaseModel):
    association_id: str | None = None
    unit_id: str | None = None
    name: str = Field(min_length=1, max_length=100)
    type: str = Field(min_length=1, max_length=50)
    description: str | None = None
    file_url: str | None = None
    file_name: str | None = None
    file_type: str | None = None
    file_size_kb: int | None = None


class UnitDocumentUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    type: str = Field(min_length=1, max_length=50)
    description: str | None = None


class UnitDocumentResponse(BaseModel):
    id: str
    association_id: str
    association_name: str | None = None
    unit_id: str | None = None
    unit_number: str | None = None
    user_id: str | None = None
    user_name: str | None = None
    name: str
    type: str
    description: str | None = None
    file_url: str | None = None
    file_name: str | None = None
    file_type: str | None = None
    file_size_kb: int | None = None
    created_at: datetime | None = None


class DocumentMutationResponse(BaseModel):
    ok: bool = True
    id: str | None = None
