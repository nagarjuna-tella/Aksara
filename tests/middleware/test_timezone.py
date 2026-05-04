"""
Tests for TimezoneMiddleware.
"""

from __future__ import annotations

from starlette.requests import Request as StarletteRequest
from starlette.testclient import TestClient

from aksara import Aksara
from aksara.middleware import TimezoneMiddleware, timezone_var


class TestTimezoneMiddleware:
    """Tests for request-scoped timezone resolution."""

    def test_reads_timezone_from_header(self):
        """The timezone header should populate request state."""
        app = Aksara(
            database_url=None,
            auto_discover_views=False,
            middlewares=[
                (TimezoneMiddleware, {"default_timezone": "UTC"}),
            ],
        )

        @app.get("/whoami")
        async def whoami(request: StarletteRequest):
            return {"timezone": request.state.timezone}

        client = TestClient(app)
        response = client.get("/whoami", headers={"X-Timezone": "America/New_York"})

        assert response.status_code == 200
        assert response.json()["timezone"] == "America/New_York"

    def test_timezone_is_available_via_contextvar(self):
        """Resolved timezone should propagate through the context variable."""
        app = Aksara(
            database_url=None,
            auto_discover_views=False,
            middlewares=[
                (TimezoneMiddleware, {"default_timezone": "UTC"}),
            ],
        )

        captured_timezone = None

        @app.get("/check-context")
        async def check_context():
            nonlocal captured_timezone
            captured_timezone = timezone_var.get()
            return {"timezone": captured_timezone}

        client = TestClient(app)
        response = client.get("/check-context", headers={"X-Timezone": "Europe/Berlin"})

        assert response.status_code == 200
        assert captured_timezone == "Europe/Berlin"

    def test_invalid_timezone_falls_back_to_default(self):
        """Invalid timezone names should fall back to the configured default."""
        app = Aksara(
            database_url=None,
            auto_discover_views=False,
            middlewares=[
                (TimezoneMiddleware, {"default_timezone": "UTC"}),
            ],
        )

        @app.get("/whoami")
        async def whoami(request: StarletteRequest):
            return {"timezone": request.state.timezone}

        client = TestClient(app)
        response = client.get("/whoami", headers={"X-Timezone": "Mars/OlympusMons"})

        assert response.status_code == 200
        assert response.json()["timezone"] == "UTC"

    def test_contextvar_resets_after_request(self):
        """Timezone context should not leak across requests."""
        app = Aksara(
            database_url=None,
            auto_discover_views=False,
            middlewares=[
                (TimezoneMiddleware, {"default_timezone": "UTC"}),
            ],
        )

        @app.get("/ping")
        async def ping():
            return {"status": "ok"}

        assert timezone_var.get() is None

        client = TestClient(app)
        client.get("/ping", headers={"X-Timezone": "Asia/Tokyo"})

        assert timezone_var.get() is None