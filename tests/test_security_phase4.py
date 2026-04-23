"""
Security Remediation Tests — Phase 4: CSRF & Rate Limiting

Tests for:
- CSRF token generation, cookie setting, and validation
- Admin rate limiting middleware
"""

from __future__ import annotations

import hmac
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request
from starlette.responses import Response

from aksara.conf import configure, reset_settings


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
    path: str = "/admin/",
    cookies: dict[str, str] | None = None,
    app: object = None,
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
    if app is not None:
        scope["app"] = app
    return Request(scope)


# =============================================================================
# CSRF Protection
# =============================================================================


class TestCSRFTokenGeneration:
    """Tests for CSRF token generation and management."""

    def test_generate_admin_csrf_token_returns_string(self):
        """_generate_admin_csrf_token should return a random string."""
        from aksara.contrib.admin.views import _generate_admin_csrf_token

        token = _generate_admin_csrf_token()
        assert isinstance(token, str)
        assert len(token) >= 32

    def test_generate_admin_csrf_token_unique(self):
        """Each call should generate a unique token."""
        from aksara.contrib.admin.views import _generate_admin_csrf_token

        tokens = {_generate_admin_csrf_token() for _ in range(100)}
        assert len(tokens) == 100

    def test_get_or_create_uses_cookie_if_present(self):
        """_get_or_create_admin_csrf_token should use existing cookie."""
        from aksara.contrib.admin.views import _get_or_create_admin_csrf_token

        request = _build_request(cookies={"aksara_admin_csrf": "existing-token"})
        result = _get_or_create_admin_csrf_token(request)
        assert result == "existing-token"

    def test_get_or_create_generates_new_if_no_cookie(self):
        """_get_or_create_admin_csrf_token should generate new without cookie."""
        from aksara.contrib.admin.views import _get_or_create_admin_csrf_token

        request = _build_request()
        result = _get_or_create_admin_csrf_token(request)
        assert isinstance(result, str)
        assert len(result) >= 32


class TestCSRFValidation:
    """Tests for CSRF validation in admin form processing."""

    def test_csrf_cookie_name_constant(self):
        """CSRF cookie name should be 'aksara_admin_csrf'."""
        from aksara.contrib.admin.views import ADMIN_CSRF_COOKIE_NAME
        assert ADMIN_CSRF_COOKIE_NAME == "aksara_admin_csrf"

    def test_csrf_form_field_constant(self):
        """CSRF form field name should be 'csrf_token'."""
        from aksara.contrib.admin.views import ADMIN_CSRF_FORM_FIELD
        assert ADMIN_CSRF_FORM_FIELD == "csrf_token"

    def test_is_same_origin_valid(self):
        """_is_same_origin should return True for matching origins."""
        from aksara.contrib.admin.views import _is_same_origin

        request = _build_request()
        assert _is_same_origin(request, "http://testserver") is True

    def test_is_same_origin_invalid(self):
        """_is_same_origin should return False for mismatched origins."""
        from aksara.contrib.admin.views import _is_same_origin

        request = _build_request()
        assert _is_same_origin(request, "https://evil.com") is False

    def test_csrf_cookie_settings(self):
        """CSRF cookie should use proper security settings."""
        from aksara.contrib.admin.views import _set_admin_csrf_cookie

        configure(cookie_secure=True)

        response = MagicMock()
        request = _build_request()
        _set_admin_csrf_cookie(response, request, "test-token")

        response.set_cookie.assert_called_once()
        call_kwargs = response.set_cookie.call_args[1]
        assert call_kwargs["key"] == "aksara_admin_csrf"
        assert call_kwargs["value"] == "test-token"
        assert call_kwargs["httponly"] is False  # Needs to be readable by JS for form submission
        assert call_kwargs["samesite"] == "strict"
        assert call_kwargs["path"] == "/admin"

    def test_csrf_uses_hmac_compare_digest(self):
        """CSRF validation should use hmac.compare_digest for timing safety."""
        import inspect
        from aksara.contrib.admin.views import _read_admin_form

        source = inspect.getsource(_read_admin_form)
        assert "hmac.compare_digest" in source

    def test_admin_csrf_enabled_default(self):
        """admin_csrf_enabled should default to True."""
        from aksara.conf import settings
        assert settings.admin_csrf_enabled is True


# =============================================================================
# Rate Limiting
# =============================================================================


class TestAdminRateLimiting:
    """Tests for AdminRateLimitMiddleware."""

    @pytest.mark.asyncio
    async def test_rate_limit_passes_get_requests(self):
        """GET requests should not be rate limited."""
        from aksara.contrib.admin.mount import AdminRateLimitMiddleware

        configure(admin_rate_limit_enabled=True)

        mock_app = MagicMock()
        mock_app.state = MagicMock()
        middleware = AdminRateLimitMiddleware(mock_app, prefix="/admin")

        request = _build_request(method="GET", path="/admin/", app=mock_app)

        called = False

        async def call_next(req: Request) -> Response:
            nonlocal called
            called = True
            return Response("ok")

        response = await middleware.dispatch(request, call_next)
        assert called

    @pytest.mark.asyncio
    async def test_rate_limit_disableable(self):
        """Rate limiting should be disabled when configured off."""
        from aksara.contrib.admin.mount import AdminRateLimitMiddleware

        configure(admin_rate_limit_enabled=False)

        mock_app = MagicMock()
        middleware = AdminRateLimitMiddleware(mock_app, prefix="/admin")

        request = _build_request(method="POST", path="/admin/login/")

        called = False

        async def call_next(req: Request) -> Response:
            nonlocal called
            called = True
            return Response("ok")

        response = await middleware.dispatch(request, call_next)
        assert called

    @pytest.mark.asyncio
    async def test_rate_limit_blocks_excessive_posts(self):
        """Should return 429 after exceeding limit."""
        from aksara.contrib.admin.mount import AdminRateLimitMiddleware

        configure(
            admin_rate_limit_enabled=True,
            admin_rate_limit_requests=3,
            admin_rate_limit_window_seconds=60,
        )

        mock_app = MagicMock()
        mock_app.state = MagicMock()
        mock_app.state._aksara_admin_rate_limits = None
        delattr(mock_app.state, "_aksara_admin_rate_limits")
        middleware = AdminRateLimitMiddleware(mock_app, prefix="/admin")

        async def call_next(req: Request) -> Response:
            return Response("ok")

        responses = []
        for i in range(5):
            request = _build_request(
                method="POST",
                path="/admin/login/",
                client_host="10.0.0.1",
                app=mock_app,
            )

            response = await middleware.dispatch(request, call_next)
            responses.append(response.status_code)

        # First 3 should pass, 4th and 5th should be 429
        assert responses[:3] == [200, 200, 200]
        assert responses[3] == 429
        assert responses[4] == 429

    @pytest.mark.asyncio
    async def test_rate_limit_only_applies_to_admin_prefix(self):
        """Requests outside /admin/ should not be rate limited."""
        from aksara.contrib.admin.mount import AdminRateLimitMiddleware

        configure(admin_rate_limit_enabled=True, admin_rate_limit_requests=1)

        mock_app = MagicMock()
        mock_app.state = MagicMock()
        middleware = AdminRateLimitMiddleware(mock_app, prefix="/admin")

        async def call_next(req: Request) -> Response:
            return Response("ok")

        # Request outside admin prefix should always pass
        for _ in range(5):
            request = _build_request(method="POST", path="/api/users/", app=mock_app)

            response = await middleware.dispatch(request, call_next)
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_rate_limit_returns_retry_after_header(self):
        """429 response should include Retry-After header."""
        from aksara.contrib.admin.mount import AdminRateLimitMiddleware

        configure(
            admin_rate_limit_enabled=True,
            admin_rate_limit_requests=1,
            admin_rate_limit_window_seconds=60,
        )

        mock_app = MagicMock()
        mock_app.state = MagicMock()
        mock_app.state._aksara_admin_rate_limits = None
        delattr(mock_app.state, "_aksara_admin_rate_limits")
        middleware = AdminRateLimitMiddleware(mock_app, prefix="/admin")

        async def call_next(req: Request) -> Response:
            return Response("ok")

        # First request passes
        request1 = _build_request(method="POST", path="/admin/login/", client_host="192.168.1.1", app=mock_app)
        await middleware.dispatch(request1, call_next)

        # Second request should get 429
        request2 = _build_request(method="POST", path="/admin/login/", client_host="192.168.1.1", app=mock_app)
        response = await middleware.dispatch(request2, call_next)

        assert response.status_code == 429
        assert "retry-after" in dict(response.headers)

    def test_rate_limit_settings_defaults(self):
        """Rate limit settings should have sensible defaults."""
        from aksara.conf import settings

        assert settings.admin_rate_limit_enabled is True
        assert settings.admin_rate_limit_requests == 20
        assert settings.admin_rate_limit_window_seconds == 60
