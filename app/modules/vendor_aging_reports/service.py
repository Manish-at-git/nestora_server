import uuid
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.vendor_aging_reports.messages import VendorAgingReportMessage
from app.modules.vendor_aging_reports.models import VendorAgingReport, VendorAgingRow
from app.modules.vendor_aging_reports.repository import VendorAgingReportRepository
from app.modules.vendor_aging_reports.schemas import (
    VendorAgingDistributionItem,
    VendorAgingReportRequest,
    VendorAgingReportResponse,
    VendorAgingRowResponse,
    VendorAgingStatus,
    VendorAgingSummary,
)

ZERO = Decimal("0.00")
BUCKETS = (
    ("Current", "current_due"),
    ("1-30 days", "days_1_30"),
    ("31-60 days", "days_31_60"),
    ("61-90 days", "days_61_90"),
    ("> 90 days", "days_over_90"),
)


class VendorAgingReportService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = VendorAgingReportRepository(session)

    async def check_association(self, account, association_id: str) -> None:
        if not await self.repository.association_exists(association_id):
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                VendorAgingReportMessage.ASSOCIATION_NOT_FOUND,
            )
        scoped = await self.repository.scoped_associations(
            account.id,
            account.role.code,
            account.user_id,
        )
        if scoped is not None and association_id not in scoped:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                VendorAgingReportMessage.UNAUTHORIZED_ASSOCIATION,
            )

    @staticmethod
    def row_amounts(row) -> tuple[Decimal, Decimal, Decimal]:
        current = Decimal(row.current_due)
        overdue = sum(
            (
                Decimal(row.days_1_30),
                Decimal(row.days_31_60),
                Decimal(row.days_61_90),
                Decimal(row.days_over_90),
            ),
            ZERO,
        )
        return current + overdue, overdue, current

    @classmethod
    def totals(cls, rows) -> tuple[Decimal, Decimal, Decimal]:
        outstanding = ZERO
        overdue = ZERO
        current = ZERO
        for row in rows:
            row_total, row_overdue, row_current = cls.row_amounts(row)
            outstanding += row_total
            overdue += row_overdue
            current += row_current
        return outstanding, overdue, current

    @staticmethod
    def derive_status(total: Decimal, overdue: Decimal) -> VendorAgingStatus:
        if total <= ZERO:
            return VendorAgingStatus.SETTLED
        if overdue > ZERO:
            return VendorAgingStatus.OVERDUE
        return VendorAgingStatus.DUE_SOON

    @staticmethod
    def build_rows(report_id: str, requests) -> list[VendorAgingRow]:
        return [
            VendorAgingRow(
                id=str(uuid.uuid4()),
                vendor_aging_report_id=report_id,
                vendor_name=item.vendor_name,
                category=item.category,
                invoice_number=item.invoice_number,
                invoice_date=item.invoice_date,
                current_due=item.current_due,
                days_1_30=item.days_1_30,
                days_31_60=item.days_31_60,
                days_61_90=item.days_61_90,
                days_over_90=item.days_over_90,
                sort_order=index,
            )
            for index, item in enumerate(requests)
        ]

    async def create(self, account, payload: VendorAgingReportRequest) -> VendorAgingReport:
        await self.check_association(account, payload.association_id)
        if await self.repository.duplicate_period(
            payload.association_id,
            payload.fiscal_period,
        ):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                VendorAgingReportMessage.DUPLICATE_PERIOD,
            )
        report_id = str(uuid.uuid4())
        outstanding, overdue, current = self.totals(payload.rows)
        report = VendorAgingReport(
            id=report_id,
            association_id=payload.association_id,
            fiscal_period=payload.fiscal_period,
            total_outstanding=outstanding,
            overdue_amount=overdue,
            current_amount=current,
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
        payload: VendorAgingReportRequest,
    ) -> VendorAgingReport:
        report = await self.repository.get_by_id(report_id)
        if not report:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                VendorAgingReportMessage.NOT_FOUND,
            )
        await self.check_association(account, report.association_id)
        if payload.association_id != report.association_id:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "A Vendor Aging Report cannot be moved to another association",
            )
        if await self.repository.duplicate_period(
            payload.association_id,
            payload.fiscal_period,
            excluding_id=report.id,
        ):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                VendorAgingReportMessage.DUPLICATE_PERIOD,
            )
        outstanding, overdue, current = self.totals(payload.rows)
        report.fiscal_period = payload.fiscal_period
        report.total_outstanding = outstanding
        report.overdue_amount = overdue
        report.current_amount = current
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
    ) -> VendorAgingReport | None:
        await self.check_association(account, association_id)
        return await self.repository.get_by_period(association_id, fiscal_period)

    async def periods(self, account, association_id: str) -> list[str]:
        await self.check_association(account, association_id)
        return await self.repository.list_periods(association_id)

    @staticmethod
    def distribution_item(
        name: str,
        amount: Decimal,
        total: Decimal,
        invoice_count: int,
    ) -> VendorAgingDistributionItem:
        return VendorAgingDistributionItem(
            name=name,
            amount=amount,
            percentage=(amount / total * Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if total
            else ZERO,
            invoice_count=invoice_count,
        )

    async def serialize(
        self,
        report: VendorAgingReport,
        category: str | None = None,
        search: str | None = None,
    ) -> VendorAgingReportResponse:
        available_categories = sorted({row.category for row in report.rows})
        normalized_search = search.strip().casefold() if search and search.strip() else None
        selected_rows = [
            row
            for row in report.rows
            if (not category or row.category.casefold() == category.casefold())
            and (
                not normalized_search
                or normalized_search in row.vendor_name.casefold()
                or normalized_search in row.category.casefold()
                or normalized_search in row.invoice_number.casefold()
            )
        ]

        rows: list[VendorAgingRowResponse] = []
        for row in selected_rows:
            total, overdue, _current = self.row_amounts(row)
            rows.append(
                VendorAgingRowResponse(
                    id=row.id,
                    vendor_name=row.vendor_name,
                    category=row.category,
                    invoice_number=row.invoice_number,
                    invoice_date=row.invoice_date,
                    current_due=row.current_due,
                    days_1_30=row.days_1_30,
                    days_31_60=row.days_31_60,
                    days_61_90=row.days_61_90,
                    days_over_90=row.days_over_90,
                    total_outstanding=total,
                    overdue_amount=overdue,
                    status=self.derive_status(total, overdue),
                )
            )

        outstanding, overdue, current = self.totals(rows)
        overdue_invoice_count = sum(row.status == VendorAgingStatus.OVERDUE for row in rows)
        summary = VendorAgingSummary(
            vendor_count=len({row.vendor_name.casefold() for row in rows}),
            invoice_count=len(rows),
            total_outstanding=outstanding,
            overdue_amount=overdue,
            current_amount=current,
            overdue_percentage=(overdue / outstanding * Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if outstanding
            else ZERO,
            overdue_invoice_count=overdue_invoice_count,
        )

        aging_distribution = []
        for label, attribute in BUCKETS:
            amount = sum((Decimal(getattr(row, attribute)) for row in rows), ZERO)
            count = sum(Decimal(getattr(row, attribute)) > ZERO for row in rows)
            aging_distribution.append(
                self.distribution_item(label, amount, outstanding, count)
            )

        category_amounts: dict[str, Decimal] = defaultdict(lambda: ZERO)
        category_counts: dict[str, int] = defaultdict(int)
        for row in rows:
            category_amounts[row.category] += row.total_outstanding
            category_counts[row.category] += 1
        category_distribution = [
            self.distribution_item(
                name,
                amount,
                outstanding,
                category_counts[name],
            )
            for name, amount in sorted(category_amounts.items())
        ]

        top_vendor = max(rows, key=lambda row: row.total_outstanding, default=None)
        over_90 = sum((Decimal(row.days_over_90) for row in rows), ZERO)
        over_90_percentage = (
            (over_90 / outstanding * Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if outstanding
            else ZERO
        )
        insights = [
            f"{summary.overdue_percentage}% of outstanding invoices are overdue.",
            f"{over_90_percentage}% of outstanding value is more than 90 days old.",
            f"{overdue_invoice_count} of {summary.invoice_count} invoice(s) have overdue balances.",
        ]
        if top_vendor:
            insights.append(
                f"{top_vendor.vendor_name} has the largest outstanding balance at "
                f"{top_vendor.total_outstanding:.2f}."
            )

        return VendorAgingReportResponse(
            id=report.id,
            association_id=report.association_id,
            association_name=report.association.name,
            fiscal_period=report.fiscal_period,
            applied_category=category,
            applied_search=search.strip() if search and search.strip() else None,
            available_categories=available_categories,
            rows=rows,
            summary=summary,
            aging_distribution=aging_distribution,
            category_distribution=category_distribution,
            insights=insights,
            created_at=report.created_at,
            updated_at=report.updated_at,
        )
