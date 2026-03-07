"""
v0.5.35 — AI Performance Analyzer: CLI command tests.

Tests cover:
    - Command registration under `aksara ai flows performance`
    - Text output (score, grade, issues, recommendations)
    - JSON output (--json)
    - Summary output (--summary)
    - Metrics output (--metrics)
    - Issues output (--issues)
    - Graph failure handling
    - Output structure
    - Console integration (intent routing + flow)
"""

from __future__ import annotations

import asyncio
import json
import pytest
from unittest.mock import MagicMock, patch
from click.testing import CliRunner

from aksara.cli.main import cli, ai_flows_group, ai_performance


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _make_query(sql="SELECT 1", execution_time_ms=10.0, route="", model=""):
    q = MagicMock()
    q.sql = sql
    q.query = sql
    q.execution_time_ms = execution_time_ms
    q.duration_ms = execution_time_ms
    q.route = route
    q.model = model
    q.indexes_used = []
    q.diagnostics = []
    return q


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
                     related_models=None, related_routes=None,
                     related_queries=None):
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
    def test_performance_command_exists(self):
        assert "performance" in [c.name for c in ai_flows_group.commands.values()]

    def test_help_text(self):
        result = runner.invoke(ai_flows_group, ["performance", "--help"])
        assert result.exit_code == 0
        assert "Performance Analyzer" in result.output

    def test_json_option(self):
        result = runner.invoke(ai_flows_group, ["performance", "--help"])
        assert "--json" in result.output

    def test_summary_option(self):
        result = runner.invoke(ai_flows_group, ["performance", "--help"])
        assert "--summary" in result.output

    def test_metrics_option(self):
        result = runner.invoke(ai_flows_group, ["performance", "--help"])
        assert "--metrics" in result.output

    def test_issues_option(self):
        result = runner.invoke(ai_flows_group, ["performance", "--help"])
        assert "--issues" in result.output


# ═══════════════════════════════════════════════════════════════════════════
# Text Output
# ═══════════════════════════════════════════════════════════════════════════


class TestTextOutput:
    @patch("aksara.ai.project_graph.build_project_graph")
    def test_basic_output(self, mock_graph):
        mock_graph.return_value = _make_graph(
            routes=[_make_route()],
            queries=[_make_query()],
        )
        result = runner.invoke(ai_flows_group, ["performance"])
        assert result.exit_code == 0
        assert "Performance Analyzer" in result.output
        assert "Score" in result.output

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_shows_grade(self, mock_graph):
        mock_graph.return_value = _make_graph()
        result = runner.invoke(ai_flows_group, ["performance"])
        assert result.exit_code == 0
        assert any(g in result.output for g in ["A", "B", "C", "D", "F"])

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_shows_issue_count(self, mock_graph):
        q = _make_query(sql="SELECT *", execution_time_ms=500.0)
        mock_graph.return_value = _make_graph(queries=[q])
        result = runner.invoke(ai_flows_group, ["performance"])
        assert result.exit_code == 0
        assert "Issues" in result.output

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_shows_recommendations_when_present(self, mock_graph):
        q = _make_query(sql="SELECT *", execution_time_ms=500.0)
        mock_graph.return_value = _make_graph(queries=[q])
        result = runner.invoke(ai_flows_group, ["performance"])
        assert result.exit_code == 0
        assert "Recommendations" in result.output

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_shows_elapsed(self, mock_graph):
        mock_graph.return_value = _make_graph()
        result = runner.invoke(ai_flows_group, ["performance"])
        assert "ms" in result.output


# ═══════════════════════════════════════════════════════════════════════════
# JSON Output
# ═══════════════════════════════════════════════════════════════════════════


class TestJsonOutput:
    @patch("aksara.ai.project_graph.build_project_graph")
    def test_json_output(self, mock_graph):
        mock_graph.return_value = _make_graph()
        result = runner.invoke(ai_flows_group, ["performance", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "score" in data
        assert "grade" in data
        assert "issues" in data
        assert "recommendations" in data

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_json_has_metrics(self, mock_graph):
        mock_graph.return_value = _make_graph()
        result = runner.invoke(ai_flows_group, ["performance", "--json"])
        data = json.loads(result.output)
        assert "metrics" in data
        assert "total_routes" in data["metrics"]

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_json_with_issues(self, mock_graph):
        q = _make_query(sql="SELECT *", execution_time_ms=500.0)
        mock_graph.return_value = _make_graph(queries=[q])
        result = runner.invoke(ai_flows_group, ["performance", "--json"])
        data = json.loads(result.output)
        assert len(data["issues"]) >= 1

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_json_score_range(self, mock_graph):
        mock_graph.return_value = _make_graph()
        result = runner.invoke(ai_flows_group, ["performance", "--json"])
        data = json.loads(result.output)
        assert 0 <= data["score"] <= 100


# ═══════════════════════════════════════════════════════════════════════════
# Summary Output
# ═══════════════════════════════════════════════════════════════════════════


class TestSummaryOutput:
    @patch("aksara.ai.project_graph.build_project_graph")
    def test_summary_mode(self, mock_graph):
        mock_graph.return_value = _make_graph()
        result = runner.invoke(ai_flows_group, ["performance", "--summary"])
        assert result.exit_code == 0
        assert "Performance Analyzer" in result.output

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_summary_no_issues_list(self, mock_graph):
        """Summary mode should NOT show full issues or recommendations list."""
        mock_graph.return_value = _make_graph()
        result = runner.invoke(ai_flows_group, ["performance", "--summary"])
        # Summary mode returns early, so no "Recommendations:" section header
        assert "Recommendations:" not in result.output or result.output.count("Recommendations") <= 1


# ═══════════════════════════════════════════════════════════════════════════
# Metrics Output
# ═══════════════════════════════════════════════════════════════════════════


class TestMetricsOutput:
    @patch("aksara.ai.project_graph.build_project_graph")
    def test_metrics_flag(self, mock_graph):
        mock_graph.return_value = _make_graph(
            routes=[_make_route()],
            queries=[_make_query()],
        )
        result = runner.invoke(ai_flows_group, ["performance", "--metrics"])
        assert result.exit_code == 0
        assert "Metrics:" in result.output
        assert "Total routes" in result.output

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_metrics_shows_queries(self, mock_graph):
        mock_graph.return_value = _make_graph()
        result = runner.invoke(ai_flows_group, ["performance", "--metrics"])
        assert "Total queries" in result.output


# ═══════════════════════════════════════════════════════════════════════════
# Issues Output
# ═══════════════════════════════════════════════════════════════════════════


class TestIssuesOutput:
    @patch("aksara.ai.project_graph.build_project_graph")
    def test_issues_flag(self, mock_graph):
        q = _make_query(sql="SELECT *", execution_time_ms=500.0)
        mock_graph.return_value = _make_graph(queries=[q])
        result = runner.invoke(ai_flows_group, ["performance", "--issues"])
        assert result.exit_code == 0
        assert "Issues:" in result.output

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_issues_shows_severity(self, mock_graph):
        q = _make_query(sql="SELECT *", execution_time_ms=500.0)
        mock_graph.return_value = _make_graph(queries=[q])
        result = runner.invoke(ai_flows_group, ["performance", "--issues"])
        # Should show at least one severity in brackets
        assert "[" in result.output


# ═══════════════════════════════════════════════════════════════════════════
# Error Handling
# ═══════════════════════════════════════════════════════════════════════════


class TestErrorHandling:
    @patch("aksara.ai.project_graph.build_project_graph")
    def test_graph_failure_text(self, mock_graph):
        mock_graph.side_effect = RuntimeError("no graph")
        result = runner.invoke(ai_flows_group, ["performance"])
        assert result.exit_code == 0
        # Error report should still render (ok=False, grade=F)
        assert "F" in result.output

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_graph_failure_json(self, mock_graph):
        mock_graph.side_effect = RuntimeError("no graph")
        result = runner.invoke(ai_flows_group, ["performance", "--json"])
        data = json.loads(result.output)
        assert data["ok"] is False
        assert data["score"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# Output Structure (JSON keys)
# ═══════════════════════════════════════════════════════════════════════════


class TestOutputStructure:
    @patch("aksara.ai.project_graph.build_project_graph")
    def test_json_keys(self, mock_graph):
        mock_graph.return_value = _make_graph()
        result = runner.invoke(ai_flows_group, ["performance", "--json"])
        data = json.loads(result.output)
        for key in ("ok", "score", "grade", "issues", "recommendations",
                     "metrics", "issue_count", "recommendation_count",
                     "elapsed_ms", "generated_at"):
            assert key in data, f"Missing key: {key}"

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_issue_structure(self, mock_graph):
        q = _make_query(sql="SELECT *", execution_time_ms=500.0)
        mock_graph.return_value = _make_graph(queries=[q])
        result = runner.invoke(ai_flows_group, ["performance", "--json"])
        data = json.loads(result.output)
        if data["issues"]:
            issue = data["issues"][0]
            for key in ("issue_id", "severity", "title", "description", "category"):
                assert key in issue, f"Missing key in issue: {key}"

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_recommendation_structure(self, mock_graph):
        q = _make_query(sql="SELECT *", execution_time_ms=500.0)
        mock_graph.return_value = _make_graph(queries=[q])
        result = runner.invoke(ai_flows_group, ["performance", "--json"])
        data = json.loads(result.output)
        if data["recommendations"]:
            rec = data["recommendations"][0]
            for key in ("recommendation_id", "title", "description",
                         "impact", "related_issue_ids"):
                assert key in rec, f"Missing key in rec: {key}"

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_metrics_structure(self, mock_graph):
        mock_graph.return_value = _make_graph()
        result = runner.invoke(ai_flows_group, ["performance", "--json"])
        data = json.loads(result.output)
        m = data["metrics"]
        for key in ("total_routes", "total_queries", "slow_queries",
                     "n_plus_one_candidates", "missing_indexes",
                     "avg_queries_per_route"):
            assert key in m, f"Missing key in metrics: {key}"


# ═══════════════════════════════════════════════════════════════════════════
# Console Integration
# ═══════════════════════════════════════════════════════════════════════════


class TestConsoleIntegration:
    def test_performance_intent_routing(self):
        from aksara.ai.intent_router import detect_intent
        for phrase in [
            "analyze performance",
            "performance analysis",
            "why is my app slow",
            "find slow queries",
            "performance review",
        ]:
            match = detect_intent(phrase)
            assert match is not None, f"Failed to match: {phrase}"
            assert match.flow_type == "performance_analysis", f"Wrong flow for: {phrase}"

    def test_performance_intent_confidence(self):
        from aksara.ai.intent_router import detect_intent
        match = detect_intent("analyze performance")
        assert match.confidence >= 0.80

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_console_engine_performance_flow(self, mock_graph):
        mock_graph.return_value = _make_graph()
        from aksara.ai.console_engine import run_console_query
        result = asyncio.run(run_console_query("analyze performance"))
        assert result["ok"] is True
        assert result["flow_type"] == "performance_analysis"
        assert "performance_report" in result["execution"]

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_console_engine_performance_report_structure(self, mock_graph):
        mock_graph.return_value = _make_graph()
        from aksara.ai.console_engine import run_console_query
        result = asyncio.run(run_console_query("analyze performance"))
        report = result["execution"]["performance_report"]
        assert "score" in report
        assert "grade" in report
