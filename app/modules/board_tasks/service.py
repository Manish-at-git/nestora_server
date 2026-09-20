"""Authorization and workflow rules for board tasks."""

import uuid
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode
from app.modules.auth.models import Account
from app.modules.board_tasks.constants import (
    BOARD_TASK_ADMIN_ROLES,
    BOARD_TASK_MANAGER_ROLES,
    BoardTaskStatus,
)
from app.modules.board_tasks.messages import BoardTaskMessage as Messages
from app.modules.board_tasks.models import BoardTask, BoardTaskMessage
from app.modules.board_tasks.repository import BoardTaskRepository
from app.modules.notifications.service import notify_accounts
from app.modules.board_tasks.schemas import BoardTaskCreateRequest, BoardTaskMessageRequest


@dataclass(frozen=True)
class BoardTaskMessageEvent:
    task_id: str
    message: dict
    recipient_account_ids: set[str]


class BoardTaskService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = BoardTaskRepository(session)

    @staticmethod
    def role_code(account: Account) -> RoleCode:
        if account.role is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.FORBIDDEN)
        try:
            return RoleCode(account.role.code)
        except ValueError as exc:
            raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.FORBIDDEN) from exc

    async def list(self, account: Account, association_id: str | None = None) -> list[dict]:
        role_code = self.role_code(account)
        if role_code in BOARD_TASK_ADMIN_ROLES:
            allowed = await self.repository.association_ids_for_admin(account.id)
            if role_code == RoleCode.SUPER_ADMIN:
                allowed = None
            if association_id and association_id != "ALL":
                if allowed is not None and association_id not in allowed:
                    raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.FORBIDDEN)
                return await self.repository.list([association_id])
            return await self.repository.list(allowed)
        if role_code == RoleCode.BOARD_MEMBER:
            member_association = await self.repository.member_association_id(account)
            if not member_association:
                return []
            if association_id and association_id not in {"ALL", member_association}:
                raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.FORBIDDEN)
            return await self.repository.list([member_association])
        return []

    async def detail(self, task_id: str, account: Account) -> dict:
        task = await self._authorized_task(task_id, account)
        detail = await self.repository.get(task.id)
        if detail is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, Messages.NOT_FOUND)
        return detail

    async def create(self, payload: BoardTaskCreateRequest, account: Account) -> str:
        role_code = self.role_code(account)
        if role_code not in BOARD_TASK_MANAGER_ROLES:
            raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.FORBIDDEN)
        association_id = payload.association_id
        if not association_id or association_id == "me":
            if role_code != RoleCode.BOARD_MEMBER:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, Messages.INVALID_ASSOCIATION)
            association_id = await self.repository.member_association_id(account)
        if not association_id or not await self.repository.association_exists(association_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, Messages.INVALID_ASSOCIATION)
        await self._require_association_access(account, association_id)
        if not await self.repository.board_member(payload.supervised_by, association_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, Messages.INVALID_SUPERVISOR)
        task = BoardTask(
            id=str(uuid.uuid4()),
            association_id=association_id,
            created_by=account.id,
            title=payload.title,
            description=payload.description,
            supervised_by=payload.supervised_by,
            image_url=payload.image_url,
            status=BoardTaskStatus.NEW,
            is_deleted=False,
        )
        self.repository.add(task)
        await self.repository.session.flush()
        participants = await self.repository.participant_account_ids(task)
        await notify_accounts(
            self.repository.session,
            participants,
            "New Board Task Created",
            f"A new board task '{task.title}' was created.",
            account.id,
            notification_type="board_task",
            entity_type="board_task",
            entity_id=task.id,
            action_url="/board-tasks",
        )
        return task.id

    async def update_status(
        self,
        task_id: str,
        new_status: BoardTaskStatus,
        account: Account,
    ) -> None:
        if self.role_code(account) not in BOARD_TASK_MANAGER_ROLES:
            raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.FORBIDDEN)
        task = await self._authorized_task(task_id, account)
        task.status = new_status.value
        await self.repository.session.flush()
        recipients = {task.created_by, task.supervised_by}
        await notify_accounts(
            self.repository.session,
            recipients,
            "Board Task Updated",
            f"The status of '{task.title}' was changed to {new_status.value}.",
            account.id,
            notification_type="board_task",
            entity_type="board_task",
            entity_id=task.id,
            action_url="/board-tasks",
        )

    async def delete(self, task_id: str, account: Account) -> None:
        if self.role_code(account) not in BOARD_TASK_ADMIN_ROLES:
            raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.FORBIDDEN)
        task = await self._authorized_task(task_id, account)
        task.is_deleted = True
        await self.repository.session.flush()

    async def messages(self, task_id: str, account: Account) -> list[dict]:
        task = await self._authorized_task(task_id, account)
        return await self.repository.messages(task.id)

    async def send_message(
        self,
        task_id: str,
        payload: BoardTaskMessageRequest,
        account: Account,
    ) -> BoardTaskMessageEvent:
        task = await self._authorized_task(task_id, account)
        message = BoardTaskMessage(
            id=str(uuid.uuid4()),
            board_task_id=task.id,
            sender_id=account.id,
            message=payload.message,
            attachment_url=payload.attachment_url,
            is_deleted=False,
        )
        self.repository.add_message(message)
        await self.repository.session.flush()
        recipients = await self.repository.participant_account_ids(task)
        await notify_accounts(
            self.repository.session,
            recipients,
            "New message on Board Task",
            f"New message on '{task.title}'.",
            account.id,
            notification_type="board_task",
            entity_type="board_task",
            entity_id=task.id,
            action_url="/board-tasks",
        )
        recipients.discard(account.id)
        event_message = await self.repository.message_event(message.id)
        if event_message is None:
            raise RuntimeError("Persisted board-task message could not be loaded")
        return BoardTaskMessageEvent(task.id, event_message, recipients)

    async def board_members(self, association_id: str, account: Account) -> list[dict]:
        if association_id == "me":
            member_association = await self.repository.member_association_id(account)
            if not member_association:
                raise HTTPException(status.HTTP_404_NOT_FOUND, Messages.INVALID_ASSOCIATION)
            association_id = member_association
        role_code = self.role_code(account)
        if role_code in {RoleCode.HOMEOWNER, RoleCode.TENANT, RoleCode.COMMITTEE_MEMBER}:
            if await self.repository.member_association_id(account) != association_id:
                raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.INVALID_ASSOCIATION)
        else:
            await self._require_association_access(account, association_id)
        return await self.repository.board_members(association_id)

    async def _authorized_task(self, task_id: str, account: Account) -> BoardTask:
        task = await self.repository.task_model(task_id)
        if task is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, Messages.NOT_FOUND)
        role_code = self.role_code(account)
        if role_code == RoleCode.SUPER_ADMIN:
            return task
        if role_code == RoleCode.ADMIN:
            await self._require_admin_association(account, task.association_id)
            return task
        if role_code == RoleCode.BOARD_MEMBER:
            association_id = await self.repository.member_association_id(account)
            if association_id != task.association_id:
                raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.FORBIDDEN)
            return task
        raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.FORBIDDEN)

    async def _require_admin_association(self, account: Account, association_id: str) -> None:
        role_code = self.role_code(account)
        if role_code == RoleCode.SUPER_ADMIN:
            return
        if role_code != RoleCode.ADMIN:
            raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.FORBIDDEN)
        allowed = await self.repository.association_ids_for_admin(account.id)
        if association_id not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.INVALID_ASSOCIATION)

    async def _require_association_access(self, account: Account, association_id: str) -> None:
        role_code = self.role_code(account)
        if role_code == RoleCode.SUPER_ADMIN:
            return
        if role_code == RoleCode.ADMIN:
            await self._require_admin_association(account, association_id)
            return
        if role_code == RoleCode.BOARD_MEMBER:
            if await self.repository.member_association_id(account) != association_id:
                raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.INVALID_ASSOCIATION)
            return
        raise HTTPException(status.HTTP_403_FORBIDDEN, Messages.FORBIDDEN)
