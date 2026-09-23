"""Shared server-side validation helpers for request and import validation."""

import re
from datetime import date, datetime
from decimal import Decimal


EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_PATTERN = re.compile(r"^\+?[1-9]\d{6,14}$")
PINCODE_PATTERN = re.compile(r"^\d{6}$")
PERSON_NAME_PATTERN = re.compile(r"^[^\W\d_]+(?:[ '\u2019-][^\W\d_]+)*$", re.UNICODE)
ALPHANUMERIC_PATTERN = re.compile(r"^[a-zA-Z0-9]+$")
DECIMAL_PATTERN = re.compile(r"^\d+(?:\.\d+)?$")


def is_email(value: str) -> bool:
    return bool(EMAIL_PATTERN.fullmatch(value.strip()))


def is_phone_number(value: str) -> bool:
    normalized = re.sub(r"[\s().-]", "", value.strip())
    return bool(PHONE_PATTERN.fullmatch(normalized))


def is_pincode(value: str) -> bool:
    return bool(PINCODE_PATTERN.fullmatch(value.strip()))


def is_required_text(value: str) -> bool:
    return bool(value.strip())


def is_person_name(value: str) -> bool:
    return bool(PERSON_NAME_PATTERN.fullmatch(value.strip()))


def is_alphanumeric(value: str) -> bool:
    return bool(ALPHANUMERIC_PATTERN.fullmatch(value.strip()))


def is_positive_integer(value: str | int) -> bool:
    text = str(value).strip()
    return bool(re.fullmatch(r"\d+", text)) and int(text) > 0


def is_non_negative_integer(value: str | int) -> bool:
    text = str(value).strip()
    return bool(re.fullmatch(r"\d+", text)) and int(text) >= 0


def is_decimal(value: str | int | float | Decimal) -> bool:
    return bool(DECIMAL_PATTERN.fullmatch(str(value).strip()))


def _to_date(value: str | date | datetime) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def is_valid_date(value: str | date | datetime) -> bool:
    return _to_date(value) is not None


def is_date_after(
    value: str | date | datetime,
    reference: str | date | datetime,
    inclusive: bool = False,
) -> bool:
    current_date = _to_date(value)
    reference_date = _to_date(reference)
    if current_date is None or reference_date is None:
        return False
    return current_date >= reference_date if inclusive else current_date > reference_date


def is_date_before(
    value: str | date | datetime,
    reference: str | date | datetime,
    inclusive: bool = False,
) -> bool:
    current_date = _to_date(value)
    reference_date = _to_date(reference)
    if current_date is None or reference_date is None:
        return False
    return current_date <= reference_date if inclusive else current_date < reference_date


def is_date_range_valid(
    start: str | date | datetime,
    end: str | date | datetime,
    inclusive: bool = True,
) -> bool:
    start_date = _to_date(start)
    end_date = _to_date(end)
    if start_date is None or end_date is None:
        return False
    return start_date <= end_date if inclusive else start_date < end_date
