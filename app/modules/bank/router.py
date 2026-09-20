"""Protected association bank account routes."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode
from app.core.dependencies import AuthContext, get_auth_context, require_csrf, require_role
from app.core.responses import ApiResponse, success_response
from app.db.session import get_db_session
from app.db.unit_of_work import UnitOfWork
from app.modules.bank.schemas import BankAccountMutationResponse, BankAccountRequest, BankAccountResponse
from app.modules.bank.service import BankService


router = APIRouter(
    prefix="/admin/bank-accounts",
    tags=["Bank Accounts"],
    dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN, RoleCode.ADMIN, RoleCode.ACCOUNTANT))],
)


@router.get("", response_model=ApiResponse[list[BankAccountResponse]])
async def list_bank_accounts(
    association_id: str | None = None,
    context: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    accounts = await BankService(session).list(context.account.id, context.account.role.code, association_id)
    return success_response(accounts)


@router.post("", response_model=ApiResponse[BankAccountMutationResponse], status_code=status.HTTP_201_CREATED)
async def create_bank_account(
    payload: BankAccountRequest,
    context: AuthContext = Depends(get_auth_context),
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        account = await BankService(session).create(context.account.id, context.account.role.code, payload)
    return success_response(BankAccountMutationResponse(id=account.id))


@router.put("/{bank_id}", response_model=ApiResponse[BankAccountMutationResponse])
async def update_bank_account(
    bank_id: str,
    payload: BankAccountRequest,
    context: AuthContext = Depends(get_auth_context),
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        await BankService(session).update(context.account.id, context.account.role.code, bank_id, payload)
    return success_response(BankAccountMutationResponse())


@router.delete("/{bank_id}", response_model=ApiResponse[BankAccountMutationResponse])
async def delete_bank_account(
    bank_id: str,
    context: AuthContext = Depends(get_auth_context),
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        await BankService(session).delete(context.account.id, context.account.role.code, bank_id)
    return success_response(BankAccountMutationResponse())
