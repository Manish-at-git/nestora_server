"""Exception handlers that keep framework and validation failures inside the common response shape."""

import logging
import traceback
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.messages import Message
from app.core.responses import error_response


def _is_development() -> bool:
    """Only expose diagnostic exception details in local development."""
    settings = get_settings()
    return settings.debug or settings.environment == "development"


def _development_error_data(
    request: Request,
    exc: Exception,
    *,
    detail: Any | None = None,
) -> dict[str, Any]:
    """Provide actionable diagnostics without changing production error contracts."""
    debug_data: dict[str, Any] = {
        "exception_type": type(exc).__name__,
        "exception_message": str(exc),
        "request": {
            "method": request.method,
            "path": request.url.path,
        },
        "traceback": traceback.format_exception(type(exc), exc, exc.__traceback__),
    }
    if detail is not None:
        debug_data["detail"] = detail
    return {"debug": debug_data}


def install_exception_handlers(app: FastAPI) -> None:
    """Install once during app creation so routers stay focused on business behavior."""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else Message.BAD_REQUEST
        data = (
            _development_error_data(request, exc, detail=exc.detail)
            if _is_development()
            else None
        )
        return JSONResponse(status_code=exc.status_code, content=error_response(detail, data=data))

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        data: dict[str, Any] = {"errors": exc.errors()}
        if _is_development():
            data.update(_development_error_data(request, exc, detail=exc.errors()))
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_response(Message.VALIDATION_ERROR, data=data),
        )

    @app.exception_handler(Exception)
    async def unexpected_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Hide implementation details from callers while retaining the exception in server logs."""
        logging.getLogger("nestora.server").exception("Unhandled API exception", exc_info=exc)
        is_development = _is_development()
        data = _development_error_data(request, exc) if is_development else None
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response(Message.INTERNAL_ERROR, data=data),
        )
