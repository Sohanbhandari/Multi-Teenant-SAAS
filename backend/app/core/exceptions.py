"""
Global exception handling and standard error envelope.

Per docs/debugging/developer-debugging-guide.md, all API errors follow:
{
  "detail": "Human-readable message safe to display",
  "error_code": "MACHINE_READABLE_CODE",
  "request_id": "<uuid>"
}
"""

import logging
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def get_request_id(request: Request) -> str:
    """Helper to extract request ID from request state."""
    return getattr(request.state, "request_id", "unknown")


def register_exception_handlers(app: FastAPI) -> None:
    """Registers standard error response handlers on the FastAPI app."""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        req_id = get_request_id(request)
        error_code = f"HTTP_{exc.status_code}"
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            error_code = "AUTH_UNAUTHORIZED"
        elif exc.status_code == status.HTTP_403_FORBIDDEN:
            error_code = "AUTH_FORBIDDEN"
        elif exc.status_code == status.HTTP_404_NOT_FOUND:
            error_code = "NOT_FOUND"

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "error_code": error_code,
                "request_id": req_id,
            },
            headers=getattr(exc, "headers", None) or {},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        req_id = get_request_id(request)
        # Simplify validation error messages for human consumption
        errors = exc.errors()
        message = "Validation error in request parameters or body."
        if errors:
            first_err = errors[0]
            field = " -> ".join(str(loc) for loc in first_err.get("loc", []))
            message = f"Invalid field '{field}': {first_err.get('msg', 'invalid value')}"

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": message,
                "error_code": "VALIDATION_ERROR",
                "request_id": req_id,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        req_id = get_request_id(request)
        logger.exception("Unhandled server exception: %s | request_id=%s", exc, req_id)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "An internal server error occurred. Please contact support with the request ID.",
                "error_code": "INTERNAL_SERVER_ERROR",
                "request_id": req_id,
            },
        )

