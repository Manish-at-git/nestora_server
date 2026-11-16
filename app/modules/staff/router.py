"""Protected staff directory, attendance, and monthly report routes."""

from io import BytesIO

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode
from app.core.dependencies import AuthContext, get_auth_context, require_csrf, require_role
from app.core.responses import ApiResponse, success_response
from app.db.session import get_db_session
from app.db.unit_of_work import UnitOfWork
from app.modules.staff.schemas import (
    StaffAttendanceActionRequest,
    StaffAttendanceActionResponse,
    StaffAttendanceResponse,
    StaffCreateRequest,
    StaffBlockResponse,
    StaffMemberResponse,
    StaffMonthlyAttendanceReportResponse,
    StaffMutationResponse,
    StaffPastAttendanceRequest,
    StaffUpdateRequest,
    StaffUnitResponse,
)
from app.modules.staff.service import StaffService


router = APIRouter(prefix="/staff", tags=["Staff"])
OPERATORS = Depends(require_role(RoleCode.SUPER_ADMIN, RoleCode.ADMIN, RoleCode.SECURITY))
MANAGERS = Depends(require_role(RoleCode.SUPER_ADMIN, RoleCode.ADMIN))
EXCEL_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def build_monthly_attendance_workbook(report: dict) -> Workbook:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Attendance"
    days = report["rows"][0]["days"] if report["rows"] else []
    headers = ["Staff ID", "Staff Member", "Work Type", *[day["date"] for day in days], "Present Days"]
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(color="FFFFFF", bold=True)
        cell.fill = PatternFill("solid", fgColor="1E3A5F")
    for row in report["rows"]:
        values = [row["staff_code"], row["staff_name"], row["designation"]]
        values.extend("P" if day["status"] == "present" else "IN" if day["status"] == "incomplete" else "—" for day in row["days"])
        values.append(row["present_days"])
        sheet.append(values)
    sheet.freeze_panes = "D2"
    sheet.auto_filter.ref = f"A1:{sheet.cell(row=max(1, sheet.max_row), column=sheet.max_column).coordinate}"
    sheet.column_dimensions["A"].width = 16
    sheet.column_dimensions["B"].width = 28
    sheet.column_dimensions["C"].width = 18
    for column in range(4, sheet.max_column + 1):
        sheet.column_dimensions[get_column_letter(column)].width = 12
    return workbook


@router.get("", response_model=ApiResponse[list[StaffMemberResponse]], dependencies=[OPERATORS])
async def list_staff(
    context: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return success_response(await StaffService(session).list(context.account))


@router.get("/attendance", response_model=ApiResponse[list[StaffAttendanceResponse]], dependencies=[OPERATORS])
async def attendance_history(
    context: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return success_response(await StaffService(session).history(context.account))


@router.get("/reports/monthly", response_model=ApiResponse[StaffMonthlyAttendanceReportResponse], dependencies=[MANAGERS])
async def monthly_attendance_report(
    association_id: str,
    month: str = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    staff_id: str | None = None,
    designation: str | None = None,
    context: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return success_response(await StaffService(session).monthly_report(
        association_id=association_id,
        month=month,
        staff_id=staff_id,
        designation=designation,
        account=context.account,
    ))


@router.get("/reports/monthly/export", dependencies=[MANAGERS])
async def export_monthly_attendance_report(
    association_id: str,
    month: str = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    staff_id: str | None = None,
    designation: str | None = None,
    context: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    report = await StaffService(session).monthly_report(
        association_id=association_id,
        month=month,
        staff_id=staff_id,
        designation=designation,
        account=context.account,
    )
    stream = BytesIO()
    build_monthly_attendance_workbook(report).save(stream)
    stream.seek(0)
    return StreamingResponse(
        stream,
        media_type=EXCEL_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="staff_attendance_{month}.xlsx"'},
    )


@router.get("/lookups/associations/{association_id}/blocks", response_model=ApiResponse[list[StaffBlockResponse]], dependencies=[MANAGERS])
async def staff_blocks(
    association_id: str,
    context: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return success_response(await StaffService(session).blocks(association_id, context.account))


@router.get("/lookups/blocks/{block_id}/units", response_model=ApiResponse[list[StaffUnitResponse]], dependencies=[MANAGERS])
async def staff_units(
    block_id: str,
    context: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return success_response(await StaffService(session).units(block_id, context.account))


@router.post("", response_model=ApiResponse[StaffMutationResponse], status_code=status.HTTP_201_CREATED, dependencies=[MANAGERS])
async def create_staff(
    payload: StaffCreateRequest,
    context: AuthContext = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        staff_id, temporary_password = await StaffService(session).create(payload, context.account)
    return success_response(StaffMutationResponse(id=staff_id, temp_password=temporary_password))


@router.put("/{staff_id}", response_model=ApiResponse[StaffMutationResponse], dependencies=[MANAGERS])
async def update_staff(
    staff_id: str,
    payload: StaffUpdateRequest,
    context: AuthContext = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        temporary_password = await StaffService(session).update(staff_id, payload, context.account)
    return success_response(StaffMutationResponse(id=staff_id, temp_password=temporary_password))


@router.post("/attendance/scan", response_model=ApiResponse[StaffAttendanceActionResponse], dependencies=[OPERATORS])
async def scan_staff_pass(
    payload: StaffAttendanceActionRequest,
    context: AuthContext = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        action, attendance = await StaffService(session).toggle_attendance(
            payload.pass_code,
            context.account,
            gate=payload.gate,
            remarks=payload.remarks,
        )
    return success_response(StaffAttendanceActionResponse(action=action, attendance=attendance))


@router.post("/attendance/past", response_model=ApiResponse[StaffAttendanceResponse], status_code=status.HTTP_201_CREATED, dependencies=[MANAGERS])
async def create_past_attendance(
    payload: StaffPastAttendanceRequest,
    context: AuthContext = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        attendance = await StaffService(session).record_past_attendance(payload, context.account)
    return success_response(attendance)
