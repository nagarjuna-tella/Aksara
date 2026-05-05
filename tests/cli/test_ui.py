"""
v0.5.45 — CLI UI configuration tests.

Tests the semantic CLI renderer selection and quiet-mode behavior.
"""

from __future__ import annotations

from unittest.mock import patch

from aksara.cli import ui as cli_ui


class _FakeStream:
    """Minimal stream object with controllable TTY detection."""

    def __init__(self, is_tty: bool):
        self._is_tty = is_tty

    def isatty(self) -> bool:
        return self._is_tty


def _set_streams(monkeypatch, *, is_tty: bool) -> None:
    """Patch stdout/stderr TTY detection for UI config tests."""

    monkeypatch.setattr(cli_ui.sys, "stdout", _FakeStream(is_tty))
    monkeypatch.setattr(cli_ui.sys, "stderr", _FakeStream(is_tty))


class TestResolveUiConfig:
    """Test CLI UI mode resolution."""

    def test_ci_forces_plain_mode(self, monkeypatch):
        monkeypatch.setenv("CI", "true")
        monkeypatch.setenv("TERM", "xterm-256color")
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.delenv("FORCE_COLOR", raising=False)
        monkeypatch.delenv("AKSARA_CLI_MODE", raising=False)
        _set_streams(monkeypatch, is_tty=True)

        config = cli_ui.resolve_ui_config()

        assert config.mode == "plain"
        assert config.is_ci is True

    def test_no_color_forces_plain_mode(self, monkeypatch):
        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.setenv("TERM", "xterm-256color")
        monkeypatch.delenv("CI", raising=False)
        monkeypatch.delenv("FORCE_COLOR", raising=False)
        monkeypatch.delenv("AKSARA_CLI_MODE", raising=False)
        _set_streams(monkeypatch, is_tty=True)

        config = cli_ui.resolve_ui_config()

        assert config.mode == "plain"
        assert config.no_color is True

    def test_force_color_enables_rich_mode_in_auto_mode(self, monkeypatch):
        monkeypatch.setenv("TERM", "xterm-256color")
        monkeypatch.delenv("CI", raising=False)
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.delenv("FORCE_COLOR", raising=False)
        monkeypatch.delenv("AKSARA_CLI_MODE", raising=False)
        _set_streams(monkeypatch, is_tty=False)

        config = cli_ui.resolve_ui_config(force_color=True)

        assert config.mode == "rich"
        assert config.force_color is True

    def test_plain_flag_disables_unicode(self, monkeypatch):
        monkeypatch.setenv("TERM", "xterm-256color")
        monkeypatch.delenv("CI", raising=False)
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.delenv("FORCE_COLOR", raising=False)
        monkeypatch.delenv("AKSARA_CLI_MODE", raising=False)
        _set_streams(monkeypatch, is_tty=True)

        config = cli_ui.resolve_ui_config(plain=True)

        assert config.mode == "plain"
        assert config.unicode is False


class TestBuildUi:
    """Test UI object construction."""

    def test_build_ui_falls_back_to_plain_when_rich_renderer_fails(self):
        config = cli_ui.CLIUIConfig(mode="rich", is_tty=True)

        with patch("aksara.cli.ui.RichRenderer", side_effect=RuntimeError("boom")):
            ui = cli_ui.build_ui(config)

        assert ui.config.mode == "plain"
        assert ui.is_rich is False


class TestCliUiBehavior:
    """Test semantic output behavior."""

    def test_quiet_mode_suppresses_non_error_text(self):
        ui = cli_ui.build_ui(cli_ui.CLIUIConfig(mode="plain", quiet=True))

        with patch("click.echo") as echo:
            ui.text("hidden")
            ui.blank()
            ui.success("done")
            ui.error("problem")

        assert echo.call_count == 1
        assert echo.call_args.kwargs["err"] is True
        assert "problem" in echo.call_args.args[0]
