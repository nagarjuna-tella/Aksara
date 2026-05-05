"""
Tests for runtime console output emitted by Aksara applications.
"""

from __future__ import annotations


class TestRuntimeOutput:
    """Validate startup and shutdown console output behavior."""

    def test_startup_suppresses_brand_when_cli_banner_already_shown(self, monkeypatch, capsys):
        from aksara.app import Aksara

        monkeypatch.setenv("AKSARA_SUPPRESS_RUNTIME_BRAND", "1")

        app = Aksara(database_url=None, auto_discover_views=False)
        app._print_startup()

        captured = capsys.readouterr().out
        assert "Database connected" in captured
        assert "Async Postgres ORM" not in captured

    def test_shutdown_suppresses_brand_when_cli_banner_already_shown(self, monkeypatch, capsys):
        from aksara.app import Aksara

        monkeypatch.setenv("AKSARA_SUPPRESS_RUNTIME_BRAND", "1")

        app = Aksara(database_url=None, auto_discover_views=False)
        app._print_shutdown()

        captured = capsys.readouterr().out
        assert "Database disconnected" in captured
        assert "Shutting down" not in captured