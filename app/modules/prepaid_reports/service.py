import uuid
from collections import defaultdict
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.prepaid_reports.messages import PrepaidReportMessage
from app.modules.prepaid_reports.models import PrepaidReport, PrepaidReportRow
from app.modules.prepaid_reports.repository import PrepaidReportRepository
from app.modules.prepaid_reports.schemas import (
    PrepaidDistributionItem,
    PrepaidReportRequest,
    PrepaidReportResponse,
    PrepaidReportRowResponse,
    PrepaidReportSummary,
    PrepaidStatus,
)

ZERO = Decimal("0.00")


class PrepaidReportService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = PrepaidReportRepository(session)

    async def check_association(self, account, association_id: str) -> None:
        if not await self.repository.association_exists(association_id):
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                PrepaidReportMessage.ASSOCIATION_NOT_FOUND,
            )
        scoped = await self.repository.scoped_associations(
            account.id,
            account.role.code,
            account.user_id,
        )
        if scoped is not None and association_id not in scoped:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                PrepaidReportMessage.UNAUTHORIZED_ASSOCIATION,
            )

    @staticmethod
    def totals(rows) -> tuple[Decimal, Decimal, Decimal]:
        prepaid = sum((Decimal(row.prepaid_amount) for row in rows), ZERO)
        used = sum((Decimal(row.used_amount) for row in rows), ZERO)
        return prepaid, used, prepaid - used

    @staticmethod
    def derive_status(expiry_date: date, available: Decimal, today: date) -> PrepaidStatus:
        if expiry_date < today or available <= ZERO:
            return PrepaidStatus.EXPIRED
        return PrepaidStatus.ACTIVE

    @staticmethod
    def build_rows(report_id: str, requests) -> list[PrepaidReportRow]:
        return [
            PrepaidReportRow(
                id=str(uuid.uuid4()),
                prepaid_report_id=report_id,
                member_name=item.member_name.strip(),
                unit_number=item.unit_number.strip(),
                block=item.block.strip() if item.block and item.block.strip() else None,
                category=item.category.strip(),
                prepaid_amount=item.prepaid_amount,
                used_amount=item.used_amount,
                expiry_date=item.expiry_date,
                sort_order=index,
            )
            for index, item in enumerate(requests)
        ]

    async def create(self, account, payload: PrepaidReportRequest) -> PrepaidReport:
        await self.check_association(account, payload.association_id)
        if await self.repository.duplicate_period(
            payload.association_id,
            payload.fiscal_period,
        ):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                PrepaidReportMessage.DUPLICATE_PERIOD,
            )

        report_id = str(uuid.uuid4())
        prepaid, used, available = self.totals(payload.rows)
        report = PrepaidReport(
            id=report_id,
            association_id=payload.association_id,
            fiscal_period=payload.fiscal_period.strip(),
            total_prepaid_amount=prepaid,
            total_used_amount=used,
            total_available_balance=available,
            created_by=account.id,
            updated_by=account.id,
            rows=self.build_rows(report_id, payload.rows),
        )
        self.repository.add(report)
        await self.repository.session.flush()
        return report

    async def update(
        self,
        account,
        report_id: str,
        payload: PrepaidReportRequest,
    ) -> PrepaidReport:
        report = await self.repository.get_by_id(report_id)
        if not report:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                PrepaidReportMessage.NOT_FOUND,
            )
        await self.check_association(account, report.association_id)
        if payload.association_id != report.association_id:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "A Prepaid Report cannot be moved to another association",
            )
        if await self.repository.duplicate_period(
            payload.association_id,
            payload.fiscal_period,
            excluding_id=report.id,
        ):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                PrepaidReportMessage.DUPLICATE_PERIOD,
            )

        prepaid, used, available = self.totals(payload.rows)
        report.fiscal_period = payload.fiscal_period.strip()
        report.total_prepaid_amount = prepaid
        report.total_used_amount = used
        report.total_available_balance = available
        report.updated_by = account.id
        await self.repository.replace_rows(
            report,
            self.build_rows(report.id, payload.rows),
        )
        await self.repository.session.flush()
        return report

    async def get(
        self,
        account,
        association_id: str,
        fiscal_period: str | None,
    ) -> PrepaidReport | None:
        await self.check_association(account, association_id)
        return await self.repository.get_by_period(association_id, fiscal_period)

    async def periods(self, account, association_id: str) -> list[str]:
        await self.check_association(account, association_id)
        return await self.repository.list_periods(association_id)

    @staticmethod
    def distribution(
        rows: list[PrepaidReportRowResponse],
        attribute: str,
        total: Decimal,
    ) -> list[PrepaidDistributionItem]:
        amounts: dict[str, Decimal] = defaultdict(lambda: ZERO)
        counts: dict[str, int] = defaultdict(int)
        for row in rows:
            key = str(getattr(row, attribute))
            amounts[key] += row.available_balance
            counts[key] += 1
        return [
            PrepaidDistributionItem(
                name=name,
                amount=amount,
                percentage=(amount / total * Decimal("100")).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                if total
                else ZERO,
                row_count=counts[name],
            )
            for name, amount in sorted(amounts.items())
        ]

    async def serialize(
        self,
        report: PrepaidReport,
        block: str | None = None,
        today: date | None = None,
    ) -> PrepaidReportResponse:
        effective_today = today or date.today()
        available_blocks = sorted({row.block for row in report.rows if row.block})
        selected_rows = [row for row in report.rows if not block or row.block == block]
        rows: list[PrepaidReportRowResponse] = []
        for row in selected_rows:
            available = Decimal(row.prepaid_amount) - Decimal(row.used_amount)
            rows.append(
                PrepaidReportRowResponse(
                    id=row.id,
                    member_name=row.member_name,
                    unit_number=row.unit_number,
                    block=row.block,
                    category=row.category,
                    prepaid_amount=row.prepaid_amount,
                    used_amount=row.used_amount,
                    available_balance=available,
                    expiry_date=row.expiry_date,
                    status=self.derive_status(row.expiry_date, available, effective_today),
                )
            )

        prepaid, used, available = self.totals(rows)
        active_count = sum(row.status == PrepaidStatus.ACTIVE for row in rows)
        expired_count = len(rows) - active_count
        summary = PrepaidReportSummary(
            total_prepaid_amount=prepaid,
            total_used_amount=used,
            total_available_balance=available,
            member_count=len(rows),
            average_prepaid_amount=(prepaid / len(rows)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if rows
            else ZERO,
            utilization_pct=(used / prepaid * Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if prepaid
            else ZERO,
            active_count=active_count,
            expired_count=expired_count,
        )
        category_distribution = self.distribution(rows, "category", available)
        status_distribution = self.distribution(rows, "status", available)
        expiring_soon = sum(
            row.status == PrepaidStatus.ACTIVE
            and effective_today <= row.expiry_date <= effective_today + timedelta(days=30)
            for row in rows
        )
        top_category = max(category_distribution, key=lambda item: item.amount, default=None)
        insights = [
            f"{summary.utilization_pct}% of prepaid funds have been used in this view.",
            f"{active_count} active and {expired_count} expired prepaid balances are shown.",
        ]
        if expiring_soon:
            insights.append(f"{expiring_soon} active balance(s) expire within 30 days.")
        if top_category:
            insights.append(
                f"{top_category.name} has the largest available balance at "
                f"{top_category.percentage}%."
            )

        return PrepaidReportResponse(
            id=report.id,
            association_id=report.association_id,
            association_name=report.association.name,
            fiscal_period=report.fiscal_period,
            applied_block=block,
            available_blocks=available_blocks,
            rows=rows,
            summary=summary,
            category_distribution=category_distribution,
            status_distribution=status_distribution,
            insights=insights,
            created_at=report.created_at,
            updated_at=report.updated_at,
        )
