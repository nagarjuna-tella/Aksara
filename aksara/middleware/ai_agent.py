"""
AI agent middleware.

Validates server-side AI agent identity from a shared request token.
"""

from __future__ import annotations

import hmac
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

if TYPE_CHECKING:
    from starlette.types import ASGIApp


def _get_settings():
    """Lazy import settings to avoid importing app configuration at module load time."""
    from aksara.conf import settings

    return settings


class AIAgentMiddleware(BaseHTTPMiddleware):
    """Populate request.state.is_ai_agent from a shared secret header."""

    def __init__(self, app: "ASGIApp", header_name: str = "X-Aksara-AI-Token"):
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(self, request: Request, call_next) -> Response:
        request.state.is_ai_agent = False

        token = request.headers.get(self.header_name)
        expected_token = _get_settings().ai_agent_token
        if token and expected_token and hmac.compare_digest(token, expected_token):
            request.state.is_ai_agent = True
            # Resolve a canonical Principal and attach it for downstream consumers.
            from aksara.security.adapters import annotate_request_state
            from aksara.security.context import principal_from_request
            principal = principal_from_request(request)
            annotate_request_state(request, principal)

        try:
            response: Response = await call_next(request)
        finally:
            request.state.is_ai_agent = False

        return response


__all__ = ["AIAgentMiddleware"]