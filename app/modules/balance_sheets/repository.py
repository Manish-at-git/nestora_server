"""Database access for association Balance Sheets."""

from datetime import date

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.constants import RoleCode
from app.modules.associations.models import Association
from app.modules.balance_sheets.models import BalanceSheet, BalanceSheetItem
from app.modules.chart_of_accounts.models import AssociationChartOfAccount


class BalanceSheetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def scoped_associations(
        self,
        account_id: str,
        role_code: str,
        user_id: str | None,
    ) -> list[str] | None:
        if role_code == RoleCode.SUPER_ADMIN.value:
            return None

        rows = await self.session.scalars(
            text(
                "SELECT association_id FROM admin_associations "
                "WHERE admin_id=:account_id"
            ),
            {"account_id": account_id},
        )
        association_ids = list(rows.all())
        if association_ids:
            return association_ids

        if user_id:
            association_id = await self.session.scalar(
                text(
                    "SELECT association_id FROM user_details "
                    "WHERE user_id=:user_id AND is_deleted=0 LIMIT 1"
                ),
                {"user_id": user_id},
            )
            if association_id:
                return [association_id]

        return []

    async def association_exists(self, association_id: str) -> bool:
        statement = select(Association.id).where(
            Association.id == association_id,
            Association.is_deleted.is_(False),
        )
        return await self.session.scalar(statement) is not None

    async def get_by_id(self, balance_sheet_id: str) -> BalanceSheet | None:
        statement = (
            select(BalanceSheet)
            .options(selectinload(BalanceSheet.items))
            .where(BalanceSheet.id == balance_sheet_id)
        )
        return await self.session.scalar(statement)

    async def get_by_date(
        self,
        association_id: str,
        as_on_date: date | None,
    ) -> BalanceSheet | None:
        statement = (
            select(BalanceSheet)
            .options(selectinload(BalanceSheet.items))
            .where(BalanceSheet.association_id == association_id)
        )
        if as_on_date:
            statement = statement.where(BalanceSheet.as_on_date == as_on_date)
        else:
            statement = statement.order_by(BalanceSheet.as_on_date.desc()).limit(1)
        return await self.session.scalar(statement)

    async def list_dates(self, association_id: str) -> list[date]:
        statement = (
            select(BalanceSheet.as_on_date)
            .where(BalanceSheet.association_id == association_id)
            .order_by(BalanceSheet.as_on_date.desc())
        )
        return list((await self.session.scalars(statement)).all())

    async def previous_snapshot(
        self,
        association_id: str,
        as_on_date: date,
    ) -> BalanceSheet | None:
        statement = (
            select(BalanceSheet)
            .options(selectinload(BalanceSheet.items))
            .where(
                BalanceSheet.association_id == association_id,
                BalanceSheet.as_on_date < as_on_date,
            )
            .order_by(BalanceSheet.as_on_date.desc())
            .limit(1)
        )
        return await self.session.scalar(statement)

    async def duplicate_date(
        self,
        association_id: str,
        as_on_date: date,
        excluding_id: str | None = None,
    ) -> bool:
        statement = select(BalanceSheet.id).where(
            BalanceSheet.association_id == association_id,
            BalanceSheet.as_on_date == as_on_date,
        )
        if excluding_id:
            statement = statement.where(BalanceSheet.id != excluding_id)
        return await self.session.scalar(statement) is not None

    async def association_accounts_by_id(
        self,
        association_id: str,
        account_ids: set[str],
    ) -> dict[str, AssociationChartOfAccount]:
        if not account_ids:
            return {}
        statement = select(AssociationChartOfAccount).where(
            AssociationChartOfAccount.association_id == association_id,
            AssociationChartOfAccount.id.in_(account_ids),
            AssociationChartOfAccount.is_deleted.is_(False),
        )
        accounts = (await self.session.scalars(statement)).all()
        return {account.id: account for account in accounts}

    async def association_accounts_by_code(
        self,
        association_id: str,
        account_codes: set[str],
    ) -> dict[str, AssociationChartOfAccount]:
        if not account_codes:
            return {}
        statement = select(AssociationChartOfAccount).where(
            AssociationChartOfAccount.association_id == association_id,
            AssociationChartOfAccount.gl_code.in_(account_codes),
            AssociationChartOfAccount.is_deleted.is_(False),
        )
        accounts = (await self.session.scalars(statement)).all()
        return {account.gl_code: account for account in accounts}

    async def item_account_codes(
        self,
        account_ids: set[str],
    ) -> dict[str, str]:
        if not account_ids:
            return {}
        statement = select(
            AssociationChartOfAccount.id,
            AssociationChartOfAccount.gl_code,
        ).where(AssociationChartOfAccount.id.in_(account_ids))
        rows = (await self.session.execute(statement)).all()
        return {row.id: row.gl_code for row in rows}

    def add(self, balance_sheet: BalanceSheet) -> None:
        self.session.add(balance_sheet)

    async def replace_items(
        self,
        balance_sheet: BalanceSheet,
        items: list[BalanceSheetItem],
    ) -> None:
        await self.session.execute(
            delete(BalanceSheetItem).where(
                BalanceSheetItem.balance_sheet_id == balance_sheet.id
            )
        )
        balance_sheet.items = items
