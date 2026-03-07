"""
v0.5.32 — Project Context Graph: unit tests.

Tests cover:
    - Data model construction (all node types, ProjectGraph, GraphMetadata)
    - build_project_graph() — caching, rebuild, empty graph
    - _collect_models() — with mocked registry
    - _collect_routes() — with and without app
    - _collect_queries() — with mocked tracing
    - _collect_migrations() — with mocked discovery
    - _collect_diagnostics() — with mocked report
    - _collect_gaps() — with mocked gap report
    - _collect_ai_hub() — with mocked hub settings
    - _collect_flows() — from AI_FLOW_ACTIONS
    - _collect_events() — from graph_events store
    - Serialisation: to_dict(), to_summary_dict(), to_console_context()
    - Heuristics: model inference from routes, SQL, migration names
    - Cache TTL and invalidation
"""

from __future__ import annotations

import time
import pytest
from unittest.mock import MagicMock, patch

from aksara.ai.project_graph import (
    ModelNode,
    RouteNode,
    QueryNode,
    MigrationNode,
    DiagnosticNode,
    GapNode,
    AiHubNode,
    AiFlowNode,
    GraphMetadata,
    ProjectGraph,
    build_project_graph,
    _invalidate_cache,
    _collect_models,
    _collect_routes,
    _collect_queries,
    _collect_events,
    _collect_flows,
    _collect_ai_hub,
    _collect_diagnostics,
    _collect_gaps,
    _collect_migrations,
    _infer_models_from_route,
    _infer_models_from_sql,
    _infer_models_from_migration_name,
    _known_model_names,
    _table_to_model_map,
)


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


class _FakeField:
    pass


class _FakeFK:
    __class__ = type("ForeignKey", (), {})

    def __init__(self, target_name):
        self._to = target_name


class _FakeModelCls:
    __tablename__ = "users"
    __name__ = "User"
    _fields = {
        "id": _FakeField(),
        "name": _FakeField(),
        "email": _FakeField(),
    }


class _FakeModelWithFK:
    __tablename__ = "posts"
    __name__ = "Post"

    class _FK:
        _to = "User"

    _ftype = type("ForeignKey", (), {})
    _fields = {"id": _FakeField(), "title": _FakeField()}


def _fake_registry(models=None):
    """Patch ModelRegistry.all() to return given models dict."""
    if models is None:
        models = {"User": _FakeModelCls}
    return patch("aksara.registry.ModelRegistry.all", return_value=models)


def _empty_registry():
    return _fake_registry({})


class _FakeDefaults:
    chat_model = "gpt-4o"
    chat_provider = "openai"
    code_model = "gpt-4o"
    code_provider = "openai"
    embeddings_model = "text-embedding-3-small"
    embeddings_provider = "openai"


class _FakeProvider:
    kind = "openai"
    enabled = True
    is_configured = True
    api_key = "sk-test"
    model = "gpt-4o"
    base_url = ""
    def get_supported_modes(self): return ["chat"]
    def to_unified_provider(self): return MagicMock()


class _FakeHub:
    providers = [_FakeProvider()]
    defaults = _FakeDefaults()
    active_provider = "openai"
    version = "0.5.35"
    def configured_providers(self): return [_FakeProvider()]
    def get_provider(self, kind): return _FakeProvider() if kind == "openai" else None
    def provider_status_summary(self): return {}
    def resolve_defaults(self): return {}
    def to_safe_dict(self): return {}


def _mock_hub():
    return patch("aksara.ai.hub_settings.load_aihub_settings", return_value=_FakeHub())


def _mock_inspect_model(summary=None):
    """Stub inspect_model to avoid real model inspection."""
    if summary is None:
        mock_summary = MagicMock()
        mock_summary.constraints = []
    else:
        mock_summary = summary
    return patch("aksara.inspectors.models.inspect_model", return_value=mock_summary)


# ═══════════════════════════════════════════════════════════════════════════
# Tests: Data Model Construction
# ═══════════════════════════════════════════════════════════════════════════


class TestModelNode:
    def test_default_fields(self):
        node = ModelNode(name="User", table="users")
        assert node.name == "User"
        assert node.table == "users"
        assert node.fields == []
        assert node.indexes == []
        assert node.relations == []
        assert node.tags == []

    def test_with_fields(self):
        node = ModelNode(name="Post", table="posts", fields=["id", "title"])
        assert node.fields == ["id", "title"]


class TestRouteNode:
    def test_defaults(self):
        node = RouteNode(method="GET", path="/api/users", name="users", handler="list_users")
        assert node.method == "GET"
        assert node.models == []
        assert node.queries == []
        assert node.diagnostics == []


class TestQueryNode:
    def test_defaults(self):
        node = QueryNode(name="q1", sql="SELECT * FROM users")
        assert node.models == []
        assert node.indexes_used == []


class TestMigrationNode:
    def test_defaults(self):
        node = MigrationNode(name="001_create_users", app="auth")
        assert node.operations == []
        assert node.models == []


class TestDiagnosticNode:
    def test_defaults(self):
        node = DiagnosticNode(code="missing_index", severity="warning", message="no index")
        assert node.related_models == []
        assert node.related_routes == []
        assert node.related_queries == []


class TestGapNode:
    def test_defaults(self):
        node = GapNode(code="gap1", severity="info", summary="missing doc", category="docs")
        assert node.related_components == []


class TestAiHubNode:
    def test_defaults(self):
        node = AiHubNode()
        assert node.providers == []
        assert node.status == "unknown"

    def test_with_values(self):
        node = AiHubNode(providers=["openai"], status="ready")
        assert node.providers == ["openai"]


class TestAiFlowNode:
    def test_defaults(self):
        node = AiFlowNode(action_key="explain_model", title="Explain Model", flow_type="model", risk="low")
        assert node.flow_type == "model"
        assert node.risk == "low"


class TestGraphMetadata:
    def test_defaults(self):
        meta = GraphMetadata()
        assert meta.version == ""
        assert meta.model_count == 0
        assert meta.route_count == 0
        assert meta.cache_ttl_seconds == 5


class TestProjectGraph:
    def test_defaults(self):
        g = ProjectGraph()
        assert g.models == []
        assert g.routes == []
        assert g.queries == []
        assert g.migrations == []
        assert g.diagnostics == []
        assert g.gaps == []
        assert g.ai_hub is None
        assert g.flows == []
        assert g.events == []
        assert isinstance(g.metadata, GraphMetadata)


# ═══════════════════════════════════════════════════════════════════════════
# Tests: to_dict / to_summary_dict / to_console_context
# ═══════════════════════════════════════════════════════════════════════════


class TestProjectGraphSerialization:
    def test_to_dict_returns_dict(self):
        g = ProjectGraph()
        d = g.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_has_metadata(self):
        g = ProjectGraph()
        d = g.to_dict()
        assert "metadata" in d

    def test_to_dict_has_all_sections(self):
        g = ProjectGraph()
        d = g.to_dict()
        for key in ("models", "routes", "queries", "migrations", "diagnostics",
                     "gaps", "ai_hub", "flows", "events", "metadata"):
            assert key in d, f"Missing key: {key}"

    def test_to_dict_model_nodes(self):
        g = ProjectGraph()
        g.models = [ModelNode(name="User", table="users", fields=["id"])]
        d = g.to_dict()
        assert len(d["models"]) == 1
        assert d["models"][0]["name"] == "User"

    def test_to_summary_dict(self):
        g = ProjectGraph()
        g.metadata.model_count = 3
        s = g.to_summary_dict()
        assert isinstance(s, dict)
        assert "counts" in s
        assert s["counts"]["models"] == 3

    def test_to_console_context(self):
        g = ProjectGraph()
        g.models = [ModelNode(name="User", table="users")]
        g.metadata.model_count = 1
        ctx = g.to_console_context()
        assert isinstance(ctx, str)
        assert "1 model" in ctx.lower() or "User" in ctx


# ═══════════════════════════════════════════════════════════════════════════
# Tests: build_project_graph
# ═══════════════════════════════════════════════════════════════════════════


class TestBuildProjectGraph:
    def setup_method(self):
        _invalidate_cache()

    def test_returns_project_graph(self):
        with _empty_registry(), _mock_inspect_model():
            graph = build_project_graph(rebuild=True)
        assert isinstance(graph, ProjectGraph)

    def test_has_version(self):
        with _empty_registry(), _mock_inspect_model():
            graph = build_project_graph(rebuild=True)
        assert graph.metadata.version  # should be non-empty

    def test_has_generated_at(self):
        with _empty_registry(), _mock_inspect_model():
            graph = build_project_graph(rebuild=True)
        assert graph.metadata.generated_at

    def test_cache_returns_same_object(self):
        with _empty_registry(), _mock_inspect_model():
            g1 = build_project_graph(rebuild=True)
            g2 = build_project_graph(rebuild=False)
        assert g1 is g2

    def test_rebuild_creates_new_object(self):
        with _empty_registry(), _mock_inspect_model():
            g1 = build_project_graph(rebuild=True)
            g2 = build_project_graph(rebuild=True)
        assert g1 is not g2

    def test_empty_graph_models(self):
        with _empty_registry(), _mock_inspect_model():
            graph = build_project_graph(rebuild=True)
        assert graph.models == []
        assert graph.metadata.model_count == 0


# ═══════════════════════════════════════════════════════════════════════════
# Tests: _collect_models
# ═══════════════════════════════════════════════════════════════════════════


class TestCollectModels:
    def test_empty_registry(self):
        with _empty_registry(), _mock_inspect_model():
            nodes = _collect_models()
        assert nodes == []

    def test_single_model(self):
        with _fake_registry({"User": _FakeModelCls}), _mock_inspect_model():
            nodes = _collect_models()
        assert len(nodes) == 1
        assert nodes[0].name == "User"
        assert nodes[0].table == "users"

    def test_model_fields(self):
        with _fake_registry({"User": _FakeModelCls}), _mock_inspect_model():
            nodes = _collect_models()
        assert "id" in nodes[0].fields
        assert "name" in nodes[0].fields
        assert "email" in nodes[0].fields

    def test_import_failure_returns_empty(self):
        with patch("aksara.registry.ModelRegistry.all", side_effect=ImportError):
            nodes = _collect_models()
        assert nodes == []


# ═══════════════════════════════════════════════════════════════════════════
# Tests: _collect_routes
# ═══════════════════════════════════════════════════════════════════════════


class TestCollectRoutes:
    def test_no_app_returns_empty(self):
        nodes = _collect_routes(app=None)
        assert nodes == []

    def test_with_app_returns_routes(self):
        mock_route = MagicMock()
        mock_route.path = "/api/users"
        mock_route.methods = {"GET"}
        mock_route.name = "list_users"

        mock_app = MagicMock()
        mock_app.routes = [mock_route]

        fake_info = MagicMock()
        fake_info.path = "/api/users"
        fake_info.methods = ["GET"]
        fake_info.name = "list_users"
        fake_info.handler = "list_users"

        with patch("aksara.studio.utils.build_routes_info", return_value=[fake_info]), \
             _empty_registry():
            nodes = _collect_routes(app=mock_app)
        assert len(nodes) >= 1

    def test_import_failure_returns_empty(self):
        with patch("aksara.studio.utils.build_routes_info", side_effect=ImportError):
            nodes = _collect_routes(app=MagicMock())
        assert nodes == []


# ═══════════════════════════════════════════════════════════════════════════
# Tests: _collect_queries
# ═══════════════════════════════════════════════════════════════════════════


class TestCollectQueries:
    def test_no_tracing_returns_empty(self):
        with patch.dict("sys.modules", {"aksara.db.tracing": None}):
            nodes = _collect_queries()
        assert nodes == []

    def test_with_queries(self):
        fake_queries = [
            MagicMock(sql="SELECT * FROM users WHERE id=1"),
            MagicMock(sql="SELECT * FROM posts"),
        ]
        with patch("aksara.db.tracing.get_recent_queries", return_value=fake_queries, create=True), \
             _empty_registry():
            nodes = _collect_queries()
        assert len(nodes) == 2
        assert "SELECT" in nodes[0].sql


# ═══════════════════════════════════════════════════════════════════════════
# Tests: _collect_events
# ═══════════════════════════════════════════════════════════════════════════


class TestCollectEvents:
    def test_empty(self):
        from aksara.ai.graph_events import clear_graph_events
        clear_graph_events()
        events = _collect_events()
        assert events == []

    def test_with_events(self):
        from aksara.ai.graph_events import emit_graph_event, clear_graph_events
        clear_graph_events()
        emit_graph_event("route_error", "route", "/api/users")
        events = _collect_events()
        assert len(events) >= 1
        assert events[0]["kind"] == "route_error"
        # cleanup
        clear_graph_events()


# ═══════════════════════════════════════════════════════════════════════════
# Tests: _collect_flows
# ═══════════════════════════════════════════════════════════════════════════


class TestCollectFlows:
    def test_returns_list(self):
        nodes = _collect_flows()
        assert isinstance(nodes, list)

    def test_ai_flow_node_shape(self):
        nodes = _collect_flows()
        if nodes:
            node = nodes[0]
            assert isinstance(node, AiFlowNode)
            assert node.action_key
            assert node.title


# ═══════════════════════════════════════════════════════════════════════════
# Tests: _collect_ai_hub
# ═══════════════════════════════════════════════════════════════════════════


class TestCollectAiHub:
    def test_with_hub(self):
        with _mock_hub():
            hub = _collect_ai_hub()
        assert isinstance(hub, AiHubNode)
        assert hub.status == "ready"
        assert "openai" in hub.providers

    def test_hub_failure_returns_unavailable(self):
        with patch("aksara.ai.hub_settings.load_aihub_settings", side_effect=Exception("no")):
            hub = _collect_ai_hub()
        assert hub.status == "unavailable"


# ═══════════════════════════════════════════════════════════════════════════
# Tests: _collect_diagnostics
# ═══════════════════════════════════════════════════════════════════════════


class TestCollectDiagnostics:
    def test_no_cached_report(self):
        with patch("aksara.diagnostics.DiagnosticReport._last_report", None, create=True):
            nodes = _collect_diagnostics()
        assert nodes == []

    def test_with_issues(self):
        fake_issue = MagicMock()
        fake_issue.kind = "perf_warning"
        fake_issue.severity = "warning"
        fake_issue.title = "Slow query detected"
        fake_issue.message = ""

        fake_report = MagicMock()
        fake_report.issues = [fake_issue]

        with patch("aksara.diagnostics.DiagnosticReport._last_report", fake_report, create=True):
            nodes = _collect_diagnostics()
        assert len(nodes) == 1
        assert nodes[0].code == "perf_warning"
        assert nodes[0].severity == "warning"


# ═══════════════════════════════════════════════════════════════════════════
# Tests: _collect_gaps
# ═══════════════════════════════════════════════════════════════════════════


class TestCollectGaps:
    def test_no_report(self):
        with patch("aksara.gapanalysis._last_report", None, create=True):
            nodes = _collect_gaps()
        assert nodes == []

    def test_with_gaps(self):
        fake_gap = MagicMock()
        fake_gap.code = "api_missing_auth"
        fake_gap.severity = "error"
        fake_gap.title = "Missing authentication"
        fake_gap.message = ""
        fake_gap.category = "security"
        fake_gap.related_components = []

        fake_report = MagicMock()
        fake_report.issues = [fake_gap]

        with patch("aksara.gapanalysis._last_report", fake_report, create=True):
            nodes = _collect_gaps()
        assert len(nodes) == 1
        assert nodes[0].code == "api_missing_auth"


# ═══════════════════════════════════════════════════════════════════════════
# Tests: _collect_migrations
# ═══════════════════════════════════════════════════════════════════════════


class TestCollectMigrations:
    def test_import_failure_returns_empty(self):
        with patch("aksara.migrations.discover_all_migrations", side_effect=ImportError):
            nodes = _collect_migrations()
        assert nodes == []


# ═══════════════════════════════════════════════════════════════════════════
# Tests: Relationship Heuristics
# ═══════════════════════════════════════════════════════════════════════════


class TestInferModelsFromRoute:
    def test_direct_match(self):
        found = _infer_models_from_route("/api/user", "", ["User"])
        assert "User" in found

    def test_plural_match(self):
        found = _infer_models_from_route("/api/users", "", ["User"])
        assert "User" in found

    def test_handler_match(self):
        found = _infer_models_from_route("/api/v1", "list_user", ["User"])
        assert "User" in found

    def test_no_match(self):
        found = _infer_models_from_route("/api/v1/data", "handler", ["User"])
        assert found == []

    def test_case_insensitive(self):
        found = _infer_models_from_route("/api/USER", "", ["User"])
        assert "User" in found

    def test_no_duplicates(self):
        found = _infer_models_from_route("/api/user", "user_handler", ["User"])
        assert found.count("User") == 1


class TestInferModelsFromSql:
    def test_table_match(self):
        mapping = {"users": "User", "posts": "Post"}
        found = _infer_models_from_sql("SELECT * FROM users", mapping)
        assert "User" in found

    def test_multiple_tables(self):
        mapping = {"users": "User", "posts": "Post"}
        found = _infer_models_from_sql("SELECT * FROM users JOIN posts", mapping)
        assert "User" in found
        assert "Post" in found

    def test_no_match(self):
        mapping = {"users": "User"}
        found = _infer_models_from_sql("SELECT 1", mapping)
        assert found == []


class TestInferModelsFromMigrationName:
    def test_model_in_name(self):
        found = _infer_models_from_migration_name("001_create_user_table", ["User"])
        assert "User" in found

    def test_no_match(self):
        found = _infer_models_from_migration_name("001_initial", ["User"])
        assert found == []


class TestKnownModelNames:
    def test_with_registry(self):
        with _fake_registry({"User": _FakeModelCls, "Post": MagicMock()}):
            names = _known_model_names()
        assert "User" in names
        assert "Post" in names

    def test_empty_registry(self):
        with _empty_registry():
            names = _known_model_names()
        assert names == []


class TestTableToModelMap:
    def test_mapping(self):
        with _fake_registry({"User": _FakeModelCls}):
            mapping = _table_to_model_map()
        assert mapping.get("users") == "User"

    def test_empty(self):
        with _empty_registry():
            mapping = _table_to_model_map()
        assert mapping == {}


# ═══════════════════════════════════════════════════════════════════════════
# Tests: Cache Invalidation
# ═══════════════════════════════════════════════════════════════════════════


class TestCacheInvalidation:
    def setup_method(self):
        _invalidate_cache()

    def test_invalidate_makes_next_call_fresh(self):
        with _empty_registry(), _mock_inspect_model():
            g1 = build_project_graph(rebuild=True)
        _invalidate_cache()
        with _empty_registry(), _mock_inspect_model():
            g2 = build_project_graph(rebuild=False)
        assert g1 is not g2
