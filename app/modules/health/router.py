"""Minimal liveness and readiness endpoints with the shared response contract."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.responses import ApiResponse, success_response
from app.db.session import get_db_session

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/live", response_model=ApiResponse[dict[str, str]])
async def live() -> dict:
    """Liveness intentionally avoids the database so process health remains independently visible."""
    return success_response({"status": "alive"}, "Application is alive")


@router.get("/ready", response_model=ApiResponse[dict[str, str]])
async def ready(session: AsyncSession = Depends(get_db_session)) -> dict:
    """Readiness proves that a database connection can execute a harmless query."""
    await session.execute(text("SELECT 1"))
    return success_response({"status": "ready"}, "Application is ready")
