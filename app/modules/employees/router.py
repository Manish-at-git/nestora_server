"""Protected employee administration routes."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode
from app.core.dependencies import require_csrf, require_role
from app.core.responses import ApiResponse, success_response
from app.db.session import get_db_session
from app.db.unit_of_work import UnitOfWork
from app.modules.employees.schemas import (
    EmployeeCreateRequest,
    EmployeeCreateResponse,
    EmployeeMutationResponse,
    EmployeeResponse,
    EmployeeUpdateRequest,
)
from app.modules.employees.service import EmployeeService


router = APIRouter(
    prefix="/admin/employees",
    tags=["Employees"],
    dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN, RoleCode.ADMIN))],
)


def serialize_employee(record: dict) -> EmployeeResponse:
    account = record["account"]
    employee = record["employee"]
    role = record["role"]
    return EmployeeResponse(
        account_id=account.id,
        email=account.email,
        role_id=account.role_id,
        role_name=role.name,
        employee_id_number=employee.employee_id_number,
        first_name=employee.first_name,
        last_name=employee.last_name,
        name=employee.name,
        contact_number=employee.contact_number,
        address=employee.address,
        address_line_1=employee.address_line_1,
        address_line_2=employee.address_line_2,
        city_id=employee.city_id,
        city=employee.location_city.name if employee.location_city else None,
        state=employee.location_city.region.name if employee.location_city else None,
        pincode=employee.pincode,
        onboard_date=employee.onboard_date,
        end_date=employee.end_date,
        emergency_contact_name=employee.emergency_contact_name,
        emergency_contact_number=employee.emergency_contact_number,
        id_proof_url=employee.id_proof_url,
        temp_password=employee.temp_password,
        associations=record["associations"],
        created_at=account.created_at,
    )


@router.get("", response_model=ApiResponse[list[EmployeeResponse]])
async def list_employees(session: AsyncSession = Depends(get_db_session)) -> dict:
    records = await EmployeeService(session).list()
    return success_response([serialize_employee(record) for record in records])


@router.post("", response_model=ApiResponse[EmployeeCreateResponse], status_code=status.HTTP_201_CREATED)
async def create_employee(
    payload: EmployeeCreateRequest,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        account_id, temporary_password = await EmployeeService(session).create(payload)
    return success_response(
        EmployeeCreateResponse(account_id=account_id, temp_password=temporary_password)
    )


@router.put("/{account_id}", response_model=ApiResponse[EmployeeMutationResponse])
async def update_employee(
    account_id: str,
    payload: EmployeeUpdateRequest,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        await EmployeeService(session).update(account_id, payload)
    return success_response(EmployeeMutationResponse())
