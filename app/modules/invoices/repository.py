from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.invoices.models import Invoice
from app.modules.invoices.schemas import InvoiceStatus
from app.modules.vendors.models import Vendor


class InvoiceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def base_query():
        return (
            select(Invoice)
            .options(selectinload(Invoice.lines))
            .where(Invoice.is_deleted.is_(False))
        )

    async def list_filtered(
        self,
        association_id: str,
        vendor_id: str | None,
        status_filter: InvoiceStatus | None,
        period_start: date | None,
        period_end: date | None,
        search: str | None,
    ) -> list[Invoice]:
        query = self.base_query().where(Invoice.association_id == association_id)
        if vendor_id:
            query = query.where(Invoice.vendor_id == vendor_id)
        if status_filter:
            query = query.where(Invoice.status == status_filter.value)
        if period_start and period_end:
            query = query.where(
                Invoice.issue_date >= period_start, Invoice.issue_date <= period_end
            )
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            query = query.join(Invoice.vendor).where(
                or_(Invoice.invoice_number.ilike(pattern), Vendor.name.ilike(pattern))
            )
        query = query.order_by(Invoice.issue_date.desc(), Invoice.created_at.desc())
        return list((await self.session.scalars(query)).unique().all())

    async def get_scoped(self, invoice_id: str, association_id: str) -> Invoice | None:
        return await self.session.scalar(
            self.base_query().where(
                Invoice.id == invoice_id, Invoice.association_id == association_id
            )
        )

    async def number_exists(
        self, association_id: str, invoice_number: str, excluding_id: str | None = None
    ) -> bool:
        query = select(Invoice.id).where(
            Invoice.association_id == association_id,
            func.lower(Invoice.invoice_number) == invoice_number.strip().lower(),
        )
        if excluding_id:
            query = query.where(Invoice.id != excluding_id)
        return await self.session.scalar(query) is not None

    async def fiscal_periods(self, association_id: str) -> list[str]:
        dates = list(
            (
                await self.session.scalars(
                    select(Invoice.issue_date)
                    .where(Invoice.association_id == association_id, Invoice.is_deleted.is_(False))
                    .distinct()
                    .order_by(Invoice.issue_date.desc())
                )
            ).all()
        )
        return list(dict.fromkeys(value.strftime("%Y-%m") for value in dates))

    def add(self, invoice: Invoice) -> None:
        self.session.add(invoice)
