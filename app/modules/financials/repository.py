"""Database access for published financial reports."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.associations.models import Association
from app.modules.financials.models import FinancialReport


class FinancialRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self) -> list[FinancialReport]:
        statement = (
            select(FinancialReport)
            .options(selectinload(FinancialReport.association))
            .join(Association, Association.id == FinancialReport.association_id)
            .where(
                FinancialReport.is_deleted.is_(False),
                Association.is_deleted.is_(False),
            )
            .order_by(FinancialReport.created_at.desc())
        )
        return list((await self.session.scalars(statement)).all())

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

    def add(self, report: FinancialReport) -> None:
        self.session.add(report)
