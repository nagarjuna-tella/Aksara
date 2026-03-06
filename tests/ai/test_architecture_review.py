"""
v0.5.34 — AI Architecture Review: core pipeline tests.

Tests cover:
    - run_architecture_review() — full pipeline with mocked graph
    - ArchitectureReport / ArchitectureFinding / ArchitectureSuggestion / ArchitectureMetrics
    - Metric computation
    - Score computation and grade mapping
    - Finding detection: coupling, schema, API, migration, performance
    - Suggestion generation
    - Edge cases: empty graph, no findings, graph failure
    - Safety: review never modifies code or DB
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import asdict

from aksara.ai.architecture_review import (
    run_architecture_review,
    ArchitectureReport,
    ArchitectureFinding,
    ArchitectureSuggestion,
    ArchitectureMetrics,
    _compute_metrics,
    _detect_coupling,
    _detect_schema_issues,
    _detect_api_issues,
    _detect_migration_risks,
    _detect_performance_risks,
    _compute_score,
    _generate_suggestions,
    _score_to_grade,
    _reset_counters,
    _elapsed,
)


# ═══════════════════════════════════════════════════════════════════════════
# Fake graph helpers
# ═══════════════════════════════════════════════════════════════════════════

def _make_model(name="User", fields=None, relations=None, indexes=None):
    m = MagicMock()
    m.name = name
    m.table = name.lower() + "s"
    m.fields = fields or ["id", "name", "email"]
    m.relations = relations or []
    m.indexes = indexes or []
    m.tags = []
    return m


def _make_route(method="GET", path="/api/users", models=None, queries=None):
    r = MagicMock()
    r.method = method
    r.path = path
    r.name = f"{method.lower()}_{path.replace('/', '_')}"
    r.handler = "handler"
    r.models = models or []
    r.queries = queries or []
    r.diagnostics = []
    return r


def _make_migration(name="0001_initial", app="core", models=None):
    m = MagicMock()
    m.name = name
    m.app = app
    m.operations = ["CreateModel"]
    m.models = models or []
    return m


def _make_diagnostic(code="DIAG_001", severity="warning", message="Some issue",
                     related_models=None, related_routes=None, related_queries=None):
    d = MagicMock()
    d.code = code
    d.severity = severity
    d.message = message
    d.related_models = related_models or []
    d.related_routes = related_routes or []
    d.related_queries = related_queries or []
    return d


def _make_query(name="q1", sql="SELECT * FROM users"):
    q = MagicMock()
    q.name = name
    q.sql = sql
    q.models = []
    q.indexes_used = []
    q.diagnostics = []
    return q


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
    g.metadata = MagicMock()
    g.metadata.version = "0.5.34"
    g.metadata.model_count = len(g.models)
    g.metadata.route_count = len(g.routes)
    return g


# ═══════════════════════════════════════════════════════════════════════════
# Data Model Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestArchitectureMetrics:
    def test_defaults(self):
        m = ArchitectureMetrics()
        assert m.model_count == 0
        assert m.route_count == 0
        assert m.coupling_score == 0.0

    def test_to_dict(self):
        m = ArchitectureMetrics(model_count=5, route_count=10)
        d = m.to_dict()
        assert d["model_count"] == 5
        assert d["route_count"] == 10

    def test_all_fields(self):
        m = ArchitectureMetrics(
            model_count=5, route_count=10, query_count=20,
            migration_count=3, diagnostic_count=2,
            avg_models_per_route=2.5, avg_queries_per_route=4.0,
            coupling_score=0.45,
        )
        assert m.avg_models_per_route == 2.5
        assert m.coupling_score == 0.45


class TestArchitectureFinding:
    def test_defaults(self):
        f = ArchitectureFinding(id="F1", severity="warning", title="Test", description="Desc")
        assert f.category == "general"
        assert f.related_nodes == []

    def test_to_dict(self):
        f = ArchitectureFinding(id="F1", severity="error", title="T", description="D",
                                related_nodes=["User"], category="coupling")
        d = f.to_dict()
        assert d["id"] == "F1"
        assert d["category"] == "coupling"
        assert "User" in d["related_nodes"]

    def test_severity_values(self):
        for sev in ("critical", "error", "warning", "info"):
            f = ArchitectureFinding(id="X", severity=sev, title="T", description="D")
            assert f.severity == sev

    def test_category_values(self):
        for cat in ("coupling", "complexity", "performance", "schema_design",
                     "api_design", "migration_risk", "security"):
            f = ArchitectureFinding(id="X", severity="info", title="T",
                                    description="D", category=cat)
            assert f.category == cat


class TestArchitectureSuggestion:
    def test_defaults(self):
        s = ArchitectureSuggestion(suggestion_id="S1", title="T", description="D")
        assert s.impact == "medium"
        assert s.related_findings == []

    def test_to_dict(self):
        s = ArchitectureSuggestion(suggestion_id="S1", title="Add index",
                                   description="Add index on users.email",
                                   impact="high", related_findings=["F1"])
        d = s.to_dict()
        assert d["impact"] == "high"
        assert "F1" in d["related_findings"]


class TestArchitectureReport:
    def test_defaults(self):
        r = ArchitectureReport()
        assert r.score == 100
        assert r.grade == "A"
        assert r.ok is True
        assert r.findings == []
        assert r.suggestions == []

    def test_finding_count(self):
        r = ArchitectureReport(findings=[
            ArchitectureFinding(id="F1", severity="warning", title="T", description="D"),
            ArchitectureFinding(id="F2", severity="error", title="T2", description="D2"),
        ])
        assert r.finding_count == 2

    def test_suggestion_count(self):
        r = ArchitectureReport(suggestions=[
            ArchitectureSuggestion(suggestion_id="S1", title="T", description="D"),
        ])
        assert r.suggestion_count == 1

    def test_to_dict(self):
        r = ArchitectureReport(score=85, grade="B")
        d = r.to_dict()
        assert d["score"] == 85
        assert d["grade"] == "B"
        assert "finding_count" in d
        assert "suggestion_count" in d

    def test_to_summary_dict(self):
        r = ArchitectureReport(score=72, grade="C")
        s = r.to_summary_dict()
        assert s["score"] == 72
        assert s["grade"] == "C"
        assert "top_findings" in s
        assert "top_suggestions" in s
        assert "metrics" in s

    def test_to_dict_includes_metrics(self):
        r = ArchitectureReport(metrics=ArchitectureMetrics(model_count=5))
        d = r.to_dict()
        assert d["metrics"]["model_count"] == 5


# ═══════════════════════════════════════════════════════════════════════════
# Grade Mapping
# ═══════════════════════════════════════════════════════════════════════════


class TestGradeMapping:
    def test_grade_a(self):
        assert _score_to_grade(100) == "A"
        assert _score_to_grade(95) == "A"
        assert _score_to_grade(90) == "A"

    def test_grade_b(self):
        assert _score_to_grade(89) == "B"
        assert _score_to_grade(85) == "B"
        assert _score_to_grade(80) == "B"

    def test_grade_c(self):
        assert _score_to_grade(79) == "C"
        assert _score_to_grade(75) == "C"
        assert _score_to_grade(70) == "C"

    def test_grade_d(self):
        assert _score_to_grade(69) == "D"
        assert _score_to_grade(65) == "D"
        assert _score_to_grade(60) == "D"

    def test_grade_f(self):
        assert _score_to_grade(59) == "F"
        assert _score_to_grade(30) == "F"
        assert _score_to_grade(0) == "F"


# ═══════════════════════════════════════════════════════════════════════════
# Metric Computation
# ═══════════════════════════════════════════════════════════════════════════


class TestComputeMetrics:
    def test_empty_graph(self):
        g = _make_graph()
        m = _compute_metrics(g)
        assert m.model_count == 0
        assert m.route_count == 0
        assert m.avg_models_per_route == 0.0
        assert m.avg_queries_per_route == 0.0
        assert m.coupling_score == 0.0

    def test_counts(self):
        g = _make_graph(
            models=[_make_model("A"), _make_model("B")],
            routes=[_make_route()],
            queries=[_make_query(), _make_query("q2")],
            migrations=[_make_migration()],
            diagnostics=[_make_diagnostic()],
        )
        m = _compute_metrics(g)
        assert m.model_count == 2
        assert m.route_count == 1
        assert m.query_count == 2
        assert m.migration_count == 1
        assert m.diagnostic_count == 1

    def test_avg_models_per_route(self):
        routes = [
            _make_route(path="/a", models=["User", "Order"]),
            _make_route(path="/b", models=["Product"]),
        ]
        g = _make_graph(routes=routes)
        m = _compute_metrics(g)
        assert m.avg_models_per_route == 1.5

    def test_avg_queries_per_route(self):
        routes = [
            _make_route(path="/a", queries=["q1", "q2", "q3"]),
            _make_route(path="/b", queries=["q4"]),
        ]
        g = _make_graph(routes=routes)
        m = _compute_metrics(g)
        assert m.avg_queries_per_route == 2.0

    def test_coupling_score_capped_at_one(self):
        routes = [_make_route(path="/a", models=list(range(20)), queries=list(range(40)))]
        g = _make_graph(routes=routes)
        m = _compute_metrics(g)
        assert m.coupling_score <= 1.0


# ═══════════════════════════════════════════════════════════════════════════
# Coupling Detection
# ═══════════════════════════════════════════════════════════════════════════


class TestDetectCoupling:
    def setup_method(self):
        _reset_counters()

    def test_no_coupling_issues(self):
        routes = [_make_route(models=["User"])]
        g = _make_graph(routes=routes)
        m = _compute_metrics(g)
        findings = _detect_coupling(g, m)
        assert len(findings) == 0

    def test_high_model_coupling(self):
        routes = [_make_route(models=["A", "B", "C", "D"])]
        g = _make_graph(routes=routes)
        m = _compute_metrics(g)
        findings = _detect_coupling(g, m)
        coupling = [f for f in findings if "route-to-model" in f.title.lower()]
        assert len(coupling) == 1
        assert coupling[0].category == "coupling"

    def test_excessive_queries(self):
        routes = [_make_route(queries=["q1", "q2", "q3", "q4", "q5", "q6"])]
        g = _make_graph(routes=routes)
        m = _compute_metrics(g)
        findings = _detect_coupling(g, m)
        query_f = [f for f in findings if "excessive" in f.title.lower()]
        assert len(query_f) == 1

    def test_model_hotspot(self):
        routes = [_make_route(path=f"/r{i}", models=["User"]) for i in range(11)]
        g = _make_graph(routes=routes)
        m = _compute_metrics(g)
        findings = _detect_coupling(g, m)
        hotspot = [f for f in findings if "hotspot" in f.title.lower()]
        assert len(hotspot) == 1
        assert "User" in hotspot[0].description

    def test_three_models_no_finding(self):
        """Exactly 3 models — should NOT trigger."""
        routes = [_make_route(models=["A", "B", "C"])]
        g = _make_graph(routes=routes)
        m = _compute_metrics(g)
        findings = _detect_coupling(g, m)
        coupling = [f for f in findings if "route-to-model" in f.title.lower()]
        assert len(coupling) == 0

    def test_five_queries_no_finding(self):
        """Exactly 5 queries — should NOT trigger."""
        routes = [_make_route(queries=["q1", "q2", "q3", "q4", "q5"])]
        g = _make_graph(routes=routes)
        m = _compute_metrics(g)
        findings = _detect_coupling(g, m)
        query_f = [f for f in findings if "excessive" in f.title.lower()]
        assert len(query_f) == 0

    def test_ten_routes_no_hotspot(self):
        """Exactly 10 routes — should NOT trigger."""
        routes = [_make_route(path=f"/r{i}", models=["User"]) for i in range(10)]
        g = _make_graph(routes=routes)
        m = _compute_metrics(g)
        findings = _detect_coupling(g, m)
        hotspot = [f for f in findings if "hotspot" in f.title.lower()]
        assert len(hotspot) == 0


# ═══════════════════════════════════════════════════════════════════════════
# Schema Design Issues
# ═══════════════════════════════════════════════════════════════════════════


class TestDetectSchemaIssues:
    def setup_method(self):
        _reset_counters()

    def test_no_schema_issues(self):
        g = _make_graph(models=[_make_model(fields=["id", "name"])])
        findings = _detect_schema_issues(g)
        assert len(findings) == 0

    def test_large_model(self):
        fields = [f"field_{i}" for i in range(21)]
        g = _make_graph(models=[_make_model("BigModel", fields=fields)])
        findings = _detect_schema_issues(g)
        large = [f for f in findings if "overloaded" in f.title.lower()]
        assert len(large) == 1
        assert large[0].category == "schema_design"

    def test_many_relations(self):
        rels = [f"rel_{i}" for i in range(9)]
        g = _make_graph(models=[_make_model("RelModel", relations=rels)])
        findings = _detect_schema_issues(g)
        rel_f = [f for f in findings if "relational" in f.title.lower()]
        assert len(rel_f) == 1

    def test_missing_index_diagnostic(self):
        diag = _make_diagnostic(code="IDX_001", message="Missing index on users.email")
        g = _make_graph(diagnostics=[diag])
        findings = _detect_schema_issues(g)
        idx = [f for f in findings if "index" in f.title.lower()]
        assert len(idx) == 1
        assert idx[0].severity == "error"

    def test_twenty_fields_no_large(self):
        """Exactly 20 fields — should NOT trigger."""
        fields = [f"f{i}" for i in range(20)]
        g = _make_graph(models=[_make_model(fields=fields)])
        findings = _detect_schema_issues(g)
        large = [f for f in findings if "overloaded" in f.title.lower()]
        assert len(large) == 0

    def test_eight_relations_no_finding(self):
        """Exactly 8 relations — should NOT trigger."""
        rels = [f"r{i}" for i in range(8)]
        g = _make_graph(models=[_make_model(relations=rels)])
        findings = _detect_schema_issues(g)
        rel_f = [f for f in findings if "relational" in f.title.lower()]
        assert len(rel_f) == 0


# ═══════════════════════════════════════════════════════════════════════════
# API Design Issues
# ═══════════════════════════════════════════════════════════════════════════


class TestDetectApiIssues:
    def setup_method(self):
        _reset_counters()

    def test_no_api_issues(self):
        routes = [_make_route(path="/api/users")]
        g = _make_graph(routes=routes)
        findings = _detect_api_issues(g)
        assert len(findings) == 0

    def test_route_explosion(self):
        routes = [_make_route(path=f"/r{i}") for i in range(101)]
        g = _make_graph(routes=routes)
        findings = _detect_api_issues(g)
        explosion = [f for f in findings if "large" in f.title.lower()]
        assert len(explosion) == 1
        assert explosion[0].category == "api_design"

    def test_deep_nesting(self):
        routes = [_make_route(path="/api/v1/users/orders/history/payments")]
        g = _make_graph(routes=routes)
        findings = _detect_api_issues(g)
        deep = [f for f in findings if "nesting" in f.title.lower()]
        assert len(deep) == 1

    def test_four_segments_no_finding(self):
        """Exactly 4 segments — should NOT trigger."""
        routes = [_make_route(path="/api/v1/users/list")]
        g = _make_graph(routes=routes)
        findings = _detect_api_issues(g)
        deep = [f for f in findings if "nesting" in f.title.lower()]
        assert len(deep) == 0

    def test_hundred_routes_no_explosion(self):
        """Exactly 100 routes — should NOT trigger."""
        routes = [_make_route(path=f"/r{i}") for i in range(100)]
        g = _make_graph(routes=routes)
        findings = _detect_api_issues(g)
        explosion = [f for f in findings if "large" in f.title.lower()]
        assert len(explosion) == 0


# ═══════════════════════════════════════════════════════════════════════════
# Migration Risks
# ═══════════════════════════════════════════════════════════════════════════


class TestDetectMigrationRisks:
    def setup_method(self):
        _reset_counters()

    def test_no_migration_risks(self):
        g = _make_graph(migrations=[_make_migration(models=["User"])])
        findings = _detect_migration_risks(g)
        assert len(findings) == 0

    def test_migration_churn(self):
        migs = [_make_migration(name=f"m{i}", models=["Order"]) for i in range(11)]
        g = _make_graph(migrations=migs)
        findings = _detect_migration_risks(g)
        churn = [f for f in findings if "churn" in f.title.lower()]
        assert len(churn) == 1
        assert "Order" in churn[0].description

    def test_recent_migration_event(self):
        events = [{"kind": "migration", "message": "Applied 0005_add_email", "severity": "info"}]
        g = _make_graph(events=events)
        findings = _detect_migration_risks(g)
        recent = [f for f in findings if "recent" in f.title.lower()]
        assert len(recent) == 1

    def test_ten_migrations_no_churn(self):
        """Exactly 10 migrations for one model — should NOT trigger."""
        migs = [_make_migration(name=f"m{i}", models=["User"]) for i in range(10)]
        g = _make_graph(migrations=migs)
        findings = _detect_migration_risks(g)
        churn = [f for f in findings if "churn" in f.title.lower()]
        assert len(churn) == 0


# ═══════════════════════════════════════════════════════════════════════════
# Performance Risks
# ═══════════════════════════════════════════════════════════════════════════


class TestDetectPerformanceRisks:
    def setup_method(self):
        _reset_counters()

    def test_no_perf_risks(self):
        g = _make_graph()
        findings = _detect_performance_risks(g)
        assert len(findings) == 0

    def test_slow_query_event(self):
        events = [{"kind": "slow_query", "message": "SELECT * FROM users took 5s", "severity": "warning"}]
        g = _make_graph(events=events)
        findings = _detect_performance_risks(g)
        slow = [f for f in findings if "slow" in f.title.lower()]
        assert len(slow) == 1
        assert slow[0].category == "performance"

    def test_perf_diagnostic(self):
        diag = _make_diagnostic(message="N+1 query pattern detected in /api/orders")
        g = _make_graph(diagnostics=[diag])
        findings = _detect_performance_risks(g)
        perf = [f for f in findings if "performance diagnostics" in f.title.lower()]
        assert len(perf) == 1

    def test_security_diagnostic(self):
        diag = _make_diagnostic(message="Security: CSRF protection missing on POST /api/users")
        g = _make_graph(diagnostics=[diag])
        findings = _detect_performance_risks(g)
        sec = [f for f in findings if "security" in f.title.lower()]
        assert len(sec) == 1
        assert sec[0].category == "security"

    def test_slow_message_event(self):
        events = [{"kind": "query", "message": "slow response from database", "severity": "warning"}]
        g = _make_graph(events=events)
        findings = _detect_performance_risks(g)
        slow = [f for f in findings if "slow" in f.title.lower()]
        assert len(slow) == 1


# ═══════════════════════════════════════════════════════════════════════════
# Score Computation
# ═══════════════════════════════════════════════════════════════════════════


class TestComputeScore:
    def setup_method(self):
        _reset_counters()

    def test_no_findings_full_score(self):
        assert _compute_score([]) == 100

    def test_high_coupling_penalty(self):
        f = ArchitectureFinding(id="F1", severity="warning",
                                title="High route-to-model coupling",
                                description="", category="coupling")
        assert _compute_score([f]) == 90  # 100 - 10

    def test_missing_index_penalty(self):
        f = ArchitectureFinding(id="F1", severity="error",
                                title="Schema lacks indexes on frequently queried columns",
                                description="", category="schema_design")
        assert _compute_score([f]) == 90  # 100 - 10

    def test_slow_query_penalty(self):
        f = ArchitectureFinding(id="F1", severity="error",
                                title="Slow query events detected",
                                description="", category="performance")
        assert _compute_score([f]) == 85  # 100 - 15

    def test_multiple_penalties_stack(self):
        findings = [
            ArchitectureFinding(id="F1", severity="warning",
                                title="High route-to-model coupling",
                                description="", category="coupling"),
            ArchitectureFinding(id="F2", severity="error",
                                title="Schema lacks indexes on frequently queried columns",
                                description="", category="schema_design"),
        ]
        assert _compute_score(findings) == 80  # 100 - 10 - 10

    def test_score_clamped_at_zero(self):
        findings = [
            ArchitectureFinding(id=f"F{i}", severity="error",
                                title="Slow query events detected",
                                description="", category="performance")
            for i in range(10)
        ]
        assert _compute_score(findings) == 0

    def test_unknown_finding_default_penalty(self):
        f = ArchitectureFinding(id="F1", severity="error",
                                title="Something unknown",
                                description="", category="unknown")
        assert _compute_score([f]) == 90  # error default = -10

    def test_info_default_penalty(self):
        f = ArchitectureFinding(id="F1", severity="info",
                                title="Something",
                                description="", category="unknown")
        assert _compute_score([f]) == 98  # info default = -2


# ═══════════════════════════════════════════════════════════════════════════
# Suggestion Generation
# ═══════════════════════════════════════════════════════════════════════════


class TestGenerateSuggestions:
    def setup_method(self):
        _reset_counters()

    def test_no_findings_no_suggestions(self):
        m = ArchitectureMetrics()
        suggestions = _generate_suggestions([], m)
        assert len(suggestions) == 0

    def test_coupling_suggestion(self):
        f = ArchitectureFinding(id="F1", severity="warning",
                                title="High route-to-model coupling",
                                description="", category="coupling")
        suggestions = _generate_suggestions([f], ArchitectureMetrics())
        assert len(suggestions) >= 1
        assert any("service layer" in s.title.lower() for s in suggestions)

    def test_index_suggestion(self):
        f = ArchitectureFinding(id="F1", severity="error",
                                title="Schema lacks indexes on frequently queried columns",
                                description="", category="schema_design")
        suggestions = _generate_suggestions([f], ArchitectureMetrics())
        assert any("index" in s.title.lower() for s in suggestions)

    def test_large_model_suggestion(self):
        f = ArchitectureFinding(id="F1", severity="warning",
                                title="Model may be overloaded",
                                description="", category="schema_design")
        suggestions = _generate_suggestions([f], ArchitectureMetrics())
        assert any("split" in s.title.lower() for s in suggestions)

    def test_suggestions_sorted_by_impact(self):
        findings = [
            ArchitectureFinding(id="F1", severity="info",
                                title="Deep route nesting",
                                description="", category="api_design"),
            ArchitectureFinding(id="F2", severity="error",
                                title="Schema lacks indexes on frequently queried columns",
                                description="", category="schema_design"),
        ]
        suggestions = _generate_suggestions(findings, ArchitectureMetrics())
        if len(suggestions) >= 2:
            impact_order = {"high": 0, "medium": 1, "low": 2}
            for i in range(len(suggestions) - 1):
                assert impact_order[suggestions[i].impact] <= impact_order[suggestions[i + 1].impact]

    def test_deduplicated_suggestions(self):
        findings = [
            ArchitectureFinding(id="F1", severity="warning",
                                title="High route-to-model coupling",
                                description="Route A", category="coupling"),
            ArchitectureFinding(id="F2", severity="warning",
                                title="High route-to-model coupling",
                                description="Route B", category="coupling"),
        ]
        suggestions = _generate_suggestions(findings, ArchitectureMetrics())
        titles = [s.title for s in suggestions]
        assert len(titles) == len(set(titles)), "Suggestions should be deduplicated"

    def test_security_suggestion(self):
        f = ArchitectureFinding(id="F1", severity="error",
                                title="Security concerns detected",
                                description="", category="security")
        suggestions = _generate_suggestions([f], ArchitectureMetrics())
        assert any("security" in s.title.lower() for s in suggestions)

    def test_migration_churn_suggestion(self):
        f = ArchitectureFinding(id="F1", severity="warning",
                                title="Frequent schema churn",
                                description="", category="migration_risk")
        suggestions = _generate_suggestions([f], ArchitectureMetrics())
        assert any("stabilis" in s.title.lower() or "schema" in s.title.lower()
                    for s in suggestions)

    def test_excessive_queries_suggestion(self):
        f = ArchitectureFinding(id="F1", severity="warning",
                                title="Route performing excessive database work",
                                description="", category="coupling")
        suggestions = _generate_suggestions([f], ArchitectureMetrics())
        assert any("optim" in s.title.lower() or "query" in s.title.lower()
                    for s in suggestions)


# ═══════════════════════════════════════════════════════════════════════════
# Full Pipeline (run_architecture_review)
# ═══════════════════════════════════════════════════════════════════════════


class TestRunArchitectureReview:
    @patch("aksara.ai.project_graph.build_project_graph")
    def test_full_pipeline_ok(self, mock_graph):
        mock_graph.return_value = _make_graph(
            models=[_make_model()],
            routes=[_make_route()],
        )
        report = run_architecture_review()
        assert report.ok is True
        assert 0 <= report.score <= 100
        assert report.grade in ("A", "B", "C", "D", "F")
        assert report.generated_at != ""
        assert report.elapsed_ms >= 0

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_empty_graph_perfect_score(self, mock_graph):
        mock_graph.return_value = _make_graph()
        report = run_architecture_review()
        assert report.ok is True
        assert report.score == 100
        assert report.grade == "A"
        assert report.finding_count == 0

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_graph_failure(self, mock_graph):
        mock_graph.side_effect = RuntimeError("no graph")
        report = run_architecture_review()
        assert report.ok is False
        assert report.score == 0
        assert report.grade == "F"

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_coupling_detected(self, mock_graph):
        routes = [_make_route(models=["A", "B", "C", "D"])]
        mock_graph.return_value = _make_graph(routes=routes)
        report = run_architecture_review()
        assert report.ok is True
        coupling = [f for f in report.findings if f.category == "coupling"]
        assert len(coupling) >= 1

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_schema_issues_detected(self, mock_graph):
        fields = [f"f{i}" for i in range(25)]
        mock_graph.return_value = _make_graph(models=[_make_model("Big", fields=fields)])
        report = run_architecture_review()
        schema = [f for f in report.findings if f.category == "schema_design"]
        assert len(schema) >= 1

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_suggestions_generated(self, mock_graph):
        routes = [_make_route(models=["A", "B", "C", "D"])]
        mock_graph.return_value = _make_graph(routes=routes)
        report = run_architecture_review()
        assert report.suggestion_count >= 1

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_to_dict_from_full_pipeline(self, mock_graph):
        mock_graph.return_value = _make_graph()
        report = run_architecture_review()
        d = report.to_dict()
        assert "score" in d
        assert "grade" in d
        assert "findings" in d
        assert "metrics" in d

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_to_summary_dict_from_full_pipeline(self, mock_graph):
        mock_graph.return_value = _make_graph()
        report = run_architecture_review()
        s = report.to_summary_dict()
        assert "score" in s
        assert "top_findings" in s
        assert "top_suggestions" in s

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_app_param_forwarded(self, mock_graph):
        mock_graph.return_value = _make_graph()
        app = MagicMock()
        run_architecture_review(app=app)
        mock_graph.assert_called_once_with(app=app)


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


class TestHelpers:
    def test_elapsed(self):
        import time
        t0 = time.monotonic()
        time.sleep(0.001)
        ms = _elapsed(t0)
        assert ms >= 0

    def test_reset_counters(self):
        _reset_counters()
        from aksara.ai.architecture_review import _FINDING_COUNTER, _SUGGESTION_COUNTER
        assert _FINDING_COUNTER == 0
        assert _SUGGESTION_COUNTER == 0
