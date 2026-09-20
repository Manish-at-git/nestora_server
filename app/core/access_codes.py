"""Shared access-code generation and validation rules."""

import re
import secrets
import string

ACCESS_CODE_LENGTH = 8
_ACCESS_CODE_ALPHABET = string.ascii_uppercase + string.digits
_ACCESS_CODE_PATTERN = re.compile(rf"[A-Z0-9]{{{ACCESS_CODE_LENGTH}}}")


def generate_access_code() -> str:
    """Return a random access code containing exactly eight alphanumeric characters."""
    return "".join(secrets.choice(_ACCESS_CODE_ALPHABET) for _ in range(ACCESS_CODE_LENGTH))


def normalize_access_code(value: str) -> str:
    """Normalize user input and reject anything other than eight alphanumeric characters."""
    normalized = value.strip().upper()
    if _ACCESS_CODE_PATTERN.fullmatch(normalized) is None:
        raise ValueError("Access code must be exactly 8 letters and numbers.")
    return normalized
