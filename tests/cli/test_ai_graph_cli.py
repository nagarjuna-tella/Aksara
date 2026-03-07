"""
v0.5.32 — CLI ``aksara ai graph`` tests.

Tests cover:
    - Command registration and help text
    - --summary flag output
    - --json flag output (full and summary)
    - --events flag output
    - --rebuild flag
    - _print_graph_summary() output format
    - _print_graph_events() output format
    - Empty graph handling
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock, patch
from click.testing import CliRunner

from aksara.ai.project_graph import (
    ProjectGraph,
    ModelNode,
    AiHubNode,
    AiFlowNode,
    _invalidate_cache,
)


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _get_cli_group():
    from aksara.cli.main import ai_flows_group
    return ai_flows_group


def _make_graph():
    g = ProjectGraph()
    g.models = [ModelNode(name="User", table="users", fields=["id", "name"])]
    g.ai_hub = AiHubNode(providers=["openai"], status="ready")
    g.flows = [AiFlowNode(action_key="explain_model", title="Explain", flow_type="model", risk="low")]
    g.events = [
        {"kind": "route_error", "severity": "error", "message": "500 on /api", "timestamp": "2025-01-01T00:00:00Z", "source_type": "route", "source_id": "/api"},
        {"kind": "ai_flow_executed", "severity": "info", "message": "ran explain", "timestamp": "2025-01-01T00:01:00Z", "source_type": "flow", "source_id": "explain_model"},
    ]
    g.metadata.model_count = 1
    g.metadata.route_count = 0
    g.metadata.query_count = 0
    g.metadata.migration_count = 0
    g.metadata.diagnostic_count = 0
    g.metadata.gap_count = 0
    g.metadata.event_count = 2
    g.metadata.version = "0.5.35"
    g.metadata.generated_at = "2025-01-01T00:00:00Z"
    return g


def _patch_graph(graph=None):
    g = graph or _make_graph()
    return patch("aksara.ai.project_graph.build_project_graph", return_value=g)


# ═══════════════════════════════════════════════════════════════════════════
# Tests: Command Registration
# ═══════════════════════════════════════════════════════════════════════════


class TestGraphCommandRegistration:
    def test_graph_command_exists(self):
        group = _get_cli_group()
        names = [c.name for c in group.commands.values()]
        assert "graph" in names

    def test_graph_help_text(self):
        runner = CliRunner()
        group = _get_cli_group()
        result = runner.invoke(group, ["graph", "--help"])
        assert result.exit_code == 0
        assert "Project Context Graph" in result.output

    def test_graph_has_json_option(self):
        runner = CliRunner()
        group = _get_cli_group()
        result = runner.invoke(group, ["graph", "--help"])
        assert "--json" in result.output

    def test_graph_has_summary_option(self):
        runner = CliRunner()
        group = _get_cli_group()
        result = runner.invoke(group, ["graph", "--help"])
        assert "--summary" in result.output

    def test_graph_has_events_option(self):
        runner = CliRunner()
        group = _get_cli_group()
        result = runner.invoke(group, ["graph", "--help"])
        assert "--events" in result.output

    def test_graph_has_rebuild_option(self):
        runner = CliRunner()
        group = _get_cli_group()
        result = runner.invoke(group, ["graph", "--help"])
        assert "--rebuild" in result.output


# ═══════════════════════════════════════════════════════════════════════════
# Tests: Default Invocation (text summary)
# ═══════════════════════════════════════════════════════════════════════════


class TestGraphDefaultInvocation:
    def test_default_shows_summary(self):
        runner = CliRunner()
        group = _get_cli_group()
        with _patch_graph():
            result = runner.invoke(group, ["graph"])
        assert result.exit_code == 0
        assert "Project Graph" in result.output

    def test_default_shows_model_count(self):
        runner = CliRunner()
        group = _get_cli_group()
        with _patch_graph():
            result = runner.invoke(group, ["graph"])
        assert "Models:" in result.output
        assert "1" in result.output

    def test_default_shows_hub_status(self):
        runner = CliRunner()
        group = _get_cli_group()
        with _patch_graph():
            result = runner.invoke(group, ["graph"])
        assert "ready" in result.output

    def test_default_shows_version(self):
        runner = CliRunner()
        group = _get_cli_group()
        with _patch_graph():
            result = runner.invoke(group, ["graph"])
        assert "0.5.35" in result.output


# ═══════════════════════════════════════════════════════════════════════════
# Tests: --json flag
# ═══════════════════════════════════════════════════════════════════════════


class TestGraphJsonFlag:
    def test_json_output_is_valid(self):
        runner = CliRunner()
        group = _get_cli_group()
        with _patch_graph():
            result = runner.invoke(group, ["graph", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, dict)

    def test_json_has_models(self):
        runner = CliRunner()
        group = _get_cli_group()
        with _patch_graph():
            result = runner.invoke(group, ["graph", "--json"])
        data = json.loads(result.output)
        assert "models" in data

    def test_json_summary_flag(self):
        runner = CliRunner()
        group = _get_cli_group()
        with _patch_graph():
            result = runner.invoke(group, ["graph", "--json", "--summary"])
        data = json.loads(result.output)
        assert "counts" in data

    def test_json_events_flag(self):
        runner = CliRunner()
        group = _get_cli_group()
        with _patch_graph():
            result = runner.invoke(group, ["graph", "--json", "--events"])
        data = json.loads(result.output)
        assert "events" in data
        assert len(data["events"]) == 2


# ═══════════════════════════════════════════════════════════════════════════
# Tests: --summary flag
# ═══════════════════════════════════════════════════════════════════════════


class TestGraphSummaryFlag:
    def test_summary_shows_counts(self):
        runner = CliRunner()
        group = _get_cli_group()
        with _patch_graph():
            result = runner.invoke(group, ["graph", "--summary"])
        assert result.exit_code == 0
        assert "Models:" in result.output


# ═══════════════════════════════════════════════════════════════════════════
# Tests: --events flag
# ═══════════════════════════════════════════════════════════════════════════


class TestGraphEventsFlag:
    def test_events_shows_list(self):
        runner = CliRunner()
        group = _get_cli_group()
        with _patch_graph():
            result = runner.invoke(group, ["graph", "--events"])
        assert result.exit_code == 0
        assert "Recent Events" in result.output

    def test_events_shows_kind(self):
        runner = CliRunner()
        group = _get_cli_group()
        with _patch_graph():
            result = runner.invoke(group, ["graph", "--events"])
        assert "route_error" in result.output

    def test_empty_events(self):
        runner = CliRunner()
        group = _get_cli_group()
        g = _make_graph()
        g.events = []
        with _patch_graph(g):
            result = runner.invoke(group, ["graph", "--events"])
        assert "No recent events" in result.output


# ═══════════════════════════════════════════════════════════════════════════
# Tests: --rebuild flag
# ═══════════════════════════════════════════════════════════════════════════


class TestGraphRebuildFlag:
    def test_rebuild_calls_build_with_flag(self):
        runner = CliRunner()
        group = _get_cli_group()
        with _patch_graph() as mock_build:
            result = runner.invoke(group, ["graph", "--rebuild"])
        assert result.exit_code == 0
        mock_build.assert_called_once_with(rebuild=True)
