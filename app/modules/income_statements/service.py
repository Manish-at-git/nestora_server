import json
import uuid
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.income_statements.messages import IncomeStatementMessage
from app.modules.income_statements.models import IncomeStatement, IncomeStatementItem
from app.modules.income_statements.repository import IncomeStatementRepository
from app.modules.income_statements.schemas import IncomeStatementRequest, IncomeStatementResponse


class IncomeStatementService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = IncomeStatementRepository(session)

    async def check_association(self, account, association_id: str) -> None:
        if not await self.repository.association_exists(association_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, IncomeStatementMessage.ASSOCIATION_NOT_FOUND)
        scoped = await self.repository.scoped_associations(account.id, account.role.code, account.user_id)
        if scoped is not None and association_id not in scoped:
            raise HTTPException(status.HTTP_403_FORBIDDEN, IncomeStatementMessage.UNAUTHORIZED_ASSOCIATION)

    @staticmethod
    def totals(items) -> tuple[Decimal, Decimal, Decimal, Decimal]:
        income = sum((Decimal(item.current_amount) for item in items if item.item_type == "income"), Decimal("0"))
        expenses = sum((Decimal(item.current_amount) for item in items if item.item_type == "expense"), Decimal("0"))
        surplus = income - expenses
        margin = (surplus / income * Decimal("100")) if income else Decimal("0")
        return income, expenses, surplus, margin.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def build_items(statement_id: str, requests) -> list[IncomeStatementItem]:
        return [IncomeStatementItem(id=str(uuid.uuid4()), income_statement_id=statement_id, item_type=item.item_type.value, name=item.name.strip(), current_amount=item.current_amount, previous_amount=item.previous_amount, sort_order=index) for index, item in enumerate(requests)]

    async def save(self, account, payload: IncomeStatementRequest, statement: IncomeStatement | None = None) -> IncomeStatement:
        await self.check_association(account, payload.association_id)
        if statement is None:
            if await self.repository.duplicate_period(payload.association_id, payload.fiscal_period):
                raise HTTPException(status.HTTP_409_CONFLICT, IncomeStatementMessage.DUPLICATE_PERIOD)
            statement = IncomeStatement(id=str(uuid.uuid4()), association_id=payload.association_id, fiscal_period=payload.fiscal_period, created_by=account.id)
            self.repository.add(statement)
        elif payload.association_id != statement.association_id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "An Income Statement cannot be moved to another association")
        elif await self.repository.duplicate_period(payload.association_id, payload.fiscal_period, excluding_id=statement.id):
            raise HTTPException(status.HTTP_409_CONFLICT, IncomeStatementMessage.DUPLICATE_PERIOD)

        income, expenses, surplus, margin = self.totals(payload.items)
        statement.fiscal_period = payload.fiscal_period
        statement.total_income = income
        statement.total_expenses = expenses
        statement.net_surplus = surplus
        statement.operating_margin_pct = margin
        statement.income_growth_pct = payload.income_growth_pct
        statement.expenses_growth_pct = payload.expenses_growth_pct
        statement.net_surplus_growth_pct = payload.net_surplus_growth_pct
        statement.operating_margin_growth_pct = payload.operating_margin_growth_pct
        statement.insights_json = json.dumps([item.model_dump() for item in payload.insights])
        statement.monthly_trend_json = json.dumps(payload.monthly_trend)
        statement.updated_by = account.id
        await self.repository.replace_items(statement, self.build_items(statement.id, payload.items))
        await self.repository.session.flush()
        return statement

    async def get(self, account, association_id: str, fiscal_period: str | None) -> IncomeStatement | None:
        await self.check_association(account, association_id)
        return await self.repository.get_by_period(association_id, fiscal_period)

    async def periods(self, account, association_id: str) -> list[str]:
        await self.check_association(account, association_id)
        return await self.repository.list_periods(association_id)

    async def serialize(self, statement: IncomeStatement) -> IncomeStatementResponse:
        items = []
        for item in statement.items:
            previous = Decimal(item.previous_amount or 0)
            current = Decimal(item.current_amount or 0)
            variance = ((current - previous) / previous * Decimal("100")) if previous else Decimal("0")
            items.append({"id": item.id, "item_type": item.item_type, "name": item.name, "current_amount": current, "previous_amount": previous, "variance_pct": variance.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)})
        return IncomeStatementResponse(id=statement.id, association_id=statement.association_id, association_name=statement.association.name, fiscal_period=statement.fiscal_period, items=items, total_income=statement.total_income, total_expenses=statement.total_expenses, net_surplus=statement.net_surplus, operating_margin_pct=statement.operating_margin_pct, income_growth_pct=statement.income_growth_pct, expenses_growth_pct=statement.expenses_growth_pct, net_surplus_growth_pct=statement.net_surplus_growth_pct, operating_margin_growth_pct=statement.operating_margin_growth_pct, insights=json.loads(statement.insights_json or "[]"), monthly_trend=json.loads(statement.monthly_trend_json or "[]"), created_at=statement.created_at, updated_at=statement.updated_at)
