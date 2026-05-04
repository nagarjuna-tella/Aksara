"""
Tests for LocaleMiddleware.
"""

from __future__ import annotations

from starlette.requests import Request as StarletteRequest
from starlette.testclient import TestClient

from aksara import Aksara
from aksara.middleware import LocaleMiddleware, locale_var


class TestLocaleMiddleware:
    """Tests for request-scoped locale resolution."""

    def test_resolves_locale_from_accept_language(self):
        """Accept-Language should resolve to the best supported locale."""
        app = Aksara(
            database_url=None,
            auto_discover_views=False,
            middlewares=[
                (LocaleMiddleware, {
                    "supported_locales": ["en", "fr", "es"],
                    "default_locale": "en",
                }),
            ],
        )

        @app.get("/whoami")
        async def whoami(request: StarletteRequest):
            return {"locale": request.state.locale}

        client = TestClient(app)
        response = client.get("/whoami", headers={"Accept-Language": "fr-CA,fr;q=0.9,en;q=0.5"})

        assert response.status_code == 200
        assert response.json()["locale"] == "fr"

    def test_locale_is_available_via_contextvar(self):
        """Resolved locale should propagate through the context variable."""
        app = Aksara(
            database_url=None,
            auto_discover_views=False,
            middlewares=[
                (LocaleMiddleware, {
                    "supported_locales": ["en", "de"],
                    "default_locale": "en",
                }),
            ],
        )

        captured_locale = None

        @app.get("/check-context")
        async def check_context():
            nonlocal captured_locale
            captured_locale = locale_var.get()
            return {"locale": captured_locale}

        client = TestClient(app)
        response = client.get("/check-context", headers={"Accept-Language": "de-DE,de;q=0.9"})

        assert response.status_code == 200
        assert captured_locale == "de"

    def test_falls_back_to_default_locale(self):
        """Requests without Accept-Language should use the configured default."""
        app = Aksara(
            database_url=None,
            auto_discover_views=False,
            middlewares=[
                (LocaleMiddleware, {
                    "supported_locales": ["en", "fr"],
                    "default_locale": "en",
                }),
            ],
        )

        @app.get("/whoami")
        async def whoami(request: StarletteRequest):
            return {"locale": request.state.locale}

        client = TestClient(app)
        response = client.get("/whoami")

        assert response.status_code == 200
        assert response.json()["locale"] == "en"

    def test_contextvar_resets_after_request(self):
        """Locale context should not leak across requests."""
        app = Aksara(
            database_url=None,
            auto_discover_views=False,
            middlewares=[
                (LocaleMiddleware, {
                    "supported_locales": ["en", "fr"],
                    "default_locale": "en",
                }),
            ],
        )

        @app.get("/ping")
        async def ping():
            return {"status": "ok"}

        assert locale_var.get() is None

        client = TestClient(app)
        client.get("/ping", headers={"Accept-Language": "fr"})

        assert locale_var.get() is None