"""Canonical contact-value normalization used by duplicate validation."""

import re


def normalize_email(value: object) -> str:
    """Normalize an email for comparisons while preserving stored values."""
    return str(value or "").strip().casefold()


def normalize_phone(value: object) -> str:
    """Normalize a phone number to its digits for comparisons."""
    return re.sub(r"\D+", "", str(value or "").strip())
