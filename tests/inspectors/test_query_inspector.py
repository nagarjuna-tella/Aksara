"""
Tests for aksara.inspectors.queries — Query Inspector utilities.

v0.5.21: Query plan and statistics tests.
"""

import pytest
from aksara.inspectors.queries import (
    QueryPlanRequest,
    QueryPlanResult,
    QueryStats,
    explain_query,
    get_query_stats,
)


# =============================================================================
# QueryPlanRequest / QueryPlanResult model tests
# =============================================================================


class TestQueryPlanRequest:
    """Tests for QueryPlanRequest model."""

    def test_create_minimal(self):
        req = QueryPlanRequest(sql="SELECT 1")
        assert req.sql == "SELECT 1"
        assert req.analyze is False

    def test_create_with_analyze(self):
        req = QueryPlanRequest(sql="SELECT * FROM users", analyze=True)
        assert req.analyze is True

    def test_roundtrip_json(self):
        req = QueryPlanRequest(sql="INSERT INTO t VALUES (1)")
        data = req.model_dump()
        req2 = QueryPlanRequest(**data)
        assert req2.sql == req.sql


class TestQueryPlanResult:
    """Tests for QueryPlanResult model."""

    def test_create_minimal(self):
        result = QueryPlanResult(sql="SELECT 1")
        assert result.sql == "SELECT 1"
        assert result.plan == []
        assert result.estimated_cost is None
        assert result.plan_type == "EXPLAIN"
        assert result.warnings == []

    def test_create_full(self):
        result = QueryPlanResult(
            sql="SELECT * FROM users",
            plan=["Seq Scan (cost=0.00..35.50 rows=10 width=64)"],
            estimated_cost=35.50,
            plan_type="EXPLAIN ANALYZE",
            warnings=["Synthetic plan"],
        )
        assert result.estimated_cost == 35.50
        assert len(result.plan) == 1
        assert result.plan_type == "EXPLAIN ANALYZE"

    def test_roundtrip_json(self):
        result = QueryPlanResult(
            sql="SELECT 1",
            plan=["Plan line 1"],
            estimated_cost=10.0,
        )
        data = result.model_dump()
        result2 = QueryPlanResult(**data)
        assert result2.estimated_cost == 10.0


class TestQueryStats:
    """Tests for QueryStats model."""

    def test_create_defaults(self):
        stats = QueryStats()
        assert stats.total_queries == 0
        assert stats.total_batches == 0
        assert stats.total_slow_queries == 0
        assert stats.avg_duration_ms == 0.0
        assert stats.max_duration_ms == 0.0
        assert stats.top_slow == []
        assert stats.by_operation == {}

    def test_create_full(self):
        stats = QueryStats(
            total_queries=100,
            total_batches=20,
            total_slow_queries=5,
            avg_duration_ms=12.5,
            max_duration_ms=150.0,
            slow_threshold_ms=100.0,
            top_slow=[{"sql": "SELECT 1", "duration_ms": 150.0, "table": "t", "operation": "SELECT"}],
            n_plus_one_count=2,
            by_operation={"SELECT": 80, "INSERT": 20},
        )
        assert stats.total_queries == 100
        assert len(stats.top_slow) == 1
        assert stats.by_operation["SELECT"] == 80


# =============================================================================
# explain_query tests (synthetic mode)
# =============================================================================


class TestExplainQuery:
    """Tests for explain_query function (synthetic/offline mode)."""

    def test_select_plan(self):
        result = explain_query("SELECT * FROM users WHERE id = 1")
        assert result.sql == "SELECT * FROM users WHERE id = 1"
        assert len(result.plan) > 0
        assert result.estimated_cost is not None
        assert result.estimated_cost > 0
        assert "Seq Scan" in result.plan[0]

    def test_insert_plan(self):
        result = explain_query("INSERT INTO users (name) VALUES ('Alice')")
        assert len(result.plan) > 0
        assert "Insert" in result.plan[0]
        assert result.estimated_cost is not None

    def test_update_plan(self):
        result = explain_query("UPDATE users SET name = 'Bob' WHERE id = 1")
        assert len(result.plan) > 0
        assert "Update" in result.plan[0]

    def test_delete_plan(self):
        result = explain_query("DELETE FROM users WHERE id = 1")
        assert len(result.plan) > 0
        assert "Delete" in result.plan[0]

    def test_unknown_statement(self):
        result = explain_query("VACUUM ANALYZE users")
        assert len(result.plan) > 0
        assert "Utility" in result.plan[0]
        assert any("Unsupported" in w for w in result.warnings)

    def test_analyze_flag(self):
        result = explain_query("SELECT 1", analyze=True)
        assert result.plan_type == "EXPLAIN ANALYZE"

    def test_no_analyze_flag(self):
        result = explain_query("SELECT 1", analyze=False)
        assert result.plan_type == "EXPLAIN"

    def test_synthetic_warning(self):
        result = explain_query("SELECT 1", analyze=False)
        assert any("Synthetic" in w for w in result.warnings)

    def test_plan_has_lines(self):
        result = explain_query("SELECT * FROM orders")
        assert isinstance(result.plan, list)
        for line in result.plan:
            assert isinstance(line, str)
            assert len(line) > 0

    def test_select_cost_stable(self):
        r1 = explain_query("SELECT * FROM t1")
        r2 = explain_query("SELECT * FROM t2")
        assert r1.estimated_cost == r2.estimated_cost  # Both synthetic


# =============================================================================
# get_query_stats tests
# =============================================================================

class TestGetQueryStats:
    """Tests for get_query_stats function."""

    def test_empty_stats(self):
        """Empty trace storage should return zero stats."""
        from aksara.db.tracing import clear_traces
        clear_traces()
        stats = get_query_stats()
        assert stats.total_queries == 0
        assert stats.total_batches == 0
        assert stats.avg_duration_ms == 0.0
        assert stats.top_slow == []
        assert stats.by_operation == {}

    def test_stats_with_traces(self):
        """Stats with some traces should return non-zero values."""
        from aksara.db.tracing import (
            clear_traces,
            _trace_storage,
            DbQueryTrace,
            DbQueryBatch,
        )

        clear_traces()

        batch = DbQueryBatch(
            request_id="test-stats-1",
            queries=[
                DbQueryTrace(sql="SELECT * FROM users", duration_ms=5.0, operation="SELECT", table="users"),
                DbQueryTrace(sql="INSERT INTO logs VALUES (1)", duration_ms=2.0, operation="INSERT", table="logs"),
            ],
        )
        _trace_storage.store(batch)

        stats = get_query_stats()
        assert stats.total_queries == 2
        assert stats.total_batches == 1
        assert stats.avg_duration_ms > 0
        assert stats.max_duration_ms == 5.0
        assert stats.by_operation.get("SELECT") == 1
        assert stats.by_operation.get("INSERT") == 1

        clear_traces()

    def test_stats_limit_slow(self):
        from aksara.db.tracing import clear_traces, _trace_storage, DbQueryTrace, DbQueryBatch

        clear_traces()
        queries = [
            DbQueryTrace(sql=f"SELECT {i}", duration_ms=float(i * 10), operation="SELECT", table="t")
            for i in range(20)
        ]
        batch = DbQueryBatch(request_id="test-limit", queries=queries)
        _trace_storage.store(batch)

        stats = get_query_stats(limit_slow=3)
        assert len(stats.top_slow) <= 3

        clear_traces()

    def test_stats_roundtrip(self):
        stats = get_query_stats()
        data = stats.model_dump(mode="json")
        stats2 = QueryStats(**data)
        assert stats2.total_queries == stats.total_queries
