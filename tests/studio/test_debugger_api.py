"""
v0.5.33 — Studio AI Debugger API: endpoint tests.

Tests cover:
    - Route registration: POST /studio/ai/debug on the router
    - Response shape and key validation
    - Query parameter handling
    - StudioDebugRequest / StudioDebugResponse models
    - Error handling when debugger fails
    - Empty project (no issues)
    - Full project with issues
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from aksara.ai.debugger import (
    DebugReport,
    DebugIssue,
    IssueCluster,
    RootCause,
    run_debugger,
)
from aksara.studio.models import (
    StudioDebugRequest,
    StudioDebugResponse,
    StudioDebugRootCause,
    StudioDebugCluster,
    StudioDebugIssue,
)


# ═══════════════════════════════════════════════════════════════════════════
# Pydantic model tests
# ═══════════════════════════════════════════════════════════════════════════


class TestStudioDebugRequest:
    def test_default_query_none(self):
        req = StudioDebugRequest()
        assert req.query is None

    def test_with_query(self):
        req = StudioDebugRequest(query="why is /api/users failing?")
        assert req.query == "why is /api/users failing?"

    def test_model_dump(self):
        req = StudioDebugRequest(query="debug")
        d = req.model_dump()
        assert "query" in d


class TestStudioDebugResponse:
    def test_default_values(self):
        resp = StudioDebugResponse()
        assert resp.ok is False
        assert resp.issues == []
        assert resp.clusters == []
        assert resp.root_causes == []
        assert resp.issue_count == 0

    def test_full_response(self):
        resp = StudioDebugResponse(
            ok=True,
            query="debug",
            issues=[StudioDebugIssue(id="1", source="diagnostic", severity="error",
                                     title="DB_NO_URL", message="No database URL")],
            clusters=[StudioDebugCluster(cluster_id="c-1", label="General",
                                         component_type="general", component_name="uncategorised",
                                         issue_ids=["1"], severity="error", size=1)],
            root_causes=[StudioDebugRootCause(cause_id="rc-1", title="DB issue",
                                              description="Database connectivity problem",
                                              confidence=0.85, severity="error")],
            summary="Test",
            issue_count=1,
            cluster_count=1,
            root_cause_count=1,
            elapsed_ms=5.0,
            generated_at="2025-01-01T00:00:00Z",
        )
        assert resp.ok is True
        assert resp.issue_count == 1
        assert resp.root_causes[0].confidence == 0.85

    def test_model_dump(self):
        resp = StudioDebugResponse(ok=True)
        d = resp.model_dump()
        assert "ok" in d
        assert "issues" in d
        assert "root_causes" in d


class TestStudioDebugRootCause:
    def test_defaults(self):
        rc = StudioDebugRootCause()
        assert rc.cause_id == ""
        assert rc.confidence == 0.0
        assert rc.fix_suggestions == []

    def test_full(self):
        rc = StudioDebugRootCause(
            cause_id="rc-1", title="DB issue", description="desc",
            confidence=0.9, severity="error", evidence=["e1"],
            related_issues=["i1"], related_clusters=["c1"],
            category="database", fix_suggestions=["fix1"],
        )
        assert rc.category == "database"
        assert rc.fix_suggestions == ["fix1"]


class TestStudioDebugCluster:
    def test_defaults(self):
        cl = StudioDebugCluster()
        assert cl.cluster_id == ""
        assert cl.size == 0

    def test_full(self):
        cl = StudioDebugCluster(
            cluster_id="c-1", label="Model: User",
            component_type="model", component_name="User",
            issue_ids=["1", "2"], severity="error", size=2,
        )
        assert cl.size == 2
        assert cl.component_type == "model"


class TestStudioDebugIssue:
    def test_defaults(self):
        i = StudioDebugIssue()
        assert i.id == ""
        assert i.severity == "info"

    def test_full(self):
        i = StudioDebugIssue(
            id="d-1", source="diagnostic", severity="error",
            title="DB_NO_URL", message="No database URL",
            related_models=["User"], related_routes=["/api/users"],
        )
        assert i.related_models == ["User"]


# ═══════════════════════════════════════════════════════════════════════════
# Route registration tests
# ═══════════════════════════════════════════════════════════════════════════


class TestRouteRegistration:
    def test_debug_endpoint_registered(self):
        from aksara.studio.fastapi import router

        paths = [r.path for r in router.routes]
        assert "/studio/ai/debug" in paths

    def test_debug_endpoint_method(self):
        from aksara.studio.fastapi import router

        for route in router.routes:
            if getattr(route, "path", None) == "/studio/ai/debug":
                assert "POST" in route.methods
                break
        else:
            pytest.fail("POST /studio/ai/debug not found")


# ═══════════════════════════════════════════════════════════════════════════
# Endpoint integration tests (mocked debugger)
# ═══════════════════════════════════════════════════════════════════════════


class TestDebugEndpoint:
    @patch("aksara.ai.project_graph.build_project_graph")
    def test_endpoint_returns_report(self, mock_build):
        from aksara.ai.project_graph import ProjectGraph
        mock_build.return_value = ProjectGraph()

        report = run_debugger()
        assert isinstance(report, DebugReport)
        assert report.ok is True

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_endpoint_with_query(self, mock_build):
        from aksara.ai.project_graph import ProjectGraph
        mock_build.return_value = ProjectGraph()

        report = run_debugger(query="database issues")
        assert report.query == "database issues"

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_report_to_dict_shape(self, mock_build):
        from aksara.ai.project_graph import ProjectGraph
        mock_build.return_value = ProjectGraph()

        report = run_debugger()
        d = report.to_dict()
        assert "ok" in d
        assert "issues" in d
        assert "clusters" in d
        assert "root_causes" in d
        assert "summary" in d
        assert "issue_count" in d
        assert "cluster_count" in d
        assert "root_cause_count" in d
        assert "elapsed_ms" in d
        assert "generated_at" in d

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_report_summary_dict_shape(self, mock_build):
        from aksara.ai.project_graph import ProjectGraph
        mock_build.return_value = ProjectGraph()

        report = run_debugger()
        s = report.to_summary_dict()
        assert "ok" in s
        assert "top_root_causes" in s
        assert "elapsed_ms" in s

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_graph_failure_returns_error_report(self, mock_build):
        mock_build.side_effect = RuntimeError("boom")

        report = run_debugger()
        assert report.ok is False
        assert "boom" in report.summary


# ═══════════════════════════════════════════════════════════════════════════
# Response compatibility
# ═══════════════════════════════════════════════════════════════════════════


class TestResponseCompatibility:
    @patch("aksara.ai.project_graph.build_project_graph")
    def test_report_maps_to_response_model(self, mock_build):
        from aksara.ai.project_graph import ProjectGraph
        mock_build.return_value = ProjectGraph()

        report = run_debugger()
        d = report.to_dict()
        resp = StudioDebugResponse(**d)
        assert resp.ok is True

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_report_with_issues_maps(self, mock_build):
        g = MagicMock()
        g.diagnostics = [MagicMock(code="X", severity="error", message="Y",
                                   related_models=[], related_routes=[], related_queries=[])]
        g.gaps = []
        g.events = []
        g.models = []
        g.routes = []
        g.queries = []
        g.migrations = []
        g.ai_hub = None
        m = MagicMock()
        m.model_count = 0
        m.route_count = 0
        m.query_count = 0
        m.migration_count = 0
        m.diagnostic_count = 1
        m.gap_count = 0
        m.event_count = 0
        g.metadata = m
        mock_build.return_value = g

        report = run_debugger()
        d = report.to_dict()
        resp = StudioDebugResponse(**d)
        assert resp.issue_count >= 1
