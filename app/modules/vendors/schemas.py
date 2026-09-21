from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class VendorRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    service_type: str = Field(default="General", max_length=150)
    contact_person: str | None = None
    email: str | None = None
    contact_number: str | None = None
    address: str | None = None
    gst_number: str | None = None
    licence_url: str | None = None
    certificate_url: str | None = None
    status: str = "Active"
    vendor_code: str | None = None
    vendor_category: str | None = None
    business_name: str | None = None
    mobile_number: str | None = None
    alternate_mobile_number: str | None = None
    website: str | None = None
    whatsapp_number: str | None = None
    address_line_1: str | None = None
    address_line_2: str | None = None
    city_id: str | None = None
    zip_code: str | None = None
    pan_number: str | None = None
    registration_number: str | None = None
    license_number: str | None = None
    trade_license_number: str | None = None
    years_of_experience: int | None = None
    available_days: str | None = None
    working_hours: str | None = None
    emergency_service: bool | None = None
    support_24_7: bool | None = None
    contract_start_date: date | None = None
    contract_end_date: date | None = None
    contract_value: Decimal | None = None
    payment_terms: str | None = None
    contract_document_url: str | None = None
    renewal_reminder: bool | None = None
    bank_account_name: str | None = None
    bank_name: str | None = None
    bank_account_number: str | None = None
    bank_ifsc_code: str | None = None
    bank_upi_id: str | None = None
    gst_certificate_url: str | None = None
    pan_card_url: str | None = None
    business_license_url: str | None = None
    insurance_certificate_url: str | None = None
    agreement_copy_url: str | None = None
    identity_proof_url: str | None = None
    address_proof_url: str | None = None
    other_documents_url: str | None = None
    vendor_rating: Decimal | None = None
    preferred_vendor: bool | None = None
    verified_vendor: bool | None = None
    remarks: str | None = None
    association_name: str | None = None
    assigned_blocks: str | None = None
    assigned_services: str | None = None
    assigned_manager: str | None = None
    contact_details_json: str | None = None
    services_offered_json: str | None = None


class VendorResponse(VendorRequest):
    model_config = ConfigDict(from_attributes=True)
    id: str
    city: str | None = None
    state: str | None = None
    country: str | None = None
    created_at: datetime | None = None


class VendorMutationResponse(BaseModel):
    ok: bool = True
    message: str
