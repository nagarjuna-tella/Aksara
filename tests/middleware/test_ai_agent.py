"""
Tests for AI agent middleware.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from starlette.requests import Request
from starlette.responses import Response

from aksara.conf import configure, reset_settings
from aksara.middleware.ai_agent import AIAgentMiddleware


class TestAIAgentMiddleware:
    """Tests for AIAgentMiddleware."""

    @pytest.fixture(autouse=True)
    def reset_config(self):
        """Reset settings around each test."""
        reset_settings()
        yield
        reset_settings()

    @staticmethod
    def _build_request(token: str | None = None) -> Request:
        headers = []
        if token is not None:
            headers.append((b"x-aksara-ai-token", token.encode("utf-8")))

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
            "state": {},
        }
        return Request(scope)

    @pytest.mark.asyncio
    async def test_sets_state_for_valid_token(self):
        """Middleware should mark request as AI when token matches."""
        configure(ai_agent_token="shared-secret")
        middleware = AIAgentMiddleware(MagicMock())
        request = self._build_request("shared-secret")

        observed = {}

        async def call_next(inner_request: Request) -> Response:
            observed["is_ai_agent"] = inner_request.state.is_ai_agent
            return Response("ok")

        response = await middleware.dispatch(request, call_next)

        assert response.status_code == 200
        assert observed["is_ai_agent"] is True
        assert request.state.is_ai_agent is False

    @pytest.mark.asyncio
    async def test_does_not_set_state_for_invalid_token(self):
        """Middleware should leave request as non-AI when token mismatches."""
        configure(ai_agent_token="shared-secret")
        middleware = AIAgentMiddleware(MagicMock())
        request = self._build_request("wrong-secret")

        observed = {}

        async def call_next(inner_request: Request) -> Response:
            observed["is_ai_agent"] = inner_request.state.is_ai_agent
            return Response("ok")

        await middleware.dispatch(request, call_next)

        assert observed["is_ai_agent"] is False

    @pytest.mark.asyncio
    async def test_does_not_set_state_without_token(self):
        """Middleware should leave request as non-AI when token is absent."""
        configure(ai_agent_token="shared-secret")
        middleware = AIAgentMiddleware(MagicMock())
        request = self._build_request()

        observed = {}

        async def call_next(inner_request: Request) -> Response:
            observed["is_ai_agent"] = inner_request.state.is_ai_agent
            return Response("ok")

        await middleware.dispatch(request, call_next)

        assert observed["is_ai_agent"] is False

    def test_aksara_auto_registers_middleware_when_token_configured(self):
        """Aksara should auto-register AI agent middleware when token auth is enabled."""
        from aksara.app import Aksara

        configure(ai_agent_token="shared-secret")

        app = Aksara(database_url=None, auto_discover_views=False, enable_admin=False)

        assert any(getattr(mw, "cls", None) is AIAgentMiddleware for mw in app.user_middleware)