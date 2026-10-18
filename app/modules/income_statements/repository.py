from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.constants import RoleCode
from app.modules.associations.models import Association
from app.modules.income_statements.models import IncomeStatement, IncomeStatementItem


class IncomeStatementRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def scoped_associations(self, account_id: str, role_code: str, user_id: str | None) -> list[str] | None:
        if role_code == RoleCode.SUPER_ADMIN.value:
            return None
        rows = await self.session.scalars(text("SELECT association_id FROM admin_associations WHERE admin_id=:account_id"), {"account_id": account_id})
        ids = list(rows.all())
        if ids:
            return ids
        if user_id:
            value = await self.session.scalar(text("SELECT association_id FROM user_details WHERE user_id=:user_id AND is_deleted=0 LIMIT 1"), {"user_id": user_id})
            if value:
                return [value]
        return []

    async def association_exists(self, association_id: str) -> bool:
        return await self.session.scalar(select(Association.id).where(Association.id == association_id, Association.is_deleted.is_(False))) is not None

    async def get_by_id(self, statement_id: str) -> IncomeStatement | None:
        query = select(IncomeStatement).options(selectinload(IncomeStatement.items)).where(IncomeStatement.id == statement_id)
        return await self.session.scalar(query)

    async def get_by_period(self, association_id: str, fiscal_period: str | None) -> IncomeStatement | None:
        query = select(IncomeStatement).options(selectinload(IncomeStatement.items)).where(IncomeStatement.association_id == association_id)
        if fiscal_period:
            query = query.where(IncomeStatement.fiscal_period == fiscal_period)
        else:
            query = query.order_by(IncomeStatement.created_at.desc()).limit(1)
        return await self.session.scalar(query)

    async def list_periods(self, association_id: str) -> list[str]:
        query = select(IncomeStatement.fiscal_period).where(IncomeStatement.association_id == association_id).order_by(IncomeStatement.created_at.desc())
        return list((await self.session.scalars(query)).all())

    async def duplicate_period(self, association_id: str, fiscal_period: str, excluding_id: str | None = None) -> bool:
        query = select(IncomeStatement.id).where(IncomeStatement.association_id == association_id, IncomeStatement.fiscal_period == fiscal_period)
        if excluding_id:
            query = query.where(IncomeStatement.id != excluding_id)
        return await self.session.scalar(query) is not None

    def add(self, statement: IncomeStatement) -> None:
        self.session.add(statement)

    async def replace_items(self, statement: IncomeStatement, items: list[IncomeStatementItem]) -> None:
        await self.session.execute(delete(IncomeStatementItem).where(IncomeStatementItem.income_statement_id == statement.id))
        statement.items = items
