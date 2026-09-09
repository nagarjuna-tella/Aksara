"""
Security Remediation Tests — Phase 2: Auth Hardening

Tests for:
- DB-backed session management (aksara_sessions table)
- Studio access control (verify_studio_auth authentication)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request

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
    path: str = "/studio/handshake",
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
# DB-Backed Sessions
# =============================================================================


class TestDBSessionModule:
    """Tests for the session management module."""

    def test_sessions_table_constant(self):
        """The sessions table name should be 'aksara_sessions'."""
        from aksara.contrib.auth.session import SESSIONS_TABLE
        assert SESSIONS_TABLE == "aksara_sessions"

    def test_session_token_length(self):
        """Session tokens should be cryptographically random and of decent length."""
        import secrets
        token = secrets.token_urlsafe(32)
        assert len(token) >= 32

    def test_parse_affected_rows_valid(self):
        """_parse_affected_rows handles asyncpg status strings."""
        from aksara.contrib.auth.session import _parse_affected_rows

        assert _parse_affected_rows("DELETE 5") == 5
        assert _parse_affected_rows("DELETE 0") == 0
        assert _parse_affected_rows("INSERT 0 1") == 1
        assert _parse_affected_rows("UPDATE 3") == 3

    def test_parse_affected_rows_invalid(self):
        """_parse_affected_rows handles non-string inputs safely."""
        from aksara.contrib.auth.session import _parse_affected_rows

        assert _parse_affected_rows(None) == 0
        assert _parse_affected_rows(42) == 0
        assert _parse_affected_rows("NO_MATCH") == 0

    @pytest.mark.asyncio
    async def test_ensure_sessions_table_handles_none_db(self):
        """_ensure_sessions_table should no-op when db is None."""
        from aksara.contrib.auth.session import _ensure_sessions_table
        # Should not raise
        await _ensure_sessions_table(None)

    @pytest.mark.asyncio
    async def test_ensure_sessions_table_creates_table(self):
        """_ensure_sessions_table should execute CREATE TABLE IF NOT EXISTS."""
        from aksara.contrib.auth.session import _ensure_sessions_table

        mock_db = AsyncMock()
        mock_db.fetchval.return_value = False
        await _ensure_sessions_table(mock_db)

        mock_db.execute.assert_called_once()
        sql = mock_db.execute.call_args[0][0]
        assert "CREATE TABLE IF NOT EXISTS" in sql
        assert "aksara_sessions" in sql
        assert "token TEXT PRIMARY KEY" in sql
        assert "expires_at" in sql

    @pytest.mark.asyncio
    async def test_create_session_generates_token(self):
        """create_session_token should generate a token and store in DB."""
        from aksara.contrib.auth.session import create_session_token

        mock_db = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = "user-123"

        token = await create_session_token(mock_db, mock_user)

        assert isinstance(token, str)
        assert len(token) >= 32
        mock_db.execute.assert_called_once()
        call_args = mock_db.execute.call_args[0]
        assert "INSERT INTO" in call_args[0]
        assert call_args[1] == token

    @pytest.mark.asyncio
    async def test_invalidate_session_deletes_row(self):
        """invalidate_session_token should DELETE the token from DB."""
        from aksara.contrib.auth.session import invalidate_session_token

        mock_db = AsyncMock()
        await invalidate_session_token(mock_db, "test-token")

        mock_db.execute.assert_called_once()
        call_args = mock_db.execute.call_args[0]
        assert "DELETE FROM" in call_args[0]
        assert call_args[1] == "test-token"

    @pytest.mark.asyncio
    async def test_expired_session_returns_none(self):
        """get_user_from_session_token should return None for expired sessions."""
        from aksara.contrib.auth.session import get_user_from_session_token

        mock_db = AsyncMock()
        mock_db.fetchrow.return_value = {
            "user_id": "user-123",
            "expires_at": datetime.now(timezone.utc) - timedelta(hours=1),
        }

        result = await get_user_from_session_token(mock_db, "expired-token")
        assert result is None

        # Should also delete the expired session
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_missing_session_returns_none(self):
        """get_user_from_session_token should return None when session not found."""
        from aksara.contrib.auth.session import get_user_from_session_token

        mock_db = AsyncMock()
        mock_db.fetchrow.return_value = None

        result = await get_user_from_session_token(mock_db, "nonexistent-token")
        assert result is None

    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(self):
        """cleanup_expired_sessions should delete old sessions."""
        from aksara.contrib.auth.session import cleanup_expired_sessions

        mock_db = AsyncMock()
        mock_db.execute.return_value = "DELETE 3"

        count = await cleanup_expired_sessions(mock_db)
        assert count == 3


# =============================================================================
# Studio Access Control
# =============================================================================


class TestStudioAccessControl:
    """Tests for Studio authentication enforcement."""

    @pytest.mark.asyncio
    async def test_auth_required_rejects_unauthenticated(self):
        """Studio with studio_require_auth=True should reject unauthenticated requests."""
        from fastapi import HTTPException

        configure(studio_require_auth=True, studio_auth_token="secret-token")

        from aksara.studio.fastapi import verify_studio_auth

        mock_app = MagicMock()
        mock_app.db = None
        request = _build_request(app=mock_app)
        request._app = mock_app

        # Patch request.app to return our mock
        with patch.object(type(request), 'app', new_callable=lambda: property(lambda self: mock_app)):
            with pytest.raises(HTTPException) as exc_info:
                await verify_studio_auth(request)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_auth_not_required_allows_all(self):
        """Studio with studio_require_auth=False should allow unauthenticated requests."""
        configure(studio_require_auth=False)

        from aksara.studio.fastapi import verify_studio_auth

        request = _build_request()
        # Should not raise
        await verify_studio_auth(request)

    @pytest.mark.asyncio
    async def test_valid_bearer_token_passes(self):
        """Studio with valid bearer token should pass authentication."""
        configure(studio_require_auth=True, studio_auth_token="my-studio-token")

        from aksara.studio.fastapi import verify_studio_auth

        request = _build_request(
            headers=[(b"authorization", b"Bearer my-studio-token")]
        )

        # Should not raise
        await verify_studio_auth(request)

    @pytest.mark.asyncio
    async def test_invalid_bearer_token_rejected(self):
        """Studio with invalid bearer token should be rejected."""
        from fastapi import HTTPException

        configure(studio_require_auth=True, studio_auth_token="correct-token")

        from aksara.studio.fastapi import verify_studio_auth

        mock_app = MagicMock()
        mock_app.db = None
        request = _build_request(
            headers=[(b"authorization", b"Bearer wrong-token")],
            app=mock_app,
        )

        with patch.object(type(request), 'app', new_callable=lambda: property(lambda self: mock_app)):
            with pytest.raises(HTTPException) as exc_info:
                await verify_studio_auth(request)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_debug_mode_does_not_bypass_required_auth(self):
        """Explicit studio auth should still be enforced in debug mode."""
        from fastapi import HTTPException

        configure(studio_require_auth=True, studio_auth_token=None, debug=True)

        from aksara.studio.fastapi import verify_studio_auth

        mock_app = MagicMock()
        mock_app.db = None
        request = _build_request(app=mock_app)

        with patch.object(type(request), 'app', new_callable=lambda: property(lambda self: mock_app)):
            with pytest.raises(HTTPException) as exc_info:
                await verify_studio_auth(request)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_staff_session_cookie_uses_db_backed_lookup(self):
        """Studio should accept valid staff session cookies via the shared session store."""
        configure(studio_require_auth=True, studio_auth_token=None, debug=False)

        from aksara.studio.fastapi import verify_studio_auth

        mock_db = AsyncMock()
        mock_app = MagicMock()
        mock_app.db = mock_db
        request = _build_request(cookies={"session_token": "staff-session"}, app=mock_app)

        mock_user = MagicMock()
        mock_user.is_staff = True

        with patch(
            "aksara.contrib.auth.get_user_from_session_token",
            new=AsyncMock(return_value=mock_user),
        ) as get_user_from_session_token:
            await verify_studio_auth(request)

        get_user_from_session_token.assert_awaited_once_with(mock_db, "staff-session")

    @pytest.mark.asyncio
    async def test_disallowed_origin_rejected(self):
        """Requests from disallowed origins should be rejected."""
        from fastapi import HTTPException

        configure(
            studio_require_auth=False,
            studio_allowed_origins=["https://studio.aksara.dev"],
        )

        from aksara.studio.fastapi import _check_studio_origin

        request = _build_request(
            headers=[(b"origin", b"https://evil.com")]
        )

        with pytest.raises(HTTPException) as exc_info:
            await _check_studio_origin(request)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_allowed_origin_passes(self):
        """Requests from allowed origins should pass."""
        configure(
            studio_require_auth=False,
            studio_allowed_origins=["https://studio.aksara.dev"],
        )

        from aksara.studio.fastapi import _check_studio_origin

        request = _build_request(
            headers=[(b"origin", b"https://studio.aksara.dev")]
        )

        # Should not raise
        await _check_studio_origin(request)

    @pytest.mark.asyncio
    async def test_missing_origin_allowed(self):
        """Same-origin requests (no Origin header) should be allowed."""
        configure(
            studio_require_auth=False,
            studio_allowed_origins=["https://studio.aksara.dev"],
        )

        from aksara.studio.fastapi import _check_studio_origin

        request = _build_request()  # No origin header

        # Should not raise
        await _check_studio_origin(request)

    def test_studio_require_auth_default_true(self):
        """studio_require_auth should default to True."""
        from aksara.conf import settings
        assert settings.studio_require_auth is True

    def test_verify_uses_hmac_compare(self):
        """Studio token comparison should use hmac.compare_digest."""
        import inspect
        from aksara.studio.fastapi import verify_studio_auth

        source = inspect.getsource(verify_studio_auth)
        assert "hmac.compare_digest" in source
