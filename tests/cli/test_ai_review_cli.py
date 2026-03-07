"""
v0.5.34 — AI Architecture Review: CLI command tests.

Tests cover:
    - Command registration under `aksara ai flows review`
    - Text output (score, grade, findings, suggestions)
    - JSON output (--json)
    - Summary output (--summary)
    - Metrics output (--metrics)
    - Graph failure handling
    - Output structure
    - Console integration (intent routing)
"""

from __future__ import annotations

import asyncio
import json
import pytest
from unittest.mock import MagicMock, patch
from click.testing import CliRunner

from aksara.cli.main import cli, ai_flows_group, ai_review


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _make_model(name="User"):
    m = MagicMock()
    m.name = name
    m.table = name.lower() + "s"
    m.fields = ["id", "name"]
    m.relations = []
    m.indexes = []
    m.tags = []
    return m


def _make_route(method="GET", path="/api/users", models=None, queries=None):
    r = MagicMock()
    r.method = method
    r.path = path
    r.name = "route"
    r.handler = "h"
    r.models = models or []
    r.queries = queries or []
    r.diagnostics = []
    return r


def _make_diagnostic(code="D1", severity="warning", message="issue",
                     related_models=None, related_routes=None, related_queries=None):
    d = MagicMock()
    d.code = code
    d.severity = severity
    d.message = message
    d.related_models = related_models or []
    d.related_routes = related_routes or []
    d.related_queries = related_queries or []
    return d


def _make_graph(models=None, routes=None, queries=None, migrations=None,
                diagnostics=None, events=None):
    g = MagicMock()
    g.models = models or []
    g.routes = routes or []
    g.queries = queries or []
    g.migrations = migrations or []
    g.diagnostics = diagnostics or []
    g.gaps = []
    g.events = events or []
    g.flows = []
    g.ai_hub = None
    g.metadata = MagicMock()
    g.metadata.version = "0.5.36"
    g.metadata.model_count = len(g.models)
    g.metadata.route_count = len(g.routes)
    return g


# ═══════════════════════════════════════════════════════════════════════════
# Command Registration
# ═══════════════════════════════════════════════════════════════════════════

runner = CliRunner()


class TestCommandRegistration:
    def test_review_command_exists(self):
        assert "review" in [c.name for c in ai_flows_group.commands.values()]

    def test_help_text(self):
        result = runner.invoke(ai_flows_group, ["review", "--help"])
        assert result.exit_code == 0
        assert "Architecture Review" in result.output

    def test_json_option(self):
        result = runner.invoke(ai_flows_group, ["review", "--help"])
        assert "--json" in result.output

    def test_summary_option(self):
        result = runner.invoke(ai_flows_group, ["review", "--help"])
        assert "--summary" in result.output

    def test_metrics_option(self):
        result = runner.invoke(ai_flows_group, ["review", "--help"])
        assert "--metrics" in result.output


# ═══════════════════════════════════════════════════════════════════════════
# Text Output
# ═══════════════════════════════════════════════════════════════════════════


class TestTextOutput:
    @patch("aksara.ai.project_graph.build_project_graph")
    def test_basic_output(self, mock_graph):
        mock_graph.return_value = _make_graph(
            models=[_make_model()],
            routes=[_make_route()],
        )
        result = runner.invoke(ai_flows_group, ["review"])
        assert result.exit_code == 0
        assert "Architecture Score" in result.output
        assert "Findings" in result.output

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_shows_grade(self, mock_graph):
        mock_graph.return_value = _make_graph()
        result = runner.invoke(ai_flows_group, ["review"])
        assert result.exit_code == 0
        # Grade should be one of A-F
        assert any(f"({g})" in result.output for g in ["A", "B", "C", "D", "F"])

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_shows_findings_when_present(self, mock_graph):
        routes = [_make_route(models=["A", "B", "C", "D"])]
        mock_graph.return_value = _make_graph(routes=routes)
        result = runner.invoke(ai_flows_group, ["review"])
        assert result.exit_code == 0
        assert "Top Findings" in result.output

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_shows_suggestions_when_present(self, mock_graph):
        routes = [_make_route(models=["A", "B", "C", "D"])]
        mock_graph.return_value = _make_graph(routes=routes)
        result = runner.invoke(ai_flows_group, ["review"])
        assert result.exit_code == 0
        assert "Suggestions" in result.output

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_shows_elapsed(self, mock_graph):
        mock_graph.return_value = _make_graph()
        result = runner.invoke(ai_flows_group, ["review"])
        assert "ms" in result.output


# ═══════════════════════════════════════════════════════════════════════════
# JSON Output
# ═══════════════════════════════════════════════════════════════════════════


class TestJsonOutput:
    @patch("aksara.ai.project_graph.build_project_graph")
    def test_json_output(self, mock_graph):
        mock_graph.return_value = _make_graph()
        result = runner.invoke(ai_flows_group, ["review", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "score" in data
        assert "grade" in data
        assert "findings" in data
        assert "suggestions" in data

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_json_has_metrics(self, mock_graph):
        mock_graph.return_value = _make_graph()
        result = runner.invoke(ai_flows_group, ["review", "--json"])
        data = json.loads(result.output)
        assert "metrics" in data
        assert "model_count" in data["metrics"]

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_json_with_findings(self, mock_graph):
        routes = [_make_route(models=["A", "B", "C", "D"])]
        mock_graph.return_value = _make_graph(routes=routes)
        result = runner.invoke(ai_flows_group, ["review", "--json"])
        data = json.loads(result.output)
        assert len(data["findings"]) >= 1

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_json_score_range(self, mock_graph):
        mock_graph.return_value = _make_graph()
        result = runner.invoke(ai_flows_group, ["review", "--json"])
        data = json.loads(result.output)
        assert 0 <= data["score"] <= 100


# ═══════════════════════════════════════════════════════════════════════════
# Summary Output
# ═══════════════════════════════════════════════════════════════════════════


class TestSummaryOutput:
    @patch("aksara.ai.project_graph.build_project_graph")
    def test_summary_mode(self, mock_graph):
        mock_graph.return_value = _make_graph()
        result = runner.invoke(ai_flows_group, ["review", "--summary"])
        assert result.exit_code == 0
        assert "Architecture Score" in result.output

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_summary_no_findings_list(self, mock_graph):
        """Summary mode should NOT show full findings list."""
        mock_graph.return_value = _make_graph()
        result = runner.invoke(ai_flows_group, ["review", "--summary"])
        assert "Top Findings" not in result.output

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_summary_json(self, mock_graph):
        mock_graph.return_value = _make_graph()
        result = runner.invoke(ai_flows_group, ["review", "--json", "--summary"])
        data = json.loads(result.output)
        assert "score" in data
        assert "top_findings" in data
        assert "top_suggestions" in data


# ═══════════════════════════════════════════════════════════════════════════
# Metrics Output
# ═══════════════════════════════════════════════════════════════════════════


class TestMetricsOutput:
    @patch("aksara.ai.project_graph.build_project_graph")
    def test_metrics_flag(self, mock_graph):
        mock_graph.return_value = _make_graph(
            models=[_make_model()],
            routes=[_make_route()],
        )
        result = runner.invoke(ai_flows_group, ["review", "--metrics"])
        assert result.exit_code == 0
        assert "Metrics" in result.output
        assert "Models" in result.output
        assert "Routes" in result.output

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_metrics_shows_coupling(self, mock_graph):
        mock_graph.return_value = _make_graph()
        result = runner.invoke(ai_flows_group, ["review", "--metrics"])
        assert "Coupling score" in result.output


# ═══════════════════════════════════════════════════════════════════════════
# Error Handling
# ═══════════════════════════════════════════════════════════════════════════


class TestErrorHandling:
    @patch("aksara.ai.project_graph.build_project_graph")
    def test_graph_failure_text(self, mock_graph):
        mock_graph.side_effect = RuntimeError("no graph")
        result = runner.invoke(ai_flows_group, ["review"])
        assert result.exit_code == 0
        assert "failed" in result.output.lower()

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_graph_failure_json(self, mock_graph):
        mock_graph.side_effect = RuntimeError("no graph")
        result = runner.invoke(ai_flows_group, ["review", "--json"])
        data = json.loads(result.output)
        assert data["ok"] is False
        assert data["score"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# Output Structure
# ═══════════════════════════════════════════════════════════════════════════


class TestOutputStructure:
    @patch("aksara.ai.project_graph.build_project_graph")
    def test_json_keys(self, mock_graph):
        mock_graph.return_value = _make_graph()
        result = runner.invoke(ai_flows_group, ["review", "--json"])
        data = json.loads(result.output)
        expected_keys = ["score", "grade", "findings", "suggestions",
                         "metrics", "ok", "generated_at", "elapsed_ms"]
        for key in expected_keys:
            assert key in data, f"Missing key: {key}"

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_finding_structure(self, mock_graph):
        routes = [_make_route(models=["A", "B", "C", "D"])]
        mock_graph.return_value = _make_graph(routes=routes)
        result = runner.invoke(ai_flows_group, ["review", "--json"])
        data = json.loads(result.output)
        assert len(data["findings"]) >= 1
        f = data["findings"][0]
        assert "id" in f
        assert "severity" in f
        assert "title" in f
        assert "category" in f

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_suggestion_structure(self, mock_graph):
        routes = [_make_route(models=["A", "B", "C", "D"])]
        mock_graph.return_value = _make_graph(routes=routes)
        result = runner.invoke(ai_flows_group, ["review", "--json"])
        data = json.loads(result.output)
        assert len(data["suggestions"]) >= 1
        s = data["suggestions"][0]
        assert "suggestion_id" in s
        assert "title" in s
        assert "impact" in s

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_metrics_structure(self, mock_graph):
        mock_graph.return_value = _make_graph()
        result = runner.invoke(ai_flows_group, ["review", "--json"])
        data = json.loads(result.output)
        m = data["metrics"]
        expected = ["model_count", "route_count", "query_count",
                    "migration_count", "diagnostic_count",
                    "avg_models_per_route", "avg_queries_per_route",
                    "coupling_score"]
        for key in expected:
            assert key in m, f"Missing metric: {key}"


# ═══════════════════════════════════════════════════════════════════════════
# Console Integration
# ═══════════════════════════════════════════════════════════════════════════


class TestConsoleIntegration:
    def test_architecture_intents_registered(self):
        from aksara.ai.intent_router import detect_intent
        for phrase in ["review my architecture", "how healthy is my system",
                       "architecture analysis", "check anti-patterns",
                       "coupling analysis"]:
            match = detect_intent(phrase)
            assert match.flow_type == "architecture_review", f"Failed for: {phrase}"

    def test_architecture_intent_confidence(self):
        from aksara.ai.intent_router import detect_intent
        match = detect_intent("architecture review")
        assert match.confidence >= 0.8

    def test_refactor_intent(self):
        from aksara.ai.intent_router import detect_intent
        match = detect_intent("refactoring advice")
        assert match.flow_type == "architecture_review"

    def test_health_check_intent(self):
        from aksara.ai.intent_router import detect_intent
        match = detect_intent("health check")
        assert match.flow_type == "architecture_review"

    def test_design_review_intent(self):
        from aksara.ai.intent_router import detect_intent
        match = detect_intent("design review")
        assert match.flow_type == "architecture_review"

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_console_engine_flow(self, mock_graph):
        mock_graph.return_value = _make_graph()
        from aksara.ai.console_engine import run_console_query
        result = asyncio.run(
            run_console_query("review my architecture")
        )
        assert result["ok"] is True
        assert result["flow_type"] == "architecture_review"
        assert "architecture_report" in result["execution"]

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_console_engine_report_structure(self, mock_graph):
        mock_graph.return_value = _make_graph()
        from aksara.ai.console_engine import run_console_query
        result = asyncio.run(
            run_console_query("architecture analysis")
        )
        report = result["execution"]["architecture_report"]
        assert "score" in report
        assert "grade" in report
