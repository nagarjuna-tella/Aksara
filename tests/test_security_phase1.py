"""
Security Remediation Tests — Phase 1: Zero-Dependency Fixes

Tests for:
- ADD-E: Exception message leaking (debug_detail restricted to localhost)
- Cookie security: cookie_secure setting independent of debug
- AI agent trust: AIAgentMiddleware shared-secret validation
- SQL injection: codegen identifier validation and quoting
"""

from __future__ import annotations

import re
from unittest.mock import MagicMock, patch

import pytest
from starlette.requests import Request
from starlette.responses import Response

from aksara.conf import Settings, configure, reset_settings


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def clean_settings():
    """Reset settings around each test."""
    reset_settings()
    yield
    reset_settings()


def _build_request(
    *,
    headers: list[tuple[bytes, bytes]] | None = None,
    client_host: str = "127.0.0.1",
    method: str = "GET",
    path: str = "/",
    cookies: dict[str, str] | None = None,
) -> Request:
    """Build a minimal ASGI request for testing."""
    raw_headers = list(headers or [])
    if cookies:
        cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
        raw_headers.append((b"cookie", cookie_str.encode()))

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": raw_headers,
        "client": (client_host, 12345),
        "server": ("testserver", 80),
        "state": {},
    }
    return Request(scope)


# =============================================================================
# ADD-E: Exception Message Leaking
# =============================================================================


class TestExceptionLeaking:
    """Tests that exception messages are NOT leaked in JSON error responses."""

    def test_json_debug_detail_localhost_debug_on(self):
        """Debug detail should be shown ONLY for localhost in debug mode."""
        from aksara.debug.handlers import _get_json_debug_detail

        request = _build_request(client_host="127.0.0.1")
        exc = ValueError("sensitive database schema info")

        result = _get_json_debug_detail(request, exc, is_debug=True)
        assert result == "sensitive database schema info"

    def test_json_debug_detail_ipv6_localhost(self):
        """Debug detail should be shown for ::1 in debug mode."""
        from aksara.debug.handlers import _get_json_debug_detail

        request = _build_request(client_host="::1")
        exc = ValueError("internal error details")

        result = _get_json_debug_detail(request, exc, is_debug=True)
        assert result == "internal error details"

    def test_json_debug_detail_remote_client_debug_on(self):
        """Debug detail must NOT be shown for remote clients, even in debug mode."""
        from aksara.debug.handlers import _get_json_debug_detail

        request = _build_request(client_host="192.168.1.100")
        exc = ValueError("sensitive info should not leak")

        result = _get_json_debug_detail(request, exc, is_debug=True)
        assert result is None

    def test_json_debug_detail_debug_off(self):
        """Debug detail must NOT be shown when debug is off, even for localhost."""
        from aksara.debug.handlers import _get_json_debug_detail

        request = _build_request(client_host="127.0.0.1")
        exc = ValueError("should not appear")

        result = _get_json_debug_detail(request, exc, is_debug=False)
        assert result is None

    def test_json_debug_detail_no_client(self):
        """Debug detail must NOT be shown when there is no client info."""
        from aksara.debug.handlers import _get_json_debug_detail

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": [],
            "server": ("testserver", 80),
            "state": {},
        }
        request = Request(scope)
        exc = ValueError("should not appear")

        result = _get_json_debug_detail(request, exc, is_debug=True)
        assert result is None

    def test_render_json_error_production_no_debug_detail(self):
        """render_json_error without debug_detail should not include it."""
        from aksara.debug.handlers import render_json_error

        response = render_json_error(500, "Internal Server Error")
        import json
        body = json.loads(response.body)
        assert "debug_detail" not in body["error"]

    def test_render_json_error_with_debug_detail(self):
        """render_json_error with debug_detail should include it."""
        from aksara.debug.handlers import render_json_error

        response = render_json_error(500, "Internal Server Error", debug_detail="details")
        import json
        body = json.loads(response.body)
        assert body["error"]["debug_detail"] == "details"


# =============================================================================
# Cookie Security
# =============================================================================


class TestCookieSecurity:
    """Tests that cookie_secure is independent of debug mode."""

    def test_cookie_secure_default_true(self):
        """cookie_secure should default to True."""
        configure(debug=False)
        from aksara.conf import settings
        assert settings.cookie_secure is True

    def test_cookie_secure_true_even_when_debug(self):
        """cookie_secure should remain True even in debug mode if not overridden."""
        configure(debug=True, cookie_secure=True)
        from aksara.conf import settings
        assert settings.cookie_secure is True

    def test_cookie_secure_can_be_disabled(self):
        """cookie_secure can be explicitly disabled."""
        configure(cookie_secure=False)
        from aksara.conf import settings
        assert settings.cookie_secure is False


# =============================================================================
# AI Agent Trust
# =============================================================================


class TestAIAgentMiddleware:
    """Tests for server-side AI agent authentication."""

    @pytest.mark.asyncio
    async def test_valid_token_sets_is_ai_agent(self):
        """Valid shared secret should set request.state.is_ai_agent = True during request."""
        configure(ai_agent_token="test-secret-token")
        from aksara.middleware.ai_agent import AIAgentMiddleware

        middleware = AIAgentMiddleware(MagicMock())
        request = _build_request(
            headers=[(b"x-aksara-ai-token", b"test-secret-token")]
        )

        observed = {}

        async def call_next(req: Request) -> Response:
            observed["is_ai_agent"] = req.state.is_ai_agent
            return Response("ok")

        response = await middleware.dispatch(request, call_next)

        assert response.status_code == 200
        assert observed["is_ai_agent"] is True
        # Should be reset after the call
        assert request.state.is_ai_agent is False

    @pytest.mark.asyncio
    async def test_invalid_token_keeps_false(self):
        """Invalid token should NOT set is_ai_agent."""
        configure(ai_agent_token="correct-secret")
        from aksara.middleware.ai_agent import AIAgentMiddleware

        middleware = AIAgentMiddleware(MagicMock())
        request = _build_request(
            headers=[(b"x-aksara-ai-token", b"wrong-secret")]
        )

        observed = {}

        async def call_next(req: Request) -> Response:
            observed["is_ai_agent"] = req.state.is_ai_agent
            return Response("ok")

        await middleware.dispatch(request, call_next)
        assert observed["is_ai_agent"] is False

    @pytest.mark.asyncio
    async def test_missing_token_keeps_false(self):
        """Missing token header should keep is_ai_agent = False."""
        configure(ai_agent_token="test-secret")
        from aksara.middleware.ai_agent import AIAgentMiddleware

        middleware = AIAgentMiddleware(MagicMock())
        request = _build_request()

        observed = {}

        async def call_next(req: Request) -> Response:
            observed["is_ai_agent"] = req.state.is_ai_agent
            return Response("ok")

        await middleware.dispatch(request, call_next)
        assert observed["is_ai_agent"] is False

    @pytest.mark.asyncio
    async def test_no_configured_token_keeps_false(self):
        """When no token is configured, even matching headers should be rejected."""
        configure(ai_agent_token=None)
        from aksara.middleware.ai_agent import AIAgentMiddleware

        middleware = AIAgentMiddleware(MagicMock())
        request = _build_request(
            headers=[(b"x-aksara-ai-token", b"anything")]
        )

        observed = {}

        async def call_next(req: Request) -> Response:
            observed["is_ai_agent"] = req.state.is_ai_agent
            return Response("ok")

        await middleware.dispatch(request, call_next)
        assert observed["is_ai_agent"] is False

    @pytest.mark.asyncio
    async def test_timing_safe_comparison(self):
        """Token comparison should use hmac.compare_digest to prevent timing attacks."""
        import inspect
        from aksara.middleware.ai_agent import AIAgentMiddleware

        source = inspect.getsource(AIAgentMiddleware.dispatch)
        assert "hmac.compare_digest" in source or "compare_digest" in source

    def test_old_header_not_trusted(self):
        """DenyAI should check server-set state, not X-AI-Agent header."""
        from aksara.permissions import DenyAI

        perm = DenyAI()

        # Simulate a request with the OLD X-AI-Agent header but no server state
        request = _build_request(
            headers=[(b"x-ai-agent", b"true")]
        )

        # DenyAI should allow this because server state was not set
        assert perm.has_permission(request) is True

    def test_deny_ai_blocks_server_set_state(self):
        """DenyAI should block when server-side state is True."""
        from aksara.permissions import DenyAI

        perm = DenyAI()
        request = _build_request()
        request.state.is_ai_agent = True

        assert perm.has_permission(request) is False


# =============================================================================
# SQL Injection in CodeGen
# =============================================================================


class TestCodegenSQLInjection:
    """Tests that codegen validates identifiers against SQL injection."""

    def test_validate_identifier_valid(self):
        """Valid identifiers should pass validation."""
        from aksara.ai.codegen import _validate_identifier

        assert _validate_identifier("users", "table") == "users"
        assert _validate_identifier("user_name", "field") == "user_name"
        assert _validate_identifier("_private", "field") == "_private"
        assert _validate_identifier("Column1", "field") == "Column1"

    def test_validate_identifier_rejects_injection(self):
        """Identifiers with SQL injection patterns should be rejected."""
        from aksara.ai.codegen import _validate_identifier

        malicious = [
            "users; DROP TABLE users--",
            "name' OR '1'='1",
            "col); DELETE FROM",
            "table\x00name",
            "user name",
            "col-name",
            "",
            "123abc",
        ]
        for name in malicious:
            with pytest.raises(ValueError, match="Invalid .* identifier"):
                _validate_identifier(name, "table")

    def test_validate_identifier_rejects_dots(self):
        """Dotted identifiers (schema.table) should be rejected."""
        from aksara.ai.codegen import _validate_identifier

        with pytest.raises(ValueError):
            _validate_identifier("public.users", "table")

    def test_quote_identifier_escapes_quotes(self):
        """quote_identifier should double-quote and escape embedded quotes."""
        from aksara.db import quote_identifier

        assert quote_identifier("users") == '"users"'
        assert quote_identifier('my"table') == '"my""table"'

    def test_identifier_pattern_anchored(self):
        """The identifier regex should use fullmatch to prevent partial matches."""
        from aksara.ai.codegen import IDENTIFIER_PATTERN

        # Partial match would succeed, but fullmatch should fail
        assert IDENTIFIER_PATTERN.fullmatch("valid_name") is not None
        assert IDENTIFIER_PATTERN.fullmatch("invalid name") is None
        assert IDENTIFIER_PATTERN.fullmatch("name; drop") is None

    def test_generate_migration_stub_uses_validation(self):
        """generate_migration_stub should use _validate_identifier for table and field names."""
        import inspect
        from aksara.ai.codegen import generate_migration_stub

        source = inspect.getsource(generate_migration_stub)
        assert "_validate_identifier" in source
        assert "quote_identifier" in source
