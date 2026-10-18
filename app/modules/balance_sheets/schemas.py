"""Request and response contracts for association Balance Sheets."""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field


class BalanceSheetSection(StrEnum):
    CURRENT_ASSET = "current_asset"
    NON_CURRENT_ASSET = "non_current_asset"
    CURRENT_LIABILITY = "current_liability"
    NON_CURRENT_LIABILITY = "non_current_liability"
    EQUITY = "equity"


class BalanceSheetItemRequest(BaseModel):
    section: BalanceSheetSection
    account_name: str = Field(min_length=1, max_length=255)
    amount: Decimal = Field(max_digits=18, decimal_places=2)
    chart_of_account_id: str | None = None


class BalanceSheetRequest(BaseModel):
    association_id: str
    as_on_date: date
    items: list[BalanceSheetItemRequest] = Field(min_length=1, max_length=1000)
    health_status: str | None = Field(default=None, max_length=50)
    health_note: str | None = Field(default=None, max_length=2000)


class BalanceSheetItemResponse(BaseModel):
    id: str
    chart_of_account_id: str | None = None
    account_code: str | None = None
    section: BalanceSheetSection
    account_name: str
    amount: Decimal
    sort_order: int


class BalanceSheetTotals(BaseModel):
    current_assets: Decimal
    non_current_assets: Decimal
    total_assets: Decimal
    current_liabilities: Decimal
    non_current_liabilities: Decimal
    total_liabilities: Decimal
    total_equity: Decimal
    liabilities_and_equity: Decimal
    working_capital: Decimal
    current_ratio: Decimal | None = None
    debt_to_equity_ratio: Decimal | None = None


class BalanceSheetResponse(BaseModel):
    id: str
    association_id: str
    association_name: str
    as_on_date: date
    items: list[BalanceSheetItemResponse]
    totals: BalanceSheetTotals
    assets_growth_pct: Decimal | None = None
    liabilities_growth_pct: Decimal | None = None
    equity_growth_pct: Decimal | None = None
    health_status: str | None = None
    health_note: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class BalanceSheetMutationResponse(BaseModel):
    id: str
    imported_items: int | None = None
