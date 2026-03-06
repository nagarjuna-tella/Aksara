"""
v0.5.32 — Graph Context Builders: unit tests.

Tests cover:
    - build_graph_summary_context() — returns compact summary dict
    - build_graph_console_context() — context for AI Console with flow_type variants
    - build_graph_debug_context() — focused on diagnostics/gaps/queries
    - build_graph_prompt_section() — formatted text for LLM prompts
    - inject_graph_context() in console_context.py
    - Event inclusion / exclusion
    - Empty graph scenarios
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from aksara.ai.graph_context import (
    build_graph_summary_context,
    build_graph_console_context,
    build_graph_debug_context,
    build_graph_prompt_section,
)
from aksara.ai.console_context import inject_graph_context
from aksara.ai.project_graph import (
    ProjectGraph,
    ModelNode,
    RouteNode,
    QueryNode,
    DiagnosticNode,
    GapNode,
    AiHubNode,
    AiFlowNode,
    MigrationNode,
    _invalidate_cache,
)


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _make_populated_graph() -> ProjectGraph:
    """Build a graph with representative data for testing."""
    g = ProjectGraph()
    g.models = [
        ModelNode(name="User", table="users", fields=["id", "name", "email"], relations=["profile → Profile"]),
        ModelNode(name="Post", table="posts", fields=["id", "title", "author_id"]),
    ]
    g.routes = [
        RouteNode(method="GET", path="/api/users", name="list_users", handler="list_users", models=["User"]),
        RouteNode(method="POST", path="/api/posts", name="create_post", handler="create_post", models=["Post"]),
    ]
    g.queries = [
        QueryNode(name="q0", sql="SELECT * FROM users", models=["User"]),
    ]
    g.migrations = [
        MigrationNode(name="001_create_user", app="auth", models=["User"]),
    ]
    g.diagnostics = [
        DiagnosticNode(code="perf_warning", severity="warning", message="Slow query on users"),
    ]
    g.gaps = [
        GapNode(code="missing_auth", severity="error", summary="No auth on /api/posts", category="security"),
    ]
    g.ai_hub = AiHubNode(providers=["openai"], status="ready",
                          default_chat_model="gpt-4o", default_code_model="gpt-4o")
    g.flows = [
        AiFlowNode(action_key="explain_model", title="Explain Model", flow_type="model", risk="low"),
    ]
    g.events = [
        {"kind": "ai_flow_executed", "severity": "info", "message": "Ran explain model", "source_type": "flow", "source_id": "explain_model"},
        {"kind": "route_error", "severity": "error", "message": "500 on /api/users", "source_type": "route", "source_id": "/api/users"},
    ]
    # Update metadata counts
    g.metadata.model_count = len(g.models)
    g.metadata.route_count = len(g.routes)
    g.metadata.query_count = len(g.queries)
    g.metadata.migration_count = len(g.migrations)
    g.metadata.diagnostic_count = len(g.diagnostics)
    g.metadata.gap_count = len(g.gaps)
    g.metadata.event_count = len(g.events)
    g.metadata.version = "0.5.34"
    return g


def _patch_build_graph(graph=None):
    """Patch build_project_graph to return a given graph."""
    g = graph or _make_populated_graph()
    return patch("aksara.ai.project_graph.build_project_graph", return_value=g)


def _empty_graph():
    return _patch_build_graph(ProjectGraph())


# ═══════════════════════════════════════════════════════════════════════════
# Tests: build_graph_summary_context
# ═══════════════════════════════════════════════════════════════════════════


class TestBuildGraphSummaryContext:
    def test_returns_dict(self):
        with _patch_build_graph():
            result = build_graph_summary_context()
        assert isinstance(result, dict)

    def test_has_counts(self):
        with _patch_build_graph():
            result = build_graph_summary_context()
        assert "counts" in result
        assert result["counts"]["models"] == 2

    def test_has_hub_status(self):
        with _patch_build_graph():
            result = build_graph_summary_context()
        assert result["ai_hub_status"] == "ready"

    def test_empty_graph(self):
        with _empty_graph():
            result = build_graph_summary_context()
        assert result["counts"]["models"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# Tests: build_graph_console_context
# ═══════════════════════════════════════════════════════════════════════════


class TestBuildGraphConsoleContext:
    def test_returns_dict(self):
        with _patch_build_graph():
            result = build_graph_console_context()
        assert isinstance(result, dict)

    def test_has_graph_text(self):
        with _patch_build_graph():
            result = build_graph_console_context()
        assert "graph_text" in result
        assert isinstance(result["graph_text"], str)

    def test_has_model_names(self):
        with _patch_build_graph():
            result = build_graph_console_context()
        assert "model_names" in result
        assert "User" in result["model_names"]

    def test_has_route_paths(self):
        with _patch_build_graph():
            result = build_graph_console_context()
        assert "route_paths" in result
        assert any("/api/users" in r for r in result["route_paths"])

    def test_includes_events_by_default(self):
        with _patch_build_graph():
            result = build_graph_console_context()
        assert "recent_events" in result
        assert len(result["recent_events"]) == 2

    def test_excludes_events_when_disabled(self):
        with _patch_build_graph():
            result = build_graph_console_context(include_events=False)
        assert "recent_events" not in result

    def test_max_events_respected(self):
        with _patch_build_graph():
            result = build_graph_console_context(max_events=1)
        assert len(result["recent_events"]) == 1

    def test_flow_type_model(self):
        with _patch_build_graph():
            result = build_graph_console_context(flow_type="model")
        assert "models_detail" in result
        assert result["models_detail"][0]["name"] == "User"

    def test_flow_type_route(self):
        with _patch_build_graph():
            result = build_graph_console_context(flow_type="route")
        assert "routes_detail" in result

    def test_flow_type_query(self):
        with _patch_build_graph():
            result = build_graph_console_context(flow_type="query")
        assert "queries_detail" in result

    def test_flow_type_diagnostic(self):
        with _patch_build_graph():
            result = build_graph_console_context(flow_type="diagnostic")
        assert "diagnostics_detail" in result

    def test_flow_type_migration(self):
        with _patch_build_graph():
            result = build_graph_console_context(flow_type="migration")
        assert "migrations_detail" in result

    def test_no_flow_type(self):
        with _patch_build_graph():
            result = build_graph_console_context(flow_type=None)
        # Should not have any detail sections
        for key in ("models_detail", "routes_detail", "queries_detail",
                     "diagnostics_detail", "migrations_detail"):
            assert key not in result

    def test_empty_graph(self):
        with _empty_graph():
            result = build_graph_console_context()
        assert result["model_names"] == []
        assert result["route_paths"] == []


# ═══════════════════════════════════════════════════════════════════════════
# Tests: build_graph_debug_context
# ═══════════════════════════════════════════════════════════════════════════


class TestBuildGraphDebugContext:
    def test_returns_dict(self):
        with _patch_build_graph():
            result = build_graph_debug_context()
        assert isinstance(result, dict)

    def test_has_diagnostics(self):
        with _patch_build_graph():
            result = build_graph_debug_context()
        assert "diagnostics" in result
        assert len(result["diagnostics"]) == 1

    def test_has_gaps(self):
        with _patch_build_graph():
            result = build_graph_debug_context()
        assert "gaps" in result
        assert len(result["gaps"]) == 1

    def test_has_queries(self):
        with _patch_build_graph():
            result = build_graph_debug_context()
        assert "queries" in result

    def test_has_recent_events(self):
        with _patch_build_graph():
            result = build_graph_debug_context()
        assert "recent_events" in result

    def test_has_model_count(self):
        with _patch_build_graph():
            result = build_graph_debug_context()
        assert result["model_count"] == 2

    def test_has_ai_hub_status(self):
        with _patch_build_graph():
            result = build_graph_debug_context()
        assert result["ai_hub_status"] == "ready"

    def test_empty_graph(self):
        with _empty_graph():
            result = build_graph_debug_context()
        assert result["diagnostics"] == []
        assert result["gaps"] == []


# ═══════════════════════════════════════════════════════════════════════════
# Tests: build_graph_prompt_section
# ═══════════════════════════════════════════════════════════════════════════


class TestBuildGraphPromptSection:
    def test_returns_string(self):
        with _patch_build_graph():
            result = build_graph_prompt_section()
        assert isinstance(result, str)

    def test_contains_summary(self):
        with _patch_build_graph():
            result = build_graph_prompt_section()
        assert "PROJECT GRAPH SUMMARY" in result
        assert "Models: 2" in result

    def test_contains_model_names(self):
        with _patch_build_graph():
            result = build_graph_prompt_section()
        assert "User" in result

    def test_flow_type_model(self):
        with _patch_build_graph():
            result = build_graph_prompt_section(flow_type="model")
        assert "RELEVANT MODEL DETAIL" in result
        assert "User" in result

    def test_flow_type_route(self):
        with _patch_build_graph():
            result = build_graph_prompt_section(flow_type="route")
        assert "RELEVANT ROUTES" in result

    def test_flow_type_diagnostic(self):
        with _patch_build_graph():
            result = build_graph_prompt_section(flow_type="diagnostic")
        assert "DIAGNOSTIC ISSUES" in result

    def test_events_included(self):
        with _patch_build_graph():
            result = build_graph_prompt_section(max_events=5)
        assert "RECENT EVENTS" in result

    def test_empty_graph(self):
        with _empty_graph():
            result = build_graph_prompt_section()
        assert "Models: 0" in result


# ═══════════════════════════════════════════════════════════════════════════
# Tests: inject_graph_context (from console_context.py)
# ═══════════════════════════════════════════════════════════════════════════


class TestInjectGraphContext:
    def test_adds_graph_key(self):
        with _patch_build_graph():
            ctx = {"existing": True}
            result = inject_graph_context(ctx, "model")
        assert "_graph" in result
        assert isinstance(result["_graph"], dict)

    def test_preserves_existing_context(self):
        with _patch_build_graph():
            ctx = {"existing": True, "other": 42}
            result = inject_graph_context(ctx, "model")
        assert result["existing"] is True
        assert result["other"] == 42

    def test_flow_type_passed(self):
        with _patch_build_graph():
            ctx = {}
            result = inject_graph_context(ctx, "model")
        assert "models_detail" in result["_graph"]

    def test_failure_does_not_raise(self):
        with patch("aksara.ai.graph_context.build_graph_console_context", side_effect=Exception("fail")):
            ctx = {"existing": True}
            result = inject_graph_context(ctx, "model")
        # Should silently fail without adding _graph
        assert "_graph" not in result
        assert result["existing"] is True
