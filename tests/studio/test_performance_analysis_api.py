"""
v0.5.35 — AI Performance Analyzer: Studio API endpoint tests.

Tests cover:
    - Pydantic models (StudioPerformanceAnalysisResponse, etc.)
    - POST /studio/ai/performance-analysis route registration
    - Endpoint integration with mocked graph
    - Response structure and field types
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from aksara.studio.models import (
    StudioPerformanceMetrics,
    StudioPerformanceIssue,
    StudioPerformanceRecommendation,
    StudioPerformanceAnalysisResponse,
)


# ═══════════════════════════════════════════════════════════════════════════
# Pydantic Model Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestStudioPerformanceMetrics:
    def test_defaults(self):
        m = StudioPerformanceMetrics()
        assert m.total_routes == 0
        assert m.total_queries == 0
        assert m.slow_queries == 0
        assert m.avg_queries_per_route == 0.0
        assert m.max_queries_route is None

    def test_custom_values(self):
        m = StudioPerformanceMetrics(
            total_routes=5, total_queries=20,
            slow_queries=3, avg_queries_per_route=4.0,
        )
        assert m.total_routes == 5
        assert m.avg_queries_per_route == 4.0

    def test_serialise(self):
        m = StudioPerformanceMetrics(total_routes=3)
        d = m.model_dump()
        assert d["total_routes"] == 3
        assert "max_queries_route" in d


class TestStudioPerformanceIssue:
    def test_defaults(self):
        i = StudioPerformanceIssue()
        assert i.issue_id == ""
        assert i.severity == "medium"
        assert i.category == "slow_query"
        assert i.route is None
        assert i.model is None
        assert i.query is None

    def test_custom(self):
        i = StudioPerformanceIssue(
            issue_id="PERF-0001", severity="high",
            title="Slow query", description="Desc",
            route="/api/users", category="slow_query",
        )
        assert i.issue_id == "PERF-0001"
        assert i.category == "slow_query"

    def test_serialise(self):
        i = StudioPerformanceIssue(issue_id="PERF-0001", title="T")
        d = i.model_dump()
        assert d["issue_id"] == "PERF-0001"


class TestStudioPerformanceRecommendation:
    def test_defaults(self):
        r = StudioPerformanceRecommendation()
        assert r.recommendation_id == ""
        assert r.impact == "medium"
        assert r.related_issue_ids == []

    def test_custom(self):
        r = StudioPerformanceRecommendation(
            recommendation_id="REC-0001", title="Add index",
            description="Add index on email",
            impact="high", related_issue_ids=["PERF-0001"],
        )
        assert r.impact == "high"
        assert "PERF-0001" in r.related_issue_ids

    def test_serialise(self):
        r = StudioPerformanceRecommendation(
            recommendation_id="R1", title="T", description="D",
        )
        d = r.model_dump()
        assert d["recommendation_id"] == "R1"


class TestStudioPerformanceAnalysisResponse:
    def test_defaults(self):
        r = StudioPerformanceAnalysisResponse()
        assert r.ok is False
        assert r.score == 0
        assert r.grade == "F"
        assert r.issues == []
        assert r.recommendations == []

    def test_custom(self):
        r = StudioPerformanceAnalysisResponse(
            ok=True, score=85, grade="B",
            issue_count=3, recommendation_count=2,
        )
        assert r.ok is True
        assert r.score == 85
        assert r.grade == "B"

    def test_serialise(self):
        r = StudioPerformanceAnalysisResponse(ok=True, score=90, grade="A")
        d = r.model_dump()
        assert d["score"] == 90
        assert d["grade"] == "A"
        assert "issues" in d
        assert "recommendations" in d
        assert "metrics" in d

    def test_nested_metrics(self):
        m = StudioPerformanceMetrics(total_routes=5)
        r = StudioPerformanceAnalysisResponse(ok=True, score=90, grade="A", metrics=m)
        d = r.model_dump()
        assert d["metrics"]["total_routes"] == 5


# ═══════════════════════════════════════════════════════════════════════════
# Route Registration
# ═══════════════════════════════════════════════════════════════════════════


class TestRouteRegistration:
    def test_performance_analysis_route_exists(self):
        from aksara.studio.fastapi import router
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/studio/ai/performance-analysis" in paths

    def test_performance_analysis_route_methods(self):
        from aksara.studio.fastapi import router
        for route in router.routes:
            if hasattr(route, "path") and route.path == "/studio/ai/performance-analysis":
                assert "POST" in route.methods
                break
        else:
            pytest.fail("Route not found")

    def test_both_ai_routes_exist(self):
        from aksara.studio.fastapi import router
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/studio/ai/architecture-review" in paths
        assert "/studio/ai/performance-analysis" in paths


# ═══════════════════════════════════════════════════════════════════════════
# Endpoint Integration
# ═══════════════════════════════════════════════════════════════════════════


def _make_graph(models=None, routes=None, queries=None, diagnostics=None,
                events=None):
    g = MagicMock()
    g.models = models or []
    g.routes = routes or []
    g.queries = queries or []
    g.migrations = []
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


def _make_query(sql="SELECT 1", execution_time_ms=10.0, route="", model=""):
    q = MagicMock()
    q.sql = sql
    q.query = sql
    q.execution_time_ms = execution_time_ms
    q.duration_ms = execution_time_ms
    q.route = route
    q.model = model
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


class TestEndpointIntegration:
    @patch("aksara.ai.project_graph.build_project_graph")
    def test_endpoint_returns_dict(self, mock_graph):
        mock_graph.return_value = _make_graph()
        from aksara.ai.performance_analyzer import run_performance_analysis
        report = run_performance_analysis()
        d = report.to_dict()
        assert isinstance(d, dict)
        assert "score" in d

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_endpoint_has_required_keys(self, mock_graph):
        mock_graph.return_value = _make_graph()
        from aksara.ai.performance_analyzer import run_performance_analysis
        d = run_performance_analysis().to_dict()
        for key in ("ok", "score", "grade", "issues", "recommendations",
                     "metrics", "issue_count", "recommendation_count",
                     "elapsed_ms", "generated_at"):
            assert key in d, f"Missing key: {key}"

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_endpoint_score_range(self, mock_graph):
        mock_graph.return_value = _make_graph()
        from aksara.ai.performance_analyzer import run_performance_analysis
        d = run_performance_analysis().to_dict()
        assert 0 <= d["score"] <= 100

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_endpoint_with_issues(self, mock_graph):
        q = _make_query(sql="SELECT * FROM big", execution_time_ms=500.0)
        mock_graph.return_value = _make_graph(queries=[q])
        from aksara.ai.performance_analyzer import run_performance_analysis
        d = run_performance_analysis().to_dict()
        assert len(d["issues"]) >= 1

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_endpoint_failure(self, mock_graph):
        mock_graph.side_effect = RuntimeError("no graph")
        from aksara.ai.performance_analyzer import run_performance_analysis
        d = run_performance_analysis().to_dict()
        assert d["ok"] is False
        assert d["score"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# Response Compatibility
# ═══════════════════════════════════════════════════════════════════════════


class TestResponseCompatibility:
    @patch("aksara.ai.project_graph.build_project_graph")
    def test_response_fits_pydantic_model(self, mock_graph):
        mock_graph.return_value = _make_graph()
        from aksara.ai.performance_analyzer import run_performance_analysis
        d = run_performance_analysis().to_dict()
        resp = StudioPerformanceAnalysisResponse(**d)
        assert resp.ok is True

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_issue_fits_pydantic(self, mock_graph):
        q = _make_query(sql="SELECT *", execution_time_ms=500.0)
        mock_graph.return_value = _make_graph(queries=[q])
        from aksara.ai.performance_analyzer import run_performance_analysis
        d = run_performance_analysis().to_dict()
        if d["issues"]:
            issue = StudioPerformanceIssue(**d["issues"][0])
            assert issue.issue_id != ""

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_recommendation_fits_pydantic(self, mock_graph):
        q = _make_query(sql="SELECT *", execution_time_ms=500.0)
        mock_graph.return_value = _make_graph(queries=[q])
        from aksara.ai.performance_analyzer import run_performance_analysis
        d = run_performance_analysis().to_dict()
        if d["recommendations"]:
            rec = StudioPerformanceRecommendation(**d["recommendations"][0])
            assert rec.recommendation_id != ""

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_metrics_fits_pydantic(self, mock_graph):
        mock_graph.return_value = _make_graph(
            routes=[_make_route()],
            queries=[_make_query()],
        )
        from aksara.ai.performance_analyzer import run_performance_analysis
        d = run_performance_analysis().to_dict()
        m = StudioPerformanceMetrics(**d["metrics"])
        assert m.total_routes >= 0
