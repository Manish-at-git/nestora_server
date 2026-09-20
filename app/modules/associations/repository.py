"""Association directory queries and aggregate statistics."""

import uuid
from datetime import date

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.constants import RoleCode
from app.modules.associations.models import Association
from app.modules.subscriptions.models import SubscriptionPlanFeature
from app.modules.iam.models import Feature


class AssociationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self, account_id: str, role_code: str) -> list[Association]:
        statement = (
            select(Association)
            .options(selectinload(Association.plan))
            .where(Association.is_deleted.is_(False))
            .order_by(Association.created_at.desc())
        )
        if role_code in {RoleCode.ADMIN, RoleCode.ACCOUNTANT}:
            scoped_ids = select(text("association_id")).select_from(text("admin_associations")).where(
                text("admin_id = :account_id")
            ).params(account_id=account_id)
            statement = statement.where(Association.id.in_(scoped_ids))
        elif role_code == RoleCode.BOARD_MEMBER:
            scoped_ids = select(text("association_id")).select_from(text("board_members")).where(
                text("account_id = :account_id AND status = 'active' AND is_deleted = 0")
            ).params(account_id=account_id)
            statement = statement.where(Association.id.in_(scoped_ids))
        return list((await self.session.scalars(statement)).all())

    async def get(self, association_id: str) -> Association | None:
        return await self.session.scalar(
            select(Association)
            .options(selectinload(Association.plan))
            .where(Association.id == association_id, Association.is_deleted.is_(False))
        )

    async def association_ids_for_admin(self, account_id: str) -> list[str]:
        result = await self.session.scalars(
            text("SELECT association_id FROM admin_associations WHERE admin_id = :account_id"),
            {"account_id": account_id},
        )
        return list(result.all())

    async def unit_count(self, association_id: str) -> int:
        result = await self.session.scalar(
            text(
                "SELECT COUNT(*) FROM units u JOIN blocks b ON u.block_id = b.id "
                "WHERE b.association_id = :association_id"
            ).bindparams(association_id=association_id)
        )
        return int(result or 0)

    async def stats(self, association_id: str) -> dict:
        blocks = await self.session.scalar(
            text("SELECT COUNT(*) FROM blocks WHERE association_id = :id").bindparams(id=association_id)
        )
        units = await self.session.scalar(
            text(
                "SELECT COUNT(*) FROM units u JOIN blocks b ON u.block_id=b.id "
                "WHERE b.association_id=:id"
            ).bindparams(id=association_id)
        )
        rented = await self.session.scalar(
            text(
                "SELECT COUNT(*) FROM units u JOIN blocks b ON u.block_id=b.id "
                "WHERE b.association_id=:id AND u.is_rented=1"
            ).bindparams(id=association_id)
        )
        floors = list(
            (
                await self.session.execute(
                    text(
                        "SELECT b.name AS block_name, COUNT(DISTINCT u.floor) AS floors "
                        "FROM units u JOIN blocks b ON u.block_id=b.id "
                        "WHERE b.association_id=:id GROUP BY b.id, b.name"
                    ).bindparams(id=association_id)
                )
            ).mappings()
        )
        return {
            "total_blocks": int(blocks or 0),
            "total_units": int(units or 0),
            "rented_units": int(rented or 0),
            "floors_per_block": floors,
        }

    async def settings(self, association_id: str) -> dict | None:
        association = await self.session.execute(
            text(
                "SELECT COALESCE(onboarding_date, subscription_start, DATE(created_at)) AS onboarding_date, "
                "end_date FROM associations "
                "WHERE id = :association_id AND is_deleted = 0"
            ),
            {"association_id": association_id},
        )
        row = association.mappings().first()
        if row is None:
            return None

        assessment = await self.session.execute(
            text(
                "SELECT frequency, default_amount, due_day_of_month FROM assessment_rules "
                "WHERE association_id = :association_id LIMIT 1"
            ),
            {"association_id": association_id},
        )
        fines = await self.session.execute(
            text(
                "SELECT id, fine_type, amount, grace_period_days FROM fine_rules "
                "WHERE association_id = :association_id ORDER BY id"
            ),
            {"association_id": association_id},
        )
        assessment_row = assessment.mappings().first()
        return {
            **dict(row),
            "assessment_rules": dict(assessment_row) if assessment_row else None,
            "fine_rules": [dict(fine) for fine in fines.mappings().all()],
        }

    async def update_settings(
        self,
        association_id: str,
        end_date: date | None,
        assessment_rules: dict | None,
        fine_rules: list[dict] | None,
        update_end_date: bool,
    ) -> bool:
        if not await self.get(association_id):
            return False

        if update_end_date:
            await self.session.execute(
                text("UPDATE associations SET end_date = :end_date WHERE id = :association_id"),
                {"association_id": association_id, "end_date": end_date},
            )

        if assessment_rules is not None:
            existing = await self.session.scalar(
                text(
                    "SELECT id FROM assessment_rules WHERE association_id = :association_id LIMIT 1"
                ),
                {"association_id": association_id},
            )
            values = {"association_id": association_id, **assessment_rules}
            if existing:
                await self.session.execute(
                    text(
                        "UPDATE assessment_rules SET frequency = :frequency, "
                        "default_amount = :default_amount, due_day_of_month = :due_day_of_month "
                        "WHERE association_id = :association_id"
                    ),
                    values,
                )
            else:
                await self.session.execute(
                    text(
                        "INSERT INTO assessment_rules "
                        "(id, association_id, frequency, default_amount, due_day_of_month) "
                        "VALUES (:id, :association_id, :frequency, :default_amount, :due_day_of_month)"
                    ),
                    {"id": str(uuid.uuid4()), **values},
                )

        if fine_rules is not None:
            await self.session.execute(
                text("DELETE FROM fine_rules WHERE association_id = :association_id"),
                {"association_id": association_id},
            )
            for fine_rule in fine_rules:
                await self.session.execute(
                    text(
                        "INSERT INTO fine_rules "
                        "(id, association_id, fine_type, amount, grace_period_days) "
                        "VALUES (:id, :association_id, :fine_type, :amount, :grace_period_days)"
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "association_id": association_id,
                        **fine_rule,
                    },
                )
        return True

    async def allowed_features(self, plan_id: str | None) -> list[str]:
        if not plan_id:
            return []
        result = await self.session.scalars(
            select(Feature.name)
            .join(SubscriptionPlanFeature, SubscriptionPlanFeature.feature_id == Feature.id)
            .where(
                SubscriptionPlanFeature.plan_id == plan_id,
                SubscriptionPlanFeature.is_deleted.is_(False),
                Feature.is_deleted.is_(False),
            )
        )
        return list(result.all())
