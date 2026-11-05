"""
Custom ASGI / Starlette middleware.

Includes:
- RequestIDMiddleware: Generates or extracts a correlation ID for every request,
  stores it in request.state.request_id, and attaches it as X-Request-ID response header.
"""

import uuid
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware that assigns a unique UUID to every incoming HTTP request.
    If the client provided an X-Request-ID header, it is preserved.
    """
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming_request_id = request.headers.get("X-Request-ID")
        request_id = incoming_request_id or str(uuid.uuid4())

        # Store in request state for downstream handlers and logging
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

