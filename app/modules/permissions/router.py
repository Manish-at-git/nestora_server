"""Protected administrative routes for permission assignments and matrices."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.constants import RoleCode
from app.core.dependencies import require_csrf, require_role
from app.core.responses import ApiResponse, success_response
from app.db.session import get_db_session
from app.db.unit_of_work import UnitOfWork
from app.modules.permissions.schemas import (
    BulkPermissionRequest,
    MatrixPermissionItem,
    MatrixRole,
    PermissionMutationResponse,
    PermissionRequest,
    PermissionResponse,
    RolePermissionMatrixResponse,
    RolePermissionSummary,
)
from app.modules.permissions.service import PermissionService
from app.modules.iam.models import Role


router = APIRouter(
    prefix="/admin",
    tags=["Permissions"],
    dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN, RoleCode.ADMIN))],
)


def serialize_permission(permission, role_name=None, feature_name=None) -> PermissionResponse:
    return PermissionResponse(
        id=permission.id,
        role_id=permission.role_id,
        feature_id=permission.feature_id,
        can_create=permission.can_create,
        can_view=permission.can_view,
        can_update=permission.can_update,
        can_delete=permission.can_delete,
        sidebar_order=permission.sidebar_order,
        role_name=role_name,
        feature_name=feature_name,
        created_at=permission.created_at,
    )


@router.get("/permissions", response_model=ApiResponse[list[PermissionResponse]])
async def list_permissions(session: AsyncSession = Depends(get_db_session)) -> dict:
    rows = await PermissionService(session).list()
    return success_response(
        [serialize_permission(permission, role, feature) for permission, role, feature in rows]
    )


@router.post("/permissions", response_model=ApiResponse[PermissionResponse], status_code=201)
async def create_permission(
    payload: PermissionRequest,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        permission = await PermissionService(session).create(payload)
    return success_response(serialize_permission(permission))


@router.put("/permissions/{permission_id}", response_model=ApiResponse[PermissionResponse])
async def update_permission(
    permission_id: str,
    payload: PermissionRequest,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        permission = await PermissionService(session).update(permission_id, payload)
    return success_response(serialize_permission(permission))


@router.delete("/permissions/{permission_id}", response_model=ApiResponse[PermissionMutationResponse])
async def delete_permission(
    permission_id: str,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        await PermissionService(session).delete(permission_id)
    return success_response(PermissionMutationResponse())


@router.get("/roles-permissions-summary", response_model=ApiResponse[list[RolePermissionSummary]])
async def role_permissions_summary(session: AsyncSession = Depends(get_db_session)) -> dict:
    rows = await PermissionService(session).repository.summary()
    return success_response(
        [
            RolePermissionSummary(
                id=row["role"].id,
                name=row["role"].name,
                code=row["role"].code,
                description=row["role"].description,
                entity_id=row["role"].entity_id,
                entity_name=row["role"].entity.name if row["role"].entity else None,
                is_active=row["role"].is_active,
                created_at=row["role"].created_at,
                configured_features_count=row["configured"],
                accounts_count=row["accounts"],
                total_features_count=row["features"],
            )
            for row in rows
        ]
    )


@router.get("/roles/{role_id}/permissions-matrix", response_model=ApiResponse[RolePermissionMatrixResponse])
async def role_permissions_matrix(role_id: str, session: AsyncSession = Depends(get_db_session)) -> dict:
    service = PermissionService(session)
    rows = await service.matrix(role_id)
    role = await session.scalar(
        select(Role).options(joinedload(Role.entity)).where(Role.id == role_id)
    )
    role_response = MatrixRole(
        id=role.id,
        name=role.name,
        code=role.code,
        description=role.description,
        entity_id=role.entity_id,
        entity_name=role.entity.name if role.entity else None,
        is_active=role.is_active,
    )
    features = [
        MatrixPermissionItem(
            feature_id=feature.id,
            feature_name=feature.name,
            feature_code=feature.code,
            feature_description=feature.description,
            parent_id=feature.parent_id,
            parent_name=parent_name,
            url=feature.route,
            order_index=feature.order_index,
            icon=feature.icon,
            can_create=permission.can_create if permission else False,
            can_view=permission.can_view if permission else False,
            can_update=permission.can_update if permission else False,
            can_delete=permission.can_delete if permission else False,
            sidebar_order=permission.sidebar_order if permission else 0,
        )
        for feature, parent_name, permission in rows
    ]
    return success_response(RolePermissionMatrixResponse(role=role_response, features=features))


@router.post("/roles/{role_id}/permissions-bulk", response_model=ApiResponse[PermissionMutationResponse])
async def update_role_permissions_bulk(
    role_id: str,
    payload: BulkPermissionRequest,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        await PermissionService(session).bulk_update(role_id, payload)
    return success_response(PermissionMutationResponse())
