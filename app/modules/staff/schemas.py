"""HTTP contracts for staff records, passes, and daily attendance."""

import re
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.core.contact_normalization import normalize_phone
from app.modules.staff.constants import STAFF_WORK_TYPES


PERSON_NAME_PATTERN = re.compile(r"^[^\W\d_]+(?:[ '\u2019-][^\W\d_]+)*$", re.UNICODE)


class StaffDetailsRequest(BaseModel):
    """Shared required profile fields for staff creation and editing."""

    association_id: str = Field(min_length=1, max_length=36)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    designation: str = Field(min_length=1, max_length=100)
    contact_number: str = Field(min_length=7, max_length=30)
    email: EmailStr
    assignment_type: str = Field(default="common_area", pattern=r"^(common_area|unit)$")
    block_id: str | None = Field(default=None, max_length=36)
    unit_id: str | None = Field(default=None, max_length=36)
    address_line_1: str = Field(min_length=1, max_length=255)
    address_line_2: str | None = Field(default=None, max_length=255)
    city_id: str = Field(min_length=1, max_length=36)
    pincode: str = Field(pattern=r"^\d{6}$")
    emergency_contact_name: str | None = Field(default=None, max_length=150)
    emergency_contact_number: str | None = Field(default=None, min_length=7, max_length=30)
    id_proof_url: str | None = Field(default=None, max_length=255)
    profile_pic_url: str | None = Field(default=None, max_length=255)

    @field_validator(
        "first_name",
        "last_name",
        "designation",
        "address_line_1",
        "address_line_2",
        "emergency_contact_name",
        "id_proof_url",
        "profile_pic_url",
        mode="before",
    )
    @classmethod
    def trim_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_person_name(cls, value: str | None) -> str:
        if not value or PERSON_NAME_PATTERN.fullmatch(value) is None:
            raise ValueError("Enter a valid name")
        return value

    @field_validator("designation")
    @classmethod
    def validate_work_type(cls, value: str | None) -> str:
        if value not in STAFF_WORK_TYPES:
            raise ValueError("Select a valid work type")
        return value

    @field_validator("contact_number", "emergency_contact_number")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_phone(value)
        if not 7 <= len(normalized) <= 15:
            raise ValueError("Enter a valid phone number")
        return normalized

    @model_validator(mode="after")
    def validate_assignment(self) -> "StaffDetailsRequest":
        if self.assignment_type == "unit" and (not self.block_id or not self.unit_id):
            raise ValueError("Select both a block and unit for a unit assignment")
        if self.assignment_type == "common_area":
            self.block_id = None
            self.unit_id = None
        return self


class StaffCreateRequest(StaffDetailsRequest):
    pass


class StaffUpdateRequest(StaffDetailsRequest):
    is_active: bool = True


class StaffAttendanceActionRequest(BaseModel):
    pass_code: str = Field(min_length=1, max_length=255)
    gate: str | None = Field(default=None, max_length=100)
    remarks: str | None = Field(default=None, max_length=500)


class StaffPastAttendanceRequest(BaseModel):
    staff_id: str = Field(min_length=1, max_length=36)
    check_in_at: datetime
    check_out_at: datetime
    gate: str | None = Field(default=None, max_length=100)
    remarks: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_past_attendance(self) -> "StaffPastAttendanceRequest":
        if self.check_in_at.date() >= date.today() or self.check_out_at.date() >= date.today():
            raise ValueError("Past attendance can only be recorded for a previous date")
        if self.check_in_at.date() != self.check_out_at.date():
            raise ValueError("Check-in and check-out must be on the same date")
        if self.check_out_at <= self.check_in_at:
            raise ValueError("Check-out time must be after check-in time")
        return self


class StaffMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    association_id: str
    association_name: str
    staff_code: str
    first_name: str
    last_name: str
    designation: str
    contact_number: str
    email: str | None = None
    assignment_type: str = "common_area"
    block_id: str | None = None
    block_name: str | None = None
    unit_id: str | None = None
    unit_number: str | None = None
    account_id: str | None = None
    temp_password: str | None = None
    address_line_1: str | None = None
    address_line_2: str | None = None
    city_id: str | None = None
    city: str | None = None
    region_id: str | None = None
    state: str | None = None
    country_id: str | None = None
    pincode: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_number: str | None = None
    id_proof_url: str | None = None
    profile_pic_url: str | None = None
    pass_code: str
    is_active: bool
    active_attendance_id: str | None = None
    today_check_out_at: datetime | None = None
    created_at: datetime | None = None


class StaffAttendanceResponse(BaseModel):
    id: str
    staff_id: str
    staff_name: str
    staff_code: str
    designation: str
    association_id: str
    association_name: str
    check_in_at: datetime
    check_out_at: datetime | None = None
    gate: str | None = None
    remarks: str | None = None


class StaffAttendanceActionResponse(BaseModel):
    action: str
    attendance: StaffAttendanceResponse


class StaffMonthlyAttendanceDayResponse(BaseModel):
    date: str
    status: str
    check_in_at: datetime | None = None
    check_out_at: datetime | None = None
    duration_minutes: int | None = None


class StaffMonthlyAttendanceRowResponse(BaseModel):
    staff_id: str
    staff_code: str
    staff_name: str
    designation: str
    days: list[StaffMonthlyAttendanceDayResponse]
    present_days: int
    incomplete_days: int
    total_minutes: int
    average_minutes: int


class StaffMonthlyAttendanceReportResponse(BaseModel):
    association_id: str
    month: str
    total_staff: int
    present_days: int
    incomplete_days: int
    total_minutes: int
    rows: list[StaffMonthlyAttendanceRowResponse]


class StaffMutationResponse(BaseModel):
    ok: bool = True
    id: str
    temp_password: str | None = None


class StaffBlockResponse(BaseModel):
    id: str
    name: str


class StaffUnitResponse(BaseModel):
    id: str
    unit_number: str
