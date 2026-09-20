"""Protected administrative routes for feature catalogue CRUD."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode
from app.core.dependencies import require_csrf, require_role
from app.core.responses import ApiResponse, success_response
from app.db.session import get_db_session
from app.db.unit_of_work import UnitOfWork
from app.modules.features.schemas import FeatureMutationResponse, FeatureRequest, FeatureResponse
from app.modules.features.service import FeatureService


router = APIRouter(
    prefix="/admin/features",
    tags=["Features"],
    dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN, RoleCode.ADMIN))],
)


def serialize_feature(feature) -> FeatureResponse:
    return FeatureResponse(
        id=feature.id,
        name=feature.name,
        code=feature.code,
        description=feature.description,
        parent_id=feature.parent_id,
        parent_name=feature.parent.name if feature.parent else None,
        icon=feature.icon,
        url=feature.route,
        order_index=feature.order_index,
        is_active=feature.is_active,
        created_at=feature.created_at,
    )


@router.get("", response_model=ApiResponse[list[FeatureResponse]])
async def list_features(session: AsyncSession = Depends(get_db_session)) -> dict:
    features = await FeatureService(session).list()
    return success_response([serialize_feature(feature) for feature in features])


@router.post("", response_model=ApiResponse[FeatureResponse], status_code=status.HTTP_201_CREATED)
async def create_feature(
    payload: FeatureRequest,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        feature = await FeatureService(session).create(payload)
    return success_response(serialize_feature(feature))


@router.put("/{feature_id}", response_model=ApiResponse[FeatureMutationResponse])
async def update_feature(
    feature_id: str,
    payload: FeatureRequest,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        await FeatureService(session).update(feature_id, payload)
    return success_response(FeatureMutationResponse())


@router.delete("/{feature_id}", response_model=ApiResponse[FeatureMutationResponse])
async def delete_feature(
    feature_id: str,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        await FeatureService(session).delete(feature_id)
    return success_response(FeatureMutationResponse())
