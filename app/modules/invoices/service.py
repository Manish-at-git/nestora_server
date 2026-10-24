from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode
from app.modules.associations.models import Association
from app.modules.invoices.models import Invoice
from app.modules.invoices.schemas import InvoiceListResponse, InvoiceResponse, InvoiceStatus

ZERO = Decimal("0.00")


class InvoiceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def check_association(self, account, association_id: str) -> None:
        exists = await self.session.scalar(select(Association.id).where(Association.id == association_id, Association.is_deleted.is_(False)))
        if not exists:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Association not found")
        if account.role.code == RoleCode.SUPER_ADMIN.value:
            return
        admin_associations = list((await self.session.scalars(text("SELECT association_id FROM admin_associations WHERE admin_id=:account_id"), {"account_id": account.id})).all())
        if not admin_associations and account.user_id:
            member_association = await self.session.scalar(text("SELECT association_id FROM user_details WHERE user_id=:user_id AND is_deleted=0 LIMIT 1"), {"user_id": account.user_id})
            admin_associations = [member_association] if member_association else []
        if association_id not in admin_associations:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You are not authorized for this association")

    @staticmethod
    def total(invoice: Invoice) -> Decimal:
        return Decimal(invoice.subtotal) + Decimal(invoice.tax_amount)

    @classmethod
    def serialize(cls, invoice: Invoice) -> InvoiceResponse:
        return InvoiceResponse(
            id=invoice.id, association_id=invoice.association_id,
            association_name=invoice.association.name, invoice_number=invoice.invoice_number,
            vendor_name=invoice.vendor_name, category=invoice.category,
            description=invoice.description, invoice_date=invoice.invoice_date, due_date=invoice.due_date,
            subtotal=invoice.subtotal, tax_percentage=invoice.tax_percentage, tax_amount=invoice.tax_amount,
            total_amount=cls.total(invoice), status=InvoiceStatus(invoice.status),
            payment_date=invoice.payment_date, payment_method=invoice.payment_method,
            created_at=invoice.created_at, updated_at=invoice.updated_at,
        )

    async def list(self, account, association_id: str, category: str | None, status_filter: InvoiceStatus | None, search: str | None) -> InvoiceListResponse:
        await self.check_association(account, association_id)
        query = select(Invoice).where(Invoice.association_id == association_id).order_by(Invoice.invoice_date.desc(), Invoice.created_at.desc())
        if category:
            query = query.where(Invoice.category == category)
        if status_filter:
            query = query.where(Invoice.status == status_filter.value)
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            query = query.where(Invoice.vendor_name.ilike(pattern) | Invoice.invoice_number.ilike(pattern))
        invoices = list((await self.session.scalars(query)).all())
        categories = list((await self.session.scalars(select(Invoice.category).where(Invoice.association_id == association_id).distinct().order_by(Invoice.category))).all())
        rows = [self.serialize(invoice) for invoice in invoices]
        total = sum((row.total_amount for row in rows), ZERO)
        return InvoiceListResponse(rows=rows, total_count=len(rows), total_amount=total,
            paid_amount=sum((row.total_amount for row in rows if row.status == InvoiceStatus.PAID), ZERO),
            pending_amount=sum((row.total_amount for row in rows if row.status == InvoiceStatus.PENDING), ZERO),
            overdue_amount=sum((row.total_amount for row in rows if row.status == InvoiceStatus.OVERDUE), ZERO),
            available_categories=categories)
