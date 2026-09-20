"""Protected Super Admin routes for subscription plan management."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode
from app.core.dependencies import require_csrf, require_role
from app.core.responses import ApiResponse, success_response
from app.db.session import get_db_session
from app.db.unit_of_work import UnitOfWork
from app.modules.subscriptions.schemas import (
    MutationResponse,
    PlanFeatureRequest,
    SubscriptionPlanRequest,
    SubscriptionPlanResponse,
)
from app.modules.subscriptions.service import SubscriptionService


router = APIRouter(
    prefix="/admin/subscription-plans",
    tags=["Subscriptions"],
    dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN))],
)


def serialize_plan(plan) -> SubscriptionPlanResponse:
    return SubscriptionPlanResponse(
        id=plan.id,
        name=plan.name,
        code=plan.code,
        country=plan.country,
        description=plan.description,
        monthly_price=plan.monthly_price,
        yearly_price=plan.yearly_price,
        trial_days=plan.trial_days,
        is_active=plan.is_active,
        features=[
            assignment.feature_id
            for assignment in plan.feature_assignments
            if not assignment.is_deleted
        ],
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


@router.get("", response_model=ApiResponse[list[SubscriptionPlanResponse]])
async def list_subscription_plans(session: AsyncSession = Depends(get_db_session)) -> dict:
    plans = await SubscriptionService(session).list()
    return success_response([serialize_plan(plan) for plan in plans])


@router.post("", response_model=ApiResponse[SubscriptionPlanResponse], status_code=status.HTTP_201_CREATED)
async def create_subscription_plan(
    payload: SubscriptionPlanRequest,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        plan = await SubscriptionService(session).create(payload)
    return success_response(serialize_plan(plan))


@router.put("/{plan_id}", response_model=ApiResponse[MutationResponse])
async def update_subscription_plan(
    plan_id: str,
    payload: SubscriptionPlanRequest,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        await SubscriptionService(session).update(plan_id, payload)
    return success_response(MutationResponse())


@router.delete("/{plan_id}", response_model=ApiResponse[MutationResponse])
async def delete_subscription_plan(
    plan_id: str,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        await SubscriptionService(session).delete(plan_id)
    return success_response(MutationResponse())


@router.post("/{plan_id}/features", response_model=ApiResponse[MutationResponse])
async def set_subscription_plan_features(
    plan_id: str,
    payload: PlanFeatureRequest,
    _: object = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        await SubscriptionService(session).set_features(plan_id, payload)
    return success_response(MutationResponse())
