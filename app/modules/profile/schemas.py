"""Profile request and response contracts."""

from typing import Any

from pydantic import BaseModel, Field


class ProfileData(BaseModel):
    user_details: dict[str, Any] = Field(default_factory=dict)
    family_members: list[dict[str, Any]] = Field(default_factory=list)
    unit_homeowners: list[dict[str, Any]] = Field(default_factory=list)
    vehicles: list[dict[str, Any]] = Field(default_factory=list)
    pets: list[dict[str, Any]] = Field(default_factory=list)
    education: list[dict[str, Any]] = Field(default_factory=list)
    experience: list[dict[str, Any]] = Field(default_factory=list)
    association_name: str | None = None
    association_id: str | None = None


class ProfileUpdateRequest(BaseModel):
    name: str | None = None
    address: str | None = None
    email: str | None = None
    contact_number: str | None = None
    alt_contact_number: str | None = None
    profile_pic_url: str | None = None


class FamilyMemberRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    email: str | None = None
    contact_number: str | None = None
    alt_contact_number: str | None = None


class VehicleRequest(BaseModel):
    type: str | None = None
    registration_number: str = Field(min_length=1, max_length=50)
    insurance_url: str | None = None
    puc_url: str | None = None


class PetRequest(BaseModel):
    type: str | None = None
    name: str = Field(min_length=1, max_length=150)
    breed: str | None = None
    vaccinated: bool = False
    vaccination_date: str | None = None
    next_vaccination_reminder: bool = False
    vaccination_certificate_url: str | None = None
    reminder_date: str | None = None


class EducationRequest(BaseModel):
    education_level: str = Field(min_length=1, max_length=100)
    degree: str = Field(min_length=1, max_length=150)
    field_of_study: str | None = None
    institution: str = Field(min_length=1, max_length=255)
    board_university: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    currently_studying: bool = False
    grade: str | None = None
    location: str | None = None
    description: str | None = None
    certificate_url: str | None = None


class ExperienceRequest(BaseModel):
    job_title: str = Field(min_length=1, max_length=150)
    employment_type: str = Field(min_length=1, max_length=50)
    company: str = Field(min_length=1, max_length=255)
    industry: str | None = None
    location: str | None = None
    work_mode: str | None = None
    start_date: str = Field(min_length=1, max_length=50)
    end_date: str | None = None
    currently_working: bool = False
    description: str | None = None
    skills: str | None = None
    website_url: str | None = None
    certificate_url: str | None = None


class ProfileMutationResponse(BaseModel):
    ok: bool = True
    id: str | None = None
