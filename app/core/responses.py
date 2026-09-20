"""Reusable API response envelope so every endpoint returns the same outer structure."""

from typing import Any, Generic, TypeVar

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """The standard successful or unsuccessful API response contract."""

    success: bool
    message: str
    data: T | None = None
    meta: dict[str, Any] | None = None


def success_response(data: T | None = None, message: str = "Success") -> dict[str, Any]:
    """Create JSON-safe success payloads with optional endpoint-specific data."""
    return jsonable_encoder(ApiResponse[T](success=True, message=message, data=data).model_dump())


def error_response(message: str, data: Any | None = None) -> dict[str, Any]:
    """Create JSON-safe error payloads using the same shape as success responses."""
    return jsonable_encoder(ApiResponse[Any](success=False, message=message, data=data).model_dump())
