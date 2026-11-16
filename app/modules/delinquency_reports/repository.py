from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.constants import RoleCode
from app.modules.associations.models import Association
from app.modules.delinquency_reports.models import (
    DelinquencyReport,
    DelinquencyReportRow,
)


class DelinquencyReportRepository:
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
        return (
            await self.session.scalar(
                select(Association.id).where(
                    Association.id == association_id,
                    Association.is_deleted.is_(False),
                )
            )
            is not None
        )

    async def get_by_id(self, report_id: str) -> DelinquencyReport | None:
        return await self.session.scalar(
            select(DelinquencyReport)
            .options(selectinload(DelinquencyReport.rows))
            .where(DelinquencyReport.id == report_id)
        )

    async def get_by_period(
        self,
        association_id: str,
        fiscal_period: str | None,
    ) -> DelinquencyReport | None:
        query = (
            select(DelinquencyReport)
            .options(selectinload(DelinquencyReport.rows))
            .where(DelinquencyReport.association_id == association_id)
        )
        if fiscal_period:
            query = query.where(DelinquencyReport.fiscal_period == fiscal_period)
        else:
            query = query.order_by(DelinquencyReport.created_at.desc()).limit(1)
        return await self.session.scalar(query)

    async def list_periods(self, association_id: str) -> list[str]:
        query = (
            select(DelinquencyReport.fiscal_period)
            .where(DelinquencyReport.association_id == association_id)
            .order_by(DelinquencyReport.created_at.desc())
        )
        return list((await self.session.scalars(query)).all())

    async def member_options(self, association_id: str) -> list[dict]:
        result = await self.session.execute(
            text(
                "SELECT DISTINCT ud.user_id, COALESCE(ud.name, a.email) AS name, "
                "u.unit_number, b.name AS block, 'Homeowner' AS role_label "
                "FROM accounts a JOIN roles r ON r.id=a.role_id "
                "JOIN user_details ud ON ud.user_id=a.user_id "
                "LEFT JOIN units u ON u.id=ud.unit_id LEFT JOIN blocks b ON b.id=u.block_id "
                "WHERE ud.is_deleted=0 AND r.code=:homeowner_role "
                "AND COALESCE(ud.association_id,b.association_id)=:association_id "
                "UNION "
                "SELECT DISTINCT ud.user_id, COALESCE(ud.name, a.email) AS name, "
                "u.unit_number, b.name AS block, 'Board Member' AS role_label "
                "FROM board_members bm JOIN accounts a ON a.account_id=bm.account_id "
                "LEFT JOIN user_details ud ON ud.user_id=a.user_id "
                "LEFT JOIN units u ON u.id=ud.unit_id LEFT JOIN blocks b ON b.id=u.block_id "
                "WHERE bm.is_deleted=0 AND bm.status='active' "
                "AND (bm.term_end_date IS NULL OR bm.term_end_date>=CURRENT_DATE) "
                "AND bm.association_id=:association_id "
                "UNION "
                "SELECT DISTINCT ud.user_id, COALESCE(ud.name, a.email) AS name, "
                "u.unit_number, b.name AS block, 'Committee Member' AS role_label "
                "FROM committee_members cm JOIN committees c ON c.id=cm.committee_id "
                "JOIN accounts a ON a.user_id=cm.user_id "
                "LEFT JOIN user_details ud ON ud.user_id=cm.user_id "
                "LEFT JOIN units u ON u.id=ud.unit_id LEFT JOIN blocks b ON b.id=u.block_id "
                "WHERE cm.is_deleted=0 AND c.is_deleted=0 "
                "AND (cm.start_date IS NULL OR cm.start_date<=CURRENT_DATE) "
                "AND (cm.end_date IS NULL OR cm.end_date>=CURRENT_DATE) "
                "AND c.association_id=:association_id "
                "ORDER BY name, block, unit_number"
            ),
            {"association_id": association_id, "homeowner_role": RoleCode.HOMEOWNER.value},
        )
        return [dict(row) for row in result.mappings().all()]

    async def duplicate_period(
        self,
        association_id: str,
        fiscal_period: str,
        excluding_id: str | None = None,
    ) -> bool:
        query = select(DelinquencyReport.id).where(
            DelinquencyReport.association_id == association_id,
            DelinquencyReport.fiscal_period == fiscal_period,
        )
        if excluding_id:
            query = query.where(DelinquencyReport.id != excluding_id)
        return await self.session.scalar(query) is not None

    def add(self, report: DelinquencyReport) -> None:
        self.session.add(report)

    async def replace_rows(
        self,
        report: DelinquencyReport,
        rows: list[DelinquencyReportRow],
    ) -> None:
        await self.session.execute(
            delete(DelinquencyReportRow).where(
                DelinquencyReportRow.delinquency_report_id == report.id
            )
        )
        report.rows = rows
