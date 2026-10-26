"""Protected API routes for association Income Statements."""

from io import BytesIO
from decimal import Decimal, InvalidOperation
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode
from app.core.dependencies import AuthContext, get_auth_context, require_csrf, require_role
from app.core.responses import ApiResponse, success_response
from app.db.session import get_db_session
from app.db.unit_of_work import UnitOfWork
from app.modules.income_statements.schemas import (
    IncomeStatementMutationResponse,
    IncomeStatementRequest,
    IncomeStatementResponse,
)
from app.modules.income_statements.service import IncomeStatementService

VIEWER_DEP = Depends(require_role(RoleCode.SUPER_ADMIN, RoleCode.ADMIN, RoleCode.ACCOUNTANT, RoleCode.BOARD_MEMBER, RoleCode.COMMITTEE_MEMBER, RoleCode.HOMEOWNER))
MANAGER_DEP = Depends(require_role(RoleCode.SUPER_ADMIN, RoleCode.ADMIN, RoleCode.ACCOUNTANT))
router = APIRouter(prefix="/income-statements", tags=["Income Statements"])


def workbook_response(workbook: Workbook, filename: str) -> StreamingResponse:
    stream = BytesIO()
    workbook.save(stream)
    stream.seek(0)
    return StreamingResponse(stream, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def build_export_workbook(response: IncomeStatementResponse) -> Workbook:
    """Build a presentation-ready Income Statement workbook for downloads."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Income Statement"
    amount_format = '#,##0.00;[Red]-#,##0.00'
    row_border = Border(bottom=Side(style="thin", color="E2E8F0"))

    sheet.merge_cells("A1:E1")
    sheet["A1"] = f"{response.association_name} - Income Statement"
    sheet["A1"].font = Font(name="Arial", size=16, bold=True, color="334155")
    sheet.row_dimensions[1].height = 26
    sheet.merge_cells("A2:E2")
    sheet["A2"] = response.fiscal_period
    sheet["A2"].font = Font(name="Arial", size=10, italic=True, color="64748B")

    headers = ["Category", "Particulars", "Current Year (₹)", "Previous Year (₹)", "Variance (%)"]
    for column, value in enumerate(headers, start=1):
        cell = sheet.cell(row=4, column=column, value=value)
        cell.font = Font(name="Arial", bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="059669")
        cell.alignment = Alignment(horizontal="right" if column >= 3 else "left")

    rows_by_type = {
        "income": [item for item in response.items if item.item_type.value == "income"],
        "expense": [item for item in response.items if item.item_type.value == "expense"],
    }
    previous_totals = {
        key: sum((item.previous_amount for item in items), Decimal("0"))
        for key, items in rows_by_type.items()
    }
    row = 5

    for item_type, label, fill, color in (
        ("income", "Income", "ECFDF5", "047857"),
        ("expense", "Expenses", "FFF1F2", "BE123C"),
    ):
        sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
        for column in range(1, 6):
            sheet.cell(row=row, column=column).fill = PatternFill("solid", fgColor=fill)
        sheet.cell(row=row, column=1, value=label).font = Font(name="Arial", bold=True, color=color)
        row += 1

        for item in rows_by_type[item_type]:
            sheet.cell(row=row, column=2, value=item.name)
            current = sheet.cell(row=row, column=3, value=float(item.current_amount))
            previous = sheet.cell(row=row, column=4, value=float(item.previous_amount))
            variance = sheet.cell(row=row, column=5, value=float(item.variance_pct) / 100)
            current.number_format = amount_format
            previous.number_format = amount_format
            variance.number_format = "0.00%"
            for column in range(1, 6):
                sheet.cell(row=row, column=column).border = row_border
            row += 1

        current_total = response.total_income if item_type == "income" else response.total_expenses
        previous_total = previous_totals[item_type]
        sheet.cell(row=row, column=2, value=f"Total {label}")
        current_cell = sheet.cell(row=row, column=3, value=float(current_total))
        previous_cell = sheet.cell(row=row, column=4, value=float(previous_total))
        variance_cell = sheet.cell(
            row=row,
            column=5,
            value=float((current_total - previous_total) / abs(previous_total) / 100)
            if previous_total
            else 0,
        )
        current_cell.number_format = amount_format
        previous_cell.number_format = amount_format
        variance_cell.number_format = "0.00%"
        for column in range(1, 6):
            cell = sheet.cell(row=row, column=column)
            cell.fill = PatternFill("solid", fgColor=fill)
            cell.font = Font(name="Arial", bold=True, color=color)
        row += 2

    previous_surplus = previous_totals["income"] - previous_totals["expense"]
    sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
    sheet.cell(row=row, column=1, value="NET SURPLUS / (DEFICIT)")
    current_cell = sheet.cell(row=row, column=3, value=float(response.net_surplus))
    previous_cell = sheet.cell(row=row, column=4, value=float(previous_surplus))
    variance_cell = sheet.cell(
        row=row,
        column=5,
        value=float((response.net_surplus - previous_surplus) / abs(previous_surplus) / 100)
        if previous_surplus
        else 0,
    )
    current_cell.number_format = amount_format
    previous_cell.number_format = amount_format
    variance_cell.number_format = "0.00%"
    for column in range(1, 6):
        cell = sheet.cell(row=row, column=column)
        cell.fill = PatternFill("solid", fgColor="E0F2FE")
        cell.font = Font(name="Arial", bold=True, color="0369A1")

    sheet.column_dimensions["A"].width = 20
    sheet.column_dimensions["B"].width = 42
    sheet.column_dimensions["C"].width = 20
    sheet.column_dimensions["D"].width = 20
    sheet.column_dimensions["E"].width = 16
    sheet.freeze_panes = "A5"
    sheet.sheet_view.showGridLines = False
    sheet.print_area = f"A1:E{row}"
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    return workbook


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
    if not rows:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "The workbook is empty. Use the Income Statement template.",
        )

    errors: list[str] = []
    items = []
    for row_number, row in enumerate(rows[1:], start=2):
        if not row or not any(value not in (None, "") for value in row):
            continue

        item_type_value = row[0] if len(row) > 0 else None
        item_name_value = row[1] if len(row) > 1 else None
        current_value = row[2] if len(row) > 2 else None
        previous_value = row[3] if len(row) > 3 else None
        item_type = str(item_type_value or "").strip().lower()
        if item_type not in {"income", "expense"}:
            received = str(item_type_value).strip() if item_type_value not in (None, "") else "blank"
            errors.append(
                f'Row {row_number}, Type: expected "income" or "expense", received "{received}".'
            )
            continue
        if not str(item_name_value or "").strip():
            errors.append(f"Row {row_number}, Particular: a line-item name is required.")
            continue

        amounts: dict[str, Decimal] = {}
        for column_name, value in (("Current Year", current_value), ("Previous Year", previous_value)):
            if value in (None, ""):
                errors.append(f"Row {row_number}, {column_name}: an amount is required.")
                continue
            try:
                amount = Decimal(str(value)).quantize(Decimal("0.01"))
                if not amount.is_finite():
                    raise InvalidOperation
                amounts[column_name] = amount
            except (InvalidOperation, TypeError, ValueError):
                errors.append(
                    f'Row {row_number}, {column_name}: expected a number, received "{value}".'
                )

        if "Current Year" in amounts and "Previous Year" in amounts:
            items.append(
                {
                    "item_type": item_type,
                    "name": str(item_name_value).strip(),
                    "current_amount": amounts["Current Year"],
                    "previous_amount": amounts["Previous Year"],
                }
            )

    if errors:
        detail = " ".join(errors[:10])
        if len(errors) > 10:
            detail += f" And {len(errors) - 10} more row errors."
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail)
    if not items:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "The workbook contains no valid line items. Use the Income Statement template.",
        )
    service = IncomeStatementService(session)
    from app.modules.income_statements.schemas import IncomeStatementItemRequest
    payload = IncomeStatementRequest(association_id=association_id, fiscal_period=fiscal_period, items=[IncomeStatementItemRequest(**item) for item in items])
    async with UnitOfWork(session):
        statement = await service.save(context.account, payload)
    return success_response(IncomeStatementMutationResponse(id=statement.id, imported_items=len(items)), "Income Statement imported successfully")


@router.get("/export", dependencies=[MANAGER_DEP])
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
    response = await service.serialize(statement)
    workbook = build_export_workbook(response)
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
