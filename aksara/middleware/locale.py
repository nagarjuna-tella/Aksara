"""
Locale middleware for request-scoped language selection.

Resolves the active locale from the Accept-Language header and stores it in
request state and a context variable for downstream serialization.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Sequence

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from aksara.i18n import parse_accept_language

from .context import locale_var

if TYPE_CHECKING:
    from starlette.types import ASGIApp


class LocaleMiddleware(BaseHTTPMiddleware):
    """Resolve the active locale for each request."""

    def __init__(
        self,
        app: "ASGIApp",
        header_name: str = "Accept-Language",
        supported_locales: Optional[Sequence[str]] = None,
        default_locale: Optional[str] = None,
    ):
        super().__init__(app)
        self.header_name = header_name
        self.supported_locales = list(supported_locales) if supported_locales is not None else None
        self.default_locale = default_locale

    async def dispatch(self, request: Request, call_next) -> Response:
        """Resolve locale and propagate it through the request context."""
        locale = parse_accept_language(
            request.headers.get(self.header_name),
            supported_locales=self.supported_locales,
            default_locale=self.default_locale,
        )
        request.state.locale = locale
        token = locale_var.set(locale)

        try:
            response = await call_next(request)
        finally:
            locale_var.reset(token)

        return response


__all__ = ["LocaleMiddleware"]