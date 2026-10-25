import uuid
from calendar import monthrange
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode
from app.modules.associations.models import Association
from app.modules.invoices.models import Invoice, InvoiceLine
from app.modules.invoices.repository import InvoiceRepository
from app.modules.invoices.schemas import (
    DiscountType,
    InvoiceLineResponse,
    InvoiceListResponse,
    InvoicePaymentAccountResponse,
    InvoiceRequest,
    InvoiceResponse,
    InvoiceStatus,
    InvoiceStatusRequest,
    InvoiceVendorResponse,
)
from app.modules.vendors.models import Vendor

CENT = Decimal("0.01")
ZERO = Decimal("0.00")
STATUS_TRANSITIONS = {
    InvoiceStatus.PENDING: {InvoiceStatus.OVERDUE, InvoiceStatus.PAID, InvoiceStatus.CANCELLED},
    InvoiceStatus.OVERDUE: {InvoiceStatus.PAID, InvoiceStatus.CANCELLED},
    InvoiceStatus.PAID: set(),
    InvoiceStatus.CANCELLED: set(),
}


class InvoiceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = InvoiceRepository(session)

    async def check_association(self, account, association_id: str) -> Association:
        association = await self.session.scalar(
            select(Association).where(
                Association.id == association_id, Association.is_deleted.is_(False)
            )
        )
        if not association:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Association not found")
        if account.role.code == RoleCode.SUPER_ADMIN.value:
            return association
        association_ids = list(
            (
                await self.session.scalars(
                    text(
                        "SELECT association_id FROM admin_associations WHERE admin_id=:account_id"
                    ),
                    {"account_id": account.id},
                )
            ).all()
        )
        if not association_ids and account.user_id:
            member_association = await self.session.scalar(
                text(
                    "SELECT association_id FROM user_details "
                    "WHERE user_id=:user_id AND is_deleted=0 LIMIT 1"
                ),
                {"user_id": account.user_id},
            )
            association_ids = [member_association] if member_association else []
        if association_id not in association_ids:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "You are not authorized for this association"
            )
        return association

    async def eligible_vendors(self, account, association_id: str) -> list[InvoiceVendorResponse]:
        await self.check_association(account, association_id)
        vendors = list(
            (
                await self.session.scalars(
                    select(Vendor)
                    .where(Vendor.is_deleted.is_(False), Vendor.status == "Active")
                    .order_by(Vendor.name)
                )
            ).all()
        )
        return [
            InvoiceVendorResponse(
                id=item.id,
                name=item.name,
                service_type=item.service_type,
                payment_terms=item.payment_terms,
                payment_account=self.vendor_payment_account(item),
            )
            for item in vendors
        ]

    async def require_vendor(self, vendor_id: str) -> Vendor:
        vendor = await self.session.scalar(
            select(Vendor).where(
                Vendor.id == vendor_id, Vendor.is_deleted.is_(False), Vendor.status == "Active"
            )
        )
        if not vendor:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Select an active vendor")
        return vendor

    @staticmethod
    def period_bounds(fiscal_period: str | None) -> tuple[date | None, date | None]:
        if not fiscal_period:
            return None, None
        try:
            year_text, month_text = fiscal_period.split("-", maxsplit=1)
            year, month = int(year_text), int(month_text)
            start = date(year, month, 1)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "Fiscal period must use YYYY-MM format"
            ) from exc
        return start, date(year, month, monthrange(year, month)[1])

    @staticmethod
    def money(value: Decimal) -> Decimal:
        return value.quantize(CENT, rounding=ROUND_HALF_UP)

    @staticmethod
    def vendor_payment_account(vendor: Vendor | None) -> InvoicePaymentAccountResponse | None:
        if not vendor or not all(
            [vendor.bank_name, vendor.bank_account_number, vendor.bank_ifsc_code]
        ):
            return None
        return InvoicePaymentAccountResponse(
            bank_name=vendor.bank_name,
            account_number=vendor.bank_account_number,
            ifsc_code=vendor.bank_ifsc_code,
        )

    @classmethod
    def calculate(cls, payload: InvoiceRequest) -> tuple[Decimal, Decimal, Decimal, Decimal]:
        subtotal = cls.money(sum((line.quantity * line.rate for line in payload.lines), ZERO))
        if payload.discount_type == DiscountType.PERCENTAGE:
            discount = cls.money(subtotal * payload.discount_value / Decimal("100"))
        elif payload.discount_type == DiscountType.FLAT:
            discount = cls.money(payload.discount_value)
        else:
            discount = ZERO
        if discount > subtotal:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "Discount cannot exceed the invoice subtotal"
            )
        taxable = subtotal - discount
        tax = cls.money(taxable * payload.tax_rate / Decimal("100"))
        return subtotal, discount, tax, cls.money(taxable + tax)

    @classmethod
    def build_lines(
        cls, invoice_id: str, payload: InvoiceRequest, account_id: str
    ) -> list[InvoiceLine]:
        return [
            InvoiceLine(
                id=str(uuid.uuid4()),
                invoice_id=invoice_id,
                description=line.description,
                quantity=line.quantity,
                rate=line.rate,
                amount=cls.money(line.quantity * line.rate),
                sort_order=index,
                created_by=account_id,
                updated_by=account_id,
            )
            for index, line in enumerate(payload.lines)
        ]

    @staticmethod
    def validate_transition(current: InvoiceStatus, target: InvoiceStatus) -> None:
        if current != target and target not in STATUS_TRANSITIONS[current]:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"Invoice status cannot change from {current.value} to {target.value}",
            )

    @classmethod
    def serialize(cls, invoice: Invoice) -> InvoiceResponse:
        return InvoiceResponse(
            id=invoice.id,
            association_id=invoice.association_id,
            association_name=invoice.association.name,
            vendor_id=invoice.vendor_id,
            vendor_name=invoice.vendor.name if invoice.vendor else invoice.legacy_vendor_name,
            vendor_service=invoice.vendor.service_type
            if invoice.vendor
            else invoice.legacy_category,
            payment_account=cls.vendor_payment_account(invoice.vendor),
            billing_address=invoice.billing_address,
            invoice_number=invoice.invoice_number,
            issue_date=invoice.issue_date,
            due_date=invoice.due_date,
            fiscal_period=invoice.issue_date.strftime("%Y-%m"),
            payment_terms=invoice.payment_terms,
            lines=[
                InvoiceLineResponse(
                    id=line.id,
                    description=line.description,
                    quantity=line.quantity,
                    rate=line.rate,
                    amount=line.amount,
                    sort_order=line.sort_order,
                )
                for line in invoice.lines
            ],
            discount_type=invoice.discount_type,
            discount_value=invoice.discount_value,
            tax_type=invoice.tax_type,
            tax_rate=invoice.tax_rate,
            notes=invoice.notes,
            subtotal=invoice.subtotal,
            discount_amount=invoice.discount_amount,
            tax_amount=invoice.tax_amount,
            grand_total=invoice.grand_total,
            status=invoice.status,
            payment_date=invoice.payment_date,
            payment_method=invoice.payment_method,
            created_at=invoice.created_at,
            updated_at=invoice.updated_at,
        )

    async def list(
        self,
        account,
        association_id: str,
        vendor_id: str | None,
        status_filter: InvoiceStatus | None,
        fiscal_period: str | None,
        search: str | None,
        page: int,
        page_size: int,
    ) -> InvoiceListResponse:
        await self.check_association(account, association_id)
        period_start, period_end = self.period_bounds(fiscal_period)
        invoices = await self.repository.list_filtered(
            association_id, vendor_id, status_filter, period_start, period_end, search
        )
        total_count = len(invoices)
        start = (page - 1) * page_size
        return InvoiceListResponse(
            rows=[self.serialize(item) for item in invoices[start : start + page_size]],
            total_count=total_count,
            page=page,
            page_size=page_size,
            total_pages=max(1, (total_count + page_size - 1) // page_size),
            total_amount=sum((item.grand_total for item in invoices), ZERO),
            paid_amount=sum(
                (item.grand_total for item in invoices if item.status == InvoiceStatus.PAID.value),
                ZERO,
            ),
            pending_amount=sum(
                (
                    item.grand_total
                    for item in invoices
                    if item.status == InvoiceStatus.PENDING.value
                ),
                ZERO,
            ),
            overdue_amount=sum(
                (
                    item.grand_total
                    for item in invoices
                    if item.status == InvoiceStatus.OVERDUE.value
                ),
                ZERO,
            ),
            available_fiscal_periods=await self.repository.fiscal_periods(association_id),
        )

    async def get(self, account, invoice_id: str, association_id: str) -> Invoice:
        await self.check_association(account, association_id)
        invoice = await self.repository.get_scoped(invoice_id, association_id)
        if not invoice:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Invoice not found")
        return invoice

    async def create(self, account, payload: InvoiceRequest) -> Invoice:
        association = await self.check_association(account, payload.association_id)
        vendor = await self.require_vendor(payload.vendor_id)
        payload.invoice_number = payload.invoice_number or await self.generate_invoice_number(
            payload.association_id
        )
        if await self.repository.number_exists(payload.association_id, payload.invoice_number):
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Invoice number already exists for this association"
            )
        totals = self.calculate(payload)
        invoice = Invoice(
            id=str(uuid.uuid4()), association_id=payload.association_id, created_by=account.id
        )
        invoice.association = association
        invoice.vendor = vendor
        self.apply_payload(invoice, payload, account.id, *totals)
        self.repository.add(invoice)
        await self.session.flush()
        # Server defaults such as created_at are not guaranteed to be populated
        # by MySQL on flush. Load them while still in the async session so the
        # response serializer never triggers implicit I/O after commit.
        await self.session.refresh(invoice, attribute_names=["created_at", "updated_at"])
        return invoice

    async def update(self, account, invoice_id: str, payload: InvoiceRequest) -> Invoice:
        invoice = await self.get(account, invoice_id, payload.association_id)
        payload.invoice_number = payload.invoice_number or invoice.invoice_number
        self.validate_transition(InvoiceStatus(invoice.status), payload.status)
        vendor = await self.require_vendor(payload.vendor_id)
        if await self.repository.number_exists(
            payload.association_id, payload.invoice_number, invoice.id
        ):
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Invoice number already exists for this association"
            )
        invoice.vendor = vendor
        self.apply_payload(invoice, payload, account.id, *self.calculate(payload))
        await self.session.flush()
        await self.session.refresh(invoice, attribute_names=["created_at", "updated_at"])
        return invoice

    async def generate_invoice_number(self, association_id: str) -> str:
        """Create a readable, association-scoped number; the unique index remains authoritative."""
        year_month = date.today().strftime("%Y%m")
        existing_count = await self.session.scalar(
            select(func.count())
            .select_from(Invoice)
            .where(Invoice.association_id == association_id)
        )
        sequence = int(existing_count or 0) + 1
        while True:
            candidate = f"INV-{year_month}-{sequence:04d}"
            if not await self.repository.number_exists(association_id, candidate):
                return candidate
            sequence += 1

    def apply_payload(
        self,
        invoice: Invoice,
        payload: InvoiceRequest,
        account_id: str,
        subtotal: Decimal,
        discount: Decimal,
        tax: Decimal,
        grand_total: Decimal,
    ) -> None:
        invoice.vendor_id = payload.vendor_id
        invoice.legacy_vendor_name = invoice.vendor.name if invoice.vendor else ""
        invoice.legacy_category = invoice.vendor.service_type if invoice.vendor else "General"
        invoice.legacy_description = payload.notes.strip() if payload.notes else None
        invoice.invoice_date = payload.issue_date
        invoice.tax_percentage = payload.tax_rate
        invoice.invoice_number = payload.invoice_number
        invoice.billing_address = payload.billing_address
        invoice.issue_date = payload.issue_date
        invoice.due_date = payload.due_date
        invoice.payment_terms = payload.payment_terms
        invoice.discount_type = payload.discount_type.value
        invoice.discount_value = payload.discount_value
        invoice.tax_type = payload.tax_type.strip() if payload.tax_type else None
        invoice.tax_rate = payload.tax_rate
        invoice.notes = payload.notes.strip() if payload.notes else None
        invoice.status = payload.status.value
        invoice.payment_date = (
            payload.payment_date if payload.status == InvoiceStatus.PAID else None
        )
        invoice.payment_method = (
            payload.payment_method.strip()
            if payload.payment_method and payload.status == InvoiceStatus.PAID
            else None
        )
        invoice.subtotal, invoice.discount_amount, invoice.tax_amount, invoice.grand_total = (
            subtotal,
            discount,
            tax,
            grand_total,
        )
        invoice.updated_by = account_id
        invoice.lines = self.build_lines(invoice.id, payload, account_id)

    async def update_status(
        self, account, invoice_id: str, payload: InvoiceStatusRequest
    ) -> Invoice:
        invoice = await self.get(account, invoice_id, payload.association_id)
        self.validate_transition(InvoiceStatus(invoice.status), payload.status)
        if payload.payment_date and payload.payment_date < invoice.issue_date:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "Payment date cannot be before issue date"
            )
        invoice.status = payload.status.value
        invoice.payment_date = (
            payload.payment_date if payload.status == InvoiceStatus.PAID else None
        )
        invoice.payment_method = (
            payload.payment_method.strip()
            if payload.payment_method and payload.status == InvoiceStatus.PAID
            else None
        )
        invoice.updated_by = account.id
        await self.session.flush()
        await self.session.refresh(invoice, attribute_names=["created_at", "updated_at"])
        return invoice

    async def delete(self, account, invoice_id: str, association_id: str) -> Invoice:
        invoice = await self.get(account, invoice_id, association_id)
        invoice.is_deleted = True
        invoice.deleted_by = account.id
        invoice.deleted_at = datetime.now(UTC)
        invoice.updated_by = account.id
        await self.session.flush()
        return invoice
