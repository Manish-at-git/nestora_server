"""Database access for subscription plans and feature assignments."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.iam.models import Feature
from app.modules.subscriptions.models import SubscriptionPlan, SubscriptionPlanFeature


class SubscriptionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self) -> list[SubscriptionPlan]:
        statement = (
            select(SubscriptionPlan)
            .options(selectinload(SubscriptionPlan.feature_assignments))
            .where(SubscriptionPlan.is_deleted.is_(False))
            .order_by(SubscriptionPlan.created_at.desc())
        )
        return list((await self.session.scalars(statement)).all())

    async def get(self, plan_id: str) -> SubscriptionPlan | None:
        statement = (
            select(SubscriptionPlan)
            .options(selectinload(SubscriptionPlan.feature_assignments))
            .where(SubscriptionPlan.id == plan_id, SubscriptionPlan.is_deleted.is_(False))
        )
        return await self.session.scalar(statement)

    async def name_exists(self, name: str, country: str, excluding_id: str | None = None) -> bool:
        statement = select(SubscriptionPlan.id).where(
            func.lower(SubscriptionPlan.name) == name.lower(),
            SubscriptionPlan.country == country,
            SubscriptionPlan.is_deleted.is_(False),
        )
        if excluding_id:
            statement = statement.where(SubscriptionPlan.id != excluding_id)
        return await self.session.scalar(statement) is not None

    async def code_exists(self, code: str | None, excluding_id: str | None = None) -> bool:
        if not code:
            return False
        statement = select(SubscriptionPlan.id).where(
            func.lower(SubscriptionPlan.code) == code.lower(),
            SubscriptionPlan.is_deleted.is_(False),
        )
        if excluding_id:
            statement = statement.where(SubscriptionPlan.id != excluding_id)
        return await self.session.scalar(statement) is not None

    async def features_exist(self, feature_ids: list[str]) -> bool:
        if not feature_ids:
            return True
        count = await self.session.scalar(
            select(func.count(Feature.id)).where(
                Feature.id.in_(feature_ids),
                Feature.is_deleted.is_(False),
                Feature.is_active.is_(True),
            )
        )
        return count == len(set(feature_ids))

    async def replace_features(self, plan: SubscriptionPlan, feature_ids: list[str]) -> None:
        for assignment in plan.feature_assignments:
            assignment.is_deleted = True
        existing = {
            assignment.feature_id: assignment for assignment in plan.feature_assignments
        }
        for feature_id in dict.fromkeys(feature_ids):
            assignment = existing.get(feature_id)
            if assignment is None:
                assignment = SubscriptionPlanFeature(plan_id=plan.id, feature_id=feature_id)
                self.session.add(assignment)
            else:
                assignment.is_deleted = False
        await self.session.flush()
