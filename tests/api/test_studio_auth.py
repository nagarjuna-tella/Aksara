"""
Studio authentication tests.

Tests verify_studio_auth: Authorization: Bearer <token> + studio_require_auth/studio_auth_token
settings. Returns 401 on auth failure.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from aksara.app import Aksara


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings(*, require_auth: bool = True, token: str = "valid_token",
                   enable_studio: bool = True) -> MagicMock:
    """Return a settings mock pre-configured for studio auth tests."""
    mock = MagicMock()
    mock.studio_require_auth = require_auth
    mock.studio_auth_token = token
    mock.enable_studio = enable_studio
    mock.studio_allowed_origins = []
    mock.studio_ui_enabled = False
    mock.debug = True
    mock.studio_expose_in_production = False
    return mock


@pytest.fixture()
def app():
    """Test Aksara app with the studio router mounted."""
    from aksara.studio.fastapi import router
    test_app = Aksara()
    test_app.include_router(router)
    test_app._db = None
    return test_app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_studio_auth_missing_token(app):
    """No Authorization header when auth is required → 401."""
    client = TestClient(app, raise_server_exceptions=False)
    with patch("aksara.conf.settings", _make_settings(require_auth=True)):
        response = client.get("/studio/handshake")
        assert response.status_code == 401
        assert "Studio requires authentication" in response.text


def test_studio_auth_wrong_token(app):
    """Wrong Bearer token when auth is required → 401."""
    client = TestClient(app, raise_server_exceptions=False)
    with patch("aksara.conf.settings", _make_settings(require_auth=True)):
        response = client.get(
            "/studio/handshake",
            headers={"Authorization": "Bearer wrong_token"},
        )
        assert response.status_code == 401
        assert "Studio requires authentication" in response.text


def test_studio_auth_not_required_passes(app):
    """When studio_require_auth=False every request passes auth (no token needed)."""
    client = TestClient(app, raise_server_exceptions=False)
    with patch("aksara.conf.settings", _make_settings(require_auth=False)):
        response = client.get(
            "/studio/handshake",
            headers={"Accept": "application/json"},
        )
        assert response.status_code != 401


def test_studio_auth_success(app):
    """Correct Bearer token when auth is required → auth passes (not 401)."""
    client = TestClient(app, raise_server_exceptions=False)
    with patch("aksara.conf.settings", _make_settings(require_auth=True)):
        response = client.get(
            "/studio/handshake",
            headers={
                "Authorization": "Bearer valid_token",
                "Accept": "application/json",
            },
        )
        # Auth dependency passed — response is not a 401.
        # May be 500 due to no database in this unit test context; that is expected.
        assert response.status_code != 401


def test_studio_auth_no_origin_does_not_bypass_auth(app):
    """Absent Origin header does not bypass auth — missing token still → 401."""
    client = TestClient(app, raise_server_exceptions=False)
    with patch("aksara.conf.settings", _make_settings(require_auth=True)):
        # No Origin header, no Authorization header
        response = client.get("/studio/handshake")
        assert response.status_code == 401
        assert "Studio requires authentication" in response.text
