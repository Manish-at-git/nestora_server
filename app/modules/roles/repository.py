"""Database access for roles; transaction ownership stays with the service router."""

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.modules.auth.models import Account
from app.modules.iam.models import Role


class RoleRepository:
    """Small query and persistence boundary for role records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self) -> list[Role]:
        """Return active roles newest first with their optional entity scope loaded."""
        statement: Select[tuple[Role]] = (
            select(Role)
            .options(joinedload(Role.entity))
            .where(Role.is_deleted.is_(False))
            .order_by(Role.created_at.desc())
        )
        return list((await self.session.scalars(statement)).all())

    async def get(self, role_id: str) -> Role | None:
        """Load one active role by its stable identifier."""
        statement = (
            select(Role)
            .options(joinedload(Role.entity))
            .where(Role.id == role_id, Role.is_deleted.is_(False))
        )
        return await self.session.scalar(statement)

    async def name_exists(self, name: str, excluding_id: str | None = None) -> bool:
        """Check active role names case-insensitively."""
        statement = select(Role.id).where(
            func.lower(Role.name) == name.lower(),
            Role.is_deleted.is_(False),
        )
        if excluding_id is not None:
            statement = statement.where(Role.id != excluding_id)
        return await self.session.scalar(statement) is not None

    async def code_exists(self, code: str, excluding_id: str | None = None) -> bool:
        """Check active role codes case-insensitively."""
        statement = select(Role.id).where(
            func.lower(Role.code) == code.lower(),
            Role.is_deleted.is_(False),
        )
        if excluding_id is not None:
            statement = statement.where(Role.id != excluding_id)
        return await self.session.scalar(statement) is not None

    async def has_account_assignment(self, role_id: str) -> bool:
        """Prevent deleting a role still assigned to any account."""
        statement = select(Account.id).where(Account.role_id == role_id).limit(1)
        return await self.session.scalar(statement) is not None

    def add(self, role: Role) -> None:
        """Stage a new role for the surrounding unit of work."""
        self.session.add(role)

    async def soft_delete(self, role: Role) -> None:
        """Mark a role deleted while retaining its permissions and audit history."""
        role.is_deleted = True
        role.is_active = False
        await self.session.flush()
