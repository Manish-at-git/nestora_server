"""Exception handlers that keep framework and validation failures inside the common response shape."""

import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.messages import Message
from app.core.responses import error_response


def install_exception_handlers(app: FastAPI) -> None:
    """Install once during app creation so routers stay focused on business behavior."""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else Message.BAD_REQUEST
        return JSONResponse(status_code=exc.status_code, content=error_response(detail))

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_response(Message.VALIDATION_ERROR, data={"errors": exc.errors()}),
        )

    @app.exception_handler(Exception)
    async def unexpected_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        """Hide implementation details from callers while retaining the exception in server logs."""
        logging.getLogger("nestora.server").exception("Unhandled API exception", exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response(Message.INTERNAL_ERROR),
        )
