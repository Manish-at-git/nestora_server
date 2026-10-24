"""Focused Prepaid Report calculation, validation, authorization, and route checks."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.core.constants import RoleCode
from app.modules.associations.models import Association
from app.modules.prepaid_reports.models import PrepaidReport, PrepaidReportRow
from app.modules.prepaid_reports.router import (
    MANAGER_ROLE_CODES,
    VIEWER_ROLE_CODES,
    build_export_workbook,
    parse_import_workbook,
)
from app.modules.prepaid_reports.schemas import (
    PrepaidReportRequest,
    PrepaidReportRowRequest,
    PrepaidStatus,
)
from app.modules.prepaid_reports.service import PrepaidReportService


def row(
    prepaid: str = "100.00",
    used: str = "25.00",
    expiry: date = date(2027, 3, 31),
) -> PrepaidReportRowRequest:
    return PrepaidReportRowRequest(
        member_name="Test member",
        unit_number="A-101",
        block="A",
        category="Maintenance",
        prepaid_amount=Decimal(prepaid),
        used_amount=Decimal(used),
        expiry_date=expiry,
    )


def account(role_code: str = "admin") -> SimpleNamespace:
    return SimpleNamespace(
        id="account-1",
        user_id="user-1",
        role=SimpleNamespace(code=role_code),
    )


def test_totals_are_derived_from_member_rows() -> None:
    service = PrepaidReportService(AsyncMock())

    prepaid, used, available = service.totals(
        [row("100.00", "25.00"), row("80.00", "30.00")]
    )

    assert prepaid == Decimal("180.00")
    assert used == Decimal("55.00")
    assert available == Decimal("125.00")


@pytest.mark.parametrize(
    ("prepaid", "used"),
    [("-1.00", "0.00"), ("10.00", "-1.00"), ("10.00", "10.01")],
)
def test_invalid_amounts_are_rejected(prepaid: str, used: str) -> None:
    with pytest.raises(ValidationError):
        row(prepaid, used)


def test_status_is_derived_from_expiry_and_available_balance() -> None:
    service = PrepaidReportService(AsyncMock())
    today = date(2026, 10, 24)

    assert service.derive_status(date(2026, 10, 25), Decimal("1.00"), today) == PrepaidStatus.ACTIVE
    assert (
        service.derive_status(date(2026, 10, 23), Decimal("1.00"), today)
        == PrepaidStatus.EXPIRED
    )
    assert (
        service.derive_status(date(2026, 10, 25), Decimal("0.00"), today)
        == PrepaidStatus.EXPIRED
    )


@pytest.mark.asyncio
async def test_duplicate_association_period_is_rejected() -> None:
    service = PrepaidReportService(AsyncMock())
    service.check_association = AsyncMock()
    service.repository.duplicate_period = AsyncMock(return_value=True)
    payload = PrepaidReportRequest(
        association_id="association-1",
        fiscal_period="01 Apr 2026 - 31 Mar 2027",
        rows=[row()],
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.create(account(), payload)

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_association_scope_blocks_an_unassigned_association() -> None:
    service = PrepaidReportService(AsyncMock())
    service.repository.association_exists = AsyncMock(return_value=True)
    service.repository.scoped_associations = AsyncMock(return_value=["association-1"])

    with pytest.raises(HTTPException) as exc_info:
        await service.check_association(account("homeowner"), "association-2")

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_block_filter_recalculates_summaries_and_distribution() -> None:
    service = PrepaidReportService(AsyncMock())
    report = PrepaidReport(
        id="report-1",
        association_id="association-1",
        fiscal_period="01 Apr 2026 - 31 Mar 2027",
        association=Association(id="association-1", name="Test Association"),
        rows=[
            PrepaidReportRow(
                id="row-1",
                prepaid_report_id="report-1",
                member_name="Member One",
                unit_number="A-101",
                block="A",
                category="Maintenance",
                prepaid_amount=Decimal("100.00"),
                used_amount=Decimal("25.00"),
                expiry_date=date(2027, 3, 31),
                sort_order=0,
            ),
            PrepaidReportRow(
                id="row-2",
                prepaid_report_id="report-1",
                member_name="Member Two",
                unit_number="B-201",
                block="B",
                category="Utilities",
                prepaid_amount=Decimal("80.00"),
                used_amount=Decimal("30.00"),
                expiry_date=date(2027, 3, 31),
                sort_order=1,
            ),
        ],
    )

    response = await service.serialize(report, block="A", today=date(2026, 10, 24))

    assert response.applied_block == "A"
    assert response.available_blocks == ["A", "B"]
    assert [item.member_name for item in response.rows] == ["Member One"]
    assert response.summary.total_prepaid_amount == Decimal("100.00")
    assert response.summary.total_used_amount == Decimal("25.00")
    assert response.summary.total_available_balance == Decimal("75.00")
    assert response.category_distribution[0].name == "Maintenance"
    assert response.category_distribution[0].percentage == Decimal("100.00")


@pytest.mark.asyncio
async def test_export_contains_context_details_and_totals() -> None:
    service = PrepaidReportService(AsyncMock())
    report = PrepaidReport(
        id="report-1",
        association_id="association-1",
        fiscal_period="01 Apr 2026 - 31 Mar 2027",
        association=Association(id="association-1", name="Test Association"),
        rows=[
            PrepaidReportRow(
                id="row-1",
                prepaid_report_id="report-1",
                member_name="Member One",
                unit_number="A-101",
                block="A",
                category="Maintenance",
                prepaid_amount=Decimal("100.00"),
                used_amount=Decimal("25.00"),
                expiry_date=date(2027, 3, 31),
                sort_order=0,
            )
        ],
    )
    response = await service.serialize(report, block="A", today=date(2026, 10, 24))
    sheet = build_export_workbook(response).active

    assert sheet["A1"].value == "Test Association - Prepaid Report"
    assert "01 Apr 2026 - 31 Mar 2027" in sheet["A2"].value
    assert "Filter: A" in sheet["A2"].value
    assert sheet["B8"].value == "Member One"
    assert sheet["F9"].value == 100.0


@pytest.mark.asyncio
async def test_exported_workbook_can_be_imported_without_derived_columns() -> None:
    report = PrepaidReport(
        id="report-1",
        association_id="association-1",
        fiscal_period="01 Apr 2026 - 31 Mar 2027",
        association=Association(id="association-1", name="Test Association"),
        rows=[
            PrepaidReportRow(
                id="row-1",
                prepaid_report_id="report-1",
                member_name="Member One",
                unit_number="A-101",
                block="A",
                category="Maintenance",
                prepaid_amount=Decimal("100.00"),
                used_amount=Decimal("25.00"),
                expiry_date=date(2027, 3, 31),
                sort_order=0,
            )
        ],
    )
    response = await PrepaidReportService(AsyncMock()).serialize(
        report,
        today=date(2026, 10, 24),
    )
    imported = parse_import_workbook(
        build_export_workbook(response),
        "association-1",
        "01 Apr 2027 - 31 Mar 2028",
    )

    assert len(imported.rows) == 1
    assert imported.rows[0].member_name == "Member One"
    assert imported.rows[0].used_amount == Decimal("25.00")
    assert imported.rows[0].expiry_date == date(2027, 3, 31)


@pytest.mark.asyncio
async def test_import_error_explains_used_amount_validation() -> None:
    report = PrepaidReport(
        id="report-1",
        association_id="association-1",
        fiscal_period="01 Apr 2026 - 31 Mar 2027",
        association=Association(id="association-1", name="Test Association"),
        rows=[
            PrepaidReportRow(
                id="row-1",
                prepaid_report_id="report-1",
                member_name="Member One",
                unit_number="A-101",
                block="A",
                category="Maintenance",
                prepaid_amount=Decimal("100.00"),
                used_amount=Decimal("25.00"),
                expiry_date=date(2027, 3, 31),
                sort_order=0,
            )
        ],
    )
    response = await PrepaidReportService(AsyncMock()).serialize(
        report,
        today=date(2026, 10, 24),
    )
    workbook = build_export_workbook(response)
    workbook.active["G8"] = 125

    with pytest.raises(
        ValueError,
        match="Row 8: used amount cannot exceed prepaid amount",
    ):
        parse_import_workbook(
            workbook,
            "association-1",
            "01 Apr 2027 - 31 Mar 2028",
        )


def test_authorization_role_sets_match_the_feature_contract() -> None:
    assert set(MANAGER_ROLE_CODES) == {
        RoleCode.SUPER_ADMIN,
        RoleCode.ADMIN,
        RoleCode.ACCOUNTANT,
    }
    assert set(VIEWER_ROLE_CODES) == {
        *MANAGER_ROLE_CODES,
        RoleCode.HOMEOWNER,
        RoleCode.BOARD_MEMBER,
        RoleCode.COMMITTEE_MEMBER,
    }


def test_prepaid_report_routes_are_registered() -> None:
    from app.main import app

    paths = app.openapi()["paths"]
    registered = {
        (method.upper(), path)
        for path, operations in paths.items()
        for method in operations
    }
    expected = {
        ("GET", "/api/prepaid-reports"),
        ("GET", "/api/prepaid-reports/periods"),
        ("GET", "/api/prepaid-reports/export"),
        ("GET", "/api/prepaid-reports/template"),
        ("POST", "/api/prepaid-reports"),
        ("POST", "/api/prepaid-reports/import"),
        ("PUT", "/api/prepaid-reports/{report_id}"),
    }

    assert expected <= registered
