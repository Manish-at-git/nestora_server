import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode
from app.core.dependencies import AuthContext, get_auth_context, require_csrf, require_role
from app.core.responses import ApiResponse, success_response
from app.db.session import get_db_session
from app.db.unit_of_work import UnitOfWork
from app.modules.invoices.models import Invoice
from app.modules.invoices.schemas import InvoiceListResponse, InvoiceRequest, InvoiceResponse, InvoiceStatus
from app.modules.invoices.service import InvoiceService

VIEWER_DEP = Depends(require_role(RoleCode.SUPER_ADMIN, RoleCode.ADMIN, RoleCode.ACCOUNTANT, RoleCode.HOMEOWNER, RoleCode.BOARD_MEMBER, RoleCode.COMMITTEE_MEMBER))
MANAGER_DEP = Depends(require_role(RoleCode.SUPER_ADMIN, RoleCode.ADMIN, RoleCode.ACCOUNTANT))
router = APIRouter(prefix="/invoices", tags=["Invoices"])


def apply_payload(invoice: Invoice, payload: InvoiceRequest, account) -> None:
    invoice.invoice_number = payload.invoice_number
    invoice.vendor_name = payload.vendor_name
    invoice.category = payload.category
    invoice.description = payload.description.strip() if payload.description else None
    invoice.invoice_date = payload.invoice_date
    invoice.due_date = payload.due_date
    invoice.subtotal = payload.subtotal
    invoice.tax_percentage = payload.tax_percentage
    invoice.tax_amount = payload.subtotal * payload.tax_percentage / 100
    invoice.status = payload.status.value
    invoice.payment_date = payload.payment_date
    invoice.payment_method = payload.payment_method.strip() if payload.payment_method else None
    invoice.updated_by = account.id


@router.get("", response_model=ApiResponse[InvoiceListResponse])
async def list_invoices(association_id: str, category: str | None = None, status_filter: InvoiceStatus | None = None, search: str | None = None, auth: AuthContext = VIEWER_DEP, session: AsyncSession = Depends(get_db_session)):
    return success_response(await InvoiceService(session).list(auth.account, association_id, category, status_filter, search))


@router.post("", response_model=ApiResponse[InvoiceResponse], status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_csrf)])
async def create_invoice(payload: InvoiceRequest, auth: AuthContext = MANAGER_DEP, session: AsyncSession = Depends(get_db_session)):
    service = InvoiceService(session)
    await service.check_association(auth.account, payload.association_id)
    invoice = Invoice(id=str(uuid.uuid4()), association_id=payload.association_id, created_by=auth.account.id, updated_by=auth.account.id)
    apply_payload(invoice, payload, auth.account)
    async with UnitOfWork(session):
        session.add(invoice)
        try:
            await session.flush()
        except IntegrityError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, "Invoice number already exists for this association") from exc
    invoice = await session.scalar(select(Invoice).where(Invoice.id == invoice.id))
    return success_response(service.serialize(invoice), "Invoice created")


@router.put("/{invoice_id}", response_model=ApiResponse[InvoiceResponse], dependencies=[Depends(require_csrf)])
async def update_invoice(invoice_id: str, payload: InvoiceRequest, auth: AuthContext = MANAGER_DEP, session: AsyncSession = Depends(get_db_session)):
    service = InvoiceService(session)
    invoice = await session.scalar(select(Invoice).where(Invoice.id == invoice_id))
    if not invoice:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invoice not found")
    await service.check_association(auth.account, invoice.association_id)
    if payload.association_id != invoice.association_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "An invoice cannot be moved to another association")
    apply_payload(invoice, payload, auth.account)
    async with UnitOfWork(session):
        try:
            await session.flush()
        except IntegrityError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, "Invoice number already exists for this association") from exc
    return success_response(service.serialize(invoice), "Invoice updated")
