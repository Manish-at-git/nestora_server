"""Protected marketplace listing, engagement, and chat routes."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode
from app.core.dependencies import AuthContext, get_auth_context, require_csrf, require_role
from app.core.realtime import manager
from app.modules.notifications.service import create_notification, publish_pending_notifications
from app.core.responses import ApiResponse, success_response
from app.db.session import get_db_session
from app.db.unit_of_work import UnitOfWork
from app.modules.marketplace.schemas import (
    MarketplaceCategoryResponse,
    MarketplaceChatRequest,
    MarketplaceChatResponse,
    MarketplaceChatThreadResponse,
    MarketplaceFilters,
    MarketplaceItemRequest,
    MarketplaceItemResponse,
    MarketplaceItemUpdateRequest,
    MarketplaceMutationResponse,
    MarketplaceReportRequest,
)
from app.modules.marketplace.service import MarketplaceService


VIEW_DEP = Depends(require_role(*tuple(RoleCode)))
router = APIRouter(prefix="/marketplace", tags=["Marketplace"])


@router.get("/categories", response_model=ApiResponse[list[MarketplaceCategoryResponse]], dependencies=[VIEW_DEP])
async def categories(session: AsyncSession = Depends(get_db_session)) -> dict:
    return success_response([MarketplaceCategoryResponse(**row) for row in await MarketplaceService(session).categories()])


@router.get("/items", response_model=ApiResponse[list[MarketplaceItemResponse]], dependencies=[VIEW_DEP])
async def items(
    category_id: str | None = None, condition: str | None = None, min_price: float | None = None,
    max_price: float | None = None, is_negotiable: bool | None = None, status_filter: str | None = Query("Active", alias="status"),
    sort: str | None = "Newest", context: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_db_session),
) -> dict:
    filters = MarketplaceFilters(category_id=category_id, condition=condition, min_price=min_price, max_price=max_price, is_negotiable=is_negotiable, status=status_filter, sort=sort)
    rows = await MarketplaceService(session).list_items(context.account, filters)
    return success_response([MarketplaceItemResponse(**row) for row in rows])


@router.get("/items/my", response_model=ApiResponse[list[MarketplaceItemResponse]], dependencies=[VIEW_DEP])
async def my_items(context: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_db_session)) -> dict:
    rows = await MarketplaceService(session).my_items(context.account)
    return success_response([MarketplaceItemResponse(**row) for row in rows])


@router.get("/favorites", response_model=ApiResponse[list[MarketplaceItemResponse]], dependencies=[VIEW_DEP])
async def favorites(context: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_db_session)) -> dict:
    rows = await MarketplaceService(session).saved_items(context.account)
    return success_response([MarketplaceItemResponse(**row) for row in rows])


@router.post("/items", response_model=ApiResponse[MarketplaceMutationResponse], status_code=status.HTTP_201_CREATED, dependencies=[VIEW_DEP])
async def create_item(payload: MarketplaceItemRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        item_id = await MarketplaceService(session).create(payload, context.account)
    return success_response(MarketplaceMutationResponse(id=item_id))


@router.put("/items/{item_id}", response_model=ApiResponse[MarketplaceMutationResponse], dependencies=[VIEW_DEP])
async def update_item(item_id: str, payload: MarketplaceItemUpdateRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        await MarketplaceService(session).update(item_id, payload, context.account)
    return success_response(MarketplaceMutationResponse())


@router.delete("/items/{item_id}", response_model=ApiResponse[MarketplaceMutationResponse], dependencies=[VIEW_DEP])
async def delete_item(item_id: str, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        await MarketplaceService(session).delete(item_id, context.account)
    return success_response(MarketplaceMutationResponse())


@router.post("/favorites/{item_id}", response_model=ApiResponse[MarketplaceMutationResponse], dependencies=[VIEW_DEP])
async def toggle_favorite(item_id: str, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        saved = await MarketplaceService(session).toggle_favorite(item_id, context.account)
    return success_response(MarketplaceMutationResponse(saved=saved))


@router.post("/reports/{item_id}", response_model=ApiResponse[MarketplaceMutationResponse], status_code=status.HTTP_201_CREATED, dependencies=[VIEW_DEP])
async def report_item(item_id: str, payload: MarketplaceReportRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        report_id = await MarketplaceService(session).report(item_id, payload.reason, context.account)
    return success_response(MarketplaceMutationResponse(id=report_id))


@router.get("/chat/{item_id}/threads", response_model=ApiResponse[list[MarketplaceChatThreadResponse]], dependencies=[VIEW_DEP])
async def chat_threads(item_id: str, context: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_db_session)) -> dict:
    rows = await MarketplaceService(session).threads(item_id, context.account)
    return success_response([MarketplaceChatThreadResponse(**row) for row in rows])


@router.get("/chat/{item_id}", response_model=ApiResponse[list[MarketplaceChatResponse]], dependencies=[VIEW_DEP])
async def chat(item_id: str, buyer_id: str | None = None, context: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_db_session)) -> dict:
    rows = await MarketplaceService(session).chat(item_id, buyer_id, context.account)
    return success_response([MarketplaceChatResponse(is_mine=row["sender_id"] == context.account.id, **row) for row in rows])


@router.post("/chat/{item_id}", response_model=ApiResponse[MarketplaceChatResponse], status_code=status.HTTP_201_CREATED, dependencies=[VIEW_DEP])
async def send_chat(item_id: str, payload: MarketplaceChatRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        message = await MarketplaceService(session).send_chat(item_id, payload.message, payload.receiver_id, context.account)
        await create_notification(
            session,
            message["receiver_id"],
            "New Marketplace Message",
            "You received a new message about a marketplace listing.",
            notification_type="marketplace_chat",
            entity_type="marketplace_item",
            entity_id=item_id,
            action_url="/marketplace",
        )
    await manager.send_to_accounts(
        {message["sender_id"], message["receiver_id"]},
        {"type": "marketplace.chat.message", "item_id": item_id, "message": message},
    )
    await publish_pending_notifications(session)
    return success_response(MarketplaceChatResponse(is_mine=True, **message))


@router.post("/views/{item_id}", response_model=ApiResponse[MarketplaceMutationResponse], dependencies=[VIEW_DEP])
async def record_view(item_id: str, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)) -> dict:
    async with UnitOfWork(session):
        await MarketplaceService(session).record_view(item_id, context.account)
    return success_response(MarketplaceMutationResponse())
