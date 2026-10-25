"""Focused Invoice authorization, ownership, calculation, and route checks."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.core.constants import RoleCode
from app.modules.associations.models import Association
from app.modules.invoices.router import MANAGER_ROLE_CODES, VIEWER_ROLE_CODES
from app.modules.invoices.schemas import (
    DiscountType,
    InvoiceLineRequest,
    InvoiceRequest,
    InvoiceStatus,
)
from app.modules.invoices.service import InvoiceService
from app.modules.vendors.models import Vendor


def payload(**overrides) -> InvoiceRequest:
    values = {
        "association_id": "association-1",
        "vendor_id": "vendor-1",
        "billing_address": "Association billing address",
        "invoice_number": "INV-001",
        "issue_date": date(2026, 10, 1),
        "due_date": date(2026, 10, 31),
        "payment_terms": "Net 30",
        "lines": [
            InvoiceLineRequest(
                description="Service", quantity=Decimal("2.5"), rate=Decimal("10.10")
            ),
            InvoiceLineRequest(description="Parts", quantity=Decimal("1"), rate=Decimal("4.75")),
        ],
        "discount_type": DiscountType.PERCENTAGE,
        "discount_value": Decimal("10"),
        "tax_type": "GST",
        "tax_rate": Decimal("18"),
        "status": InvoiceStatus.PENDING,
    }
    values.update(overrides)
    return InvoiceRequest(**values)


def account(role: str = "admin") -> SimpleNamespace:
    return SimpleNamespace(id="account-1", user_id="user-1", role=SimpleNamespace(code=role))


def test_decimal_totals_are_calculated_from_lines() -> None:
    subtotal, discount, tax, total = InvoiceService.calculate(payload())
    assert subtotal == Decimal("30.00")
    assert discount == Decimal("3.00")
    assert tax == Decimal("4.86")
    assert total == Decimal("31.86")


def test_flat_discount_cannot_exceed_subtotal() -> None:
    with pytest.raises(HTTPException) as exc_info:
        InvoiceService.calculate(payload(discount_type="flat", discount_value="100"))
    assert exc_info.value.status_code == 422


def test_payment_account_comes_from_selected_vendor_bank_details() -> None:
    vendor = Vendor(
        id="vendor-1",
        name="Vendor",
        service_type="Testing",
        bank_name="HDFC",
        bank_account_number="234234234234",
        bank_ifsc_code="HDFC0000123",
    )

    account = InvoiceService.vendor_payment_account(vendor)

    assert account is not None
    assert account.bank_name == "HDFC"
    assert account.account_number == "234234234234"


def test_invalid_dates_and_empty_lines_are_rejected() -> None:
    with pytest.raises(ValidationError):
        payload(due_date=date(2026, 9, 30))
    with pytest.raises(ValidationError):
        payload(lines=[])


def test_status_transition_rules_are_enforced() -> None:
    InvoiceService.validate_transition(InvoiceStatus.PENDING, InvoiceStatus.PAID)
    with pytest.raises(HTTPException) as exc_info:
        InvoiceService.validate_transition(InvoiceStatus.PAID, InvoiceStatus.PENDING)
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_duplicate_invoice_number_is_rejected_before_insert() -> None:
    service = InvoiceService(AsyncMock())
    service.check_association = AsyncMock()
    service.require_vendor = AsyncMock()
    service.repository.number_exists = AsyncMock(return_value=True)
    service.repository.add = MagicMock()
    with pytest.raises(HTTPException) as exc_info:
        await service.create(account(), payload())
    assert exc_info.value.status_code == 409
    service.repository.add.assert_not_called()


@pytest.mark.asyncio
async def test_create_generates_an_association_scoped_invoice_number() -> None:
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=0)
    service = InvoiceService(session)
    service.check_association = AsyncMock(
        return_value=Association(id="association-1", name="Test Association")
    )
    service.require_vendor = AsyncMock(
        return_value=Vendor(id="vendor-1", name="Vendor", service_type="Testing")
    )
    service.repository.number_exists = AsyncMock(side_effect=[False, False])
    service.repository.add = MagicMock()

    created = await service.create(account(), payload(invoice_number=None))

    assert created.invoice_number.startswith("INV-")
    assert created.invoice_number.endswith("-0001")


@pytest.mark.asyncio
async def test_get_scopes_invoice_by_authorized_association() -> None:
    service = InvoiceService(AsyncMock())
    service.check_association = AsyncMock()
    service.repository.get_scoped = AsyncMock(return_value=None)
    with pytest.raises(HTTPException) as exc_info:
        await service.get(account("homeowner"), "invoice-1", "association-2")
    assert exc_info.value.status_code == 404
    service.repository.get_scoped.assert_awaited_once_with("invoice-1", "association-2")


@pytest.mark.asyncio
async def test_status_and_delete_mutations_reuse_scoped_invoice_lookup() -> None:
    session = AsyncMock()
    service = InvoiceService(session)
    invoice = SimpleNamespace(
        id="invoice-1",
        issue_date=date(2026, 10, 1),
        status="pending",
        payment_date=None,
        payment_method=None,
        updated_by=None,
        is_deleted=False,
        deleted_by=None,
        deleted_at=None,
    )
    service.get = AsyncMock(return_value=invoice)

    from app.modules.invoices.schemas import InvoiceStatusRequest

    await service.update_status(
        account(),
        "invoice-1",
        InvoiceStatusRequest(
            association_id="association-1",
            status=InvoiceStatus.PAID,
            payment_date=date(2026, 10, 2),
        ),
    )
    await service.delete(account(), "invoice-1", "association-1")

    assert invoice.status == "paid"
    assert invoice.is_deleted is True
    assert service.get.await_args_list[0].args[1:] == ("invoice-1", "association-1")
    assert service.get.await_args_list[1].args[1:] == ("invoice-1", "association-1")


@pytest.mark.asyncio
async def test_empty_list_returns_zero_totals_and_no_fallback_rows() -> None:
    service = InvoiceService(AsyncMock())
    service.check_association = AsyncMock()
    service.repository.list_filtered = AsyncMock(return_value=[])
    service.repository.fiscal_periods = AsyncMock(return_value=[])
    result = await service.list(account(), "association-1", None, None, None, None, 1, 20)
    assert result.rows == []
    assert result.total_count == 0
    assert result.total_amount == Decimal("0.00")


def test_authorization_role_sets_match_contract() -> None:
    assert set(MANAGER_ROLE_CODES) == {RoleCode.SUPER_ADMIN, RoleCode.ADMIN, RoleCode.ACCOUNTANT}
    assert set(VIEWER_ROLE_CODES) == {
        *MANAGER_ROLE_CODES,
        RoleCode.HOMEOWNER,
        RoleCode.BOARD_MEMBER,
        RoleCode.COMMITTEE_MEMBER,
    }


def test_invoice_routes_are_registered() -> None:
    from app.main import app

    paths = app.openapi()["paths"]
    registered = {
        (method.upper(), path) for path, operations in paths.items() for method in operations
    }
    assert {
        ("GET", "/api/invoices"),
        ("GET", "/api/invoices/vendors"),
        ("GET", "/api/invoices/export"),
        ("GET", "/api/invoices/{invoice_id}"),
        ("POST", "/api/invoices"),
        ("PUT", "/api/invoices/{invoice_id}"),
        ("PATCH", "/api/invoices/{invoice_id}/status"),
        ("DELETE", "/api/invoices/{invoice_id}"),
    } <= registered
