from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.constants import RoleCode
from app.modules.associations.models import Association
from app.modules.prepaid_reports.models import PrepaidReport, PrepaidReportRow


class PrepaidReportRepository:
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
        query = select(Association.id).where(
            Association.id == association_id,
            Association.is_deleted.is_(False),
        )
        return await self.session.scalar(query) is not None

    async def get_by_id(self, report_id: str) -> PrepaidReport | None:
        query = (
            select(PrepaidReport)
            .options(selectinload(PrepaidReport.rows))
            .where(PrepaidReport.id == report_id)
        )
        return await self.session.scalar(query)

    async def get_by_period(
        self,
        association_id: str,
        fiscal_period: str | None,
    ) -> PrepaidReport | None:
        query = (
            select(PrepaidReport)
            .options(selectinload(PrepaidReport.rows))
            .where(PrepaidReport.association_id == association_id)
        )
        if fiscal_period:
            query = query.where(PrepaidReport.fiscal_period == fiscal_period)
        else:
            query = query.order_by(PrepaidReport.created_at.desc()).limit(1)
        return await self.session.scalar(query)

    async def list_periods(self, association_id: str) -> list[str]:
        query = (
            select(PrepaidReport.fiscal_period)
            .where(PrepaidReport.association_id == association_id)
            .order_by(PrepaidReport.created_at.desc())
        )
        return list((await self.session.scalars(query)).all())

    async def duplicate_period(
        self,
        association_id: str,
        fiscal_period: str,
        excluding_id: str | None = None,
    ) -> bool:
        query = select(PrepaidReport.id).where(
            PrepaidReport.association_id == association_id,
            PrepaidReport.fiscal_period == fiscal_period,
        )
        if excluding_id:
            query = query.where(PrepaidReport.id != excluding_id)
        return await self.session.scalar(query) is not None

    def add(self, report: PrepaidReport) -> None:
        self.session.add(report)

    async def replace_rows(
        self,
        report: PrepaidReport,
        rows: list[PrepaidReportRow],
    ) -> None:
        await self.session.execute(
            delete(PrepaidReportRow).where(
                PrepaidReportRow.prepaid_report_id == report.id
            )
        )
        report.rows = rows
