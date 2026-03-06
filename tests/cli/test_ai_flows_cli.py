"""
v0.5.29 — Studio AI Flows: CLI parity tests.

Validates:
    - `aksara ai flows` CLI command group exists
    - All 6 sub-commands exist and produce correct output
    - JSON output is parseable
    - Text output has human-readable sections
    - --format flag works
    - Bad action key returns error
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from aksara.cli.main import cli
from aksara.studio.ai_flows import AI_FLOW_ACTIONS


@pytest.fixture()
def runner():
    return CliRunner()


def _make_flow_response(**overrides):
    from aksara.studio.models import StudioAiFlowResponse
    defaults = dict(
        ok=True,
        action_key="explain_model",
        risk="low",
        provider="openai",
        model="gpt-4o",
        system_prompt="System.",
        user_prompt="User.",
        result_markdown="# Result\nDone.",
        result_json={"action_key": "explain_model"},
        suggested_next=["suggest_constraints"],
        what_it_does="Explains a model.",
        what_it_cannot_do="Cannot run migrations.",
    )
    defaults.update(overrides)
    return StudioAiFlowResponse(**defaults)


def _make_error_response(code="unknown_action", msg="Bad key"):
    from aksara.studio.models import StudioAiFlowResponse
    return StudioAiFlowResponse(
        ok=False,
        action_key="bad_key",
        error_code=code,
        error=msg,
    )


# ─── Group & Sub-commands ───────────────────────────────────────────────────

class TestFlowsCLIGroup:
    def test_ai_flows_group_help(self, runner):
        result = runner.invoke(cli, ["ai", "flows", "--help"])
        assert result.exit_code == 0
        assert "flows" in result.output.lower()

    def test_ai_flows_actions_help(self, runner):
        result = runner.invoke(cli, ["ai", "flows", "actions", "--help"])
        assert result.exit_code == 0

    def test_ai_flows_model_help(self, runner):
        result = runner.invoke(cli, ["ai", "flows", "model", "--help"])
        assert result.exit_code == 0
        assert "MODEL" in result.output or "model" in result.output.lower()

    def test_ai_flows_route_help(self, runner):
        result = runner.invoke(cli, ["ai", "flows", "route", "--help"])
        assert result.exit_code == 0

    def test_ai_flows_query_help(self, runner):
        result = runner.invoke(cli, ["ai", "flows", "query", "--help"])
        assert result.exit_code == 0

    def test_ai_flows_migration_help(self, runner):
        result = runner.invoke(cli, ["ai", "flows", "migration", "--help"])
        assert result.exit_code == 0

    def test_ai_flows_diagnostic_help(self, runner):
        result = runner.invoke(cli, ["ai", "flows", "diagnostic", "--help"])
        assert result.exit_code == 0


FLOWS_MOD = "aksara.studio.ai_flows"


# ─── actions ────────────────────────────────────────────────────────────────

class TestFlowsActionsCommand:
    def test_actions_text(self, runner):
        result = runner.invoke(cli, ["ai", "flows", "actions", "--format", "text"])
        assert result.exit_code == 0
        assert "explain_model" in result.output

    def test_actions_json(self, runner):
        result = runner.invoke(cli, ["ai", "flows", "actions", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        keys = {a["action_key"] for a in data}
        assert "explain_model" in keys

    def test_actions_shows_all(self, runner):
        result = runner.invoke(cli, ["ai", "flows", "actions", "--format", "json"])
        data = json.loads(result.output)
        assert len(data) == len(AI_FLOW_ACTIONS)


# ─── model flow ─────────────────────────────────────────────────────────────

class TestFlowsModelCommand:
    @patch(f"{FLOWS_MOD}.build_model_flow")
    def test_model_text(self, mock_build, runner):
        mock_build.return_value = _make_flow_response(action_key="explain_model")
        result = runner.invoke(cli, ["ai", "flows", "model", "User", "--action", "explain_model"])
        assert result.exit_code == 0
        mock_build.assert_called_once()

    @patch(f"{FLOWS_MOD}.build_model_flow")
    def test_model_json(self, mock_build, runner):
        mock_build.return_value = _make_flow_response(action_key="explain_model")
        result = runner.invoke(cli, ["ai", "flows", "model", "User", "--action", "explain_model", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["action_key"] == "explain_model"

    @patch(f"{FLOWS_MOD}.build_model_flow")
    def test_model_error(self, mock_build, runner):
        mock_build.return_value = _make_error_response()
        result = runner.invoke(cli, ["ai", "flows", "model", "User", "--action", "bad_key"])
        assert result.exit_code == 0
        assert "Error" in result.output or "error" in result.output.lower()


# ─── route flow ─────────────────────────────────────────────────────────────

class TestFlowsRouteCommand:
    @patch(f"{FLOWS_MOD}.build_route_flow")
    def test_route_text(self, mock_build, runner):
        mock_build.return_value = _make_flow_response(action_key="review_endpoint")
        result = runner.invoke(cli, ["ai", "flows", "route", "GET:/api/users", "--action", "review_endpoint"])
        assert result.exit_code == 0
        mock_build.assert_called_once()

    @patch(f"{FLOWS_MOD}.build_route_flow")
    def test_route_json(self, mock_build, runner):
        mock_build.return_value = _make_flow_response(action_key="review_endpoint")
        result = runner.invoke(cli, ["ai", "flows", "route", "GET:/api/users", "--action", "review_endpoint", "--format", "json"])
        data = json.loads(result.output)
        assert data["ok"] is True


# ─── query flow ─────────────────────────────────────────────────────────────

class TestFlowsQueryCommand:
    @patch(f"{FLOWS_MOD}.build_query_flow")
    def test_query_text(self, mock_build, runner):
        mock_build.return_value = _make_flow_response(action_key="explain_plan")
        result = runner.invoke(cli, ["ai", "flows", "query", "--sql", "SELECT 1", "--action", "explain_plan"])
        assert result.exit_code == 0
        mock_build.assert_called_once()

    @patch(f"{FLOWS_MOD}.build_query_flow")
    def test_query_json(self, mock_build, runner):
        mock_build.return_value = _make_flow_response(action_key="explain_plan")
        result = runner.invoke(cli, ["ai", "flows", "query", "--sql", "SELECT 1", "--action", "explain_plan", "--format", "json"])
        data = json.loads(result.output)
        assert data["action_key"] == "explain_plan"


# ─── migration flow ─────────────────────────────────────────────────────────

class TestFlowsMigrationCommand:
    @patch(f"{FLOWS_MOD}.build_migration_flow")
    def test_migration_text(self, mock_build, runner):
        mock_build.return_value = _make_flow_response(action_key="explain_migration")
        result = runner.invoke(cli, ["ai", "flows", "migration", "--app", "core", "--action", "explain_migration"])
        assert result.exit_code == 0
        mock_build.assert_called_once()

    @patch(f"{FLOWS_MOD}.build_migration_flow")
    def test_migration_json(self, mock_build, runner):
        mock_build.return_value = _make_flow_response(action_key="explain_migration")
        result = runner.invoke(cli, ["ai", "flows", "migration", "--app", "core", "--action", "explain_migration", "--format", "json"])
        data = json.loads(result.output)
        assert data["action_key"] == "explain_migration"


# ─── diagnostic flow ────────────────────────────────────────────────────────

class TestFlowsDiagnosticCommand:
    @patch(f"{FLOWS_MOD}.build_diagnostic_flow")
    def test_diagnostic_text(self, mock_build, runner):
        mock_build.return_value = _make_flow_response(action_key="diagnostic_prioritize")
        result = runner.invoke(cli, ["ai", "flows", "diagnostic", "--issue-id", "d-001", "--action", "diagnostic_prioritize"])
        assert result.exit_code == 0
        mock_build.assert_called_once()

    @patch(f"{FLOWS_MOD}.build_diagnostic_flow")
    def test_diagnostic_json(self, mock_build, runner):
        mock_build.return_value = _make_flow_response(action_key="diagnostic_prioritize")
        result = runner.invoke(cli, ["ai", "flows", "diagnostic", "--issue-id", "d-001", "--action", "diagnostic_prioritize", "--format", "json"])
        data = json.loads(result.output)
        assert data["action_key"] == "diagnostic_prioritize"


# ─── Output format ──────────────────────────────────────────────────────────

class TestOutputFormat:
    @patch(f"{FLOWS_MOD}.build_model_flow")
    def test_text_output_has_sections(self, mock_build, runner):
        mock_build.return_value = _make_flow_response()
        result = runner.invoke(cli, ["ai", "flows", "model", "User", "--action", "explain_model", "--format", "text"])
        # Text output should have some readable sections
        assert "explain_model" in result.output or "Result" in result.output

    @patch(f"{FLOWS_MOD}.build_model_flow")
    def test_json_output_is_valid(self, mock_build, runner):
        mock_build.return_value = _make_flow_response()
        result = runner.invoke(cli, ["ai", "flows", "model", "User", "--action", "explain_model", "--format", "json"])
        data = json.loads(result.output)
        assert "ok" in data
        assert "action_key" in data
        assert "system_prompt" in data
        assert "user_prompt" in data
        assert "result_markdown" in data

    @patch(f"{FLOWS_MOD}.build_model_flow")
    def test_json_has_suggested_next(self, mock_build, runner):
        mock_build.return_value = _make_flow_response(suggested_next=["a", "b"])
        result = runner.invoke(cli, ["ai", "flows", "model", "User", "--action", "explain_model", "--format", "json"])
        data = json.loads(result.output)
        assert data["suggested_next"] == ["a", "b"]

    @patch(f"{FLOWS_MOD}.build_model_flow")
    def test_json_has_risk(self, mock_build, runner):
        mock_build.return_value = _make_flow_response(risk="high")
        result = runner.invoke(cli, ["ai", "flows", "model", "User", "--action", "explain_model", "--format", "json"])
        data = json.loads(result.output)
        assert data["risk"] == "high"
