"""
Tests for Agent Playbooks — CLI Commands.

v0.5.20: Tests for `aksara agent playbooks` and `aksara agent playbook-run`.
"""

import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from click.testing import CliRunner

from aksara.cli.main import cli


# =============================================================================
# Fixtures
# =============================================================================


def _mock_agent_context():
    """Create a mock agent context for CLI tests."""
    from aksara.studio.models import AgentContextSection, StudioAgentContext

    return StudioAgentContext(
        total_sections=2,
        total_size_kb=1.0,
        sections=[
            AgentContextSection(
                title="Models", description="All models", key="models",
                data=[{"name": "User"}], size_kb=0.5,
            ),
            AgentContextSection(
                title="Routes", description="All routes", key="routes",
                data=[{"path": "/api/users"}], size_kb=0.5,
            ),
        ],
    )


# =============================================================================
# aksara agent playbooks
# =============================================================================


class TestAgentPlaybooksCLI:
    """Tests for `aksara agent playbooks` command."""

    def test_playbooks_pretty(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["agent", "playbooks"])
        assert result.exit_code == 0
        assert "Agent Playbooks" in result.output
        assert "add_field_to_model" in result.output

    def test_playbooks_json(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["agent", "playbooks", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "playbooks" in data
        assert "total_count" in data
        assert data["total_count"] >= 7
        assert "by_category" in data

    def test_playbooks_filter_category(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["agent", "playbooks", "--category", "schema"])
        assert result.exit_code == 0
        assert "schema" in result.output.lower()

    def test_playbooks_filter_category_json(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["agent", "playbooks", "-f", "json", "-c", "api"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        for pb in data["playbooks"]:
            assert pb["category"] == "api"

    def test_playbooks_filter_risk(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["agent", "playbooks", "--risk", "high"])
        assert result.exit_code == 0
        assert "high" in result.output

    def test_playbooks_filter_usage(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["agent", "playbooks", "--usage", "admin"])
        assert result.exit_code == 0
        assert "admin" in result.output

    def test_playbooks_filter_no_results(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["agent", "playbooks", "-c", "nonexistent"])
        assert result.exit_code == 0
        assert "0 playbook(s)" in result.output

    def test_playbooks_shows_steps_count(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["agent", "playbooks"])
        assert result.exit_code == 0
        assert "Steps:" in result.output

    def test_playbooks_shows_risk_level(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["agent", "playbooks"])
        assert result.exit_code == 0
        assert "Risk:" in result.output

    def test_playbooks_shows_categories_summary(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["agent", "playbooks"])
        assert result.exit_code == 0
        assert "Categories:" in result.output


# =============================================================================
# aksara agent playbook-run
# =============================================================================


class TestAgentPlaybookRunCLI:
    """Tests for `aksara agent playbook-run` command."""

    @patch("aksara.cli.main._run_agent_context")
    @patch("aksara.cli.main._get_settings")
    def test_playbook_run_text(self, mock_settings, mock_run_ctx):
        mock_settings.return_value = MagicMock(app_module=None)
        mock_run_ctx.return_value = _mock_agent_context()

        runner = CliRunner()
        result = runner.invoke(cli, [
            "agent", "playbook-run", "add_field_to_model",
            "--goal", "Add email to User",
        ])
        assert result.exit_code == 0
        assert "Playbook: Add Field to Model" in result.output
        assert "Add email to User" in result.output

    @patch("aksara.cli.main._run_agent_context")
    @patch("aksara.cli.main._get_settings")
    def test_playbook_run_json(self, mock_settings, mock_run_ctx):
        mock_settings.return_value = MagicMock(app_module=None)
        mock_run_ctx.return_value = _mock_agent_context()

        runner = CliRunner()
        result = runner.invoke(cli, [
            "agent", "playbook-run", "add_field_to_model",
            "--goal", "Add email to User",
            "--format", "json",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "system_prompt" in data
        assert "Playbook: Add Field to Model" in data["system_prompt"]

    @patch("aksara.cli.main._run_agent_context")
    @patch("aksara.cli.main._get_settings")
    def test_playbook_run_default_goal(self, mock_settings, mock_run_ctx):
        mock_settings.return_value = MagicMock(app_module=None)
        mock_run_ctx.return_value = _mock_agent_context()

        runner = CliRunner()
        result = runner.invoke(cli, [
            "agent", "playbook-run", "debug_slow_queries",
        ])
        assert result.exit_code == 0
        # Should use default_goal_template since no --goal
        assert "Playbook: Debug Slow Queries" in result.output

    def test_playbook_run_unknown_key(self):
        runner = CliRunner()
        result = runner.invoke(cli, [
            "agent", "playbook-run", "nonexistent_key",
        ])
        assert result.exit_code != 0
        assert "Playbook not found" in result.output

    @patch("aksara.cli.main._run_agent_context")
    @patch("aksara.cli.main._get_settings")
    def test_playbook_run_with_sections(self, mock_settings, mock_run_ctx):
        mock_settings.return_value = MagicMock(app_module=None)
        mock_run_ctx.return_value = _mock_agent_context()

        runner = CliRunner()
        result = runner.invoke(cli, [
            "agent", "playbook-run", "add_field_to_model",
            "--goal", "Test",
            "--sections", "models,routes",
        ])
        assert result.exit_code == 0
        assert "Models" in result.output
        assert "Routes" in result.output

    @patch("aksara.cli.main._run_agent_context")
    @patch("aksara.cli.main._get_settings")
    def test_playbook_run_shows_meta(self, mock_settings, mock_run_ctx):
        mock_settings.return_value = MagicMock(app_module=None)
        mock_run_ctx.return_value = _mock_agent_context()

        runner = CliRunner()
        result = runner.invoke(cli, [
            "agent", "playbook-run", "harden_endpoint_permissions",
            "--goal", "Harden /api/users",
        ])
        assert result.exit_code == 0
        assert "Playbook:" in result.output
        assert "Model:" in result.output
        assert "Temp:" in result.output
        assert "tokens" in result.output

    @patch("aksara.cli.main._run_agent_context")
    @patch("aksara.cli.main._get_settings")
    def test_all_builtin_playbooks_runnable(self, mock_settings, mock_run_ctx):
        """Verify every built-in playbook can be run without error."""
        from aksara.ai.playbooks import get_builtin_playbooks

        mock_settings.return_value = MagicMock(app_module=None)
        mock_run_ctx.return_value = _mock_agent_context()

        runner = CliRunner()
        for pb in get_builtin_playbooks().playbooks:
            result = runner.invoke(cli, [
                "agent", "playbook-run", pb.key,
                "--goal", "Test run",
                "-f", "json",
            ])
            assert result.exit_code == 0, f"Failed for playbook: {pb.key}"
            data = json.loads(result.output)
            assert "system_prompt" in data
