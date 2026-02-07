"""
Tests for Agent Mode — CLI Commands.

v0.5.19: Tests for `aksara agent context` and `aksara agent prompt`.
"""

import pytest
import json
from click.testing import CliRunner
from unittest.mock import patch, MagicMock, AsyncMock

from aksara.studio.models import (
    AgentContextSection,
    StudioAgentContext,
    StudioAgentPromptResponse,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def runner():
    """Create CLI runner."""
    return CliRunner()


def _make_mock_context():
    """Create a mock StudioAgentContext."""
    return StudioAgentContext(
        total_sections=3,
        total_size_kb=1.5,
        sections=[
            AgentContextSection(
                title="Project Info", description="App info", key="project_info",
                data={"app_title": "TestApp"}, size_kb=0.5,
            ),
            AgentContextSection(
                title="Models", description="DB models", key="models",
                data=[{"name": "User"}], size_kb=0.6,
            ),
            AgentContextSection(
                title="Routes", description="API routes", key="routes",
                data=[], size_kb=0.4,
            ),
        ],
    )


def _make_mock_prompt_response():
    """Create a mock StudioAgentPromptResponse."""
    return StudioAgentPromptResponse(
        system_prompt="You are an expert Aksara assistant.\nGoal: Fix bugs",
        recommended_temperature=0.5,
        recommended_model="gpt-4o",
        tokens_estimate=42,
    )


# =============================================================================
# Agent Context Tests
# =============================================================================


class TestAgentContextCli:
    """Tests for `aksara agent context` command."""

    def test_context_pretty_output(self, runner):
        from aksara.cli.main import cli

        mock_ctx = _make_mock_context()

        with patch("aksara.cli.main._run_agent_context", new_callable=AsyncMock, return_value=mock_ctx):
            result = runner.invoke(cli, ["agent", "context"])
            assert result.exit_code == 0
            assert "Project Info" in result.output
            assert "Models" in result.output
            assert "Routes" in result.output

    def test_context_json_output(self, runner):
        from aksara.cli.main import cli

        mock_ctx = _make_mock_context()

        with patch("aksara.cli.main._run_agent_context", new_callable=AsyncMock, return_value=mock_ctx):
            result = runner.invoke(cli, ["agent", "context", "--output", "json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert "sections" in data
            assert len(data["sections"]) == 3

    def test_context_summary_flag(self, runner):
        from aksara.cli.main import cli

        mock_ctx = _make_mock_context()

        with patch("aksara.cli.main._run_agent_context", new_callable=AsyncMock, return_value=mock_ctx):
            result = runner.invoke(cli, ["agent", "context", "--summary"])
            assert result.exit_code == 0
            assert "Project Info" in result.output
            assert "KB" in result.output

    def test_context_size_flag(self, runner):
        from aksara.cli.main import cli

        mock_ctx = _make_mock_context()

        with patch("aksara.cli.main._run_agent_context", new_callable=AsyncMock, return_value=mock_ctx):
            result = runner.invoke(cli, ["agent", "context", "--size"])
            assert result.exit_code == 0
            assert "Total size:" in result.output
            assert "3 section(s)" in result.output

    def test_context_sections_filter(self, runner):
        from aksara.cli.main import cli

        mock_ctx = _make_mock_context()

        with patch("aksara.cli.main._run_agent_context", new_callable=AsyncMock, return_value=mock_ctx):
            result = runner.invoke(cli, ["agent", "context", "--sections", "models"])
            assert result.exit_code == 0
            assert "Models" in result.output
            # Project Info should not appear in filtered pretty output
            # (it may appear as a general header but not as a section entry)

    def test_context_sections_filter_json(self, runner):
        from aksara.cli.main import cli

        mock_ctx = _make_mock_context()

        with patch("aksara.cli.main._run_agent_context", new_callable=AsyncMock, return_value=mock_ctx):
            result = runner.invoke(cli, ["agent", "context", "--sections", "models,routes", "--output", "json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            keys = [s["key"] for s in data["sections"]]
            assert "models" in keys
            assert "routes" in keys
            assert "project_info" not in keys

    def test_context_error_handling(self, runner):
        from aksara.cli.main import cli

        with patch("aksara.cli.main._run_agent_context", new_callable=AsyncMock, side_effect=Exception("boom")):
            result = runner.invoke(cli, ["agent", "context"])
            assert result.exit_code == 1
            assert "Error" in result.output


# =============================================================================
# Agent Prompt Tests
# =============================================================================


class TestAgentPromptCli:
    """Tests for `aksara agent prompt` command."""

    def test_prompt_requires_goal(self, runner):
        from aksara.cli.main import cli
        result = runner.invoke(cli, ["agent", "prompt"])
        assert result.exit_code != 0
        assert "goal" in result.output.lower() or "required" in result.output.lower() or "Missing" in result.output

    def test_prompt_text_output(self, runner):
        from aksara.cli.main import cli

        mock_ctx = _make_mock_context()
        mock_resp = _make_mock_prompt_response()

        with patch("aksara.cli.main._run_agent_context", new_callable=AsyncMock, return_value=mock_ctx), \
             patch("aksara.cli.main.agent_prompt.__wrapped__", None, create=True), \
             patch("aksara.studio.utils.build_agent_prompt", return_value=mock_resp):
            result = runner.invoke(cli, ["agent", "prompt", "--goal", "Fix bugs"])
            assert result.exit_code == 0
            assert "expert" in result.output.lower() or "Fix bugs" in result.output

    def test_prompt_json_output(self, runner):
        from aksara.cli.main import cli

        mock_ctx = _make_mock_context()
        mock_resp = _make_mock_prompt_response()

        with patch("aksara.cli.main._run_agent_context", new_callable=AsyncMock, return_value=mock_ctx), \
             patch("aksara.studio.utils.build_agent_prompt", return_value=mock_resp):
            result = runner.invoke(cli, ["agent", "prompt", "--goal", "Fix bugs", "--format", "json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert "system_prompt" in data
            assert "recommended_model" in data

    def test_prompt_with_sections(self, runner):
        from aksara.cli.main import cli

        mock_ctx = _make_mock_context()
        mock_resp = _make_mock_prompt_response()

        with patch("aksara.cli.main._run_agent_context", new_callable=AsyncMock, return_value=mock_ctx), \
             patch("aksara.studio.utils.build_agent_prompt", return_value=mock_resp):
            result = runner.invoke(cli, ["agent", "prompt", "--goal", "Query", "--sections", "models"])
            assert result.exit_code == 0

    def test_prompt_with_custom_prefix(self, runner):
        from aksara.cli.main import cli

        mock_ctx = _make_mock_context()
        mock_resp = _make_mock_prompt_response()

        with patch("aksara.cli.main._run_agent_context", new_callable=AsyncMock, return_value=mock_ctx), \
             patch("aksara.studio.utils.build_agent_prompt", return_value=mock_resp):
            result = runner.invoke(cli, [
                "agent", "prompt",
                "--goal", "Build API",
                "--custom-system-prompt", "You are a wizard."
            ])
            assert result.exit_code == 0

    def test_prompt_shows_meta(self, runner):
        from aksara.cli.main import cli

        mock_ctx = _make_mock_context()
        mock_resp = _make_mock_prompt_response()

        with patch("aksara.cli.main._run_agent_context", new_callable=AsyncMock, return_value=mock_ctx), \
             patch("aksara.studio.utils.build_agent_prompt", return_value=mock_resp):
            result = runner.invoke(cli, ["agent", "prompt", "--goal", "Deploy", "--format", "text"])
            assert result.exit_code == 0
            assert "gpt-4o" in result.output
            assert "42" in result.output

    def test_prompt_error_handling(self, runner):
        from aksara.cli.main import cli

        with patch("aksara.cli.main._run_agent_context", new_callable=AsyncMock, side_effect=Exception("boom")):
            result = runner.invoke(cli, ["agent", "prompt", "--goal", "Help"])
            assert result.exit_code == 1
            assert "Error" in result.output
