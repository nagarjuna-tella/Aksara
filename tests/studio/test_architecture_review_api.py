"""
v0.5.34 — AI Architecture Review: Studio API endpoint tests.

Tests cover:
    - Pydantic models (StudioArchitectureReviewResponse, etc.)
    - POST /studio/ai/architecture-review route registration
    - Endpoint integration with mocked graph
    - Response structure and field types
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from aksara.studio.models import (
    StudioArchitectureMetrics,
    StudioArchitectureFinding,
    StudioArchitectureSuggestion,
    StudioArchitectureReviewResponse,
)


# ═══════════════════════════════════════════════════════════════════════════
# Pydantic Model Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestStudioArchitectureMetrics:
    def test_defaults(self):
        m = StudioArchitectureMetrics()
        assert m.model_count == 0
        assert m.coupling_score == 0.0

    def test_custom_values(self):
        m = StudioArchitectureMetrics(model_count=5, route_count=10,
                                       coupling_score=0.45)
        assert m.model_count == 5
        assert m.coupling_score == 0.45

    def test_serialise(self):
        m = StudioArchitectureMetrics(model_count=3)
        d = m.model_dump()
        assert d["model_count"] == 3
        assert "coupling_score" in d


class TestStudioArchitectureFinding:
    def test_defaults(self):
        f = StudioArchitectureFinding()
        assert f.id == ""
        assert f.severity == "info"
        assert f.related_nodes == []
        assert f.category == "general"

    def test_custom(self):
        f = StudioArchitectureFinding(
            id="F1", severity="error", title="High coupling",
            description="Desc", related_nodes=["User"],
            category="coupling",
        )
        assert f.id == "F1"
        assert f.category == "coupling"

    def test_serialise(self):
        f = StudioArchitectureFinding(id="F1", title="T")
        d = f.model_dump()
        assert d["id"] == "F1"


class TestStudioArchitectureSuggestion:
    def test_defaults(self):
        s = StudioArchitectureSuggestion()
        assert s.suggestion_id == ""
        assert s.impact == "medium"
        assert s.related_findings == []

    def test_custom(self):
        s = StudioArchitectureSuggestion(
            suggestion_id="S1", title="Add index",
            description="Add index on email",
            impact="high", related_findings=["F1"],
        )
        assert s.impact == "high"
        assert "F1" in s.related_findings

    def test_serialise(self):
        s = StudioArchitectureSuggestion(suggestion_id="S1", title="T", description="D")
        d = s.model_dump()
        assert d["suggestion_id"] == "S1"


class TestStudioArchitectureReviewResponse:
    def test_defaults(self):
        r = StudioArchitectureReviewResponse()
        assert r.ok is False
        assert r.score == 0
        assert r.grade == "F"
        assert r.findings == []
        assert r.suggestions == []

    def test_custom(self):
        r = StudioArchitectureReviewResponse(
            ok=True, score=85, grade="B",
            finding_count=3, suggestion_count=2,
        )
        assert r.ok is True
        assert r.score == 85
        assert r.grade == "B"

    def test_serialise(self):
        r = StudioArchitectureReviewResponse(ok=True, score=90, grade="A")
        d = r.model_dump()
        assert d["score"] == 90
        assert d["grade"] == "A"
        assert "findings" in d
        assert "metrics" in d


# ═══════════════════════════════════════════════════════════════════════════
# Route Registration
# ═══════════════════════════════════════════════════════════════════════════


class TestRouteRegistration:
    def test_architecture_review_route_exists(self):
        from aksara.studio.fastapi import router
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/studio/ai/architecture-review" in paths

    def test_architecture_review_route_methods(self):
        from aksara.studio.fastapi import router
        for route in router.routes:
            if hasattr(route, "path") and route.path == "/studio/ai/architecture-review":
                assert "POST" in route.methods
                break
        else:
            pytest.fail("Route not found")


# ═══════════════════════════════════════════════════════════════════════════
# Endpoint Integration
# ═══════════════════════════════════════════════════════════════════════════


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
    g.metadata.version = "0.5.35"
    g.metadata.model_count = len(g.models)
    g.metadata.route_count = len(g.routes)
    return g


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


class TestEndpointIntegration:
    @patch("aksara.ai.project_graph.build_project_graph")
    def test_endpoint_returns_dict(self, mock_graph):
        mock_graph.return_value = _make_graph()
        from aksara.ai.architecture_review import run_architecture_review
        report = run_architecture_review()
        d = report.to_dict()
        assert isinstance(d, dict)
        assert "score" in d
        assert "grade" in d

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_endpoint_score_range(self, mock_graph):
        mock_graph.return_value = _make_graph()
        from aksara.ai.architecture_review import run_architecture_review
        report = run_architecture_review()
        assert 0 <= report.score <= 100

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_endpoint_with_findings(self, mock_graph):
        routes = [_make_route(models=["A", "B", "C", "D", "E"])]
        mock_graph.return_value = _make_graph(routes=routes)
        from aksara.ai.architecture_review import run_architecture_review
        report = run_architecture_review()
        d = report.to_dict()
        assert len(d["findings"]) >= 1

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_endpoint_graph_failure(self, mock_graph):
        mock_graph.side_effect = RuntimeError("fail")
        from aksara.ai.architecture_review import run_architecture_review
        report = run_architecture_review()
        assert report.ok is False
        d = report.to_dict()
        assert d["score"] == 0
        assert d["grade"] == "F"


# ═══════════════════════════════════════════════════════════════════════════
# Response Compatibility
# ═══════════════════════════════════════════════════════════════════════════


class TestResponseCompatibility:
    @patch("aksara.ai.project_graph.build_project_graph")
    def test_response_has_all_required_fields(self, mock_graph):
        mock_graph.return_value = _make_graph()
        from aksara.ai.architecture_review import run_architecture_review
        d = run_architecture_review().to_dict()
        required = ["score", "grade", "findings", "suggestions",
                     "metrics", "generated_at", "elapsed_ms", "ok",
                     "finding_count", "suggestion_count"]
        for key in required:
            assert key in d, f"Missing key: {key}"

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_metrics_in_response(self, mock_graph):
        mock_graph.return_value = _make_graph(
            models=[_make_model()],
            routes=[_make_route()],
        )
        from aksara.ai.architecture_review import run_architecture_review
        d = run_architecture_review().to_dict()
        metrics = d["metrics"]
        assert "model_count" in metrics
        assert "route_count" in metrics
        assert "coupling_score" in metrics

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_findings_structure(self, mock_graph):
        routes = [_make_route(models=["A", "B", "C", "D"])]
        mock_graph.return_value = _make_graph(routes=routes)
        from aksara.ai.architecture_review import run_architecture_review
        d = run_architecture_review().to_dict()
        if d["findings"]:
            f = d["findings"][0]
            assert "id" in f
            assert "severity" in f
            assert "title" in f
            assert "category" in f

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_suggestions_structure(self, mock_graph):
        routes = [_make_route(models=["A", "B", "C", "D"])]
        mock_graph.return_value = _make_graph(routes=routes)
        from aksara.ai.architecture_review import run_architecture_review
        d = run_architecture_review().to_dict()
        if d["suggestions"]:
            s = d["suggestions"][0]
            assert "suggestion_id" in s
            assert "title" in s
            assert "impact" in s
