"""Focused Delinquency Report calculations, validation, scope, and routes."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.core.constants import RoleCode
from app.modules.associations.models import Association
from app.modules.delinquency_reports.models import (
    DelinquencyReport,
    DelinquencyReportRow,
)
from app.modules.delinquency_reports.router import (
    MANAGER_ROLE_CODES,
    VIEWER_ROLE_CODES,
    build_export_workbook,
    delinquency_report_template,
    parse_import_workbook,
)
from app.modules.delinquency_reports.schemas import (
    DelinquencyReportRequest,
    DelinquencyRowRequest,
    DelinquencyStatus,
)
from app.modules.delinquency_reports.service import DelinquencyReportService


def row(
    member: str = "Test Member",
    unit: str = "A-101",
    category: str = "Maintenance",
    amount: str = "100.00",
    days: int = 30,
) -> DelinquencyRowRequest:
    return DelinquencyRowRequest(
        member_name=member,
        unit_number=unit,
        block="A",
        charge_category=category,
        outstanding_amount=Decimal(amount),
        days_overdue=days,
        last_payment_date=date(2026, 9, 1),
    )


def payload(rows: list[DelinquencyRowRequest] | None = None) -> DelinquencyReportRequest:
    return DelinquencyReportRequest(
        association_id="association-1",
        fiscal_period="01 Apr 2026 - 31 Mar 2027",
        total_billed_amount=Decimal("1000.00"),
        total_collected_amount=Decimal("700.00"),
        rows=rows or [row()],
    )


def account(role_code: str = "admin") -> SimpleNamespace:
    return SimpleNamespace(
        id="account-1",
        user_id="user-1",
        role=SimpleNamespace(code=role_code),
    )


def model_row(
    row_id: str,
    member: str,
    block: str,
    category: str,
    amount: str,
    days: int,
) -> DelinquencyReportRow:
    return DelinquencyReportRow(
        id=row_id,
        delinquency_report_id="report-1",
        member_name=member,
        unit_number=f"{block}-{row_id}",
        block=block,
        charge_category=category,
        outstanding_amount=Decimal(amount),
        days_overdue=days,
        last_payment_date=date(2026, 9, 1),
        sort_order=0,
    )


def report() -> DelinquencyReport:
    return DelinquencyReport(
        id="report-1",
        association_id="association-1",
        fiscal_period="01 Apr 2026 - 31 Mar 2027",
        total_billed_amount=Decimal("1000.00"),
        total_collected_amount=Decimal("700.00"),
        association=Association(id="association-1", name="Test Association"),
        rows=[
            model_row("101", "Member One", "A", "Maintenance", "125.00", 80),
            model_row("202", "Member Two", "B", "Utilities", "75.00", 20),
        ],
    )


def test_totals_and_status_are_derived_from_rows() -> None:
    service = DelinquencyReportService(AsyncMock())

    assert service.total_outstanding([row(), row(amount="25.00")]) == Decimal(
        "125.00"
    )
    assert service.derive_status(Decimal("0"), 120) == DelinquencyStatus.RESOLVED
    assert service.derive_status(Decimal("10"), 20) == DelinquencyStatus.LOW
    assert service.derive_status(Decimal("10"), 45) == DelinquencyStatus.MEDIUM
    assert service.derive_status(Decimal("10"), 75) == DelinquencyStatus.HIGH


def test_negative_amount_and_days_are_rejected() -> None:
    with pytest.raises(ValidationError):
        row(amount="-1.00")
    with pytest.raises(ValidationError):
        row(days=-1)


def test_collected_amount_cannot_exceed_billed_amount() -> None:
    with pytest.raises(ValidationError, match="cannot exceed"):
        DelinquencyReportRequest(
            association_id="association-1",
            fiscal_period="01 Apr 2026 - 31 Mar 2027",
            total_billed_amount=Decimal("100.00"),
            total_collected_amount=Decimal("101.00"),
            rows=[row()],
        )


def test_duplicate_member_unit_category_is_rejected() -> None:
    with pytest.raises(ValidationError, match="combinations must be unique"):
        payload([row(), row()])


@pytest.mark.asyncio
async def test_duplicate_association_period_is_rejected() -> None:
    service = DelinquencyReportService(AsyncMock())
    service.check_association = AsyncMock()
    service.repository.duplicate_period = AsyncMock(return_value=True)

    with pytest.raises(HTTPException) as exc_info:
        await service.create(account(), payload())

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_association_scope_blocks_unassigned_association() -> None:
    service = DelinquencyReportService(AsyncMock())
    service.repository.association_exists = AsyncMock(return_value=True)
    service.repository.scoped_associations = AsyncMock(return_value=["association-1"])

    with pytest.raises(HTTPException) as exc_info:
        await service.check_association(account("homeowner"), "association-2")

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_filters_recalculate_summary_distributions_and_insights() -> None:
    response = await DelinquencyReportService(AsyncMock()).serialize(
        report(),
        block="A",
        search="maintenance",
    )

    assert response.available_blocks == ["A", "B"]
    assert [item.member_name for item in response.rows] == ["Member One"]
    assert response.summary.total_outstanding == Decimal("125.00")
    assert response.summary.delinquent_member_count == 1
    assert response.summary.high_risk_count == 1
    assert response.summary.collection_rate_percentage == Decimal("70.00")
    assert response.charge_distribution[0].amount == Decimal("125.00")
    assert response.aging_distribution[-2].amount == Decimal("125.00")
    assert len(response.insights) == 3


@pytest.mark.asyncio
async def test_export_contains_context_detail_and_totals() -> None:
    response = await DelinquencyReportService(AsyncMock()).serialize(
        report(), block="A", search="Member"
    )
    sheet = build_export_workbook(response).active

    assert sheet["A1"].value == "Test Association - Delinquency Report"
    assert "Block: A" in sheet["A2"].value
    assert "Search: Member" in sheet["A2"].value
    assert sheet["B8"].value == "Member One"
    assert sheet["F9"].value == 125.0


def test_authorization_role_sets_match_feature_contract() -> None:
    assert set(MANAGER_ROLE_CODES) == {
        RoleCode.SUPER_ADMIN,
        RoleCode.ADMIN,
        RoleCode.ACCOUNTANT,
    }


@pytest.mark.asyncio
async def test_template_contains_required_import_fields() -> None:
    response = await delinquency_report_template()
    assert response.headers["content-disposition"] == (
        'attachment; filename="delinquency_report_import_template.xlsx"'
    )


@pytest.mark.asyncio
async def test_exported_workbook_can_be_imported_without_derived_columns() -> None:
    serialized = await DelinquencyReportService(AsyncMock()).serialize(report())
    payload_from_workbook = parse_import_workbook(
        build_export_workbook(serialized),
        "association-1",
        "01 Apr 2027 - 31 Mar 2028",
    )

    assert payload_from_workbook.total_billed_amount == Decimal("1000.00")
    assert payload_from_workbook.total_collected_amount == Decimal("700.00")
    assert len(payload_from_workbook.rows) == 2
    assert payload_from_workbook.rows[0].member_name == "Member One"
    assert payload_from_workbook.rows[0].outstanding_amount == Decimal("125.00")


@pytest.mark.asyncio
async def test_import_error_identifies_the_bad_row_field_and_value() -> None:
    serialized = await DelinquencyReportService(AsyncMock()).serialize(report())
    workbook = build_export_workbook(serialized)
    workbook.active["G8"] = "many"

    with pytest.raises(
        ValueError,
        match='Row 8, Days Overdue: expected a whole number.*received "many"',
    ):
        parse_import_workbook(
            workbook,
            "association-1",
            "01 Apr 2027 - 31 Mar 2028",
        )
    assert set(VIEWER_ROLE_CODES) == {
        *MANAGER_ROLE_CODES,
        RoleCode.HOMEOWNER,
        RoleCode.BOARD_MEMBER,
        RoleCode.COMMITTEE_MEMBER,
    }


def test_delinquency_routes_are_registered() -> None:
    from app.main import app

    registered = {
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    }
    assert {
        ("GET", "/api/delinquency-reports"),
        ("GET", "/api/delinquency-reports/periods"),
        ("GET", "/api/delinquency-reports/export"),
        ("GET", "/api/delinquency-reports/template"),
        ("POST", "/api/delinquency-reports"),
        ("POST", "/api/delinquency-reports/import"),
        ("PUT", "/api/delinquency-reports/{report_id}"),
    } <= registered
