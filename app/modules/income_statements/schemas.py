from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field


class IncomeStatementItemType(StrEnum):
    INCOME = "income"
    EXPENSE = "expense"


class IncomeStatementItemRequest(BaseModel):
    item_type: IncomeStatementItemType
    name: str = Field(min_length=1, max_length=255)
    current_amount: Decimal = Field(max_digits=18, decimal_places=2)
    previous_amount: Decimal = Field(max_digits=18, decimal_places=2)


class IncomeStatementInsight(BaseModel):
    type: str = Field(max_length=30)
    title: str = Field(max_length=255)
    description: str = Field(max_length=1000)


class IncomeStatementRequest(BaseModel):
    association_id: str
    fiscal_period: str = Field(min_length=3, max_length=100)
    items: list[IncomeStatementItemRequest] = Field(min_length=1, max_length=1000)
    income_growth_pct: Decimal | None = None
    expenses_growth_pct: Decimal | None = None
    net_surplus_growth_pct: Decimal | None = None
    operating_margin_growth_pct: Decimal | None = None
    insights: list[IncomeStatementInsight] = Field(default_factory=list, max_length=20)
    monthly_trend: list[dict] = Field(default_factory=list, max_length=24)


class IncomeStatementItemResponse(IncomeStatementItemRequest):
    id: str
    variance_pct: Decimal


class IncomeStatementResponse(BaseModel):
    id: str
    association_id: str
    association_name: str
    fiscal_period: str
    items: list[IncomeStatementItemResponse]
    total_income: Decimal
    total_expenses: Decimal
    net_surplus: Decimal
    operating_margin_pct: Decimal
    income_growth_pct: Decimal | None = None
    expenses_growth_pct: Decimal | None = None
    net_surplus_growth_pct: Decimal | None = None
    operating_margin_growth_pct: Decimal | None = None
    insights: list[IncomeStatementInsight]
    monthly_trend: list[dict]
    created_at: datetime | None = None
    updated_at: datetime | None = None


class IncomeStatementMutationResponse(BaseModel):
    id: str
    imported_items: int | None = None
