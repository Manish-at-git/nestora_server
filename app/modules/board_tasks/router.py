"""HTTP routes for board tasks and their message threads."""

from fastapi import APIRouter, Depends, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthContext, get_auth_context, require_csrf
from app.core.realtime import manager
from app.modules.notifications.service import publish_pending_notifications
from app.core.responses import ApiResponse, success_response
from app.db.session import get_db_session
from app.db.unit_of_work import UnitOfWork
from app.modules.board_tasks.messages import BoardTaskMessage
from app.modules.board_tasks.schemas import (
    BoardMemberResponse,
    BoardTaskCreateRequest,
    BoardTaskCreateResponse,
    BoardTaskMessageCreateResponse,
    BoardTaskMessageRequest,
    BoardTaskMessageResponse,
    BoardTaskMutationResponse,
    BoardTaskResponse,
    BoardTaskStatusRequest,
)
from app.modules.board_tasks.service import BoardTaskService


router = APIRouter(tags=["Board Tasks"])


@router.post("/board-tasks", response_model=ApiResponse[BoardTaskCreateResponse], status_code=status.HTTP_201_CREATED)
async def create_board_task(
    payload: BoardTaskCreateRequest,
    context: AuthContext = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        task_id = await BoardTaskService(session).create(payload, context.account)
    await publish_pending_notifications(session)
    return success_response(BoardTaskCreateResponse(id=task_id), BoardTaskMessage.CREATED)


@router.get("/board-tasks", response_model=ApiResponse[list[BoardTaskResponse]])
async def list_board_tasks(
    association_id: str | None = None,
    context: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    rows = await BoardTaskService(session).list(context.account, association_id)
    return success_response([BoardTaskResponse(**row) for row in rows])


@router.get("/board-tasks/{task_id}", response_model=ApiResponse[BoardTaskResponse])
async def get_board_task(
    task_id: str,
    context: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    row = await BoardTaskService(session).detail(task_id, context.account)
    return success_response(BoardTaskResponse(**row))


@router.patch("/board-tasks/{task_id}/status", response_model=ApiResponse[BoardTaskMutationResponse])
async def update_board_task_status(
    task_id: str,
    payload: BoardTaskStatusRequest,
    context: AuthContext = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        await BoardTaskService(session).update_status(task_id, payload.status, context.account)
    await publish_pending_notifications(session)
    return success_response(BoardTaskMutationResponse(), BoardTaskMessage.UPDATED)


@router.delete("/board-tasks/{task_id}", response_model=ApiResponse[BoardTaskMutationResponse])
async def delete_board_task(
    task_id: str,
    context: AuthContext = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        await BoardTaskService(session).delete(task_id, context.account)
    return success_response(BoardTaskMutationResponse(), BoardTaskMessage.UPDATED)


@router.get("/board-tasks/{task_id}/messages", response_model=ApiResponse[list[BoardTaskMessageResponse]])
async def list_board_task_messages(
    task_id: str,
    context: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    rows = await BoardTaskService(session).messages(task_id, context.account)
    return success_response([BoardTaskMessageResponse(**row) for row in rows])


@router.post(
    "/board-tasks/{task_id}/messages",
    response_model=ApiResponse[BoardTaskMessageCreateResponse],
    status_code=status.HTTP_201_CREATED,
)
async def send_board_task_message(
    task_id: str,
    payload: BoardTaskMessageRequest,
    context: AuthContext = Depends(require_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    async with UnitOfWork(session):
        event = await BoardTaskService(session).send_message(task_id, payload, context.account)
    await manager.send_to_accounts(
        event.recipient_account_ids,
        {
            "type": "board_task.message",
            "task_id": event.task_id,
            "message": jsonable_encoder(event.message),
        },
    )
    await publish_pending_notifications(session)
    return success_response(
        BoardTaskMessageCreateResponse(id=event.message["id"]),
        BoardTaskMessage.MESSAGE_SENT,
    )


@router.get("/associations/{association_id}/board-members", response_model=ApiResponse[list[BoardMemberResponse]])
async def association_board_members(
    association_id: str,
    context: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    rows = await BoardTaskService(session).board_members(association_id, context.account)
    return success_response([BoardMemberResponse(**row) for row in rows])
