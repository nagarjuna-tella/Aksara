"""
v0.5.34 — AI Architecture Review: metrics computation tests.

Tests cover:
    - ArchitectureMetrics data model
    - _compute_metrics with various graph shapes
    - Coupling score calculation
    - Avg models/queries per route
    - Edge cases: no routes, no models, single route
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from aksara.ai.architecture_review import (
    ArchitectureMetrics,
    _compute_metrics,
    _score_to_grade,
    _compute_score,
    ArchitectureFinding,
    _reset_counters,
)


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _make_model(name="User", fields=None, relations=None):
    m = MagicMock()
    m.name = name
    m.table = name.lower() + "s"
    m.fields = fields or ["id", "name"]
    m.relations = relations or []
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


def _make_graph(models=None, routes=None, queries=None, migrations=None,
                diagnostics=None, gaps=None, events=None):
    g = MagicMock()
    g.models = models or []
    g.routes = routes or []
    g.queries = queries or []
    g.migrations = migrations or []
    g.diagnostics = diagnostics or []
    g.gaps = gaps or []
    g.events = events or []
    g.flows = []
    g.ai_hub = None
    return g


# ═══════════════════════════════════════════════════════════════════════════
# ArchitectureMetrics Model Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestArchitectureMetricsModel:
    def test_default_values(self):
        m = ArchitectureMetrics()
        assert m.model_count == 0
        assert m.route_count == 0
        assert m.query_count == 0
        assert m.migration_count == 0
        assert m.diagnostic_count == 0
        assert m.avg_models_per_route == 0.0
        assert m.avg_queries_per_route == 0.0
        assert m.coupling_score == 0.0

    def test_custom_values(self):
        m = ArchitectureMetrics(
            model_count=10, route_count=50, query_count=100,
            migration_count=20, diagnostic_count=5,
            avg_models_per_route=2.0, avg_queries_per_route=4.0,
            coupling_score=0.4,
        )
        assert m.model_count == 10
        assert m.coupling_score == 0.4

    def test_to_dict_roundtrip(self):
        m = ArchitectureMetrics(model_count=3, route_count=7)
        d = m.to_dict()
        assert isinstance(d, dict)
        assert d["model_count"] == 3
        assert d["route_count"] == 7
        assert "coupling_score" in d

    def test_to_dict_all_keys(self):
        m = ArchitectureMetrics()
        d = m.to_dict()
        expected = {"model_count", "route_count", "query_count",
                    "migration_count", "diagnostic_count",
                    "avg_models_per_route", "avg_queries_per_route",
                    "coupling_score"}
        assert set(d.keys()) == expected


# ═══════════════════════════════════════════════════════════════════════════
# Compute Metrics
# ═══════════════════════════════════════════════════════════════════════════


class TestComputeMetricsDetailed:
    def test_empty_graph_metrics(self):
        g = _make_graph()
        m = _compute_metrics(g)
        assert m.model_count == 0
        assert m.route_count == 0
        assert m.query_count == 0
        assert m.migration_count == 0
        assert m.diagnostic_count == 0
        assert m.avg_models_per_route == 0.0
        assert m.avg_queries_per_route == 0.0
        assert m.coupling_score == 0.0

    def test_single_model(self):
        g = _make_graph(models=[_make_model()])
        m = _compute_metrics(g)
        assert m.model_count == 1

    def test_multiple_models(self):
        models = [_make_model(f"M{i}") for i in range(5)]
        g = _make_graph(models=models)
        m = _compute_metrics(g)
        assert m.model_count == 5

    def test_single_route_no_models(self):
        g = _make_graph(routes=[_make_route()])
        m = _compute_metrics(g)
        assert m.route_count == 1
        assert m.avg_models_per_route == 0.0

    def test_single_route_with_models(self):
        routes = [_make_route(models=["User", "Order"])]
        g = _make_graph(routes=routes)
        m = _compute_metrics(g)
        assert m.avg_models_per_route == 2.0

    def test_multiple_routes_avg_models(self):
        routes = [
            _make_route(path="/a", models=["M1", "M2", "M3"]),
            _make_route(path="/b", models=["M1"]),
            _make_route(path="/c", models=[]),
        ]
        g = _make_graph(routes=routes)
        m = _compute_metrics(g)
        assert m.avg_models_per_route == pytest.approx(4.0 / 3, rel=0.01)

    def test_multiple_routes_avg_queries(self):
        routes = [
            _make_route(path="/a", queries=["q1", "q2"]),
            _make_route(path="/b", queries=["q3", "q4", "q5", "q6"]),
        ]
        g = _make_graph(routes=routes)
        m = _compute_metrics(g)
        assert m.avg_queries_per_route == 3.0

    def test_query_count(self):
        queries = [MagicMock() for _ in range(7)]
        g = _make_graph(queries=queries)
        m = _compute_metrics(g)
        assert m.query_count == 7

    def test_migration_count(self):
        migs = [MagicMock() for _ in range(12)]
        g = _make_graph(migrations=migs)
        m = _compute_metrics(g)
        assert m.migration_count == 12

    def test_diagnostic_count(self):
        diags = [MagicMock() for _ in range(3)]
        g = _make_graph(diagnostics=diags)
        m = _compute_metrics(g)
        assert m.diagnostic_count == 3


# ═══════════════════════════════════════════════════════════════════════════
# Coupling Score
# ═══════════════════════════════════════════════════════════════════════════


class TestCouplingScore:
    def test_zero_coupling(self):
        g = _make_graph()
        m = _compute_metrics(g)
        assert m.coupling_score == 0.0

    def test_moderate_coupling(self):
        routes = [
            _make_route(path="/a", models=["M1", "M2"], queries=["q1", "q2"]),
            _make_route(path="/b", models=["M1"], queries=["q3"]),
        ]
        g = _make_graph(routes=routes)
        m = _compute_metrics(g)
        # avg_models = 1.5, avg_queries = 1.5
        # coupling = min(1.0, 1.5/10 + 1.5/20) = min(1.0, 0.15 + 0.075) = 0.225
        assert 0.0 < m.coupling_score < 1.0

    def test_high_coupling_capped(self):
        routes = [_make_route(models=list(range(20)), queries=list(range(40)))]
        g = _make_graph(routes=routes)
        m = _compute_metrics(g)
        assert m.coupling_score == 1.0

    def test_coupling_only_models(self):
        routes = [_make_route(models=["A", "B", "C", "D", "E"])]
        g = _make_graph(routes=routes)
        m = _compute_metrics(g)
        # 5/10 + 0/20 = 0.5
        assert m.coupling_score == 0.5

    def test_coupling_only_queries(self):
        routes = [_make_route(queries=["q" + str(i) for i in range(10)])]
        g = _make_graph(routes=routes)
        m = _compute_metrics(g)
        # 0/10 + 10/20 = 0.5
        assert m.coupling_score == 0.5


# ═══════════════════════════════════════════════════════════════════════════
# Grade Mapping
# ═══════════════════════════════════════════════════════════════════════════


class TestGradeMapping:
    @pytest.mark.parametrize("score,expected", [
        (100, "A"), (95, "A"), (90, "A"),
        (89, "B"), (85, "B"), (80, "B"),
        (79, "C"), (75, "C"), (70, "C"),
        (69, "D"), (65, "D"), (60, "D"),
        (59, "F"), (30, "F"), (0, "F"),
    ])
    def test_grade_mapping(self, score, expected):
        assert _score_to_grade(score) == expected


# ═══════════════════════════════════════════════════════════════════════════
# Score With Multiple Penalty Types
# ═══════════════════════════════════════════════════════════════════════════


class TestScorePenalties:
    def setup_method(self):
        _reset_counters()

    def test_all_penalty_types_combined(self):
        findings = [
            ArchitectureFinding(id="F1", severity="warning",
                                title="High route-to-model coupling",
                                description="", category="coupling"),
            ArchitectureFinding(id="F2", severity="error",
                                title="Schema lacks indexes on frequently queried columns",
                                description="", category="schema_design"),
            ArchitectureFinding(id="F3", severity="warning",
                                title="API surface becoming large",
                                description="", category="api_design"),
            ArchitectureFinding(id="F4", severity="warning",
                                title="Frequent schema churn",
                                description="", category="migration_risk"),
            ArchitectureFinding(id="F5", severity="error",
                                title="Slow query events detected",
                                description="", category="performance"),
        ]
        score = _compute_score(findings)
        # 100 - 10 - 10 - 10 - 5 - 15 = 50
        assert score == 50

    def test_score_never_negative(self):
        findings = [
            ArchitectureFinding(id=f"F{i}", severity="critical",
                                title="Unknown", description="",
                                category="unknown")
            for i in range(20)
        ]
        score = _compute_score(findings)
        assert score == 0

    def test_severity_based_default_penalties(self):
        findings = [
            ArchitectureFinding(id="F1", severity="critical",
                                title="Unknown A", description="", category="x"),
            ArchitectureFinding(id="F2", severity="error",
                                title="Unknown B", description="", category="x"),
            ArchitectureFinding(id="F3", severity="warning",
                                title="Unknown C", description="", category="x"),
            ArchitectureFinding(id="F4", severity="info",
                                title="Unknown D", description="", category="x"),
        ]
        # 100 - 15 - 10 - 5 - 2 = 68
        assert _compute_score(findings) == 68
