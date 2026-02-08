"""
Tests for Agentic Workflows — CLI Commands.

v0.5.23: Tests for `aksara agent workflow` command.
"""

import pytest
import json
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from aksara.studio.models import (
    AgentWorkflow,
    AgentWorkflowStep,
)


@pytest.fixture
def runner():
    return CliRunner()


def _make_mock_workflow():
    """Build a simple mock workflow for CLI tests."""
    from aksara.ai.workflows import build_agent_workflow

    return build_agent_workflow(
        "fix slow queries on /api/posts/",
        include_diagnostics=False,
        include_search=False,
    )


# =============================================================================
# Text Output Tests
# =============================================================================


class TestAgentWorkflowTextOutput:
    """Tests for `aksara agent workflow` text output."""

    def test_basic_text_output(self, runner):
        from aksara.cli.main import cli

        result = runner.invoke(cli, [
            "agent", "workflow", "fix slow queries",
            "--no-diagnostics", "--no-search",
        ])
        assert result.exit_code == 0
        assert "Goal:" in result.output
        assert "fix slow queries" in result.output

    def test_text_output_has_steps(self, runner):
        from aksara.cli.main import cli

        result = runner.invoke(cli, [
            "agent", "workflow", "fix slow queries",
            "--no-diagnostics", "--no-search",
        ])
        assert result.exit_code == 0
        # Should have at least inspect + test steps
        assert "inspect" in result.output.lower()

    def test_text_output_with_playbook(self, runner):
        from aksara.cli.main import cli

        result = runner.invoke(cli, [
            "agent", "workflow", "add field to model",
            "--playbook", "add_field_to_model",
            "--no-diagnostics", "--no-search",
        ])
        assert result.exit_code == 0
        assert "Playbook:" in result.output
        assert "add_field_to_model" in result.output

    def test_text_output_shows_source(self, runner):
        from aksara.cli.main import cli

        result = runner.invoke(cli, [
            "agent", "workflow", "test goal",
            "--no-diagnostics", "--no-search",
        ])
        assert result.exit_code == 0
        assert "Source:" in result.output

    def test_text_output_shows_step_count(self, runner):
        from aksara.cli.main import cli

        result = runner.invoke(cli, [
            "agent", "workflow", "test goal",
            "--no-diagnostics", "--no-search",
        ])
        assert result.exit_code == 0
        assert "Steps:" in result.output


# =============================================================================
# JSON Output Tests
# =============================================================================


class TestAgentWorkflowJsonOutput:
    """Tests for `aksara agent workflow --format json` output."""

    def test_json_output_parsable(self, runner):
        from aksara.cli.main import cli

        result = runner.invoke(cli, [
            "agent", "workflow", "fix slow queries",
            "--no-diagnostics", "--no-search",
            "--format", "json",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "workflow" in data
        assert "summary" in data
        assert "stats" in data

    def test_json_output_has_correct_goal(self, runner):
        from aksara.cli.main import cli

        result = runner.invoke(cli, [
            "agent", "workflow", "fix login bug",
            "--no-diagnostics", "--no-search",
            "--format", "json",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["workflow"]["goal"] == "fix login bug"

    def test_json_output_has_steps(self, runner):
        from aksara.cli.main import cli

        result = runner.invoke(cli, [
            "agent", "workflow", "fix login bug",
            "--no-diagnostics", "--no-search",
            "--format", "json",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["workflow"]["steps"]) > 0

    def test_json_output_with_playbook(self, runner):
        from aksara.cli.main import cli

        result = runner.invoke(cli, [
            "agent", "workflow", "add email",
            "--playbook", "add_field_to_model",
            "--no-diagnostics", "--no-search",
            "--format", "json",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["workflow"]["playbook"] == "add_field_to_model"

    def test_json_stats_total_matches_steps(self, runner):
        from aksara.cli.main import cli

        result = runner.invoke(cli, [
            "agent", "workflow", "test",
            "--no-diagnostics", "--no-search",
            "--format", "json",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["stats"]["total_steps"] == len(data["workflow"]["steps"])


# =============================================================================
# Option Tests
# =============================================================================


class TestAgentWorkflowOptions:
    """Tests for CLI option handling."""

    def test_no_diagnostics_flag(self, runner):
        from aksara.cli.main import cli

        result = runner.invoke(cli, [
            "agent", "workflow", "test",
            "--no-diagnostics", "--no-search",
            "--format", "json",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        kinds = [s["kind"] for s in data["workflow"]["steps"]]
        assert "diagnostics" not in kinds

    def test_no_search_flag(self, runner):
        from aksara.cli.main import cli

        result = runner.invoke(cli, [
            "agent", "workflow", "test",
            "--no-diagnostics", "--no-search",
            "--format", "json",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        kinds = [s["kind"] for s in data["workflow"]["steps"]]
        assert "search" not in kinds

    def test_search_query_option(self, runner):
        from aksara.cli.main import cli

        result = runner.invoke(cli, [
            "agent", "workflow", "test",
            "--no-diagnostics",
            "--search-query", "custom search",
            "--format", "json",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["workflow"]["metadata"].get("search_query") == "custom search"
