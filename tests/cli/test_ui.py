"""
v0.5.45 — CLI UI configuration tests.

Tests the semantic CLI renderer selection and quiet-mode behavior.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import click
from click.testing import CliRunner

from aksara.cli import ui as cli_ui
from aksara.cli.main import cli


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

    def test_dev_server_banner_renders_plain_hero(self):
        ui = cli_ui.build_ui(cli_ui.CLIUIConfig(mode="plain", quiet=False, unicode=True))

        with patch("click.echo") as echo:
            ui.dev_server_banner(
                "0.5.52",
                env="prod",
                debug=False,
                base_url="http://127.0.0.1:8000",
                admin_enabled=False,
                studio_enabled=False,
                actual_reload=True,
                log_level="info",
            )

        output = "\n".join(call.args[0] for call in echo.call_args_list)
        assert "╚═══╝" in output  # bottom of the full-height bolt is rendered
        assert "█████╗" in output  # AKSARA block-char art is rendered
        assert "Dev Server" in output
        assert "http://127.0.0.1:8000/docs" in output


class TestRootFlagPropagation:
    """Test that --quiet/--plain/--no-color/--force-color propagate to every
    command, including ones that still emit raw ANSI escape sequences via
    click.echo (rather than going through the ui semantic layer).
    """

    def setup_method(self):
        # Capture pre-existing env so we can restore (test should not leak).
        self._prev_no_color = os.environ.get("NO_COLOR")
        self._prev_force_color = os.environ.get("FORCE_COLOR")
        os.environ.pop("NO_COLOR", None)
        os.environ.pop("FORCE_COLOR", None)
        self._prev_echo = click.echo

    def teardown_method(self):
        if self._prev_no_color is None:
            os.environ.pop("NO_COLOR", None)
        else:
            os.environ["NO_COLOR"] = self._prev_no_color
        if self._prev_force_color is None:
            os.environ.pop("FORCE_COLOR", None)
        else:
            os.environ["FORCE_COLOR"] = self._prev_force_color
        click.echo = self._prev_echo

    def test_no_color_strips_ansi_from_raw_ansi_command(self):
        """--no-color should strip raw \\033[...m codes from the `templates list`
        command output (the command emits raw ANSI via click.echo)."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--no-color", "templates", "list"])
        assert result.exit_code == 0
        assert "\x1b[" not in result.output  # no ANSI escapes in output
        assert "basic" in result.output  # but content is still there

    def test_plain_strips_ansi_from_raw_ansi_command(self):
        """--plain should also imply no-color and strip ANSI from raw-ANSI commands."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--plain", "templates", "list"])
        assert result.exit_code == 0
        assert "\x1b[" not in result.output

    def test_quiet_silences_non_error_output(self):
        """--quiet should silence non-error click.echo output across every command."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--quiet", "templates", "list"])
        assert result.exit_code == 0
        # `templates list` only emits non-error output, so --quiet drops everything.
        assert result.output.strip() == ""

    def test_quiet_preserves_error_output(self):
        """Errors (err=True) should still pass through --quiet — startproject
        on an existing directory emits an error message via ui.error()."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            os.mkdir("conflict")
            result = runner.invoke(cli, ["--quiet", "startproject", "conflict"])
            # Whatever the exit code, the error text must reach the user.
            assert "already exists" in result.output.lower()

    def test_color_env_restored_after_invocation(self):
        """Setting --no-color must not leave NO_COLOR set in the parent process env."""
        runner = CliRunner()
        runner.invoke(cli, ["--no-color", "templates", "list"])
        # NO_COLOR was unset before invocation; should still be unset after.
        assert "NO_COLOR" not in os.environ

    def test_quiet_restores_click_echo_after_invocation(self):
        """--quiet must restore click.echo after the cli invocation completes."""
        runner = CliRunner()
        runner.invoke(cli, ["--quiet", "templates", "list"])
        assert click.echo is self._prev_echo
