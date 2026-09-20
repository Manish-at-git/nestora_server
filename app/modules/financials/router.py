"""Protected financial report routes."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode
from app.core.dependencies import AuthContext, get_auth_context, require_csrf, require_role
from app.core.responses import ApiResponse, success_response
from app.db.session import get_db_session
from app.db.unit_of_work import UnitOfWork
from app.modules.financials.schemas import (
    FinancialReportMutationResponse,
    FinancialReportRequest,
    FinancialReportResponse,
)
from app.modules.financials.service import FinancialService


router = APIRouter(
    prefix="/admin/financial-reports",
    tags=["Financials"],
    dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN))],
)


def serialize_report(report) -> FinancialReportResponse:
    return FinancialReportResponse(
        id=report.id,
        association_id=report.association_id,
        association_name=report.association.name if report.association else None,
        published_month=report.published_month,
        report_type=report.report_type,
        title=report.title,
        file_url=report.file_url,
        uploaded_by=report.uploaded_by,
        created_at=report.created_at,
    )


@router.get("", response_model=ApiResponse[list[FinancialReportResponse]])
async def list_financial_reports(session: AsyncSession = Depends(get_db_session)) -> dict:
    reports = await FinancialService(session).list()
    return success_response([serialize_report(report) for report in reports])


@router.post(
    "",
    response_model=ApiResponse[FinancialReportMutationResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_financial_report(
    payload: FinancialReportRequest,
    context: AuthContext = Depends(get_auth_context),
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        report = await FinancialService(session).create(context.account.id, payload)
    return success_response(FinancialReportMutationResponse(id=report.id))
