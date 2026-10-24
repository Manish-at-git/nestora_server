import uuid
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.delinquency_reports.messages import DelinquencyReportMessage
from app.modules.delinquency_reports.models import (
    DelinquencyReport,
    DelinquencyReportRow,
)
from app.modules.delinquency_reports.repository import DelinquencyReportRepository
from app.modules.delinquency_reports.schemas import (
    DelinquencyDistributionItem,
    DelinquencyReportRequest,
    DelinquencyReportResponse,
    DelinquencyRowResponse,
    DelinquencyStatus,
    DelinquencySummary,
)

ZERO = Decimal("0.00")
ONE_HUNDRED = Decimal("100")
AGING_BUCKETS = (
    ("0 days", 0, 0),
    ("1-30 days", 1, 30),
    ("31-60 days", 31, 60),
    ("61-90 days", 61, 90),
    ("> 90 days", 91, None),
)


class DelinquencyReportService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = DelinquencyReportRepository(session)

    async def check_association(self, account, association_id: str) -> None:
        if not await self.repository.association_exists(association_id):
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                DelinquencyReportMessage.ASSOCIATION_NOT_FOUND,
            )
        scoped = await self.repository.scoped_associations(
            account.id,
            account.role.code,
            account.user_id,
        )
        if scoped is not None and association_id not in scoped:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                DelinquencyReportMessage.UNAUTHORIZED_ASSOCIATION,
            )

    @staticmethod
    def derive_status(
        outstanding_amount: Decimal,
        days_overdue: int,
    ) -> DelinquencyStatus:
        if outstanding_amount <= ZERO:
            return DelinquencyStatus.RESOLVED
        if days_overdue >= 75:
            return DelinquencyStatus.HIGH
        if days_overdue >= 45:
            return DelinquencyStatus.MEDIUM
        return DelinquencyStatus.LOW

    @staticmethod
    def total_outstanding(rows) -> Decimal:
        return sum((Decimal(row.outstanding_amount) for row in rows), ZERO)

    @staticmethod
    def build_rows(report_id: str, requests) -> list[DelinquencyReportRow]:
        return [
            DelinquencyReportRow(
                id=str(uuid.uuid4()),
                delinquency_report_id=report_id,
                member_name=item.member_name,
                unit_number=item.unit_number,
                block=item.block,
                charge_category=item.charge_category,
                outstanding_amount=item.outstanding_amount,
                days_overdue=item.days_overdue,
                last_payment_date=item.last_payment_date,
                sort_order=index,
            )
            for index, item in enumerate(requests)
        ]

    async def create(
        self,
        account,
        payload: DelinquencyReportRequest,
    ) -> DelinquencyReport:
        await self.check_association(account, payload.association_id)
        if await self.repository.duplicate_period(
            payload.association_id,
            payload.fiscal_period,
        ):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                DelinquencyReportMessage.DUPLICATE_PERIOD,
            )
        report_id = str(uuid.uuid4())
        report = DelinquencyReport(
            id=report_id,
            association_id=payload.association_id,
            fiscal_period=payload.fiscal_period,
            total_billed_amount=payload.total_billed_amount,
            total_collected_amount=payload.total_collected_amount,
            total_outstanding=self.total_outstanding(payload.rows),
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
        payload: DelinquencyReportRequest,
    ) -> DelinquencyReport:
        report = await self.repository.get_by_id(report_id)
        if not report:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                DelinquencyReportMessage.NOT_FOUND,
            )
        await self.check_association(account, report.association_id)
        if payload.association_id != report.association_id:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "A Delinquency Report cannot be moved to another association",
            )
        if await self.repository.duplicate_period(
            payload.association_id,
            payload.fiscal_period,
            excluding_id=report.id,
        ):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                DelinquencyReportMessage.DUPLICATE_PERIOD,
            )
        report.fiscal_period = payload.fiscal_period
        report.total_billed_amount = payload.total_billed_amount
        report.total_collected_amount = payload.total_collected_amount
        report.total_outstanding = self.total_outstanding(payload.rows)
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
    ) -> DelinquencyReport | None:
        await self.check_association(account, association_id)
        return await self.repository.get_by_period(association_id, fiscal_period)

    async def periods(self, account, association_id: str) -> list[str]:
        await self.check_association(account, association_id)
        return await self.repository.list_periods(association_id)

    @staticmethod
    def percentage(amount: Decimal, total: Decimal) -> Decimal:
        if not total:
            return ZERO
        return (amount / total * ONE_HUNDRED).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

    @classmethod
    def distribution_item(
        cls,
        name: str,
        amount: Decimal,
        total: Decimal,
        row_count: int,
    ) -> DelinquencyDistributionItem:
        return DelinquencyDistributionItem(
            name=name,
            amount=amount,
            percentage=cls.percentage(amount, total),
            row_count=row_count,
        )

    async def serialize(
        self,
        report: DelinquencyReport,
        block: str | None = None,
        search: str | None = None,
    ) -> DelinquencyReportResponse:
        available_blocks = sorted({row.block for row in report.rows if row.block})
        normalized_search = search.strip().casefold() if search and search.strip() else None
        selected = [
            row
            for row in report.rows
            if (not block or (row.block and row.block.casefold() == block.casefold()))
            and (
                not normalized_search
                or normalized_search in row.member_name.casefold()
                or normalized_search in row.unit_number.casefold()
                or normalized_search in row.charge_category.casefold()
            )
        ]
        rows = [
            DelinquencyRowResponse(
                id=row.id,
                member_name=row.member_name,
                unit_number=row.unit_number,
                block=row.block,
                charge_category=row.charge_category,
                outstanding_amount=row.outstanding_amount,
                days_overdue=row.days_overdue,
                last_payment_date=row.last_payment_date,
                status=self.derive_status(
                    Decimal(row.outstanding_amount),
                    row.days_overdue,
                ),
            )
            for row in selected
        ]
        total = self.total_outstanding(rows)
        member_count = len(
            {(row.member_name.casefold(), row.unit_number.casefold()) for row in rows}
        )
        average_days = (
            (sum(row.days_overdue for row in rows) / Decimal(len(rows))).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if rows
            else ZERO
        )
        billed = Decimal(report.total_billed_amount)
        collected = Decimal(report.total_collected_amount)
        summary = DelinquencySummary(
            total_outstanding=total,
            delinquent_member_count=member_count,
            row_count=len(rows),
            average_days_overdue=average_days,
            high_risk_count=sum(row.status == DelinquencyStatus.HIGH for row in rows),
            total_billed_amount=billed,
            total_collected_amount=collected,
            collection_rate_percentage=self.percentage(collected, billed),
        )

        charge_amounts: dict[str, Decimal] = defaultdict(lambda: ZERO)
        charge_counts: dict[str, int] = defaultdict(int)
        for row in rows:
            charge_amounts[row.charge_category] += row.outstanding_amount
            charge_counts[row.charge_category] += 1
        charge_distribution = [
            self.distribution_item(name, amount, total, charge_counts[name])
            for name, amount in sorted(charge_amounts.items())
        ]

        aging_distribution = []
        for label, start, end in AGING_BUCKETS:
            bucket = [
                row
                for row in rows
                if row.days_overdue >= start
                and (end is None or row.days_overdue <= end)
            ]
            amount = sum((row.outstanding_amount for row in bucket), ZERO)
            aging_distribution.append(
                self.distribution_item(label, amount, total, len(bucket))
            )

        insights: list[str] = []
        if rows:
            insights.append(
                f"{summary.high_risk_count} of {summary.row_count} delinquency rows "
                "are high risk (75 or more days overdue)."
            )
            largest = max(charge_distribution, key=lambda item: item.amount)
            insights.append(
                f"{largest.name} represents {largest.percentage}% of the filtered "
                "outstanding balance."
            )
            insights.append(
                f"The filtered average age is {summary.average_days_overdue} days overdue."
            )

        return DelinquencyReportResponse(
            id=report.id,
            association_id=report.association_id,
            association_name=report.association.name,
            fiscal_period=report.fiscal_period,
            applied_block=block,
            applied_search=search.strip() if search and search.strip() else None,
            available_blocks=available_blocks,
            rows=rows,
            summary=summary,
            charge_distribution=charge_distribution,
            aging_distribution=aging_distribution,
            insights=insights,
            created_at=report.created_at,
            updated_at=report.updated_at,
        )
