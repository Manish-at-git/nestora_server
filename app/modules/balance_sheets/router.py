"""Protected API routes for association Balance Sheets."""

from datetime import date
from io import BytesIO
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode
from app.core.dependencies import AuthContext, get_auth_context, require_csrf, require_role
from app.core.responses import ApiResponse, success_response
from app.db.session import get_db_session
from app.db.unit_of_work import UnitOfWork
from app.modules.balance_sheets.schemas import (
    BalanceSheetMutationResponse,
    BalanceSheetRequest,
    BalanceSheetResponse,
)
from app.modules.balance_sheets.service import BalanceSheetService

VIEWER_DEP = Depends(
    require_role(
        RoleCode.SUPER_ADMIN,
        RoleCode.ADMIN,
        RoleCode.ACCOUNTANT,
        RoleCode.BOARD_MEMBER,
        RoleCode.COMMITTEE_MEMBER,
        RoleCode.HOMEOWNER,
    )
)
MANAGER_DEP = Depends(
    require_role(
        RoleCode.SUPER_ADMIN,
        RoleCode.ADMIN,
        RoleCode.ACCOUNTANT,
    )
)
router = APIRouter(prefix="/balance-sheets", tags=["Balance Sheets"])

EXCEL_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MAX_IMPORT_BYTES = 5 * 1024 * 1024
TEMPLATE_HEADERS = [
    "Section",
    "Account Code (Optional)",
    "Account Name",
    "Amount",
    "Health Status (Optional)",
    "Financial Health Note (Optional)",
]
SECTION_VALUES = [
    "current_asset",
    "non_current_asset",
    "current_liability",
    "non_current_liability",
    "equity",
]


def spreadsheet_response(workbook: Workbook, filename: str) -> StreamingResponse:
    stream = BytesIO()
    workbook.save(stream)
    stream.seek(0)
    return StreamingResponse(
        stream,
        media_type=EXCEL_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def format_sheet(sheet) -> None:
    header_fill = PatternFill("solid", fgColor="1E3A5F")
    for cell in sheet[1]:
        cell.font = Font(color="FFFFFF", bold=True)
        cell.fill = header_fill
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = "A1:F1"
    sheet.column_dimensions["A"].width = 24
    sheet.column_dimensions["B"].width = 26
    sheet.column_dimensions["C"].width = 40
    sheet.column_dimensions["D"].width = 18
    sheet.column_dimensions["E"].width = 28
    sheet.column_dimensions["F"].width = 55


def build_template_workbook() -> Workbook:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Balance Sheet"
    sheet.append(TEMPLATE_HEADERS)
    format_sheet(sheet)

    values_sheet = workbook.create_sheet("Allowed Values")
    values_sheet.append(["Valid Section values"])
    for section in SECTION_VALUES:
        values_sheet.append([section])
    values_sheet.sheet_state = "hidden"

    validation = DataValidation(
        type="list",
        formula1="'Allowed Values'!$A$2:$A$6",
        allow_blank=False,
    )
    validation.error = "Choose one of the supported Balance Sheet sections."
    validation.errorTitle = "Invalid section"
    sheet.add_data_validation(validation)
    validation.add("A2:A1001")
    return workbook


@router.get(
    "/dates",
    response_model=ApiResponse[list[date]],
    dependencies=[VIEWER_DEP],
)
async def list_balance_sheet_dates(
    association_id: str,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    dates = await BalanceSheetService(session).dates(context.account, association_id)
    return success_response(dates)


@router.get("/template", dependencies=[MANAGER_DEP])
async def download_balance_sheet_template() -> StreamingResponse:
    return spreadsheet_response(
        build_template_workbook(),
        "balance_sheet_import_template.xlsx",
    )


@router.get("/export", dependencies=[VIEWER_DEP])
async def export_balance_sheet(
    association_id: str,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    as_on_date: date | None = None,
) -> StreamingResponse:
    service = BalanceSheetService(session)
    balance_sheet = await service.get(context.account, association_id, as_on_date)
    if not balance_sheet:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Balance Sheet not found")
    response = await service.serialize(balance_sheet)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Balance Sheet"
    sheet.append(TEMPLATE_HEADERS)
    for item in response.items:
        sheet.append(
            [
                item.section.value,
                item.account_code or "",
                item.account_name,
                float(item.amount),
                response.health_status or "",
                response.health_note or "",
            ]
        )
    format_sheet(sheet)
    for cell in sheet["D"][1:]:
        cell.number_format = '#,##0.00;[Red]-#,##0.00'

    return spreadsheet_response(
        workbook,
        f"balance_sheet_{balance_sheet.as_on_date.isoformat()}.xlsx",
    )


@router.post(
    "/import",
    response_model=ApiResponse[BalanceSheetMutationResponse],
    status_code=status.HTTP_201_CREATED,
    dependencies=[MANAGER_DEP],
)
async def import_balance_sheet(
    association_id: str,
    as_on_date: date,
    file: Annotated[UploadFile, File()],
    context: Annotated[AuthContext, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    filename = (file.filename or "").lower()
    if not filename.endswith(".xlsx"):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Balance Sheet import requires an .xlsx file",
        )

    content = await file.read(MAX_IMPORT_BYTES + 1)
    if len(content) > MAX_IMPORT_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            "Balance Sheet spreadsheet must be 5 MB or smaller",
        )
    try:
        workbook = load_workbook(BytesIO(content), data_only=True, read_only=True)
    except Exception as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Unable to read the Excel workbook",
        ) from exc

    service = BalanceSheetService(session)
    async with UnitOfWork(session):
        balance_sheet = await service.import_workbook(
            context.account,
            association_id,
            as_on_date,
            workbook,
        )
    return success_response(
        BalanceSheetMutationResponse(
            id=balance_sheet.id,
            imported_items=len(balance_sheet.items),
        ),
        "Balance Sheet imported successfully",
    )


@router.get(
    "",
    response_model=ApiResponse[BalanceSheetResponse | None],
    dependencies=[VIEWER_DEP],
)
async def get_balance_sheet(
    association_id: str,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    as_on_date: date | None = None,
) -> dict:
    service = BalanceSheetService(session)
    balance_sheet = await service.get(context.account, association_id, as_on_date)
    serialized = await service.serialize(balance_sheet) if balance_sheet else None
    return success_response(serialized)


@router.post(
    "",
    response_model=ApiResponse[BalanceSheetMutationResponse],
    status_code=status.HTTP_201_CREATED,
    dependencies=[MANAGER_DEP],
)
async def create_balance_sheet(
    payload: BalanceSheetRequest,
    context: Annotated[AuthContext, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    async with UnitOfWork(session):
        balance_sheet = await BalanceSheetService(session).create(
            context.account,
            payload,
        )
    return success_response(
        BalanceSheetMutationResponse(id=balance_sheet.id),
        "Balance Sheet created successfully",
    )


@router.put(
    "/{balance_sheet_id}",
    response_model=ApiResponse[BalanceSheetMutationResponse],
    dependencies=[MANAGER_DEP],
)
async def update_balance_sheet(
    balance_sheet_id: str,
    payload: BalanceSheetRequest,
    context: Annotated[AuthContext, Depends(require_csrf)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    async with UnitOfWork(session):
        balance_sheet = await BalanceSheetService(session).update(
            context.account,
            balance_sheet_id,
            payload,
        )
    return success_response(
        BalanceSheetMutationResponse(id=balance_sheet.id),
        "Balance Sheet updated successfully",
    )
