"""
Timezone middleware for request-scoped timezone selection.

Reads a timezone identifier from request headers and stores it in request state
and a context variable for downstream datetime serialization.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .context import timezone_var

if TYPE_CHECKING:
    from starlette.types import ASGIApp


class TimezoneMiddleware(BaseHTTPMiddleware):
    """Resolve the active timezone for each request."""

    def __init__(
        self,
        app: "ASGIApp",
        header_name: str = "X-Timezone",
        default_timezone: str = "UTC",
    ):
        super().__init__(app)
        self.header_name = header_name
        self.default_timezone = default_timezone

    async def dispatch(self, request: Request, call_next) -> Response:
        """Resolve timezone and propagate it through the request context."""
        timezone_name = request.headers.get(self.header_name) or self.default_timezone

        try:
            ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            timezone_name = self.default_timezone

        request.state.timezone = timezone_name
        token = timezone_var.set(timezone_name)

        try:
            response = await call_next(request)
        finally:
            timezone_var.reset(token)

        return response


__all__ = ["TimezoneMiddleware"]