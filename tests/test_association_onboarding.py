"""Validation coverage for the association onboarding workbook contract."""

import pytest
from fastapi import HTTPException

from app.modules.associations.service import AssociationService


PRIMARY_HEADERS = {"Block Name", "Unit Number", "Email", "Primary Homeowner"}
UNIT_ROWS = [
    {"Block Name": "Block A", "Floor": "", "Unit Number": "A-101"},
    {"Block Name": "Block A", "Floor": "", "Unit Number": "A-102"},
]


def test_primary_homeowner_requires_exactly_one_per_unit() -> None:
    homeowner_rows = [
        {"Block Name": "Block A", "Unit Number": "A-101", "Email": "one@example.com", "Primary Homeowner": "Yes"},
        {"Block Name": "Block A", "Unit Number": "A-101", "Email": "two@example.com", "Primary Homeowner": "No"},
        {"Block Name": "Block A", "Unit Number": "A-102", "Email": "three@example.com", "Primary Homeowner": "Yes"},
    ]

    AssociationService._validate_primary_homeowners(PRIMARY_HEADERS, homeowner_rows, UNIT_ROWS)


@pytest.mark.parametrize(
    "headers, rows",
    [
        ({"Block Name", "Unit Number", "Email"}, []),
        (PRIMARY_HEADERS, [{"Block Name": "Block A", "Unit Number": "A-101", "Email": "one@example.com", "Primary Homeowner": "No"}]),
        (PRIMARY_HEADERS, [{"Block Name": "Block A", "Unit Number": "A-101", "Email": "", "Primary Homeowner": "Yes"}]),
    ],
)
def test_primary_homeowner_rejects_missing_or_invalid_assignment(headers: set[str], rows: list[dict]) -> None:
    with pytest.raises(HTTPException):
        AssociationService._validate_primary_homeowners(headers, rows, UNIT_ROWS)


def test_non_condominium_rejects_floor_values() -> None:
    with pytest.raises(HTTPException):
        AssociationService._validate_unit_structure(
            "Single Family",
            [{"Block Name": "Street 1", "Floor": "Ground", "Unit Number": "Home 1"}],
        )


def test_condominium_allows_floor_values() -> None:
    AssociationService._validate_unit_structure(
        "Condominium",
        [{"Block Name": "Tower A", "Floor": "2", "Unit Number": "201"}],
    )
