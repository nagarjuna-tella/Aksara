"""
Tests for server-oriented CLI commands.

Validates `aksara run` and `aksara dev` command ergonomics.
"""

from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from aksara.cli.main import cli


runner = CliRunner()


class TestRunCommand:
    """Tests for the `aksara run` command."""

    @patch("aksara.cli.main._run_dev_server")
    def test_run_dev_alias_forwards_to_dev_server(self, mock_run_dev_server):
        result = runner.invoke(cli, ["run", "dev", "--port", "9000"])

        assert result.exit_code == 0
        assert "Detected 'aksara run dev'" not in result.output
        mock_run_dev_server.assert_called_once_with(
            app_path="main:app",
            host="127.0.0.1",
            port=9000,
            reload=True,
            no_reload=False,
            log_level="info",
        )

    def test_run_invalid_bare_app_path_shows_guidance(self):
        result = runner.invoke(cli, ["run", "main"])

        assert result.exit_code == 2
        assert "Invalid app path 'main'" in result.output
        assert "aksara run main:app --reload" in result.output


class TestDevCommand:
    """Tests for the `aksara dev` command."""

    def test_dev_invalid_bare_app_path_shows_guidance(self):
        result = runner.invoke(cli, ["dev", "main"])

        assert result.exit_code == 2
        assert "Invalid app path 'main'" in result.output
        assert "aksara dev main:app" in result.output