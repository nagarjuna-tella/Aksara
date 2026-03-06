"""
v0.5.33 — AI Debugger: clustering logic tests.

Tests cover:
    - Clustering by model, route, query, migration
    - Mixed component clusters
    - Cluster severity calculation
    - Cluster label generation
    - Edge cases: single issue, many issues, no components
    - Cluster ordering by size
    - Cross-component issues
"""

from __future__ import annotations

import pytest
from aksara.ai.debugger import (
    DebugIssue,
    IssueCluster,
    _cluster_issues,
    _worst_severity,
)


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _issue(id, severity="info", models=None, routes=None, queries=None):
    return DebugIssue(
        id=id, source="diagnostic", severity=severity,
        title=f"Issue-{id}", message=f"Message for {id}",
        related_models=models or [],
        related_routes=routes or [],
        related_queries=queries or [],
    )


# ═══════════════════════════════════════════════════════════════════════════
# Single-dimension clustering
# ═══════════════════════════════════════════════════════════════════════════


class TestClusterByModel:
    def test_single_model(self):
        issues = [_issue("1", models=["User"]), _issue("2", models=["User"])]
        cls = _cluster_issues(issues)
        user_cls = [c for c in cls if c.component_name == "User"]
        assert len(user_cls) == 1
        assert user_cls[0].component_type == "model"
        assert user_cls[0].size == 2

    def test_multiple_models(self):
        issues = [
            _issue("1", models=["User"]),
            _issue("2", models=["Post"]),
            _issue("3", models=["User"]),
        ]
        cls = _cluster_issues(issues)
        model_cls = [c for c in cls if c.component_type == "model"]
        assert len(model_cls) == 2
        names = {c.component_name for c in model_cls}
        assert names == {"User", "Post"}

    def test_model_cluster_ids_unique(self):
        issues = [_issue("1", models=["User"]), _issue("2", models=["Post"])]
        cls = _cluster_issues(issues)
        ids = [c.cluster_id for c in cls]
        assert len(ids) == len(set(ids))


class TestClusterByRoute:
    def test_single_route(self):
        issues = [_issue("1", routes=["/api/users"]), _issue("2", routes=["/api/users"])]
        cls = _cluster_issues(issues)
        route_cls = [c for c in cls if c.component_type == "route"]
        assert len(route_cls) == 1
        assert route_cls[0].component_name == "/api/users"
        assert route_cls[0].size == 2

    def test_multiple_routes(self):
        issues = [
            _issue("1", routes=["/api/users"]),
            _issue("2", routes=["/api/posts"]),
        ]
        cls = _cluster_issues(issues)
        route_cls = [c for c in cls if c.component_type == "route"]
        assert len(route_cls) == 2


class TestClusterByQuery:
    def test_single_query(self):
        issues = [_issue("1", queries=["select_users"]), _issue("2", queries=["select_users"])]
        cls = _cluster_issues(issues)
        q_cls = [c for c in cls if c.component_type == "query"]
        assert len(q_cls) == 1
        assert q_cls[0].component_name == "select_users"

    def test_multiple_queries(self):
        issues = [_issue("1", queries=["q1"]), _issue("2", queries=["q2"])]
        cls = _cluster_issues(issues)
        q_cls = [c for c in cls if c.component_type == "query"]
        assert len(q_cls) == 2


# ═══════════════════════════════════════════════════════════════════════════
# Cross-component clustering
# ═══════════════════════════════════════════════════════════════════════════


class TestCrossComponentClustering:
    def test_issue_in_model_and_route(self):
        issues = [_issue("1", models=["User"], routes=["/api/users"])]
        cls = _cluster_issues(issues)
        assert len(cls) >= 2
        types = {c.component_type for c in cls}
        assert "model" in types
        assert "route" in types

    def test_issue_in_all_three(self):
        issues = [_issue("1", models=["User"], routes=["/api/users"], queries=["q1"])]
        cls = _cluster_issues(issues)
        assert len(cls) >= 3

    def test_shared_issue_appears_in_multiple_clusters(self):
        issues = [_issue("1", models=["User"], routes=["/api/users"])]
        cls = _cluster_issues(issues)
        for c in cls:
            assert "1" in c.issue_ids


# ═══════════════════════════════════════════════════════════════════════════
# Uncategorised
# ═══════════════════════════════════════════════════════════════════════════


class TestUncategorised:
    def test_no_components(self):
        issues = [_issue("1"), _issue("2")]
        cls = _cluster_issues(issues)
        assert len(cls) == 1
        assert cls[0].component_type == "general"
        assert cls[0].component_name == "uncategorised"
        assert cls[0].size == 2

    def test_mixed_categorised_and_uncategorised(self):
        issues = [_issue("1", models=["User"]), _issue("2")]
        cls = _cluster_issues(issues)
        types = {c.component_type for c in cls}
        assert "model" in types
        assert "general" in types


# ═══════════════════════════════════════════════════════════════════════════
# Severity
# ═══════════════════════════════════════════════════════════════════════════


class TestClusterSeverity:
    def test_worst_is_error(self):
        issues = [
            _issue("1", severity="info", models=["User"]),
            _issue("2", severity="error", models=["User"]),
        ]
        cls = _cluster_issues(issues)
        user_cl = [c for c in cls if c.component_name == "User"][0]
        assert user_cl.severity == "error"

    def test_worst_is_warning(self):
        issues = [
            _issue("1", severity="info", models=["User"]),
            _issue("2", severity="warning", models=["User"]),
        ]
        cls = _cluster_issues(issues)
        user_cl = [c for c in cls if c.component_name == "User"][0]
        assert user_cl.severity == "warning"

    def test_all_info(self):
        issues = [_issue("1", severity="info", models=["User"])]
        cls = _cluster_issues(issues)
        assert cls[0].severity == "info"


# ═══════════════════════════════════════════════════════════════════════════
# Labels
# ═══════════════════════════════════════════════════════════════════════════


class TestClusterLabels:
    def test_model_label(self):
        issues = [_issue("1", models=["User"])]
        cls = _cluster_issues(issues)
        model_cl = [c for c in cls if c.component_type == "model"][0]
        assert "Model" in model_cl.label
        assert "User" in model_cl.label

    def test_route_label(self):
        issues = [_issue("1", routes=["/api/users"])]
        cls = _cluster_issues(issues)
        route_cl = [c for c in cls if c.component_type == "route"][0]
        assert "Route" in route_cl.label

    def test_general_label(self):
        issues = [_issue("1")]
        cls = _cluster_issues(issues)
        assert "General" in cls[0].label


# ═══════════════════════════════════════════════════════════════════════════
# Ordering
# ═══════════════════════════════════════════════════════════════════════════


class TestClusterOrdering:
    def test_largest_first(self):
        issues = [
            _issue("1", models=["User"]),
            _issue("2", models=["User"]),
            _issue("3", models=["User"]),
            _issue("4", models=["Post"]),
        ]
        cls = _cluster_issues(issues)
        sizes = [c.size for c in cls]
        assert sizes == sorted(sizes, reverse=True)

    def test_single_issue_clusters(self):
        issues = [_issue("1", models=["A"]), _issue("2", models=["B"])]
        cls = _cluster_issues(issues)
        assert all(c.size == 1 for c in cls)


# ═══════════════════════════════════════════════════════════════════════════
# Edge cases
# ═══════════════════════════════════════════════════════════════════════════


class TestClusterEdgeCases:
    def test_empty(self):
        assert _cluster_issues([]) == []

    def test_large_input(self):
        issues = [_issue(str(i), models=["BulkModel"]) for i in range(100)]
        cls = _cluster_issues(issues)
        bulk = [c for c in cls if c.component_name == "BulkModel"]
        assert len(bulk) == 1
        assert bulk[0].size == 100

    def test_to_dict(self):
        issues = [_issue("1", models=["User"])]
        cls = _cluster_issues(issues)
        for c in cls:
            d = c.to_dict()
            assert isinstance(d, dict)
            assert "cluster_id" in d

    def test_cluster_ids_sequential(self):
        issues = [_issue("1", models=["A"]), _issue("2", models=["B"])]
        cls = _cluster_issues(issues)
        ids = [c.cluster_id for c in cls]
        assert all(cid.startswith("cluster-") for cid in ids)


class TestWorstSeverity:
    def test_error_wins(self):
        assert _worst_severity(["info", "error", "warning"]) == "error"

    def test_warning_over_info(self):
        assert _worst_severity(["info", "warning"]) == "warning"

    def test_empty(self):
        assert _worst_severity([]) == "info"

    def test_single(self):
        assert _worst_severity(["error"]) == "error"

    def test_all_same(self):
        assert _worst_severity(["warning", "warning"]) == "warning"
