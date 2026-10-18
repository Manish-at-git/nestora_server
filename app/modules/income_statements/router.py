"""Protected API routes for association Income Statements."""

from typing import Annotated

from io import BytesIO
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode
from app.core.dependencies import AuthContext, get_auth_context, require_csrf, require_role
from app.core.responses import ApiResponse, success_response
from app.db.session import get_db_session
from app.db.unit_of_work import UnitOfWork
from app.modules.income_statements.schemas import IncomeStatementMutationResponse, IncomeStatementRequest, IncomeStatementResponse
from app.modules.income_statements.service import IncomeStatementService

VIEWER_DEP = Depends(require_role(RoleCode.SUPER_ADMIN, RoleCode.ADMIN, RoleCode.ACCOUNTANT, RoleCode.BOARD_MEMBER, RoleCode.COMMITTEE_MEMBER, RoleCode.HOMEOWNER))
MANAGER_DEP = Depends(require_role(RoleCode.SUPER_ADMIN, RoleCode.ADMIN, RoleCode.ACCOUNTANT))
router = APIRouter(prefix="/income-statements", tags=["Income Statements"])


def workbook_response(workbook: Workbook, filename: str) -> StreamingResponse:
    stream = BytesIO()
    workbook.save(stream)
    stream.seek(0)
    return StreamingResponse(stream, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/template", dependencies=[MANAGER_DEP])
async def income_statement_template() -> StreamingResponse:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Income Statement"
    sheet.append(["Type", "Particular", "Current Year", "Previous Year"])
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1E3A5F")
    sheet.column_dimensions["A"].width = 18
    sheet.column_dimensions["B"].width = 42
    sheet.column_dimensions["C"].width = 20
    sheet.column_dimensions["D"].width = 20
    return workbook_response(workbook, "income_statement_import_template.xlsx")


@router.post("/import", response_model=ApiResponse[IncomeStatementMutationResponse], status_code=status.HTTP_201_CREATED, dependencies=[MANAGER_DEP])
async def import_income_statement(
    association_id: str,
    fiscal_period: str,
    context: Annotated[AuthContext, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    file: UploadFile = File(...),
) -> dict:
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Select an .xlsx workbook")
    raw = await file.read()
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The workbook must be 5 MB or smaller")
    workbook = load_workbook(BytesIO(raw), read_only=True, data_only=True)
    rows = list(workbook.active.iter_rows(values_only=True))
    items = []
    for row in rows[1:]:
        if not row or not row[1]:
            continue
        item_type = str(row[0] or "").strip().lower()
        if item_type not in {"income", "expense"}:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Type must be income or expense")
        items.append({"item_type": item_type, "name": str(row[1]).strip(), "current_amount": row[2] or 0, "previous_amount": row[3] or 0})
    if not items:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The workbook contains no line items")
    service = IncomeStatementService(session)
    from app.modules.income_statements.schemas import IncomeStatementItemRequest
    payload = IncomeStatementRequest(association_id=association_id, fiscal_period=fiscal_period, items=[IncomeStatementItemRequest(**item) for item in items])
    async with UnitOfWork(session):
        statement = await service.save(context.account, payload)
    return success_response(IncomeStatementMutationResponse(id=statement.id, imported_items=len(items)), "Income Statement imported successfully")


@router.get("/export", dependencies=[VIEWER_DEP])
async def export_income_statement(
    association_id: str,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    fiscal_period: str | None = None,
) -> StreamingResponse:
    service = IncomeStatementService(session)
    statement = await service.get(context.account, association_id, fiscal_period)
    if not statement:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Income Statement not found")
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Income Statement"
    sheet.append(["Type", "Particular", "Current Year", "Previous Year", "Variance %"])
    response = await service.serialize(statement)
    for item in response.items:
        sheet.append([item.item_type.value, item.name, float(item.current_amount), float(item.previous_amount), float(item.variance_pct)])
    return workbook_response(workbook, f"income_statement_{statement.id}.xlsx")


@router.get("/periods", response_model=ApiResponse[list[str]], dependencies=[VIEWER_DEP])
async def list_income_statement_periods(
    association_id: str,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    periods = await IncomeStatementService(session).periods(context.account, association_id)
    return success_response(periods)


@router.get("", response_model=ApiResponse[IncomeStatementResponse | None], dependencies=[VIEWER_DEP])
async def get_income_statement(
    association_id: str,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    fiscal_period: str | None = None,
) -> dict:
    statement = await IncomeStatementService(session).get(context.account, association_id, fiscal_period)
    if not statement:
        return success_response(None)
    return success_response(await IncomeStatementService(session).serialize(statement))


@router.post("", response_model=ApiResponse[IncomeStatementMutationResponse], status_code=status.HTTP_201_CREATED, dependencies=[MANAGER_DEP])
async def create_income_statement(
    payload: IncomeStatementRequest,
    context: Annotated[AuthContext, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    async with UnitOfWork(session):
        statement = await IncomeStatementService(session).save(context.account, payload)
    return success_response(IncomeStatementMutationResponse(id=statement.id), "Income Statement created successfully")


@router.put("/{statement_id}", response_model=ApiResponse[IncomeStatementMutationResponse], dependencies=[MANAGER_DEP])
async def update_income_statement(
    statement_id: str,
    payload: IncomeStatementRequest,
    context: Annotated[AuthContext, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    service = IncomeStatementService(session)
    existing = await service.repository.get_by_id(statement_id)
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Income Statement not found")
    async with UnitOfWork(session):
        statement = await service.save(context.account, payload, existing)
    return success_response(IncomeStatementMutationResponse(id=statement.id), "Income Statement updated successfully")
