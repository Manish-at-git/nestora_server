"""Role-aware dashboard and legacy dashboard compatibility routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleCode
from app.core.dependencies import AuthContext, get_auth_context, require_role
from app.core.responses import success_response
from app.db.session import get_db_session
from app.modules.dashboard.schemas import (
    DashboardStatsApiResponse,
    DashboardStatsResponse,
    TimelineResponse,
)
from app.modules.dashboard.service import DashboardService


router = APIRouter(tags=["Dashboards"])


@router.get("/timeline", response_model=TimelineResponse)
@router.get("/dashboard/timeline", response_model=TimelineResponse)
async def timeline(
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    context: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    items = await DashboardService(session).timeline(context.account, limit, offset)
    payload = success_response(items)
    payload["ok"] = True
    return payload


@router.get(
    "/admin/stats",
    response_model=DashboardStatsApiResponse,
    dependencies=[Depends(require_role(RoleCode.SUPER_ADMIN, RoleCode.ADMIN))],
)
async def admin_dashboard_stats(session: AsyncSession = Depends(get_db_session)) -> dict:
    stats = await DashboardService(session).access_code_stats()
    return success_response(DashboardStatsResponse(**stats))
