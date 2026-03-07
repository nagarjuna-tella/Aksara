"""
v0.5.32 — Studio Project Graph API: endpoint tests.

Tests cover:
    - Route registration: all 3 new endpoints on the router
    - /studio/ai/project-graph — full graph, summary, rebuild query params
    - /studio/ai/project-graph/events — event retrieval with limit param
    - /studio/ai/project-graph/summary — compact summary endpoint
    - Response shape and key validation
    - StudioProjectGraphEventsResponse model
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from aksara.ai.project_graph import (
    ProjectGraph,
    ModelNode,
    RouteNode,
    AiHubNode,
    AiFlowNode,
    _invalidate_cache,
)
from aksara.ai.graph_events import GraphEvent


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _make_graph() -> ProjectGraph:
    g = ProjectGraph()
    g.models = [ModelNode(name="User", table="users", fields=["id"])]
    g.routes = [RouteNode(method="GET", path="/api/users", name="list", handler="list")]
    g.ai_hub = AiHubNode(providers=["openai"], status="ready")
    g.flows = [AiFlowNode(action_key="explain_model", title="Explain", flow_type="model", risk="low")]
    g.metadata.model_count = 1
    g.metadata.route_count = 1
    g.metadata.version = "0.5.36"
    g.metadata.generated_at = "2025-01-01T00:00:00Z"
    return g


def _patch_graph(graph=None):
    g = graph or _make_graph()
    return patch("aksara.ai.project_graph.build_project_graph", return_value=g)


# ═══════════════════════════════════════════════════════════════════════════
# Tests: Route Registration
# ═══════════════════════════════════════════════════════════════════════════


class TestEndpointRegistration:
    def test_project_graph_route_registered(self):
        from aksara.studio.fastapi import router
        paths = [r.path for r in router.routes]
        assert "/studio/ai/project-graph" in paths

    def test_events_route_registered(self):
        from aksara.studio.fastapi import router
        paths = [r.path for r in router.routes]
        assert "/studio/ai/project-graph/events" in paths

    def test_summary_route_registered(self):
        from aksara.studio.fastapi import router
        paths = [r.path for r in router.routes]
        assert "/studio/ai/project-graph/summary" in paths

    def test_graph_route_is_get(self):
        from aksara.studio.fastapi import router
        for r in router.routes:
            if getattr(r, "path", "") == "/studio/ai/project-graph":
                assert "GET" in r.methods
                break
        else:
            pytest.fail("Route not found")

    def test_events_route_is_get(self):
        from aksara.studio.fastapi import router
        for r in router.routes:
            if getattr(r, "path", "") == "/studio/ai/project-graph/events":
                assert "GET" in r.methods
                break
        else:
            pytest.fail("Route not found")


# ═══════════════════════════════════════════════════════════════════════════
# Tests: /studio/ai/project-graph
# ═══════════════════════════════════════════════════════════════════════════


class TestProjectGraphEndpoint:
    @pytest.mark.asyncio
    async def test_full_graph_response_shape(self):
        from aksara.studio.fastapi import studio_ai_project_graph
        mock_request = MagicMock()
        mock_request.query_params = {}
        mock_request.app = MagicMock()

        with _patch_graph():
            result = await studio_ai_project_graph(mock_request)

        assert isinstance(result, dict)
        for key in ("models", "routes", "metadata"):
            assert key in result

    @pytest.mark.asyncio
    async def test_summary_query_param(self):
        from aksara.studio.fastapi import studio_ai_project_graph
        mock_request = MagicMock()
        mock_request.query_params = {"summary": "true"}
        mock_request.app = MagicMock()

        with _patch_graph():
            result = await studio_ai_project_graph(mock_request)

        assert "counts" in result
        # Full "models" array should NOT be present in summary
        assert "models" not in result

    @pytest.mark.asyncio
    async def test_rebuild_query_param(self):
        from aksara.studio.fastapi import studio_ai_project_graph
        mock_request = MagicMock()
        mock_request.query_params = {"rebuild": "true"}
        mock_request.app = MagicMock()

        with _patch_graph() as mock_build:
            await studio_ai_project_graph(mock_request)
            mock_build.assert_called_once_with(rebuild=True, app=mock_request.app)


# ═══════════════════════════════════════════════════════════════════════════
# Tests: /studio/ai/project-graph/events
# ═══════════════════════════════════════════════════════════════════════════


class TestProjectGraphEventsEndpoint:
    @pytest.mark.asyncio
    async def test_events_response_shape(self):
        from aksara.studio.fastapi import studio_ai_project_graph_events
        from aksara.ai.graph_events import clear_graph_events, emit_graph_event
        clear_graph_events()
        emit_graph_event("route_error", "route", "/api/test", severity="error", message="fail")

        mock_request = MagicMock()
        mock_request.query_params = {}

        result = await studio_ai_project_graph_events(mock_request)
        assert "events" in result
        assert "count" in result
        assert result["count"] >= 1

        clear_graph_events()

    @pytest.mark.asyncio
    async def test_events_limit_param(self):
        from aksara.studio.fastapi import studio_ai_project_graph_events
        from aksara.ai.graph_events import clear_graph_events, emit_graph_event
        clear_graph_events()
        for i in range(10):
            emit_graph_event("route_error", "route", f"/{i}")

        mock_request = MagicMock()
        mock_request.query_params = {"limit": "3"}

        result = await studio_ai_project_graph_events(mock_request)
        assert result["count"] == 3

        clear_graph_events()

    @pytest.mark.asyncio
    async def test_events_invalid_limit(self):
        from aksara.studio.fastapi import studio_ai_project_graph_events
        mock_request = MagicMock()
        mock_request.query_params = {"limit": "abc"}

        result = await studio_ai_project_graph_events(mock_request)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_events_empty(self):
        from aksara.studio.fastapi import studio_ai_project_graph_events
        from aksara.ai.graph_events import clear_graph_events
        clear_graph_events()

        mock_request = MagicMock()
        mock_request.query_params = {}

        result = await studio_ai_project_graph_events(mock_request)
        assert result["count"] == 0
        assert result["events"] == []


# ═══════════════════════════════════════════════════════════════════════════
# Tests: /studio/ai/project-graph/summary
# ═══════════════════════════════════════════════════════════════════════════


class TestProjectGraphSummaryEndpoint:
    @pytest.mark.asyncio
    async def test_summary_response_shape(self):
        from aksara.studio.fastapi import studio_ai_project_graph_summary
        mock_request = MagicMock()
        mock_request.app = MagicMock()

        with _patch_graph():
            result = await studio_ai_project_graph_summary(mock_request)

        assert isinstance(result, dict)
        assert "counts" in result
        assert "version" in result

    @pytest.mark.asyncio
    async def test_summary_counts_correct(self):
        from aksara.studio.fastapi import studio_ai_project_graph_summary
        mock_request = MagicMock()
        mock_request.app = MagicMock()

        with _patch_graph():
            result = await studio_ai_project_graph_summary(mock_request)

        assert result["counts"]["models"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# Tests: StudioProjectGraphEventsResponse model
# ═══════════════════════════════════════════════════════════════════════════


class TestEventsResponseModel:
    def test_model_creation(self):
        from aksara.studio.models import StudioProjectGraphEventsResponse
        resp = StudioProjectGraphEventsResponse(
            events=[{"kind": "route_error"}],
            count=1,
        )
        assert resp.count == 1
        assert len(resp.events) == 1

    def test_model_roundtrip(self):
        from aksara.studio.models import StudioProjectGraphEventsResponse
        resp = StudioProjectGraphEventsResponse(events=[], count=0)
        d = resp.model_dump()
        resp2 = StudioProjectGraphEventsResponse(**d)
        assert resp2.count == 0
