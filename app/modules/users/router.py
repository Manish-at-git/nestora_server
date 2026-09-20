"""Protected system-user administration routes."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode
from app.core.dependencies import require_csrf, require_role
from app.core.responses import ApiResponse, success_response
from app.db.session import get_db_session
from app.db.unit_of_work import UnitOfWork
from app.modules.users.schemas import (
    UserCreateRequest,
    UserCreateResponse,
    UserMutationResponse,
    UserResponse,
    UserUpdateRequest,
)
from app.modules.users.service import UserService


router = APIRouter(
    prefix="/admin/users",
    tags=["Users"],
    dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN, RoleCode.ADMIN))],
)


@router.get("", response_model=ApiResponse[list[UserResponse]])
async def list_users(session: AsyncSession = Depends(get_db_session)) -> dict:
    return success_response([UserResponse(**row) for row in await UserService(session).list()])


@router.post("", response_model=ApiResponse[UserCreateResponse], status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreateRequest,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        activation_code = await UserService(session).create(payload)
    return success_response(
        UserCreateResponse(message="User created successfully", activation_code=activation_code)
    )


@router.post("/{user_id}/send-code", response_model=ApiResponse[UserMutationResponse])
async def send_activation_code(
    user_id: str,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        await UserService(session).send_code(user_id)
    return success_response(UserMutationResponse(message="Activation code sent successfully"))


@router.put("/{user_id}", response_model=ApiResponse[UserMutationResponse])
async def update_user(
    user_id: str,
    payload: UserUpdateRequest,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        await UserService(session).update(user_id, payload)
    return success_response(UserMutationResponse(message="User updated successfully"))


@router.delete("/{user_id}", response_model=ApiResponse[UserMutationResponse])
async def delete_user(
    user_id: str,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        await UserService(session).delete(user_id)
    return success_response(UserMutationResponse(message="User deleted successfully"))
