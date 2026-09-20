"""Response contracts for dashboard compatibility endpoints."""

from typing import Any

from pydantic import BaseModel

from app.core.responses import ApiResponse


class DashboardStatsResponse(BaseModel):
    total_codes: int = 0
    used_codes: int = 0
    pending_requests: int = 0
    members: int = 0
    open_update_requests: int = 0


class TimelineResponse(ApiResponse[list[dict[str, Any]]]):
    """Standard envelope plus the legacy timeline success flag."""

    ok: bool = True


DashboardStatsApiResponse = ApiResponse[DashboardStatsResponse]
