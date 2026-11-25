from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import settings


class LimitRequestBodyMiddleware(BaseHTTPMiddleware):
    """Reject oversized bodies early (mirror this limit on any reverse proxy)."""

    async def dispatch(self, request: Request, call_next) -> Response:
        header = request.headers.get("content-length")
        if (
            header is not None
            and header.isdigit()
            and int(header) > settings.max_request_body_bytes
        ):
            return JSONResponse(
                status_code=413,
                content={"detail": "Request body too large"},
            )
        return await call_next(request)
