"""Database access for role-feature permission assignments."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, joinedload

from app.modules.auth.models import Account
from app.modules.iam.models import Feature, Role, RoleFeaturePermission


class PermissionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, permission_id: str) -> RoleFeaturePermission | None:
        return await self.session.scalar(
            select(RoleFeaturePermission).where(
                RoleFeaturePermission.id == permission_id,
                RoleFeaturePermission.is_deleted.is_(False),
            )
        )

    async def find_active(self, role_id: str, feature_id: str, excluding_id: str | None = None):
        statement = select(RoleFeaturePermission).where(
            RoleFeaturePermission.role_id == role_id,
            RoleFeaturePermission.feature_id == feature_id,
            RoleFeaturePermission.is_deleted.is_(False),
        )
        if excluding_id:
            statement = statement.where(RoleFeaturePermission.id != excluding_id)
        return await self.session.scalar(statement)

    async def find_any(self, role_id: str, feature_id: str):
        """Find an assignment including soft-deleted history for safe restoration."""
        return await self.session.scalar(
            select(RoleFeaturePermission).where(
                RoleFeaturePermission.role_id == role_id,
                RoleFeaturePermission.feature_id == feature_id,
            )
        )

    async def role_exists(self, role_id: str) -> bool:
        return await self.session.scalar(
            select(Role.id).where(Role.id == role_id, Role.is_deleted.is_(False))
        ) is not None

    async def feature_exists(self, feature_id: str) -> bool:
        return await self.session.scalar(
            select(Feature.id).where(
                Feature.id == feature_id,
                Feature.is_deleted.is_(False),
                Feature.is_active.is_(True),
            )
        ) is not None

    async def list(self) -> list[tuple[RoleFeaturePermission, str | None, str | None]]:
        statement = (
            select(RoleFeaturePermission, Role.name, Feature.name)
            .join(Role, Role.id == RoleFeaturePermission.role_id)
            .join(Feature, Feature.id == RoleFeaturePermission.feature_id)
            .where(
                RoleFeaturePermission.is_deleted.is_(False),
                Role.is_deleted.is_(False),
                Feature.is_deleted.is_(False),
            )
            .order_by(RoleFeaturePermission.created_at.desc())
        )
        return list((await self.session.execute(statement)).tuples())

    async def summary(self) -> list[dict]:
        configured = (
            select(
                RoleFeaturePermission.role_id,
                func.count(func.distinct(RoleFeaturePermission.feature_id)).label("configured"),
            )
            .where(
                RoleFeaturePermission.is_deleted.is_(False),
                (
                    RoleFeaturePermission.can_create.is_(True)
                    | RoleFeaturePermission.can_view.is_(True)
                    | RoleFeaturePermission.can_update.is_(True)
                    | RoleFeaturePermission.can_delete.is_(True)
                ),
            )
            .group_by(RoleFeaturePermission.role_id)
            .subquery()
        )
        statement = (
            select(
                Role,
                configured.c.configured,
                func.count(func.distinct(Account.id)).label("accounts_count"),
            )
            .options(joinedload(Role.entity))
            .outerjoin(configured, configured.c.role_id == Role.id)
            .outerjoin(Account, Account.role_id == Role.id)
            .where(Role.is_deleted.is_(False))
            .group_by(Role.id, configured.c.configured)
            .order_by(Role.created_at.desc())
        )
        feature_count = await self.session.scalar(
            select(func.count(Feature.id)).where(Feature.is_deleted.is_(False), Feature.is_active.is_(True))
        )
        rows = []
        for role, configured_count, accounts_count in (await self.session.execute(statement)).tuples():
            rows.append(
                {
                    "role": role,
                    "configured": configured_count or 0,
                    "accounts": accounts_count or 0,
                    "features": feature_count or 0,
                }
            )
        return rows

    async def matrix(self, role_id: str) -> list[dict]:
        parent = aliased(Feature)
        statement = (
            select(Feature, parent.name, RoleFeaturePermission)
            .outerjoin(parent, parent.id == Feature.parent_id)
            .outerjoin(
                RoleFeaturePermission,
                (RoleFeaturePermission.feature_id == Feature.id)
                & (RoleFeaturePermission.role_id == role_id)
                & RoleFeaturePermission.is_deleted.is_(False),
            )
            .where(Feature.is_deleted.is_(False), Feature.is_active.is_(True))
            .order_by(Feature.name)
        )
        return list((await self.session.execute(statement)).tuples())

    async def soft_delete(self, permission: RoleFeaturePermission) -> None:
        permission.is_deleted = True
        await self.session.flush()
