"""Employee onboarding, updates, and safe temporary-password handling."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access_codes import generate_access_code
from app.core.security import hash_password
from app.modules.auth.models import Account
from app.modules.employees.messages import EmployeeMessage
from app.modules.employees.models import Employee
from app.modules.employees.repository import EmployeeRepository
from app.modules.employees.schemas import EmployeeCreateRequest, EmployeeUpdateRequest


def generate_temporary_password() -> str:
    """Generate the eight-character credential shown after employee onboarding."""
    return generate_access_code()


class EmployeeService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = EmployeeRepository(session)

    async def list(self) -> list[dict]:
        return await self.repository.list()

    async def create(self, payload: EmployeeCreateRequest) -> tuple[str, str]:
        email = str(payload.email).lower()
        if await self.repository.email_exists(email):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, EmployeeMessage.EMAIL_EXISTS)
        role = await self.repository.role(payload.role_id)
        if role is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, EmployeeMessage.ROLE_NOT_FOUND)
        if not await self.repository.associations_exist(payload.association_ids):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, EmployeeMessage.ASSOCIATION_NOT_FOUND)

        employee_id = str(uuid.uuid4())
        temporary_password = generate_temporary_password()
        full_name = f"{payload.first_name.strip()} {payload.last_name.strip()}"
        full_address = ", ".join(
            value for value in (
                payload.address_line_1.strip(),
                (payload.address_line_2 or "").strip(),
                payload.city.strip(),
                payload.state.strip(),
            )
            if value
        ) + f" - {payload.pincode.strip()}"
        employee = Employee(
            employee_id=employee_id,
            employee_id_number=await self.repository.next_employee_number(role.name),
            name=full_name,
            address=full_address,
            email=email,
            contact_number=payload.contact_number.strip(),
            first_name=payload.first_name.strip(),
            last_name=payload.last_name.strip(),
            address_line_1=payload.address_line_1.strip(),
            address_line_2=payload.address_line_2,
            city=payload.city.strip(),
            state=payload.state.strip(),
            pincode=payload.pincode.strip(),
            emergency_contact_name=payload.emergency_contact_name,
            emergency_contact_number=payload.emergency_contact_number,
            id_proof_url=payload.id_proof_url,
            temp_password=temporary_password,
            onboard_date=payload.onboard_date,
            end_date=payload.end_date,
            is_deleted=False,
        )
        account_id = str(uuid.uuid4())
        account = Account(
            id=account_id,
            email=email,
            password_hash=hash_password(temporary_password),
            role_id=payload.role_id,
            employee_id=employee_id,
        )
        self.repository.add_employee(employee)
        # The account has a foreign key to employees.employee_id. Persist the
        # parent row before staging the dependent account insert.
        await self.repository.session.flush()
        self.repository.add_account(account)
        await self.repository.session.flush()
        await self.repository.replace_associations(account_id, payload.association_ids)
        return account_id, temporary_password

    async def update(self, account_id: str, payload: EmployeeUpdateRequest) -> None:
        record = await self.repository.get(account_id)
        if record is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, EmployeeMessage.NOT_FOUND)
        role = await self.repository.role(payload.role_id)
        if role is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, EmployeeMessage.ROLE_NOT_FOUND)
        if not await self.repository.associations_exist(payload.association_ids):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, EmployeeMessage.ASSOCIATION_NOT_FOUND)
        account = record["account"]
        employee = record["employee"]
        account.role_id = payload.role_id
        employee.onboard_date = payload.onboard_date
        employee.end_date = payload.end_date
        await self.repository.session.flush()
        await self.repository.replace_associations(account_id, payload.association_ids)
