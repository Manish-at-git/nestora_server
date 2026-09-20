"""User creation, activation-code delivery, updates, and soft deletion."""

import logging
import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.messages import UserMessage
from app.modules.users.models import UserCode, UserDetail
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserCreateRequest, UserUpdateRequest

logger = logging.getLogger("nestora.server.users")


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = UserRepository(session)

    async def list(self) -> list[dict]:
        return await self.repository.list()

    async def create(self, payload: UserCreateRequest) -> str:
        email = str(payload.email).lower()
        if await self.repository.email_exists(email):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, UserMessage.EMAIL_EXISTS)
        if await self.repository.role(payload.role_id) is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, UserMessage.ROLE_NOT_FOUND)
        if not await self.repository.association_exists(payload.association_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, UserMessage.ASSOCIATION_NOT_FOUND)
        code = await self.repository.create_code()
        user = UserDetail(
            user_id=str(uuid.uuid4()),
            code_id=code.id,
            name=f"{payload.first_name.strip()} {payload.last_name.strip()}",
            address="",
            email=email,
            contact_number=payload.contact_number.strip(),
            first_name=payload.first_name.strip(),
            last_name=payload.last_name.strip(),
            role_id=payload.role_id,
            association_id=payload.association_id,
            is_deleted=False,
        )
        self.repository.add_user(user)
        await self.repository.session.flush()
        return code.login_code

    async def update(self, user_id: str, payload: UserUpdateRequest) -> None:
        user = await self.repository.get(user_id)
        if user is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, UserMessage.NOT_FOUND)
        email = str(payload.email).lower() if payload.email else user.email
        if email != user.email and await self.repository.email_exists(email, excluding_user_id=user_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, UserMessage.EMAIL_EXISTS)
        if payload.association_id and not await self.repository.association_exists(payload.association_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, UserMessage.ASSOCIATION_NOT_FOUND)
        if payload.role_name:
            role = await self.repository.role(role_name=payload.role_name.strip())
            if role is None:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, UserMessage.ROLE_NOT_FOUND)
            user.role_id = role.id
            account = await self.repository.find_account(user_id)
            if account:
                account.role_id = role.id
        if payload.association_id and payload.block_name and payload.unit_number:
            if not await self.repository.block_exists(payload.association_id, payload.block_name):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, UserMessage.BLOCK_NOT_FOUND)
            unit_id = await self.repository.find_unit(
                payload.association_id, payload.block_name, payload.unit_number
            )
            if unit_id is None:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, UserMessage.UNIT_NOT_FOUND)
            user.unit_id = unit_id
        if payload.email:
            user.email = email
            await self.repository.update_account_email(user_id, email)
        if payload.contact_number:
            user.contact_number = payload.contact_number.strip()
        if payload.association_id:
            user.association_id = payload.association_id
        await self.repository.session.flush()

    async def send_code(self, user_id: str) -> None:
        user = await self.repository.get(user_id)
        if user is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, UserMessage.NOT_FOUND)
        if not user.code_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, UserMessage.CODE_NOT_FOUND)
        code = await self.repository.session.get(UserCode, user.code_id)
        if code is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, UserMessage.CODE_NOT_FOUND)
        if not user.email:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, UserMessage.EMAIL_REQUIRED)
        # Delivery remains safe in development; configure SMTP before enabling
        # outbound activation-code email.
        logger.info("Activation code requested for user %s", user_id)

    async def delete(self, user_id: str) -> None:
        user = await self.repository.get(user_id)
        if user is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, UserMessage.NOT_FOUND)
        user.is_deleted = True
        await self.repository.session.flush()
