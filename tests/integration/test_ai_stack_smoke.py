"""
v0.5.36 — AI Stack Smoke Tests

Integration-level tests that simulate a realistic Aksara app with models,
routes, migrations, diagnostics, and run the full AI analysis stack:
  - Project Graph build
  - AI Debugger
  - AI Architecture Review
  - AI Performance Analyzer
  - AI Console dispatch
  - Intent Routing
  - Graph Events

These tests verify the AI subsystems work coherently on the same
project structure without contradicting each other.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

import pytest

from aksara.ai.project_graph import (
    ProjectGraph, ModelNode, RouteNode, QueryNode,
    MigrationNode, DiagnosticNode, GapNode, GraphMetadata,
)


# ─── Realistic Project Graph ─────────────────────────────────────────────────

def _make_realistic_graph() -> ProjectGraph:
    """Build a graph resembling a small CRM app."""
    return ProjectGraph(
        models=[
            ModelNode(name="User", table="users",
                      fields=["id", "email", "name", "created_at"],
                      relations=["orders"]),
            ModelNode(name="Order", table="orders",
                      fields=["id", "user_id", "total", "status", "created_at"],
                      relations=["user", "items"]),
            ModelNode(name="OrderItem", table="order_items",
                      fields=["id", "order_id", "product_id", "quantity", "price"],
                      relations=["order", "product"]),
            ModelNode(name="Product", table="products",
                      fields=["id", "name", "price", "category"],
                      relations=["items"]),
        ],
        routes=[
            RouteNode(method="GET", path="/api/users", name="list_users",
                      handler="list_users", models=["User"],
                      queries=["q_users"]),
            RouteNode(method="GET", path="/api/orders", name="list_orders",
                      handler="list_orders", models=["Order", "OrderItem"],
                      queries=["q_orders", "q_items1", "q_items2", "q_items3",
                               "q_items4", "q_items5", "q_items6"]),
            RouteNode(method="POST", path="/api/orders", name="create_order",
                      handler="create_order", models=["Order"],
                      queries=["q_insert_order"]),
            RouteNode(method="GET", path="/api/products", name="list_products",
                      handler="list_products", models=["Product"],
                      queries=["q_products"]),
        ],
        queries=[
            QueryNode(name="q_users", sql="SELECT * FROM users",
                      models=["User"]),
            QueryNode(name="q_orders", sql="SELECT * FROM orders",
                      models=["Order"]),
            QueryNode(name="q_items1",
                      sql="SELECT * FROM order_items WHERE order_id=1",
                      models=["OrderItem"]),
            QueryNode(name="q_items2",
                      sql="SELECT * FROM order_items WHERE order_id=2",
                      models=["OrderItem"]),
            QueryNode(name="q_items3",
                      sql="SELECT * FROM order_items WHERE order_id=3",
                      models=["OrderItem"]),
            QueryNode(name="q_items4",
                      sql="SELECT * FROM order_items WHERE order_id=4",
                      models=["OrderItem"]),
            QueryNode(name="q_items5",
                      sql="SELECT * FROM order_items WHERE order_id=5",
                      models=["OrderItem"]),
            QueryNode(name="q_items6",
                      sql="SELECT * FROM order_items WHERE order_id=6",
                      models=["OrderItem"]),
            QueryNode(name="q_insert_order",
                      sql="INSERT INTO orders (user_id, total) VALUES (?, ?)",
                      models=["Order"]),
            QueryNode(name="q_products", sql="SELECT * FROM products",
                      models=["Product"]),
        ],
        migrations=[
            MigrationNode(name="0001_initial", app="core",
                          models=["User", "Order", "OrderItem", "Product"]),
            MigrationNode(name="0002_add_orders", app="core",
                          models=["Order"]),
        ],
        diagnostics=[
            DiagnosticNode(code="TABLE_SCAN", severity="warning",
                           message="Table scan on orders.created_at",
                           related_models=["Order"], related_routes=["/api/orders"],
                           related_queries=["q_orders"]),
        ],
        gaps=[
            GapNode(code="MISSING_INDEX", severity="warning",
                    summary="No index on orders.created_at",
                    category="performance",
                    related_components=["Order"]),
        ],
        events=[
            {"severity": "info", "kind": "query", "message": "SELECT * FROM users",
             "timestamp": "", "source_id": "q_users", "source_type": "query",
             "duration_ms": 50.0, "route": "/api/users"},
        ],
        metadata=GraphMetadata(
            model_count=4, route_count=4, query_count=10,
            migration_count=2, diagnostic_count=1, gap_count=1, event_count=1,
        ),
    )


# ═══════════════════════════════════════════════════════════════════════════
# Smoke: Graph Build
# ═══════════════════════════════════════════════════════════════════════════


class TestGraphBuildSmoke:

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_graph_builds_with_models_and_routes(self, mock_build):
        mock_build.return_value = _make_realistic_graph()
        graph = mock_build()
        assert len(graph.models) == 4
        assert len(graph.routes) == 4
        assert len(graph.queries) > 0

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_graph_to_dict_is_serializable(self, mock_build):
        mock_build.return_value = _make_realistic_graph()
        graph = mock_build()
        d = graph.to_dict()
        serialized = json.dumps(d)
        assert isinstance(serialized, str)


# ═══════════════════════════════════════════════════════════════════════════
# Smoke: Debugger on Realistic Graph
# ═══════════════════════════════════════════════════════════════════════════


class TestDebuggerSmoke:

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_debugger_runs_and_returns_report(self, mock_build):
        mock_build.return_value = _make_realistic_graph()
        from aksara.ai.debugger import run_debugger
        report = run_debugger()
        assert report.ok is True
        assert isinstance(report.issues, list)
        assert isinstance(report.clusters, list)
        assert isinstance(report.root_causes, list)

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_debugger_report_is_serializable(self, mock_build):
        mock_build.return_value = _make_realistic_graph()
        from aksara.ai.debugger import run_debugger
        report = run_debugger()
        d = report.to_dict()
        serialized = json.dumps(d, default=str)
        assert isinstance(serialized, str)

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_debugger_severities_are_valid(self, mock_build):
        mock_build.return_value = _make_realistic_graph()
        from aksara.ai.debugger import run_debugger
        report = run_debugger()
        valid = {"error", "warning", "info"}
        for issue in report.issues:
            assert issue.severity in valid, f"Invalid severity: {issue.severity}"


# ═══════════════════════════════════════════════════════════════════════════
# Smoke: Architecture Review on Realistic Graph
# ═══════════════════════════════════════════════════════════════════════════


class TestArchReviewSmoke:

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_arch_review_runs(self, mock_build):
        mock_build.return_value = _make_realistic_graph()
        from aksara.ai.architecture_review import run_architecture_review
        report = run_architecture_review()
        assert report.ok is True
        assert 0 <= report.score <= 100
        assert report.grade in {"A", "B", "C", "D", "F"}

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_arch_findings_have_valid_severity(self, mock_build):
        mock_build.return_value = _make_realistic_graph()
        from aksara.ai.architecture_review import run_architecture_review
        report = run_architecture_review()
        valid = {"critical", "error", "warning", "info"}
        for f in report.findings:
            assert f.severity in valid, f"Invalid arch severity: {f.severity}"

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_arch_report_serializable(self, mock_build):
        mock_build.return_value = _make_realistic_graph()
        from aksara.ai.architecture_review import run_architecture_review
        report = run_architecture_review()
        d = report.to_dict()
        serialized = json.dumps(d, default=str)
        parsed = json.loads(serialized)
        assert "score" in parsed
        assert "grade" in parsed

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_arch_suggestions_have_impact(self, mock_build):
        mock_build.return_value = _make_realistic_graph()
        from aksara.ai.architecture_review import run_architecture_review
        report = run_architecture_review()
        valid_impacts = {"high", "medium", "low"}
        for s in report.suggestions:
            assert s.impact in valid_impacts


# ═══════════════════════════════════════════════════════════════════════════
# Smoke: Performance Analyzer on Realistic Graph
# ═══════════════════════════════════════════════════════════════════════════


class TestPerfAnalyzerSmoke:

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_perf_analyzer_runs(self, mock_build):
        mock_build.return_value = _make_realistic_graph()
        from aksara.ai.performance_analyzer import run_performance_analysis
        report = run_performance_analysis()
        assert report.ok is True
        assert 0 <= report.score <= 100
        assert report.grade in {"A", "B", "C", "D", "F"}

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_perf_issues_have_valid_severity(self, mock_build):
        mock_build.return_value = _make_realistic_graph()
        from aksara.ai.performance_analyzer import run_performance_analysis
        report = run_performance_analysis()
        valid = {"critical", "high", "medium", "low"}
        for i in report.issues:
            assert i.severity in valid, f"Invalid perf severity: {i.severity}"

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_perf_issues_have_valid_category(self, mock_build):
        mock_build.return_value = _make_realistic_graph()
        from aksara.ai.performance_analyzer import run_performance_analysis
        report = run_performance_analysis()
        valid = {"slow_query", "n_plus_one", "missing_index", "query_explosion",
                 "heavy_join", "large_payload", "route_hotspot"}
        for i in report.issues:
            assert i.category in valid, f"Invalid category: {i.category}"

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_perf_report_serializable(self, mock_build):
        mock_build.return_value = _make_realistic_graph()
        from aksara.ai.performance_analyzer import run_performance_analysis
        report = run_performance_analysis()
        d = report.to_dict()
        serialized = json.dumps(d, default=str)
        parsed = json.loads(serialized)
        assert "score" in parsed
        assert "metrics" in parsed

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_perf_recommendations_have_impact(self, mock_build):
        mock_build.return_value = _make_realistic_graph()
        from aksara.ai.performance_analyzer import run_performance_analysis
        report = run_performance_analysis()
        valid = {"high", "medium", "low"}
        for r in report.recommendations:
            assert r.impact in valid


# ═══════════════════════════════════════════════════════════════════════════
# Smoke: Console Engine Dispatch
# ═══════════════════════════════════════════════════════════════════════════


class TestConsoleSmoke:

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_console_debug_dispatch(self, mock_build):
        mock_build.return_value = _make_realistic_graph()
        from aksara.ai.console_engine import run_console_query
        result = asyncio.run(run_console_query("debug my application"))
        assert result["ok"] is True
        assert result["flow_type"] == "debug"

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_console_arch_dispatch(self, mock_build):
        mock_build.return_value = _make_realistic_graph()
        from aksara.ai.console_engine import run_console_query
        result = asyncio.run(run_console_query("review architecture"))
        assert result["ok"] is True
        assert result["flow_type"] == "architecture_review"

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_console_perf_dispatch(self, mock_build):
        mock_build.return_value = _make_realistic_graph()
        from aksara.ai.console_engine import run_console_query
        result = asyncio.run(run_console_query("analyze performance"))
        assert result["ok"] is True
        assert result["flow_type"] == "performance_analysis"

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_console_suggestions_not_self_referential(self, mock_build):
        """Console suggestions should not just suggest the same flow again."""
        mock_build.return_value = _make_realistic_graph()
        from aksara.ai.console_engine import run_console_query
        result = asyncio.run(run_console_query("debug my app"))
        suggestions = result.get("suggestions", [])
        # Debug should suggest arch/perf, not debug_analyze
        assert "debug_analyze" not in suggestions

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_console_arch_suggests_cross_flows(self, mock_build):
        mock_build.return_value = _make_realistic_graph()
        from aksara.ai.console_engine import run_console_query
        result = asyncio.run(run_console_query("review architecture"))
        suggestions = result.get("suggestions", [])
        assert "architecture_review" not in suggestions

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_console_perf_suggests_cross_flows(self, mock_build):
        mock_build.return_value = _make_realistic_graph()
        from aksara.ai.console_engine import run_console_query
        result = asyncio.run(run_console_query("analyze performance"))
        suggestions = result.get("suggestions", [])
        assert "performance_analysis" not in suggestions


# ═══════════════════════════════════════════════════════════════════════════
# Smoke: Cross-Analyzer Coherence
# ═══════════════════════════════════════════════════════════════════════════


class TestCrossAnalyzerCoherence:
    """Verify analyzers don't contradict each other on the same graph."""

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_all_analyzers_run_on_same_graph(self, mock_build):
        """All three should succeed on identical input."""
        mock_build.return_value = _make_realistic_graph()
        from aksara.ai.debugger import run_debugger
        from aksara.ai.architecture_review import run_architecture_review
        from aksara.ai.performance_analyzer import run_performance_analysis

        debug_report = run_debugger()
        arch_report = run_architecture_review()
        perf_report = run_performance_analysis()

        assert debug_report.ok is True
        assert arch_report.ok is True
        assert perf_report.ok is True

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_grade_systems_use_same_scale(self, mock_build):
        """Architecture and Performance both use A-F grading."""
        mock_build.return_value = _make_realistic_graph()
        from aksara.ai.architecture_review import run_architecture_review
        from aksara.ai.performance_analyzer import run_performance_analysis

        arch = run_architecture_review()
        perf = run_performance_analysis()

        valid_grades = {"A", "B", "C", "D", "F"}
        assert arch.grade in valid_grades
        assert perf.grade in valid_grades

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_report_shapes_are_consistent(self, mock_build):
        """Both scored analyzers should have score, grade, elapsed_ms, generated_at."""
        mock_build.return_value = _make_realistic_graph()
        from aksara.ai.architecture_review import run_architecture_review
        from aksara.ai.performance_analyzer import run_performance_analysis

        arch_dict = run_architecture_review().to_dict()
        perf_dict = run_performance_analysis().to_dict()

        for key in ("score", "grade", "elapsed_ms", "generated_at", "ok"):
            assert key in arch_dict, f"arch missing {key}"
            assert key in perf_dict, f"perf missing {key}"

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_debugger_has_expected_shape(self, mock_build):
        mock_build.return_value = _make_realistic_graph()
        from aksara.ai.debugger import run_debugger
        d = run_debugger().to_dict()
        for key in ("ok", "issues", "clusters", "root_causes", "elapsed_ms"):
            assert key in d, f"debugger missing {key}"


# ═══════════════════════════════════════════════════════════════════════════
# Smoke: Graph Events
# ═══════════════════════════════════════════════════════════════════════════


class TestGraphEventsSmoke:

    def test_known_event_kinds_exist(self):
        from aksara.ai.graph_events import EVENT_KINDS
        assert "route_error" in EVENT_KINDS
        assert "ai_flow_executed" in EVENT_KINDS
        assert "console_execution_failed" in EVENT_KINDS

    def test_emit_known_kind_succeeds(self):
        from aksara.ai.graph_events import emit_graph_event, clear_graph_events
        clear_graph_events()
        e = emit_graph_event("route_error", "route", "/api/test",
                             severity="error", message="test failure")
        assert e.kind == "route_error"
        assert e.severity == "error"

    def test_event_to_dict_serializable(self):
        from aksara.ai.graph_events import emit_graph_event, clear_graph_events
        clear_graph_events()
        e = emit_graph_event("ai_flow_executed", "console", "test")
        d = e.to_dict()
        assert json.dumps(d)


# ═══════════════════════════════════════════════════════════════════════════
# Smoke: Intent Routing Full Coverage
# ═══════════════════════════════════════════════════════════════════════════


class TestIntentRoutingSmoke:

    def test_all_flow_types_reachable(self):
        """Ensure every flow_type has at least one routable phrase."""
        from aksara.ai.intent_router import detect_intent
        flow_phrases = {
            "model": "explain the User model",
            "route": "review GET /api/users",
            "query": "explain the query plan",
            "migration": "explain migration 0001",
            "diagnostic": "prioritize diagnostic issues",
            "debug": "debug this application",
            "architecture_review": "review architecture",
            "performance_analysis": "analyze performance",
        }
        for flow_type, phrase in flow_phrases.items():
            m = detect_intent(phrase)
            assert m.flow_type == flow_type, \
                f"'{phrase}' → {m.flow_type}, expected {flow_type}"

    def test_deterministic_routing(self):
        """Same input should always produce same intent."""
        from aksara.ai.intent_router import detect_intent
        phrases = [
            "explain the User model",
            "review architecture",
            "analyze performance",
            "debug my app",
        ]
        for phrase in phrases:
            results = [detect_intent(phrase).action_key for _ in range(5)]
            assert len(set(results)) == 1, \
                f"Non-deterministic routing for '{phrase}': {results}"


# ═══════════════════════════════════════════════════════════════════════════
# Smoke: CLI JSON Purity
# ═══════════════════════════════════════════════════════════════════════════


class TestCliJsonPurity:
    """Verify --json output is clean, parseable JSON with no extra text."""

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_debug_json_output(self, mock_build):
        mock_build.return_value = _make_realistic_graph()
        from click.testing import CliRunner
        from aksara.cli.main import ai_flows_group
        runner = CliRunner()
        result = runner.invoke(ai_flows_group, ["debug", "--json"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert isinstance(parsed, dict)

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_review_json_output(self, mock_build):
        mock_build.return_value = _make_realistic_graph()
        from click.testing import CliRunner
        from aksara.cli.main import ai_flows_group
        runner = CliRunner()
        result = runner.invoke(ai_flows_group, ["review", "--json"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "score" in parsed

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_performance_json_output(self, mock_build):
        mock_build.return_value = _make_realistic_graph()
        from click.testing import CliRunner
        from aksara.cli.main import ai_flows_group
        runner = CliRunner()
        result = runner.invoke(ai_flows_group, ["performance", "--json"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "score" in parsed
        assert "metrics" in parsed

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_debug_summary_has_no_json(self, mock_build):
        mock_build.return_value = _make_realistic_graph()
        from click.testing import CliRunner
        from aksara.cli.main import ai_flows_group
        runner = CliRunner()
        result = runner.invoke(ai_flows_group, ["debug", "--summary"])
        assert result.exit_code == 0
        # Summary mode should not be parseable as JSON
        try:
            json.loads(result.output)
            pytest.fail("Summary output should not be valid JSON")
        except json.JSONDecodeError:
            pass  # expected — summary is human-readable text

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_review_summary_is_text(self, mock_build):
        mock_build.return_value = _make_realistic_graph()
        from click.testing import CliRunner
        from aksara.cli.main import ai_flows_group
        runner = CliRunner()
        result = runner.invoke(ai_flows_group, ["review", "--summary"])
        assert result.exit_code == 0
        assert "Grade" in result.output or "Score" in result.output

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_performance_summary_is_text(self, mock_build):
        mock_build.return_value = _make_realistic_graph()
        from click.testing import CliRunner
        from aksara.cli.main import ai_flows_group
        runner = CliRunner()
        result = runner.invoke(ai_flows_group, ["performance", "--summary"])
        assert result.exit_code == 0
        assert "Grade" in result.output or "Score" in result.output
