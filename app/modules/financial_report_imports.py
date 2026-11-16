"""Shared validation helpers for financial-report Excel imports."""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from pydantic import ValidationError

MAX_IMPORT_BYTES = 5 * 1024 * 1024


def normalize_label(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def display_value(value: object) -> str:
    if value in (None, ""):
        return "blank"
    text = str(value).strip()
    return f'"{text[:50]}{"..." if len(text) > 50 else ""}"'


def non_negative_decimal(value: object, row_number: int, field_name: str) -> Decimal:
    try:
        cleaned = str(value).replace(",", "").replace("₹", "").strip()
        amount = Decimal(cleaned).quantize(Decimal("0.01"))
        if not amount.is_finite() or amount < 0:
            raise InvalidOperation
        return amount
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(
            f"Row {row_number}, {field_name}: expected a non-negative number, "
            f"received {display_value(value)}."
        ) from exc


def typed_date(value: object, row_number: int, field_name: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    for format_string in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, format_string).date()
        except ValueError:
            continue
    raise ValueError(
        f"Row {row_number}, {field_name}: expected a valid Excel date or YYYY-MM-DD, "
        f"received {display_value(value)}."
    )


def find_header(
    rows: list[tuple],
    aliases: dict[str, set[str]],
    required: tuple[str, ...],
) -> tuple[int, dict[str, int]]:
    best_columns: dict[str, int] = {}
    best_match_count = -1
    for row_index, row in enumerate(rows[:25]):
        normalized = [normalize_label(value) for value in row]
        columns = {
            field: next(
                (index for index, value in enumerate(normalized) if value in labels),
                -1,
            )
            for field, labels in aliases.items()
        }
        match_count = sum(columns[field] >= 0 for field in required)
        if match_count > best_match_count:
            best_columns = columns
            best_match_count = match_count
        if all(columns[field] >= 0 for field in required):
            return row_index, columns
    missing = [
        field.replace("_", " ").title()
        for field in required
        if best_columns.get(field, -1) < 0
    ]
    raise ValueError(
        f"Missing required column(s): {', '.join(missing)}. "
        "Download the template and keep its column headings unchanged."
    )


def first_nonempty_label(row: tuple) -> str:
    return normalize_label(next((value for value in row if value not in (None, "")), ""))


def combined_errors(errors: list[str]) -> str:
    detail = " ".join(errors[:10])
    if len(errors) > 10:
        detail += f" And {len(errors) - 10} more row errors."
    return detail


def validation_error_message(
    error: ValidationError,
    row_number: int | None = None,
) -> str:
    messages: list[str] = []
    for item in error.errors():
        message = str(item.get("msg", "Invalid value")).removeprefix("Value error, ")
        location = [part for part in item.get("loc", ()) if not isinstance(part, int)]
        field = str(location[-1]).replace("_", " ").title() if location else ""
        if field and field.casefold() not in message.casefold():
            message = f"{field}: {message}"
        prefix = f"Row {row_number}: " if row_number is not None else ""
        messages.append(f"{prefix}{message}.")
    return " ".join(messages) or "The workbook contains invalid data."


def validate_member_assignments(rows, members: list[dict]) -> list[str]:
    """Return row-specific errors when a member, unit, and block do not match."""
    normalized_members = {
        (
            str(member.get("name") or "").strip().casefold(),
            str(member.get("unit_number") or "").strip().casefold(),
            str(member.get("block") or "").strip().casefold(),
        )
        for member in members
        if member.get("name") and member.get("unit_number") and member.get("block")
    }
    blocks = {block for _, _, block in normalized_members}
    units_by_block: dict[str, set[str]] = {}
    for _, unit, block in normalized_members:
        units_by_block.setdefault(block, set()).add(unit)

    errors: list[str] = []
    for index, item in enumerate(rows, start=1):
        row_number, row = item if isinstance(item, tuple) else (index, item)
        member_name = str(row.member_name or "").strip()
        unit_number = str(row.unit_number or "").strip()
        block = str(row.block or "").strip()
        if not block:
            errors.append(f"Row {row_number}: Block is required for the selected association.")
            continue
        normalized_block = block.casefold()
        normalized_unit = unit_number.casefold()
        normalized_name = member_name.casefold()
        if normalized_block not in blocks:
            errors.append(
                f"Row {row_number}: Block {display_value(block)} does not exist "
                "in the selected association."
            )
            continue
        if normalized_unit not in units_by_block[normalized_block]:
            errors.append(
                f"Row {row_number}: Unit {display_value(unit_number)} is not in "
                f"Block {display_value(block)}."
            )
            continue
        if (normalized_name, normalized_unit, normalized_block) not in normalized_members:
            errors.append(
                f"Row {row_number}: Member {display_value(member_name)} is not assigned to "
                f"Block {display_value(block)}, Unit {display_value(unit_number)}."
            )
    return errors


def validate_vendor_assignments(rows, vendors) -> list[str]:
    """Return row-specific errors when a vendor is not active for the association."""
    vendor_names = {
        str(vendor.name or "").strip().casefold()
        for vendor in vendors
        if vendor.name
    }
    errors: list[str] = []
    for index, item in enumerate(rows, start=1):
        row_number, row = item if isinstance(item, tuple) else (index, item)
        vendor_name = str(row.vendor_name or "").strip()
        if vendor_name.casefold() not in vendor_names:
            errors.append(
                f"Row {row_number}: Vendor {display_value(vendor_name)} does not exist "
                "or is not active and mapped to the selected association."
            )
    return errors
