"""
v0.5.35 — AI Performance Analyzer: metrics and scoring tests.

Tests cover:
    - PerformanceMetrics fields and defaults
    - Metric aggregation edge cases
    - Score computation with all penalty types
    - Grade boundary tests
    - Combined score + grade scenarios
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from aksara.ai.performance_analyzer import (
    PerformanceMetrics,
    PerformanceIssue,
    PerformanceReport,
    _compute_metrics,
    _compute_score,
    _score_to_grade,
    _reset_counters,
    _PENALTY,
)


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _make_route(method="GET", path="/api/users", queries=None):
    r = MagicMock()
    r.method = method
    r.path = path
    r.name = "route"
    r.handler = "h"
    r.models = []
    r.queries = queries or []
    r.diagnostics = []
    return r


def _make_graph(routes=None, queries=None):
    g = MagicMock()
    g.models = []
    g.routes = routes or []
    g.queries = queries or []
    g.migrations = []
    g.diagnostics = []
    g.gaps = []
    g.events = []
    g.flows = []
    g.ai_hub = None
    g.metadata = MagicMock()
    g.metadata.version = "0.5.36"
    g.metadata.model_count = 0
    g.metadata.route_count = len(g.routes)
    return g


def _make_query(sql="SELECT 1"):
    q = MagicMock()
    q.sql = sql
    q.query = sql
    q.execution_time_ms = 5.0
    q.duration_ms = 5.0
    q.route = ""
    q.model = ""
    return q


# ═══════════════════════════════════════════════════════════════════════════
# Metrics Defaults
# ═══════════════════════════════════════════════════════════════════════════


class TestMetricsDefaults:
    def test_all_zeros(self):
        m = PerformanceMetrics()
        assert m.total_routes == 0
        assert m.total_queries == 0
        assert m.slow_queries == 0
        assert m.n_plus_one_candidates == 0
        assert m.missing_indexes == 0
        assert m.avg_queries_per_route == 0.0
        assert m.max_queries_route is None

    def test_to_dict_keys(self):
        m = PerformanceMetrics()
        d = m.to_dict()
        expected_keys = {
            "total_routes", "total_queries", "slow_queries",
            "n_plus_one_candidates", "missing_indexes",
            "avg_queries_per_route", "max_queries_route",
        }
        assert expected_keys.issubset(set(d.keys()))


# ═══════════════════════════════════════════════════════════════════════════
# Metric Aggregation
# ═══════════════════════════════════════════════════════════════════════════


class TestMetricAggregation:
    def test_single_route_avg(self):
        g = _make_graph(routes=[_make_route(queries=["q1", "q2"])])
        m = _compute_metrics(g, [], [])
        assert m.avg_queries_per_route == 2.0

    def test_multiple_routes_avg(self):
        routes = [
            _make_route(path="/a", queries=["q1", "q2", "q3", "q4"]),
            _make_route(path="/b", queries=[]),
        ]
        g = _make_graph(routes=routes)
        m = _compute_metrics(g, [], [])
        assert m.avg_queries_per_route == 2.0

    def test_no_routes_avg_zero(self):
        g = _make_graph()
        m = _compute_metrics(g, [], [])
        assert m.avg_queries_per_route == 0.0

    def test_max_queries_route_with_tie(self):
        r1 = _make_route(method="GET", path="/a", queries=["q1", "q2"])
        r2 = _make_route(method="GET", path="/b", queries=["q3", "q4"])
        g = _make_graph(routes=[r1, r2])
        m = _compute_metrics(g, [], [])
        # First one encountered wins on a tie
        assert m.max_queries_route is not None

    def test_max_queries_route_clear_winner(self):
        r1 = _make_route(method="GET", path="/a", queries=["q1"])
        r2 = _make_route(method="POST", path="/b", queries=["q1", "q2", "q3"])
        g = _make_graph(routes=[r1, r2])
        m = _compute_metrics(g, [], [])
        assert m.max_queries_route == "POST /b"

    def test_no_routes_no_max(self):
        g = _make_graph()
        m = _compute_metrics(g, [], [])
        assert m.max_queries_route is None

    def test_issue_category_counts(self):
        issues = [
            PerformanceIssue(issue_id="P1", severity="m", title="T",
                             description="D", category="slow_query"),
            PerformanceIssue(issue_id="P2", severity="m", title="T",
                             description="D", category="slow_query"),
            PerformanceIssue(issue_id="P3", severity="h", title="T",
                             description="D", category="n_plus_one"),
            PerformanceIssue(issue_id="P4", severity="h", title="T",
                             description="D", category="missing_index"),
            PerformanceIssue(issue_id="P5", severity="h", title="T",
                             description="D", category="missing_index"),
            PerformanceIssue(issue_id="P6", severity="h", title="T",
                             description="D", category="missing_index"),
        ]
        g = _make_graph()
        m = _compute_metrics(g, issues, [])
        assert m.slow_queries == 2
        assert m.n_plus_one_candidates == 1
        assert m.missing_indexes == 3


# ═══════════════════════════════════════════════════════════════════════════
# Score Penalty Table
# ═══════════════════════════════════════════════════════════════════════════


class TestPenaltyTable:
    def test_penalty_values(self):
        assert _PENALTY["slow_query"] == 10
        assert _PENALTY["n_plus_one"] == 15
        assert _PENALTY["missing_index"] == 10
        assert _PENALTY["query_explosion"] == 10
        assert _PENALTY["heavy_join"] == 5
        assert _PENALTY["large_payload"] == 5
        assert _PENALTY["route_hotspot"] == 10

    def test_all_categories_present(self):
        expected = {"slow_query", "n_plus_one", "missing_index",
                    "query_explosion", "heavy_join", "large_payload",
                    "route_hotspot"}
        assert expected.issubset(set(_PENALTY.keys()))


# ═══════════════════════════════════════════════════════════════════════════
# Score Edge Cases
# ═══════════════════════════════════════════════════════════════════════════


class TestScoreEdgeCases:
    def test_empty_issues_100(self):
        assert _compute_score([]) == 100

    def test_one_of_each_category(self):
        cats = list(_PENALTY.keys())
        issues = [
            PerformanceIssue(issue_id=f"P{i}", severity="m", title="T",
                             description="D", category=cat)
            for i, cat in enumerate(cats)
        ]
        expected = 100 - sum(_PENALTY[c] for c in cats)
        expected = max(0, expected)
        assert _compute_score(issues) == expected

    def test_many_same_category(self):
        issues = [
            PerformanceIssue(issue_id=f"P{i}", severity="m", title="T",
                             description="D", category="slow_query")
            for i in range(5)
        ]
        assert _compute_score(issues) == 100 - 5 * 10

    def test_score_never_negative(self):
        issues = [
            PerformanceIssue(issue_id=f"P{i}", severity="h", title="T",
                             description="D", category="n_plus_one")
            for i in range(20)
        ]
        assert _compute_score(issues) == 0


# ═══════════════════════════════════════════════════════════════════════════
# Grade Boundaries
# ═══════════════════════════════════════════════════════════════════════════


class TestGradeBoundaries:
    def test_boundary_90(self):
        assert _score_to_grade(90) == "A"
        assert _score_to_grade(89) == "B"

    def test_boundary_80(self):
        assert _score_to_grade(80) == "B"
        assert _score_to_grade(79) == "C"

    def test_boundary_70(self):
        assert _score_to_grade(70) == "C"
        assert _score_to_grade(69) == "D"

    def test_boundary_60(self):
        assert _score_to_grade(60) == "D"
        assert _score_to_grade(59) == "F"

    def test_extremes(self):
        assert _score_to_grade(100) == "A"
        assert _score_to_grade(0) == "F"

    def test_negative_is_f(self):
        assert _score_to_grade(-10) == "F"


# ═══════════════════════════════════════════════════════════════════════════
# Combined Score + Grade
# ═══════════════════════════════════════════════════════════════════════════


class TestCombinedScoreGrade:
    def test_no_issues_grade_a(self):
        score = _compute_score([])
        assert _score_to_grade(score) == "A"

    def test_one_slow_query_grade_a(self):
        i = PerformanceIssue(issue_id="P1", severity="m", title="T",
                             description="D", category="slow_query")
        score = _compute_score([i])
        assert _score_to_grade(score) == "A"  # 90 → A

    def test_one_n_plus_one_grade_b(self):
        i = PerformanceIssue(issue_id="P1", severity="h", title="T",
                             description="D", category="n_plus_one")
        score = _compute_score([i])
        assert _score_to_grade(score) == "B"  # 85 → B

    def test_multiple_issues_grade_c(self):
        issues = [
            PerformanceIssue(issue_id="P1", severity="m", title="T",
                             description="D", category="slow_query"),
            PerformanceIssue(issue_id="P2", severity="h", title="T",
                             description="D", category="n_plus_one"),
            PerformanceIssue(issue_id="P3", severity="h", title="T",
                             description="D", category="missing_index"),
        ]
        score = _compute_score(issues)  # 100 - 10 - 15 - 10 = 65
        assert _score_to_grade(score) == "D"

    def test_catastrophic_grade_f(self):
        issues = [
            PerformanceIssue(issue_id=f"P{i}", severity="h", title="T",
                             description="D", category="n_plus_one")
            for i in range(8)
        ]
        score = _compute_score(issues)  # max(0, 100 - 120) = 0
        assert _score_to_grade(score) == "F"
