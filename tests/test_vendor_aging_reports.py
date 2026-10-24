"""Focused Vendor Aging calculation, validation, authorization, and route checks."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.core.constants import RoleCode
from app.modules.associations.models import Association
from app.modules.vendor_aging_reports.models import VendorAgingReport, VendorAgingRow
from app.modules.vendor_aging_reports.router import (
    MANAGER_ROLE_CODES,
    VIEWER_ROLE_CODES,
    build_export_workbook,
    parse_import_workbook,
)
from app.modules.vendor_aging_reports.schemas import (
    VendorAgingReportRequest,
    VendorAgingRowRequest,
    VendorAgingStatus,
)
from app.modules.vendor_aging_reports.service import VendorAgingReportService


def row(
    vendor: str = "Test Vendor",
    category: str = "Maintenance",
    current: str = "100.00",
    days_1_30: str = "25.00",
) -> VendorAgingRowRequest:
    return VendorAgingRowRequest(
        vendor_name=vendor,
        category=category,
        invoice_number="INV-TEST",
        invoice_date=date(2026, 10, 1),
        current_due=Decimal(current),
        days_1_30=Decimal(days_1_30),
        days_31_60=Decimal("10.00"),
        days_61_90=Decimal("5.00"),
        days_over_90=Decimal("2.00"),
    )


def account(role_code: str = "admin") -> SimpleNamespace:
    return SimpleNamespace(
        id="account-1",
        user_id="user-1",
        role=SimpleNamespace(code=role_code),
    )


def model_row(
    row_id: str,
    vendor: str,
    category: str,
    current: str,
    days_1_30: str,
) -> VendorAgingRow:
    return VendorAgingRow(
        id=row_id,
        vendor_aging_report_id="report-1",
        vendor_name=vendor,
        category=category,
        invoice_number=f"INV-{row_id}",
        invoice_date=date(2026, 10, 1),
        current_due=Decimal(current),
        days_1_30=Decimal(days_1_30),
        days_31_60=Decimal("0.00"),
        days_61_90=Decimal("0.00"),
        days_over_90=Decimal("0.00"),
        sort_order=0,
    )


def report() -> VendorAgingReport:
    return VendorAgingReport(
        id="report-1",
        association_id="association-1",
        fiscal_period="01 Apr 2026 - 31 Mar 2027",
        association=Association(id="association-1", name="Test Association"),
        rows=[
            model_row("one", "Vendor One", "Maintenance", "100.00", "25.00"),
            model_row("two", "Vendor Two", "Utilities", "80.00", "0.00"),
        ],
    )


def test_totals_are_derived_from_aging_buckets() -> None:
    service = VendorAgingReportService(AsyncMock())
    outstanding, overdue, current = service.totals([row()])

    assert outstanding == Decimal("142.00")
    assert overdue == Decimal("42.00")
    assert current == Decimal("100.00")


def test_negative_aging_amount_is_rejected() -> None:
    with pytest.raises(ValidationError):
        row(days_1_30="-1.00")


def test_duplicate_vendor_invoice_is_rejected() -> None:
    with pytest.raises(ValidationError):
        VendorAgingReportRequest(
            association_id="association-1",
            fiscal_period="01 Apr 2026 - 31 Mar 2027",
            rows=[row(), row()],
        )


def test_status_is_derived_from_bucket_balances() -> None:
    service = VendorAgingReportService(AsyncMock())

    assert service.derive_status(Decimal("0"), Decimal("0")) == VendorAgingStatus.SETTLED
    assert service.derive_status(Decimal("10"), Decimal("0")) == VendorAgingStatus.DUE_SOON
    assert service.derive_status(Decimal("10"), Decimal("1")) == VendorAgingStatus.OVERDUE


@pytest.mark.asyncio
async def test_duplicate_association_period_is_rejected() -> None:
    service = VendorAgingReportService(AsyncMock())
    service.check_association = AsyncMock()
    service.repository.duplicate_period = AsyncMock(return_value=True)
    payload = VendorAgingReportRequest(
        association_id="association-1",
        fiscal_period="01 Apr 2026 - 31 Mar 2027",
        rows=[row()],
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.create(account(), payload)

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_association_scope_blocks_an_unassigned_association() -> None:
    service = VendorAgingReportService(AsyncMock())
    service.repository.association_exists = AsyncMock(return_value=True)
    service.repository.scoped_associations = AsyncMock(return_value=["association-1"])

    with pytest.raises(HTTPException) as exc_info:
        await service.check_association(account("homeowner"), "association-2")

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_category_and_search_filters_recalculate_summaries() -> None:
    service = VendorAgingReportService(AsyncMock())

    response = await service.serialize(
        report(),
        category="Maintenance",
        search="INV-one",
    )

    assert response.available_categories == ["Maintenance", "Utilities"]
    assert [item.vendor_name for item in response.rows] == ["Vendor One"]
    assert response.summary.total_outstanding == Decimal("125.00")
    assert response.summary.overdue_amount == Decimal("25.00")
    assert response.summary.vendor_count == 1
    assert response.aging_distribution[1].amount == Decimal("25.00")


@pytest.mark.asyncio
async def test_export_contains_context_rows_and_totals() -> None:
    service = VendorAgingReportService(AsyncMock())
    response = await service.serialize(report(), category="Maintenance", search="Vendor")
    sheet = build_export_workbook(response).active

    assert sheet["A1"].value == "Test Association - Vendor Aging Report"
    assert "Category: Maintenance" in sheet["A2"].value
    assert "Search: Vendor" in sheet["A2"].value
    assert sheet["B8"].value == "Vendor One"
    assert sheet["K9"].value == 125.0


@pytest.mark.asyncio
async def test_exported_workbook_can_be_imported_without_derived_columns() -> None:
    response = await VendorAgingReportService(AsyncMock()).serialize(report())
    imported = parse_import_workbook(
        build_export_workbook(response),
        "association-1",
        "01 Apr 2027 - 31 Mar 2028",
    )

    assert len(imported.rows) == 2
    assert imported.rows[0].vendor_name == "Vendor One"
    assert imported.rows[0].current_due == Decimal("100.00")
    assert imported.rows[0].days_1_30 == Decimal("25.00")


@pytest.mark.asyncio
async def test_import_error_lists_a_missing_required_column() -> None:
    response = await VendorAgingReportService(AsyncMock()).serialize(report())
    workbook = build_export_workbook(response)
    workbook.active["H7"] = "Wrong heading"

    with pytest.raises(ValueError, match="Missing required column.*Days 31 60"):
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


def test_vendor_aging_routes_are_registered() -> None:
    from app.main import app

    paths = app.openapi()["paths"]
    registered = {
        (method.upper(), path)
        for path, operations in paths.items()
        for method in operations
    }
    expected = {
        ("GET", "/api/vendor-aging-reports"),
        ("GET", "/api/vendor-aging-reports/periods"),
        ("GET", "/api/vendor-aging-reports/export"),
        ("GET", "/api/vendor-aging-reports/template"),
        ("POST", "/api/vendor-aging-reports"),
        ("POST", "/api/vendor-aging-reports/import"),
        ("PUT", "/api/vendor-aging-reports/{report_id}"),
    }

    assert expected <= registered
