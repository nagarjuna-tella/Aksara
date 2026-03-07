"""
v0.5.35 — AI Performance Analyzer: core pipeline tests.

Tests cover:
    - PerformanceReport / PerformanceIssue / PerformanceRecommendation / PerformanceMetrics
    - Grade mapping (_score_to_grade)
    - Metric computation (_compute_metrics)
    - Slow query detection (_detect_slow_queries)
    - N+1 detection (_detect_n_plus_one)
    - Query explosion detection (_detect_query_explosions)
    - Missing index detection (_detect_missing_indexes)
    - Heavy join detection (_detect_heavy_joins)
    - Route hotspot detection (_detect_route_hotspots)
    - Score computation (_compute_score)
    - Recommendation generation (_generate_recommendations)
    - Query helpers (_normalise_query, _count_joins)
    - Full pipeline (run_performance_analysis)
    - Safety: never modifies code or DB
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import asdict

from aksara.ai.performance_analyzer import (
    run_performance_analysis,
    PerformanceReport,
    PerformanceIssue,
    PerformanceRecommendation,
    PerformanceMetrics,
    _collect_query_data,
    _detect_slow_queries,
    _detect_n_plus_one,
    _detect_query_explosions,
    _detect_missing_indexes,
    _detect_heavy_joins,
    _detect_route_hotspots,
    _compute_metrics,
    _compute_score,
    _generate_recommendations,
    _score_to_grade,
    _normalise_query,
    _count_joins,
    _reset_counters,
    _elapsed,
    _QueryRecord,
)


# ═══════════════════════════════════════════════════════════════════════════
# Fake graph helpers
# ═══════════════════════════════════════════════════════════════════════════


def _make_query(sql="SELECT * FROM users", execution_time_ms=10.0,
                route="", model=""):
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
    r.name = f"{method.lower()}_{path.replace('/', '_')}"
    r.handler = "handler"
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
# Data Model Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestPerformanceMetrics:
    def test_defaults(self):
        m = PerformanceMetrics()
        assert m.total_routes == 0
        assert m.total_queries == 0
        assert m.slow_queries == 0
        assert m.n_plus_one_candidates == 0
        assert m.missing_indexes == 0
        assert m.avg_queries_per_route == 0.0
        assert m.max_queries_route is None

    def test_to_dict(self):
        m = PerformanceMetrics(total_routes=5, total_queries=20)
        d = m.to_dict()
        assert d["total_routes"] == 5
        assert d["total_queries"] == 20

    def test_all_fields(self):
        m = PerformanceMetrics(
            total_routes=5, total_queries=20, slow_queries=3,
            n_plus_one_candidates=2, missing_indexes=1,
            avg_queries_per_route=4.0, max_queries_route="/api/orders",
        )
        assert m.avg_queries_per_route == 4.0
        assert m.max_queries_route == "/api/orders"


class TestPerformanceIssue:
    def test_defaults(self):
        i = PerformanceIssue(
            issue_id="PERF-0001", severity="medium",
            title="Test", description="Desc",
        )
        assert i.category == "slow_query"
        assert i.route is None
        assert i.model is None
        assert i.query is None

    def test_to_dict(self):
        i = PerformanceIssue(
            issue_id="PERF-0001", severity="high",
            title="Slow query", description="Desc",
            route="/api/users", category="slow_query",
        )
        d = i.to_dict()
        assert d["issue_id"] == "PERF-0001"
        assert d["category"] == "slow_query"
        assert d["route"] == "/api/users"

    def test_severity_values(self):
        for sev in ("critical", "high", "medium", "low"):
            i = PerformanceIssue(
                issue_id="X", severity=sev, title="T", description="D",
            )
            assert i.severity == sev

    def test_category_values(self):
        for cat in ("slow_query", "n_plus_one", "missing_index",
                     "query_explosion", "heavy_join", "route_hotspot",
                     "large_payload"):
            i = PerformanceIssue(
                issue_id="X", severity="medium", title="T",
                description="D", category=cat,
            )
            assert i.category == cat


class TestPerformanceRecommendation:
    def test_defaults(self):
        r = PerformanceRecommendation(
            recommendation_id="REC-0001", title="T", description="D",
        )
        assert r.impact == "medium"
        assert r.related_issue_ids == []

    def test_to_dict(self):
        r = PerformanceRecommendation(
            recommendation_id="REC-0001", title="Add index",
            description="Add index on email",
            impact="high", related_issue_ids=["PERF-0001"],
        )
        d = r.to_dict()
        assert d["impact"] == "high"
        assert "PERF-0001" in d["related_issue_ids"]


class TestPerformanceReport:
    def test_defaults(self):
        r = PerformanceReport()
        assert r.score == 100
        assert r.grade == "A"
        assert r.ok is True
        assert r.issues == []
        assert r.recommendations == []

    def test_issue_count(self):
        r = PerformanceReport(issues=[
            PerformanceIssue(issue_id="P1", severity="medium",
                             title="T", description="D"),
            PerformanceIssue(issue_id="P2", severity="high",
                             title="T2", description="D2"),
        ])
        assert r.issue_count == 2

    def test_recommendation_count(self):
        r = PerformanceReport(recommendations=[
            PerformanceRecommendation(
                recommendation_id="R1", title="T", description="D"),
        ])
        assert r.recommendation_count == 1

    def test_to_dict(self):
        r = PerformanceReport(score=85, grade="B")
        d = r.to_dict()
        assert d["score"] == 85
        assert d["grade"] == "B"
        assert "issue_count" in d
        assert "recommendation_count" in d
        assert "metrics" in d

    def test_to_summary_dict(self):
        r = PerformanceReport(score=72, grade="C")
        s = r.to_summary_dict()
        assert s["score"] == 72
        assert s["grade"] == "C"
        assert "top_issues" in s
        assert "top_recommendations" in s
        assert "metrics" in s

    def test_to_dict_includes_metrics(self):
        r = PerformanceReport(metrics=PerformanceMetrics(total_routes=5))
        d = r.to_dict()
        assert d["metrics"]["total_routes"] == 5

    def test_ok_false_on_low_score(self):
        r = PerformanceReport(score=40, grade="F", ok=False)
        assert r.ok is False


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
# Query Helpers
# ═══════════════════════════════════════════════════════════════════════════


class TestNormaliseQuery:
    def test_simple(self):
        result = _normalise_query("SELECT * FROM users WHERE id = 42")
        assert "42" not in result
        assert "?" in result

    def test_string_params(self):
        result = _normalise_query("SELECT * FROM users WHERE name = 'Alice'")
        assert "Alice" not in result
        assert "?" in result

    def test_no_params(self):
        result = _normalise_query("SELECT * FROM users")
        assert "SELECT" in result.upper()

    def test_empty(self):
        assert _normalise_query("") == ""

    def test_multiple_params(self):
        result = _normalise_query("SELECT * FROM t WHERE a = 1 AND b = 'x'")
        assert result.count("?") >= 2


class TestCountJoins:
    def test_no_joins(self):
        assert _count_joins("SELECT * FROM users") == 0

    def test_single_join(self):
        assert _count_joins("SELECT * FROM users JOIN orders ON users.id = orders.user_id") == 1

    def test_multiple_joins(self):
        sql = (
            "SELECT * FROM users "
            "JOIN orders ON users.id = orders.user_id "
            "LEFT JOIN payments ON orders.id = payments.order_id "
            "INNER JOIN items ON orders.id = items.order_id "
            "JOIN categories ON items.cat_id = categories.id"
        )
        assert _count_joins(sql) == 4

    def test_case_insensitive(self):
        assert _count_joins("select * from users join orders on 1=1") == 1

    def test_empty(self):
        assert _count_joins("") == 0


# ═══════════════════════════════════════════════════════════════════════════
# Collect Query Data
# ═══════════════════════════════════════════════════════════════════════════


class TestCollectQueryData:
    def test_empty_graph(self):
        g = _make_graph()
        data = _collect_query_data(g)
        assert data == []

    def test_from_graph_queries(self):
        q = _make_query(sql="SELECT 1", execution_time_ms=50.0, route="/api/test")
        g = _make_graph(queries=[q])
        data = _collect_query_data(g)
        assert len(data) == 1
        assert data[0].sql == "SELECT 1"
        assert data[0].execution_time_ms == 50.0

    def test_from_events(self):
        events = [{"kind": "slow_query", "message": "SELECT * FROM big_table",
                    "duration_ms": 500.0, "route": "/api/big"}]
        g = _make_graph(events=events)
        data = _collect_query_data(g)
        assert len(data) == 1
        assert data[0].execution_time_ms == 500.0

    def test_mixed_sources(self):
        q = _make_query()
        events = [{"kind": "query", "message": "SELECT 2", "duration_ms": 10.0, "route": ""}]
        g = _make_graph(queries=[q], events=events)
        data = _collect_query_data(g)
        assert len(data) == 2


# ═══════════════════════════════════════════════════════════════════════════
# Detect Slow Queries
# ═══════════════════════════════════════════════════════════════════════════


class TestDetectSlowQueries:
    def setup_method(self):
        _reset_counters()

    def test_no_slow_queries(self):
        qr = [_QueryRecord(sql="SELECT 1", route="/", execution_time_ms=50.0, model="")]
        g = _make_graph()
        issues = _detect_slow_queries(qr, g)
        assert len(issues) == 0

    def test_slow_query_above_threshold(self):
        qr = [_QueryRecord(sql="SELECT * FROM big", route="/api/big",
                            execution_time_ms=300.0, model="Big")]
        g = _make_graph()
        issues = _detect_slow_queries(qr, g)
        assert len(issues) == 1
        assert issues[0].category == "slow_query"
        assert issues[0].severity == "medium"

    def test_exactly_200ms_not_slow(self):
        qr = [_QueryRecord(sql="SELECT 1", route="/", execution_time_ms=200.0, model="")]
        g = _make_graph()
        issues = _detect_slow_queries(qr, g)
        assert len(issues) == 0

    def test_201ms_is_slow(self):
        qr = [_QueryRecord(sql="SELECT 1", route="/", execution_time_ms=201.0, model="")]
        g = _make_graph()
        issues = _detect_slow_queries(qr, g)
        assert len(issues) == 1

    def test_diagnostic_slow_query(self):
        diag = _make_diagnostic(message="Slow query detected in /api/users")
        g = _make_graph(diagnostics=[diag])
        issues = _detect_slow_queries([], g)
        assert len(issues) == 1
        assert issues[0].category == "slow_query"

    def test_route_and_model_captured(self):
        qr = [_QueryRecord(sql="SELECT *", route="/api/users",
                            execution_time_ms=500.0, model="User")]
        g = _make_graph()
        issues = _detect_slow_queries(qr, g)
        assert issues[0].route == "/api/users"
        assert issues[0].model == "User"


# ═══════════════════════════════════════════════════════════════════════════
# Detect N+1 Patterns
# ═══════════════════════════════════════════════════════════════════════════


class TestDetectNPlusOne:
    def setup_method(self):
        _reset_counters()

    def test_no_n_plus_one(self):
        qr = [_QueryRecord(sql=f"SELECT * FROM t WHERE id = {i}",
                            route="/", execution_time_ms=5.0, model="")
               for i in range(3)]
        g = _make_graph()
        issues = _detect_n_plus_one(qr, g)
        assert len(issues) == 0

    def test_n_plus_one_above_threshold(self):
        qr = [_QueryRecord(sql=f"SELECT * FROM users WHERE id = {i}",
                            route="/api/users", execution_time_ms=5.0, model="User")
               for i in range(6)]
        g = _make_graph()
        issues = _detect_n_plus_one(qr, g)
        assert len(issues) >= 1
        assert issues[0].category == "n_plus_one"
        assert issues[0].severity == "high"

    def test_exactly_5_no_detection(self):
        qr = [_QueryRecord(sql=f"SELECT * FROM t WHERE id = {i}",
                            route="/", execution_time_ms=5.0, model="")
               for i in range(5)]
        g = _make_graph()
        issues = _detect_n_plus_one(qr, g)
        assert len(issues) == 0

    def test_different_routes_separate(self):
        """Same query on different routes should be grouped separately."""
        qr = [_QueryRecord(sql=f"SELECT * FROM t WHERE id = {i}",
                            route=f"/route{i % 2}", execution_time_ms=5.0, model="")
               for i in range(6)]
        g = _make_graph()
        issues = _detect_n_plus_one(qr, g)
        # Should not trigger since each route has only 3
        assert len(issues) == 0

    def test_diagnostic_n_plus_one(self):
        diag = _make_diagnostic(message="N+1 query pattern in /api/orders")
        g = _make_graph(diagnostics=[diag])
        issues = _detect_n_plus_one([], g)
        assert len(issues) == 1
        assert issues[0].category == "n_plus_one"

    def test_diagnostic_prefetch(self):
        diag = _make_diagnostic(message="Consider using prefetch for Order queries")
        g = _make_graph(diagnostics=[diag])
        issues = _detect_n_plus_one([], g)
        assert len(issues) == 1


# ═══════════════════════════════════════════════════════════════════════════
# Detect Query Explosions
# ═══════════════════════════════════════════════════════════════════════════


class TestDetectQueryExplosions:
    def setup_method(self):
        _reset_counters()

    def test_no_explosion(self):
        route = _make_route(queries=["q1", "q2", "q3"])
        g = _make_graph(routes=[route])
        issues = _detect_query_explosions(g)
        assert len(issues) == 0

    def test_explosion_above_threshold(self):
        queries = [f"q{i}" for i in range(11)]
        route = _make_route(queries=queries)
        g = _make_graph(routes=[route])
        issues = _detect_query_explosions(g)
        assert len(issues) == 1
        assert issues[0].category == "query_explosion"
        assert issues[0].severity == "high"

    def test_exactly_10_no_explosion(self):
        queries = [f"q{i}" for i in range(10)]
        route = _make_route(queries=queries)
        g = _make_graph(routes=[route])
        issues = _detect_query_explosions(g)
        assert len(issues) == 0

    def test_multiple_routes_some_explode(self):
        r1 = _make_route(path="/a", queries=[f"q{i}" for i in range(15)])
        r2 = _make_route(path="/b", queries=["q1"])
        g = _make_graph(routes=[r1, r2])
        issues = _detect_query_explosions(g)
        assert len(issues) == 1
        assert "/a" in issues[0].route

    def test_route_info_captured(self):
        queries = [f"q{i}" for i in range(12)]
        route = _make_route(method="POST", path="/api/orders", queries=queries)
        g = _make_graph(routes=[route])
        issues = _detect_query_explosions(g)
        assert "POST /api/orders" in issues[0].route


# ═══════════════════════════════════════════════════════════════════════════
# Detect Missing Indexes
# ═══════════════════════════════════════════════════════════════════════════


class TestDetectMissingIndexes:
    def setup_method(self):
        _reset_counters()

    def test_no_missing_indexes(self):
        g = _make_graph()
        issues = _detect_missing_indexes(g)
        assert len(issues) == 0

    def test_index_keyword_in_message(self):
        diag = _make_diagnostic(message="Missing index on users.email")
        g = _make_graph(diagnostics=[diag])
        issues = _detect_missing_indexes(g)
        assert len(issues) == 1
        assert issues[0].category == "missing_index"

    def test_table_scan_keyword(self):
        diag = _make_diagnostic(message="Full table scan on orders table")
        g = _make_graph(diagnostics=[diag])
        issues = _detect_missing_indexes(g)
        assert len(issues) == 1

    def test_seq_scan_keyword(self):
        diag = _make_diagnostic(message="Seq scan on users detected")
        g = _make_graph(diagnostics=[diag])
        issues = _detect_missing_indexes(g)
        assert len(issues) == 1

    def test_without_index_keyword(self):
        diag = _make_diagnostic(message="Query running without index on email")
        g = _make_graph(diagnostics=[diag])
        issues = _detect_missing_indexes(g)
        assert len(issues) == 1

    def test_index_in_code(self):
        diag = _make_diagnostic(code="INDEX_MISSING", message="Check columns")
        g = _make_graph(diagnostics=[diag])
        issues = _detect_missing_indexes(g)
        assert len(issues) == 1

    def test_model_captured(self):
        diag = _make_diagnostic(
            message="Missing index on users.email",
            related_models=["User"],
        )
        g = _make_graph(diagnostics=[diag])
        issues = _detect_missing_indexes(g)
        assert issues[0].model == "User"

    def test_unrelated_diagnostic_ignored(self):
        diag = _make_diagnostic(message="Authentication failed for API key")
        g = _make_graph(diagnostics=[diag])
        issues = _detect_missing_indexes(g)
        assert len(issues) == 0


# ═══════════════════════════════════════════════════════════════════════════
# Detect Heavy Joins
# ═══════════════════════════════════════════════════════════════════════════


class TestDetectHeavyJoins:
    def setup_method(self):
        _reset_counters()

    def test_no_heavy_joins(self):
        qr = [_QueryRecord(sql="SELECT * FROM users JOIN orders ON 1=1",
                            route="/", execution_time_ms=5.0, model="")]
        g = _make_graph()
        issues = _detect_heavy_joins(qr, g)
        assert len(issues) == 0

    def test_heavy_join_above_threshold(self):
        sql = (
            "SELECT * FROM a "
            "JOIN b ON 1=1 "
            "JOIN c ON 1=1 "
            "JOIN d ON 1=1 "
            "JOIN e ON 1=1"
        )
        qr = [_QueryRecord(sql=sql, route="/api/report",
                            execution_time_ms=5.0, model="Report")]
        g = _make_graph()
        issues = _detect_heavy_joins(qr, g)
        assert len(issues) == 1
        assert issues[0].category == "heavy_join"
        assert issues[0].severity == "medium"

    def test_exactly_3_joins_no_detection(self):
        sql = "SELECT * FROM a JOIN b ON 1=1 JOIN c ON 1=1 JOIN d ON 1=1"
        qr = [_QueryRecord(sql=sql, route="/", execution_time_ms=5.0, model="")]
        g = _make_graph()
        issues = _detect_heavy_joins(qr, g)
        assert len(issues) == 0

    def test_deduplicates_same_query(self):
        sql = "SELECT * FROM a JOIN b ON 1 JOIN c ON 1 JOIN d ON 1 JOIN e ON 1"
        qr = [
            _QueryRecord(sql=sql, route="/", execution_time_ms=5.0, model=""),
            _QueryRecord(sql=sql, route="/", execution_time_ms=5.0, model=""),
        ]
        g = _make_graph()
        issues = _detect_heavy_joins(qr, g)
        assert len(issues) == 1

    def test_empty_sql_skipped(self):
        qr = [_QueryRecord(sql="", route="/", execution_time_ms=5.0, model="")]
        g = _make_graph()
        issues = _detect_heavy_joins(qr, g)
        assert len(issues) == 0


# ═══════════════════════════════════════════════════════════════════════════
# Detect Route Hotspots
# ═══════════════════════════════════════════════════════════════════════════


class TestDetectRouteHotspots:
    def setup_method(self):
        _reset_counters()

    def test_no_hotspots(self):
        qr = [_QueryRecord(sql="SELECT 1", route="/api/users",
                            execution_time_ms=50.0, model="")]
        g = _make_graph()
        issues = _detect_route_hotspots(qr, g)
        assert len(issues) == 0

    def test_hotspot_with_multiple_slow_queries(self):
        qr = [
            _QueryRecord(sql="SELECT 1", route="/api/slow",
                          execution_time_ms=300.0, model=""),
            _QueryRecord(sql="SELECT 2", route="/api/slow",
                          execution_time_ms=400.0, model=""),
        ]
        g = _make_graph()
        issues = _detect_route_hotspots(qr, g)
        assert len(issues) == 1
        assert issues[0].category == "route_hotspot"
        assert "/api/slow" in issues[0].route

    def test_single_slow_query_no_hotspot(self):
        qr = [
            _QueryRecord(sql="SELECT 1", route="/api/slow",
                          execution_time_ms=300.0, model=""),
        ]
        g = _make_graph()
        issues = _detect_route_hotspots(qr, g)
        assert len(issues) == 0

    def test_no_route_no_hotspot(self):
        qr = [
            _QueryRecord(sql="SELECT 1", route="",
                          execution_time_ms=300.0, model=""),
            _QueryRecord(sql="SELECT 2", route="",
                          execution_time_ms=400.0, model=""),
        ]
        g = _make_graph()
        issues = _detect_route_hotspots(qr, g)
        assert len(issues) == 0

    def test_multiple_routes_one_hotspot(self):
        qr = [
            _QueryRecord(sql="SELECT 1", route="/api/slow",
                          execution_time_ms=300.0, model=""),
            _QueryRecord(sql="SELECT 2", route="/api/slow",
                          execution_time_ms=400.0, model=""),
            _QueryRecord(sql="SELECT 3", route="/api/fast",
                          execution_time_ms=300.0, model=""),
        ]
        g = _make_graph()
        issues = _detect_route_hotspots(qr, g)
        assert len(issues) == 1
        assert "/api/slow" in issues[0].route


# ═══════════════════════════════════════════════════════════════════════════
# Compute Metrics
# ═══════════════════════════════════════════════════════════════════════════


class TestComputeMetrics:
    def test_empty_graph(self):
        g = _make_graph()
        m = _compute_metrics(g, [], [])
        assert m.total_routes == 0
        assert m.total_queries == 0

    def test_route_count(self):
        g = _make_graph(routes=[_make_route(), _make_route(path="/b")])
        m = _compute_metrics(g, [], [])
        assert m.total_routes == 2

    def test_query_count(self):
        g = _make_graph(queries=[_make_query(), _make_query(sql="SELECT 2")])
        m = _compute_metrics(g, [], [])
        assert m.total_queries == 2

    def test_slow_query_count_from_issues(self):
        issues = [
            PerformanceIssue(issue_id="P1", severity="medium", title="T",
                             description="D", category="slow_query"),
            PerformanceIssue(issue_id="P2", severity="medium", title="T",
                             description="D", category="slow_query"),
        ]
        g = _make_graph()
        m = _compute_metrics(g, issues, [])
        assert m.slow_queries == 2

    def test_n_plus_one_count(self):
        issues = [
            PerformanceIssue(issue_id="P1", severity="high", title="T",
                             description="D", category="n_plus_one"),
        ]
        g = _make_graph()
        m = _compute_metrics(g, issues, [])
        assert m.n_plus_one_candidates == 1

    def test_missing_index_count(self):
        issues = [
            PerformanceIssue(issue_id="P1", severity="high", title="T",
                             description="D", category="missing_index"),
        ]
        g = _make_graph()
        m = _compute_metrics(g, issues, [])
        assert m.missing_indexes == 1

    def test_avg_queries_per_route(self):
        routes = [
            _make_route(path="/a", queries=["q1", "q2", "q3"]),
            _make_route(path="/b", queries=["q4"]),
        ]
        g = _make_graph(routes=routes)
        m = _compute_metrics(g, [], [])
        assert m.avg_queries_per_route == 2.0

    def test_max_queries_route(self):
        r1 = _make_route(method="GET", path="/a", queries=["q1", "q2", "q3"])
        r2 = _make_route(method="POST", path="/b", queries=["q4"])
        g = _make_graph(routes=[r1, r2])
        m = _compute_metrics(g, [], [])
        assert m.max_queries_route == "GET /a"


# ═══════════════════════════════════════════════════════════════════════════
# Score Computation
# ═══════════════════════════════════════════════════════════════════════════


class TestComputeScore:
    def test_no_issues_full_score(self):
        assert _compute_score([]) == 100

    def test_slow_query_penalty(self):
        i = PerformanceIssue(issue_id="P1", severity="medium", title="T",
                             description="D", category="slow_query")
        assert _compute_score([i]) == 90

    def test_n_plus_one_penalty(self):
        i = PerformanceIssue(issue_id="P1", severity="high", title="T",
                             description="D", category="n_plus_one")
        assert _compute_score([i]) == 85

    def test_missing_index_penalty(self):
        i = PerformanceIssue(issue_id="P1", severity="high", title="T",
                             description="D", category="missing_index")
        assert _compute_score([i]) == 90

    def test_query_explosion_penalty(self):
        i = PerformanceIssue(issue_id="P1", severity="high", title="T",
                             description="D", category="query_explosion")
        assert _compute_score([i]) == 90

    def test_heavy_join_penalty(self):
        i = PerformanceIssue(issue_id="P1", severity="medium", title="T",
                             description="D", category="heavy_join")
        assert _compute_score([i]) == 95

    def test_route_hotspot_penalty(self):
        i = PerformanceIssue(issue_id="P1", severity="high", title="T",
                             description="D", category="route_hotspot")
        assert _compute_score([i]) == 90

    def test_multiple_penalties_stack(self):
        issues = [
            PerformanceIssue(issue_id="P1", severity="medium", title="T",
                             description="D", category="slow_query"),
            PerformanceIssue(issue_id="P2", severity="high", title="T",
                             description="D", category="n_plus_one"),
        ]
        assert _compute_score(issues) == 75

    def test_score_clamped_at_zero(self):
        issues = [
            PerformanceIssue(issue_id=f"P{i}", severity="high", title="T",
                             description="D", category="n_plus_one")
            for i in range(10)
        ]
        assert _compute_score(issues) == 0

    def test_unknown_category_default_penalty(self):
        i = PerformanceIssue(issue_id="P1", severity="medium", title="T",
                             description="D", category="unknown_cat")
        assert _compute_score([i]) == 95


# ═══════════════════════════════════════════════════════════════════════════
# Recommendation Generation
# ═══════════════════════════════════════════════════════════════════════════


class TestGenerateRecommendations:
    def setup_method(self):
        _reset_counters()

    def test_no_issues_no_recommendations(self):
        m = PerformanceMetrics()
        recs = _generate_recommendations([], m)
        assert recs == []

    def test_slow_query_recommendation(self):
        issues = [PerformanceIssue(issue_id="P1", severity="medium", title="T",
                                    description="D", category="slow_query")]
        recs = _generate_recommendations(issues, PerformanceMetrics())
        assert len(recs) >= 1
        assert any("slow" in r.title.lower() or "optimise" in r.title.lower()
                    for r in recs)

    def test_n_plus_one_recommendation(self):
        issues = [PerformanceIssue(issue_id="P1", severity="high", title="T",
                                    description="D", category="n_plus_one")]
        recs = _generate_recommendations(issues, PerformanceMetrics())
        assert any("eager" in r.title.lower() or "n+1" in r.title.lower()
                    for r in recs)

    def test_missing_index_recommendation(self):
        issues = [PerformanceIssue(issue_id="P1", severity="high", title="T",
                                    description="D", category="missing_index")]
        recs = _generate_recommendations(issues, PerformanceMetrics())
        assert any("index" in r.title.lower() for r in recs)

    def test_query_explosion_recommendation(self):
        issues = [PerformanceIssue(issue_id="P1", severity="high", title="T",
                                    description="D", category="query_explosion")]
        recs = _generate_recommendations(issues, PerformanceMetrics())
        assert any("query count" in r.title.lower() or "reduce" in r.title.lower()
                    for r in recs)

    def test_heavy_join_recommendation(self):
        issues = [PerformanceIssue(issue_id="P1", severity="medium", title="T",
                                    description="D", category="heavy_join")]
        recs = _generate_recommendations(issues, PerformanceMetrics())
        assert any("join" in r.title.lower() or "simplify" in r.title.lower()
                    for r in recs)

    def test_route_hotspot_recommendation(self):
        issues = [PerformanceIssue(issue_id="P1", severity="high", title="T",
                                    description="D", category="route_hotspot",
                                    route="/api/slow")]
        recs = _generate_recommendations(issues, PerformanceMetrics())
        assert any("caching" in r.title.lower() for r in recs)

    def test_deduplicated(self):
        """Multiple slow_query issues should produce only one recommendation."""
        issues = [
            PerformanceIssue(issue_id=f"P{i}", severity="medium", title="T",
                             description="D", category="slow_query")
            for i in range(3)
        ]
        recs = _generate_recommendations(issues, PerformanceMetrics())
        titles = [r.title for r in recs]
        assert len(titles) == len(set(titles))

    def test_sorted_by_impact(self):
        issues = [
            PerformanceIssue(issue_id="P1", severity="medium", title="T",
                             description="D", category="heavy_join"),
            PerformanceIssue(issue_id="P2", severity="high", title="T",
                             description="D", category="n_plus_one"),
        ]
        recs = _generate_recommendations(issues, PerformanceMetrics())
        if len(recs) >= 2:
            impact_order = {"high": 0, "medium": 1, "low": 2}
            for i in range(len(recs) - 1):
                assert impact_order.get(recs[i].impact, 1) <= impact_order.get(recs[i+1].impact, 1)

    def test_related_issue_ids(self):
        issues = [PerformanceIssue(issue_id="P1", severity="medium", title="T",
                                    description="D", category="slow_query")]
        recs = _generate_recommendations(issues, PerformanceMetrics())
        assert any("P1" in r.related_issue_ids for r in recs)


# ═══════════════════════════════════════════════════════════════════════════
# Full Pipeline (run_performance_analysis)
# ═══════════════════════════════════════════════════════════════════════════


class TestRunPerformanceAnalysis:
    @patch("aksara.ai.project_graph.build_project_graph")
    def test_full_pipeline_ok(self, mock_graph):
        mock_graph.return_value = _make_graph(
            routes=[_make_route()],
            queries=[_make_query()],
        )
        report = run_performance_analysis()
        assert report.ok is True
        assert 0 <= report.score <= 100
        assert report.grade in ("A", "B", "C", "D", "F")
        assert report.elapsed_ms >= 0
        assert report.generated_at != ""

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_empty_graph_perfect_score(self, mock_graph):
        mock_graph.return_value = _make_graph()
        report = run_performance_analysis()
        assert report.score == 100
        assert report.grade == "A"
        assert report.issue_count == 0

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_graph_failure(self, mock_graph):
        mock_graph.side_effect = RuntimeError("no graph")
        report = run_performance_analysis()
        assert report.ok is False
        assert report.score == 0
        assert report.grade == "F"

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_slow_queries_detected(self, mock_graph):
        q = _make_query(sql="SELECT * FROM big_table", execution_time_ms=500.0)
        mock_graph.return_value = _make_graph(queries=[q])
        report = run_performance_analysis()
        assert report.issue_count >= 1
        assert any(i.category == "slow_query" for i in report.issues)

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_n_plus_one_detected(self, mock_graph):
        queries = [
            _make_query(sql=f"SELECT * FROM users WHERE id = {i}",
                        execution_time_ms=5.0, route="/api/users")
            for i in range(6)
        ]
        mock_graph.return_value = _make_graph(queries=queries)
        report = run_performance_analysis()
        assert any(i.category == "n_plus_one" for i in report.issues)

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_recommendations_generated(self, mock_graph):
        q = _make_query(sql="SELECT * FROM big", execution_time_ms=500.0)
        mock_graph.return_value = _make_graph(queries=[q])
        report = run_performance_analysis()
        assert report.recommendation_count >= 1

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_to_dict_full(self, mock_graph):
        mock_graph.return_value = _make_graph()
        report = run_performance_analysis()
        d = report.to_dict()
        assert "score" in d
        assert "grade" in d
        assert "issues" in d
        assert "recommendations" in d
        assert "metrics" in d

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_to_summary_dict_full(self, mock_graph):
        mock_graph.return_value = _make_graph()
        report = run_performance_analysis()
        s = report.to_summary_dict()
        assert "score" in s
        assert "grade" in s
        assert "metrics" in s

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_app_param_forwarded(self, mock_graph):
        mock_graph.return_value = _make_graph()
        app = MagicMock()
        report = run_performance_analysis(app=app)
        assert report.ok is True
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
        from aksara.ai.performance_analyzer import _ISSUE_COUNTER, _REC_COUNTER
        assert _ISSUE_COUNTER == 0
        assert _REC_COUNTER == 0

    def test_query_record_dataclass(self):
        qr = _QueryRecord(sql="SELECT 1", route="/", execution_time_ms=5.0, model="User")
        assert qr.sql == "SELECT 1"
        assert qr.route == "/"
        assert qr.execution_time_ms == 5.0
        assert qr.model == "User"
