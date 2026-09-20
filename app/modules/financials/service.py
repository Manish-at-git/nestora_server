"""Financial report business rules."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.financials.messages import FinancialMessage
from app.modules.financials.models import FinancialReport
from app.modules.financials.repository import FinancialRepository
from app.modules.financials.schemas import FinancialReportRequest


class FinancialService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = FinancialRepository(session)

    async def list(self) -> list[FinancialReport]:
        return await self.repository.list()

    async def create(
        self, account_id: str, payload: FinancialReportRequest
    ) -> FinancialReport:
        if not await self.repository.association_exists(payload.association_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, FinancialMessage.ASSOCIATION_NOT_FOUND)

        report = FinancialReport(
            id=str(uuid.uuid4()),
            association_id=payload.association_id,
            published_month=payload.published_month.strip(),
            report_type=payload.report_type.strip(),
            title=payload.title.strip(),
            file_url=payload.file_url.strip(),
            uploaded_by=account_id,
        )
        self.repository.add(report)
        await self.repository.session.flush()
        await self.repository.session.refresh(report)
        return report
