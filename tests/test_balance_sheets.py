"""Focused Balance Sheet calculation, spreadsheet, and route checks."""

from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from openpyxl import Workbook

from app.modules.balance_sheets.router import build_template_workbook
from app.modules.balance_sheets.schemas import (
    BalanceSheetItemRequest,
    BalanceSheetSection,
)
from app.modules.balance_sheets.service import BalanceSheetService


def item(
    section: BalanceSheetSection,
    amount: str,
) -> BalanceSheetItemRequest:
    return BalanceSheetItemRequest(
        section=section,
        account_name="Test account",
        amount=Decimal(amount),
    )


def test_totals_are_derived_from_normalized_sections() -> None:
    service = BalanceSheetService(AsyncMock())
    totals = service.totals(
        [
            item(BalanceSheetSection.CURRENT_ASSET, "125.00"),
            item(BalanceSheetSection.NON_CURRENT_ASSET, "75.00"),
            item(BalanceSheetSection.CURRENT_LIABILITY, "40.00"),
            item(BalanceSheetSection.NON_CURRENT_LIABILITY, "60.00"),
            item(BalanceSheetSection.EQUITY, "100.00"),
        ]
    )

    assert totals.total_assets == Decimal("200.00")
    assert totals.total_liabilities == Decimal("100.00")
    assert totals.total_equity == Decimal("100.00")
    assert totals.working_capital == Decimal("85.00")
    assert totals.current_ratio == Decimal("3.13")


def test_unbalanced_statement_is_rejected() -> None:
    service = BalanceSheetService(AsyncMock())

    with pytest.raises(HTTPException) as exc_info:
        service.validate_balanced(
            [
                item(BalanceSheetSection.CURRENT_ASSET, "100.00"),
                item(BalanceSheetSection.EQUITY, "90.00"),
            ]
        )

    assert exc_info.value.status_code == 422
    assert "Difference: 10.00" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_template_round_trips_through_import_parser() -> None:
    workbook = build_template_workbook()
    sheet = workbook["Balance Sheet"]
    sheet.append(["current_asset", "", "Cash", 100])
    sheet.append(["equity", "", "Retained balance", 100])

    service = BalanceSheetService(AsyncMock())
    service.repository.association_accounts_by_code = AsyncMock(return_value={})
    parsed, health_status, health_note = await service.parse_workbook("association-1", workbook)

    assert len(parsed) == 2
    assert parsed[0].section == BalanceSheetSection.CURRENT_ASSET
    assert parsed[0].amount == Decimal("100.00")
    assert health_status is None
    assert health_note is None
    service.validate_balanced(parsed)


@pytest.mark.asyncio
async def test_import_rejects_unknown_association_account_codes() -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Section", "Account Code (Optional)", "Account Name", "Amount"])
    sheet.append(["current_asset", "1010", "Cash", 100])
    sheet.append(["equity", "", "Retained balance", 100])

    service = BalanceSheetService(AsyncMock())
    service.repository.association_accounts_by_code = AsyncMock(return_value={})

    with pytest.raises(HTTPException) as exc_info:
        await service.parse_workbook("association-1", workbook)

    assert exc_info.value.status_code == 422
    assert "1010" in str(exc_info.value.detail)


def test_balance_sheet_routes_are_registered() -> None:
    from app.main import app

    paths = app.openapi()["paths"]
    registered = {
        (method.upper(), path)
        for path, operations in paths.items()
        for method in operations
    }
    expected = {
        ("GET", "/api/balance-sheets"),
        ("GET", "/api/balance-sheets/dates"),
        ("GET", "/api/balance-sheets/template"),
        ("GET", "/api/balance-sheets/export"),
        ("POST", "/api/balance-sheets"),
        ("POST", "/api/balance-sheets/import"),
        ("PUT", "/api/balance-sheets/{balance_sheet_id}"),
    }

    assert expected <= registered
