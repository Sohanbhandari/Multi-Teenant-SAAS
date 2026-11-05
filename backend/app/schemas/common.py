"""
Common Pydantic v2 schemas used across all API resources.

Includes:
- Standard error response envelope
- Health check response
- Generic paginated response wrapper
"""

from typing import Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorResponse(BaseModel):
    """Standard error response format for all 4xx/5xx responses."""
    detail: str = Field(..., description="Human-readable error description safe to display in UI")
    error_code: str = Field(..., description="Machine-readable error identifier")
    request_id: str = Field(..., description="Correlation UUID for tracing the request in logs")


class HealthResponse(BaseModel):
    """Payload returned by the GET /health endpoint."""
    status: str = Field(..., example="ok")
    environment: str = Field(..., example="development")
    version: str = Field(..., example="0.1.0")
    database: str = Field(..., example="connected")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated envelope for list endpoints."""
    items: list[T]
    total: int = Field(..., ge=0)
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)
    total_pages: int = Field(..., ge=0)

