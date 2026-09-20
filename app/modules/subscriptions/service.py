"""Subscription plan business rules and feature assignment operations."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.subscriptions.messages import SubscriptionMessage
from app.modules.subscriptions.models import SubscriptionPlan
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.schemas import PlanFeatureRequest, SubscriptionPlanRequest


class SubscriptionService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = SubscriptionRepository(session)

    async def _validate(self, payload: SubscriptionPlanRequest, excluding_id: str | None = None) -> None:
        if await self.repository.name_exists(payload.name, payload.country, excluding_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, SubscriptionMessage.NAME_EXISTS)
        if await self.repository.code_exists(payload.code, excluding_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, SubscriptionMessage.CODE_EXISTS)

    async def list(self) -> list[SubscriptionPlan]:
        return await self.repository.list()

    async def create(self, payload: SubscriptionPlanRequest) -> SubscriptionPlan:
        await self._validate(payload)
        plan = SubscriptionPlan(id=str(uuid.uuid4()), **payload.model_dump())
        self.repository.session.add(plan)
        await self.repository.session.flush()
        return await self.repository.get(plan.id) or plan

    async def update(self, plan_id: str, payload: SubscriptionPlanRequest) -> SubscriptionPlan:
        plan = await self.repository.get(plan_id)
        if plan is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, SubscriptionMessage.NOT_FOUND)
        await self._validate(payload, plan_id)
        for key, value in payload.model_dump().items():
            setattr(plan, key, value)
        await self.repository.session.flush()
        return plan

    async def delete(self, plan_id: str) -> None:
        plan = await self.repository.get(plan_id)
        if plan is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, SubscriptionMessage.NOT_FOUND)
        plan.is_deleted = True
        plan.is_active = False
        await self.repository.session.flush()

    async def set_features(self, plan_id: str, payload: PlanFeatureRequest) -> None:
        plan = await self.repository.get(plan_id)
        if plan is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, SubscriptionMessage.NOT_FOUND)
        if not await self.repository.features_exist(payload.feature_ids):
            raise HTTPException(status.HTTP_404_NOT_FOUND, SubscriptionMessage.FEATURE_NOT_FOUND)
        await self.repository.replace_features(plan, payload.feature_ids)
