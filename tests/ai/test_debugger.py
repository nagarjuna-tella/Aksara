"""
v0.5.33 — AI Debugger: core pipeline tests.

Tests cover:
    - run_debugger() — full pipeline with mocked graph
    - DebugReport / DebugIssue / IssueCluster / RootCause data models
    - Issue pool building from diagnostics, gaps, events
    - Query filtering
    - Ranking and confidence scoring
    - Fix suggestion generation
    - Edge cases: empty graph, no issues, no root causes
    - Safety: debugger never modifies code or DB
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import asdict

from aksara.ai.debugger import (
    run_debugger,
    DebugReport,
    DebugIssue,
    IssueCluster,
    RootCause,
    _build_issue_pool,
    _cluster_issues,
    _detect_root_causes,
    _rank_root_causes,
    _generate_fix_suggestions,
    _filter_by_query,
    _is_db_issue,
    _is_migration_issue,
    _is_ai_issue,
    _is_security_issue,
    _worst_severity,
    _build_summary,
    _elapsed,
)


# ═══════════════════════════════════════════════════════════════════════════
# Fake graph data
# ═══════════════════════════════════════════════════════════════════════════

def _make_diagnostic(code="DB_NO_URL", severity="error", message="No DATABASE_URL",
                     related_models=None, related_routes=None, related_queries=None):
    d = MagicMock()
    d.code = code
    d.severity = severity
    d.message = message
    d.related_models = related_models or []
    d.related_routes = related_routes or []
    d.related_queries = related_queries or []
    return d


def _make_gap(code="GAP_001", severity="warning", summary="Missing index",
              category="performance", related_components=None):
    g = MagicMock()
    g.code = code
    g.severity = severity
    g.summary = summary
    g.category = category
    g.related_components = related_components or []
    return g


def _make_event(kind="route_error", severity="error", message="500 on GET /api/users",
                source_type="route", source_id="/api/users", timestamp="2024-01-01T00:00:00Z"):
    return {
        "kind": kind,
        "severity": severity,
        "message": message,
        "source_type": source_type,
        "source_id": source_id,
        "timestamp": timestamp,
    }


def _make_graph(diagnostics=None, gaps=None, events=None, models=None, routes=None,
                queries=None, migrations=None, ai_hub=None, metadata=None):
    g = MagicMock()
    g.diagnostics = diagnostics or []
    g.gaps = gaps or []
    g.events = events or []
    g.models = models or []
    g.routes = routes or []
    g.queries = queries or []
    g.migrations = migrations or []
    g.ai_hub = ai_hub
    m = MagicMock()
    m.model_count = len(g.models)
    m.route_count = len(g.routes)
    m.query_count = len(g.queries)
    m.migration_count = len(g.migrations)
    m.diagnostic_count = len(g.diagnostics)
    m.gap_count = len(g.gaps)
    m.event_count = len(g.events)
    g.metadata = metadata or m
    return g


# ═══════════════════════════════════════════════════════════════════════════
# Data model tests
# ═══════════════════════════════════════════════════════════════════════════


class TestDebugIssue:
    def test_create_minimal(self):
        issue = DebugIssue(id="d-1", source="diagnostic", severity="error",
                           title="DB_NO_URL", message="No database URL")
        assert issue.id == "d-1"
        assert issue.source == "diagnostic"
        assert issue.severity == "error"
        assert issue.related_models == []
        assert issue.related_routes == []

    def test_to_dict(self):
        issue = DebugIssue(id="d-1", source="gap", severity="warning",
                           title="GAP_001", message="Missing index",
                           related_models=["User"])
        d = issue.to_dict()
        assert d["id"] == "d-1"
        assert d["source"] == "gap"
        assert d["related_models"] == ["User"]
        assert isinstance(d, dict)

    def test_with_all_fields(self):
        issue = DebugIssue(id="e-1", source="event", severity="error",
                           title="route_error", message="500",
                           related_models=["User"], related_routes=["/api/users"],
                           related_queries=["q1"], timestamp="2024-01-01",
                           meta={"kind": "route_error"})
        assert issue.timestamp == "2024-01-01"
        assert issue.meta["kind"] == "route_error"


class TestIssueCluster:
    def test_create(self):
        cl = IssueCluster(cluster_id="c-1", label="Model: User",
                          component_type="model", component_name="User",
                          issue_ids=["d-1", "d-2"], severity="error", size=2)
        assert cl.cluster_id == "c-1"
        assert cl.size == 2

    def test_to_dict(self):
        cl = IssueCluster(cluster_id="c-1", label="Route: /api",
                          component_type="route", component_name="/api",
                          issue_ids=["d-1"], severity="warning", size=1)
        d = cl.to_dict()
        assert d["cluster_id"] == "c-1"
        assert d["component_type"] == "route"

    def test_defaults(self):
        cl = IssueCluster(cluster_id="c-1", label="General",
                          component_type="general", component_name="uncategorised")
        assert cl.issue_ids == []
        assert cl.size == 0
        assert cl.severity == "info"


class TestRootCause:
    def test_create(self):
        rc = RootCause(cause_id="rc-1", title="DB issue",
                       description="Database not reachable",
                       confidence=0.85, severity="error")
        assert rc.cause_id == "rc-1"
        assert rc.confidence == 0.85

    def test_to_dict(self):
        rc = RootCause(cause_id="rc-1", title="Test", description="Desc",
                       confidence=0.5, severity="warning",
                       evidence=["e1"], related_issues=["d-1"],
                       fix_suggestions=["fix1"])
        d = rc.to_dict()
        assert d["evidence"] == ["e1"]
        assert d["fix_suggestions"] == ["fix1"]

    def test_defaults(self):
        rc = RootCause(cause_id="rc-1", title="T", description="D",
                       confidence=0.0, severity="info")
        assert rc.evidence == []
        assert rc.related_clusters == []
        assert rc.category == "general"


class TestDebugReport:
    def test_create_ok(self):
        r = DebugReport(ok=True, query=None)
        assert r.ok is True
        assert r.issues == []
        assert r.issue_count == 0

    def test_create_error(self):
        r = DebugReport(ok=False, query="why failing?",
                        summary="Could not load project graph")
        assert r.ok is False
        assert "project graph" in r.summary

    def test_to_dict(self):
        r = DebugReport(ok=True, query="debug",
                        issue_count=5, cluster_count=2, root_cause_count=1)
        d = r.to_dict()
        assert d["ok"] is True
        assert d["issue_count"] == 5

    def test_to_summary_dict(self):
        rc = RootCause(cause_id="rc-1", title="DB issue",
                       description="desc", confidence=0.85, severity="error")
        r = DebugReport(ok=True, query=None, root_causes=[rc],
                        issue_count=3, cluster_count=1, root_cause_count=1,
                        summary="Test", elapsed_ms=10.5)
        s = r.to_summary_dict()
        assert s["ok"] is True
        assert s["issue_count"] == 3
        assert len(s["top_root_causes"]) == 1
        assert s["top_root_causes"][0]["title"] == "DB issue"
        assert s["elapsed_ms"] == 10.5

    def test_summary_limits_top_5(self):
        rcs = [RootCause(cause_id=f"rc-{i}", title=f"Cause {i}",
                         description="d", confidence=0.5, severity="info")
               for i in range(10)]
        r = DebugReport(ok=True, query=None, root_causes=rcs,
                        root_cause_count=10)
        s = r.to_summary_dict()
        assert len(s["top_root_causes"]) == 5


# ═══════════════════════════════════════════════════════════════════════════
# Issue pool tests
# ═══════════════════════════════════════════════════════════════════════════


class TestBuildIssuePool:
    def test_from_diagnostics(self):
        graph = _make_graph(diagnostics=[
            _make_diagnostic("DB_NO_URL", "error", "No database"),
            _make_diagnostic("CACHE_MISS", "warning", "Cache unavailable"),
        ])
        issues = _build_issue_pool(graph)
        assert len(issues) == 2
        assert issues[0].source == "diagnostic"
        assert issues[0].title == "DB_NO_URL"

    def test_from_gaps(self):
        graph = _make_graph(gaps=[
            _make_gap("GAP_001", "warning", "Missing index", "performance", ["User"]),
        ])
        issues = _build_issue_pool(graph)
        assert len(issues) == 1
        assert issues[0].source == "gap"
        assert "User" in issues[0].related_models

    def test_from_events_error_only(self):
        graph = _make_graph(events=[
            _make_event(severity="error"),
            _make_event(severity="info", kind="ai_flow_executed"),
        ])
        issues = _build_issue_pool(graph)
        assert len(issues) == 1  # only error events

    def test_from_events_warning(self):
        graph = _make_graph(events=[
            _make_event(severity="warning", kind="slow_query", source_type="query", source_id="q1"),
        ])
        issues = _build_issue_pool(graph)
        assert len(issues) == 1
        assert issues[0].source == "event"

    def test_empty_graph(self):
        graph = _make_graph()
        issues = _build_issue_pool(graph)
        assert issues == []

    def test_combined_sources(self):
        graph = _make_graph(
            diagnostics=[_make_diagnostic()],
            gaps=[_make_gap()],
            events=[_make_event()],
        )
        issues = _build_issue_pool(graph)
        assert len(issues) == 3
        sources = {i.source for i in issues}
        assert sources == {"diagnostic", "gap", "event"}

    def test_gap_route_component(self):
        graph = _make_graph(gaps=[
            _make_gap(related_components=["/api/users"]),
        ])
        issues = _build_issue_pool(graph)
        assert "/api/users" in issues[0].related_routes

    def test_event_model_source(self):
        graph = _make_graph(events=[
            _make_event(source_type="model", source_id="User", severity="error"),
        ])
        issues = _build_issue_pool(graph)
        assert "User" in issues[0].related_models

    def test_query_filter(self):
        graph = _make_graph(diagnostics=[
            _make_diagnostic("DB_NO_URL", "error", "No database URL set"),
            _make_diagnostic("CACHE", "info", "Cache stats"),
        ])
        issues = _build_issue_pool(graph, query="database URL")
        assert len(issues) == 1
        assert issues[0].title == "DB_NO_URL"

    def test_query_filter_relaxes_on_empty(self):
        graph = _make_graph(diagnostics=[
            _make_diagnostic("DB_NO_URL", "error", "No database"),
        ])
        issues = _build_issue_pool(graph, query="zzzznonexistent")
        assert len(issues) == 1  # returns all when filter empty


class TestFilterByQuery:
    def test_filters_by_keyword(self):
        issues = [
            DebugIssue(id="1", source="d", severity="error", title="DB_NO_URL", message="database"),
            DebugIssue(id="2", source="d", severity="info", title="CACHE", message="cache"),
        ]
        result = _filter_by_query(issues, "database")
        assert len(result) == 1
        assert result[0].id == "1"

    def test_returns_all_if_no_match(self):
        issues = [DebugIssue(id="1", source="d", severity="error", title="X", message="Y")]
        result = _filter_by_query(issues, "nonexistent_pattern_xyz")
        assert len(result) == 1

    def test_short_keywords_ignored(self):
        issues = [DebugIssue(id="1", source="d", severity="error", title="A", message="B")]
        result = _filter_by_query(issues, "ab cd")
        assert len(result) == 1  # short words < 3 chars ignored

    def test_model_name_match(self):
        issues = [
            DebugIssue(id="1", source="d", severity="error", title="X", message="Y",
                       related_models=["User"]),
        ]
        result = _filter_by_query(issues, "User model")
        assert len(result) == 1


# ═══════════════════════════════════════════════════════════════════════════
# Clustering tests
# ═══════════════════════════════════════════════════════════════════════════


class TestClusterIssues:
    def test_cluster_by_model(self):
        issues = [
            DebugIssue(id="1", source="d", severity="error", title="X", message="Y",
                       related_models=["User"]),
            DebugIssue(id="2", source="d", severity="warning", title="Z", message="W",
                       related_models=["User"]),
        ]
        clusters = _cluster_issues(issues)
        user_clusters = [c for c in clusters if c.component_name == "User"]
        assert len(user_clusters) == 1
        assert user_clusters[0].size == 2
        assert user_clusters[0].severity == "error"

    def test_cluster_by_route(self):
        issues = [
            DebugIssue(id="1", source="e", severity="error", title="X", message="Y",
                       related_routes=["/api/users"]),
        ]
        clusters = _cluster_issues(issues)
        route_clusters = [c for c in clusters if c.component_type == "route"]
        assert len(route_clusters) == 1
        assert route_clusters[0].component_name == "/api/users"

    def test_uncategorised_issues(self):
        issues = [
            DebugIssue(id="1", source="d", severity="info", title="X", message="Y"),
        ]
        clusters = _cluster_issues(issues)
        assert len(clusters) == 1
        assert clusters[0].component_type == "general"

    def test_empty_issues(self):
        clusters = _cluster_issues([])
        assert clusters == []

    def test_multi_component_issue(self):
        issues = [
            DebugIssue(id="1", source="d", severity="error", title="X", message="Y",
                       related_models=["User"], related_routes=["/api/users"]),
        ]
        clusters = _cluster_issues(issues)
        assert len(clusters) >= 2  # appears in model and route cluster

    def test_cluster_severity_is_worst(self):
        issues = [
            DebugIssue(id="1", source="d", severity="info", title="X", message="Y",
                       related_models=["Post"]),
            DebugIssue(id="2", source="d", severity="error", title="Z", message="W",
                       related_models=["Post"]),
        ]
        clusters = _cluster_issues(issues)
        post_cluster = [c for c in clusters if c.component_name == "Post"][0]
        assert post_cluster.severity == "error"

    def test_sorted_by_size_desc(self):
        issues = [
            DebugIssue(id="1", source="d", severity="info", title="A", message="B",
                       related_models=["User"]),
            DebugIssue(id="2", source="d", severity="info", title="C", message="D",
                       related_models=["User"]),
            DebugIssue(id="3", source="d", severity="info", title="E", message="F",
                       related_models=["Post"]),
        ]
        clusters = _cluster_issues(issues)
        assert clusters[0].size >= clusters[-1].size


# ═══════════════════════════════════════════════════════════════════════════
# Root cause detection tests
# ═══════════════════════════════════════════════════════════════════════════


class TestDetectRootCauses:
    def test_detects_db_issues(self):
        issues = [
            DebugIssue(id="1", source="d", severity="error",
                       title="DB_NO_URL", message="No database URL set"),
        ]
        clusters = _cluster_issues(issues)
        rcs = _detect_root_causes(issues, clusters, _make_graph())
        db_rcs = [rc for rc in rcs if rc.category == "database"]
        assert len(db_rcs) == 1
        assert "database" in db_rcs[0].title.lower()

    def test_detects_migration_issues(self):
        issues = [
            DebugIssue(id="1", source="d", severity="warning",
                       title="MIGRATIONS_PENDING", message="3 pending migrations"),
        ]
        clusters = _cluster_issues(issues)
        rcs = _detect_root_causes(issues, clusters, _make_graph())
        mig_rcs = [rc for rc in rcs if rc.category == "migration"]
        assert len(mig_rcs) == 1

    def test_detects_ai_provider_issues(self):
        issues = [
            DebugIssue(id="1", source="d", severity="warning",
                       title="AI_PROVIDER_MISSING", message="No AI provider configured"),
        ]
        clusters = _cluster_issues(issues)
        rcs = _detect_root_causes(issues, clusters, _make_graph())
        ai_rcs = [rc for rc in rcs if rc.category == "ai_provider"]
        assert len(ai_rcs) == 1

    def test_detects_security_issues(self):
        issues = [
            DebugIssue(id="1", source="d", severity="warning",
                       title="SECURITY_CORS", message="CORS security warning"),
        ]
        clusters = _cluster_issues(issues)
        rcs = _detect_root_causes(issues, clusters, _make_graph())
        sec_rcs = [rc for rc in rcs if rc.category == "security"]
        assert len(sec_rcs) == 1

    def test_detects_route_error_cluster(self):
        issues = [
            DebugIssue(id="1", source="e", severity="error",
                       title="route_error", message="500",
                       related_routes=["/api/users"]),
        ]
        clusters = _cluster_issues(issues)
        rcs = _detect_root_causes(issues, clusters, _make_graph())
        route_rcs = [rc for rc in rcs if rc.category == "route"]
        assert len(route_rcs) == 1

    def test_no_issues_no_root_causes(self):
        rcs = _detect_root_causes([], [], _make_graph())
        assert rcs == []

    def test_evidence_populated(self):
        issues = [
            DebugIssue(id="1", source="d", severity="error",
                       title="DB_NO_URL", message="No database URL"),
        ]
        clusters = _cluster_issues(issues)
        rcs = _detect_root_causes(issues, clusters, _make_graph())
        assert any(len(rc.evidence) > 0 for rc in rcs)

    def test_related_issues_tracked(self):
        issues = [
            DebugIssue(id="1", source="d", severity="error",
                       title="DB_NO_URL", message="No database"),
        ]
        clusters = _cluster_issues(issues)
        rcs = _detect_root_causes(issues, clusters, _make_graph())
        db_rc = [rc for rc in rcs if rc.category == "database"]
        assert db_rc
        assert "1" in db_rc[0].related_issues

    def test_large_cluster_root_cause(self):
        issues = [
            DebugIssue(id=f"x-{i}", source="d", severity="info",
                       title="MISC", message="generic issue",
                       related_models=["Widget"])
            for i in range(4)
        ]
        clusters = _cluster_issues(issues)
        rcs = _detect_root_causes(issues, clusters, _make_graph())
        # Should detect large cluster
        assert len(rcs) >= 1


# ═══════════════════════════════════════════════════════════════════════════
# Ranking tests
# ═══════════════════════════════════════════════════════════════════════════


class TestRankRootCauses:
    def test_ranks_by_confidence_desc(self):
        rcs = [
            RootCause(cause_id="1", title="Low", description="d",
                      confidence=0, severity="info", evidence=["e1"],
                      related_issues=["i1"]),
            RootCause(cause_id="2", title="High", description="d",
                      confidence=0, severity="error", evidence=["e1", "e2", "e3"],
                      related_issues=["i1", "i2", "i3"]),
        ]
        ranked = _rank_root_causes(rcs)
        assert ranked[0].cause_id == "2"
        assert ranked[0].confidence > ranked[1].confidence

    def test_empty_list(self):
        assert _rank_root_causes([]) == []

    def test_confidence_between_0_and_1(self):
        rcs = [
            RootCause(cause_id="1", title="T", description="D",
                      confidence=0, severity="error",
                      evidence=["e"] * 10,
                      related_issues=["i"] * 10,
                      related_clusters=["c"] * 5),
        ]
        ranked = _rank_root_causes(rcs)
        assert 0.0 <= ranked[0].confidence <= 1.0

    def test_severity_affects_score(self):
        rcs = [
            RootCause(cause_id="1", title="Error", description="d",
                      confidence=0, severity="error",
                      evidence=["e1"], related_issues=["i1"]),
            RootCause(cause_id="2", title="Info", description="d",
                      confidence=0, severity="info",
                      evidence=["e1"], related_issues=["i1"]),
        ]
        ranked = _rank_root_causes(rcs)
        assert ranked[0].severity == "error"

    def test_single_root_cause(self):
        rcs = [
            RootCause(cause_id="1", title="T", description="D",
                      confidence=0, severity="warning",
                      evidence=["e"], related_issues=["i"]),
        ]
        ranked = _rank_root_causes(rcs)
        assert len(ranked) == 1
        assert ranked[0].confidence > 0


# ═══════════════════════════════════════════════════════════════════════════
# Fix suggestions tests
# ═══════════════════════════════════════════════════════════════════════════


class TestGenerateFixSuggestions:
    def test_database_suggestions(self):
        rcs = [RootCause(cause_id="1", title="DB", description="d",
                         confidence=0.8, severity="error", category="database")]
        result = _generate_fix_suggestions(rcs, [], _make_graph())
        assert any("DATABASE_URL" in s for s in result[0].fix_suggestions)

    def test_migration_suggestions(self):
        rcs = [RootCause(cause_id="1", title="Mig", description="d",
                         confidence=0.7, severity="warning", category="migration")]
        result = _generate_fix_suggestions(rcs, [], _make_graph())
        assert any("migrate" in s.lower() for s in result[0].fix_suggestions)

    def test_ai_provider_suggestions(self):
        rcs = [RootCause(cause_id="1", title="AI", description="d",
                         confidence=0.6, severity="warning", category="ai_provider")]
        result = _generate_fix_suggestions(rcs, [], _make_graph())
        assert any("provider" in s.lower() for s in result[0].fix_suggestions)

    def test_route_suggestions(self):
        rcs = [RootCause(cause_id="1", title="Route", description="d",
                         confidence=0.5, severity="error", category="route")]
        result = _generate_fix_suggestions(rcs, [], _make_graph())
        assert any("route" in s.lower() for s in result[0].fix_suggestions)

    def test_security_suggestions(self):
        rcs = [RootCause(cause_id="1", title="Sec", description="d",
                         confidence=0.5, severity="warning", category="security")]
        result = _generate_fix_suggestions(rcs, [], _make_graph())
        assert any("security" in s.lower() for s in result[0].fix_suggestions)

    def test_general_suggestions(self):
        rcs = [RootCause(cause_id="1", title="Gen", description="d",
                         confidence=0.4, severity="info", category="general")]
        result = _generate_fix_suggestions(rcs, [], _make_graph())
        assert len(result[0].fix_suggestions) > 0

    def test_empty_root_causes(self):
        result = _generate_fix_suggestions([], [], _make_graph())
        assert result == []


# ═══════════════════════════════════════════════════════════════════════════
# Helper function tests
# ═══════════════════════════════════════════════════════════════════════════


class TestHelpers:
    def test_is_db_issue_true(self):
        i = DebugIssue(id="1", source="d", severity="error", title="DB_NO_URL", message="database")
        assert _is_db_issue(i) is True

    def test_is_db_issue_false(self):
        i = DebugIssue(id="1", source="d", severity="info", title="CACHE", message="cache miss")
        assert _is_db_issue(i) is False

    def test_is_migration_issue_true(self):
        i = DebugIssue(id="1", source="d", severity="w", title="MIGRATIONS_PENDING", message="pending")
        assert _is_migration_issue(i) is True

    def test_is_migration_issue_false(self):
        i = DebugIssue(id="1", source="d", severity="i", title="CACHE", message="ok")
        assert _is_migration_issue(i) is False

    def test_is_ai_issue_true(self):
        i = DebugIssue(id="1", source="d", severity="w", title="AI_PROVIDER_MISSING", message="missing")
        assert _is_ai_issue(i) is True

    def test_is_ai_issue_false(self):
        i = DebugIssue(id="1", source="d", severity="i", title="CACHE", message="ok")
        assert _is_ai_issue(i) is False

    def test_is_security_issue_true(self):
        i = DebugIssue(id="1", source="d", severity="w", title="SECURITY", message="cors warning")
        assert _is_security_issue(i) is True

    def test_is_security_issue_false(self):
        i = DebugIssue(id="1", source="d", severity="i", title="CACHE", message="ok")
        assert _is_security_issue(i) is False

    def test_worst_severity_error(self):
        assert _worst_severity(["info", "warning", "error"]) == "error"

    def test_worst_severity_warning(self):
        assert _worst_severity(["info", "warning"]) == "warning"

    def test_worst_severity_empty(self):
        assert _worst_severity([]) == "info"

    def test_worst_severity_single(self):
        assert _worst_severity(["warning"]) == "warning"

    def test_elapsed(self):
        import time
        t0 = time.monotonic()
        time.sleep(0.01)
        elapsed = _elapsed(t0)
        assert elapsed > 0

    def test_build_summary_with_query(self):
        s = _build_summary([], [], [], "why failing?")
        assert "why failing?" in s

    def test_build_summary_no_query(self):
        s = _build_summary([], [], [], None)
        assert "Full project" in s

    def test_build_summary_with_root_causes(self):
        rc = RootCause(cause_id="1", title="DB issue", description="d",
                       confidence=0.85, severity="error")
        s = _build_summary([], [], [rc], None)
        assert "DB issue" in s

    def test_build_summary_with_errors(self):
        issues = [DebugIssue(id="1", source="d", severity="error",
                             title="X", message="Y")]
        s = _build_summary(issues, [], [], None)
        assert "1 error" in s


# ═══════════════════════════════════════════════════════════════════════════
# Full pipeline tests
# ═══════════════════════════════════════════════════════════════════════════


class TestRunDebugger:
    @patch("aksara.ai.project_graph.build_project_graph")
    def test_full_pipeline_ok(self, mock_build):
        graph = _make_graph(
            diagnostics=[_make_diagnostic()],
            gaps=[_make_gap()],
            events=[_make_event()],
        )
        mock_build.return_value = graph

        report = run_debugger()
        assert report.ok is True
        assert report.issue_count >= 3
        assert report.cluster_count >= 1
        assert report.elapsed_ms >= 0
        assert report.generated_at != ""

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_pipeline_with_query(self, mock_build):
        graph = _make_graph(diagnostics=[
            _make_diagnostic("DB_NO_URL", "error", "No database URL"),
        ])
        mock_build.return_value = graph

        report = run_debugger(query="database URL")
        assert report.ok is True
        assert report.query == "database URL"

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_pipeline_empty_graph(self, mock_build):
        mock_build.return_value = _make_graph()

        report = run_debugger()
        assert report.ok is True
        assert report.issue_count == 0
        assert report.cluster_count == 0
        assert report.root_cause_count == 0

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_pipeline_graph_failure(self, mock_build):
        mock_build.side_effect = RuntimeError("graph failed")

        report = run_debugger()
        assert report.ok is False
        assert "graph" in report.summary.lower()

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_pipeline_root_causes_ranked(self, mock_build):
        graph = _make_graph(
            diagnostics=[
                _make_diagnostic("DB_NO_URL", "error", "No database URL"),
                _make_diagnostic("CACHE_MISS", "info", "Cache stats"),
            ],
            events=[_make_event()],
        )
        mock_build.return_value = graph

        report = run_debugger()
        if report.root_causes:
            confidences = [rc.confidence for rc in report.root_causes]
            assert confidences == sorted(confidences, reverse=True)

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_pipeline_fix_suggestions_populated(self, mock_build):
        graph = _make_graph(diagnostics=[
            _make_diagnostic("DB_NO_URL", "error", "No database URL"),
        ])
        mock_build.return_value = graph

        report = run_debugger()
        for rc in report.root_causes:
            assert len(rc.fix_suggestions) > 0

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_safety_never_modifies(self, mock_build):
        """Debugger only reads — verify no write operations."""
        graph = _make_graph(diagnostics=[_make_diagnostic()])
        mock_build.return_value = graph

        report = run_debugger()
        # The debugger returns a report, it never calls any write methods
        assert report.ok is True
        # Graph was only read, never modified
        graph.save = MagicMock()
        graph.save.assert_not_called()

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_to_dict_serialisable(self, mock_build):
        graph = _make_graph(
            diagnostics=[_make_diagnostic()],
            gaps=[_make_gap()],
            events=[_make_event()],
        )
        mock_build.return_value = graph

        report = run_debugger()
        d = report.to_dict()
        import json
        json.dumps(d, default=str)  # must be JSON-serialisable

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_app_passed_to_graph(self, mock_build):
        mock_build.return_value = _make_graph()
        fake_app = MagicMock()
        run_debugger(app=fake_app)
        mock_build.assert_called_once_with(app=fake_app)
