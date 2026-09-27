"""Stable Email Template Master event identifiers and preview context."""

from enum import StrEnum


class EmailTemplateEventType(StrEnum):
    """Built-in event keys offered by the master while still permitting custom keys."""

    ANNOUNCEMENT_CREATED = "announcement_created"
    EVENT_CREATED = "event_created"
    WELCOME_HOMEOWNER = "welcome_homeowner"
    PASSWORD_RESET_OTP = "password_reset_otp"
    SERVICE_REQUEST_UPDATED = "service_request_updated"
    MEETING_SCHEDULED = "meeting_scheduled"
    DUES_REMINDER = "dues_reminder"
    VIOLATION_NOTICE = "violation_notice"
    VISITOR_APPROVED = "visitor_approved"


DEFAULT_SAMPLE_CONTEXT: dict[str, str] = {
    "homeowner_name": "Sarah Jenkins",
    "association_name": "Oakridge Estates HOA",
    "title": "Annual Community Pool Opening & BBQ",
    "body": "We are excited to announce our summer season opening this weekend.",
    "date": "October 15, 2026",
    "starts_at": "Saturday, 11:00 AM",
    "location": "Main Clubhouse & Pool Deck",
    "ticket_id": "SR-8492",
    "status": "In Progress",
    "amount": "$250.00",
    "due_date": "November 1, 2026",
    "unit_number": "Unit 402 - Bldg B",
    "violation_type": "Unauthorized Exterior Alteration",
    "fine_amount": "$50.00",
    "deadline_date": "October 30, 2026",
    "visitor_name": "David Miller",
    "vehicle_number": "CA 7XYZ89",
    "entry_time": "Today at 2:30 PM",
    "description": "Please join us for food, music, and community updates.",
    "registration_code": "N8K4P2QZ",
    "otp": "482913",
    "password_reset_expiry_seconds": "60",
}
