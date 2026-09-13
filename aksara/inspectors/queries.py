"""
Aksara Query Inspector Utilities

v0.5.21: Query plan analysis and aggregate query statistics.

Provides:
    - QueryPlanRequest: Request model for EXPLAIN plan
    - QueryPlanResult: Result model with plan text and estimated cost
    - QueryStats: Aggregate statistics for agent context
    - explain_query(): Run EXPLAIN on a SQL statement (read-only)
    - get_query_stats(): Compute aggregate statistics from trace storage
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Models
# =============================================================================


class QueryPlanRequest(BaseModel):
    """Request body for EXPLAIN plan generation."""

    sql: str = Field(description="The SQL query to explain")
    analyze: bool = Field(
        default=False,
        description="Whether to run EXPLAIN ANALYZE (actually executes the query)",
    )


class QueryPlanResult(BaseModel):
    """Result of EXPLAIN query plan."""

    sql: str = Field(description="Original SQL")
    plan: List[str] = Field(
        default_factory=list,
        description="Lines of the EXPLAIN output",
    )
    estimated_cost: Optional[float] = Field(
        default=None,
        description="Total estimated cost from the planner",
    )
    plan_type: str = Field(
        default="EXPLAIN",
        description="Type of plan: EXPLAIN or EXPLAIN ANALYZE",
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Warnings or notes about the plan",
    )
    provenance: Literal["live", "synthetic", "failed", "unavailable"] = Field(
        default="unavailable",
        description="Whether the result came from PostgreSQL or a diagnostic fallback",
    )
    analyze_executed: bool = Field(
        default=False,
        description="Whether PostgreSQL actually executed EXPLAIN ANALYZE",
    )


class QueryStats(BaseModel):
    """Aggregate query statistics for agent / CLI consumption."""

    total_queries: int = Field(default=0, description="Total queries tracked")
    total_batches: int = Field(default=0, description="Total request batches")
    total_slow_queries: int = Field(default=0, description="Queries exceeding slow threshold")
    avg_duration_ms: float = Field(default=0.0, description="Average query duration")
    max_duration_ms: float = Field(default=0.0, description="Slowest query duration")
    slow_threshold_ms: float = Field(default=100.0, description="Current slow threshold")
    top_slow: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Top slow queries with sql, duration_ms, table",
    )
    n_plus_one_count: int = Field(default=0, description="Requests with N+1 suspicions")
    by_operation: Dict[str, int] = Field(
        default_factory=dict,
        description="Query count by operation type (SELECT, INSERT, ...)",
    )


# =============================================================================
# Functions
# =============================================================================


def _synthetic_plan(sql: str, analyze: bool, reason: str) -> QueryPlanResult:
    """Build a deterministic offline plan with explicit provenance."""

    import re

    plan_type = "EXPLAIN ANALYZE" if analyze else "EXPLAIN"
    warnings = [f"Synthetic plan — {reason}"]
    plan_lines: List[str] = []
    estimated_cost: Optional[float] = None
    sql_upper = sql.strip().upper()
    if sql_upper.startswith("SELECT"):
        plan_lines = [
            f"Seq Scan  (cost=0.00..35.50 rows=10 width=64)",
            f"  Filter: (condition from WHERE clause)",
        ]
        estimated_cost = 35.50
    elif sql_upper.startswith("INSERT"):
        plan_lines = [
            f"Insert  (cost=0.00..1.00 rows=1 width=0)",
        ]
        estimated_cost = 1.0
    elif sql_upper.startswith("UPDATE"):
        plan_lines = [
            f"Update  (cost=0.00..10.00 rows=1 width=64)",
            f"  ->  Seq Scan  (cost=0.00..5.00 rows=1 width=64)",
        ]
        estimated_cost = 10.0
    elif sql_upper.startswith("DELETE"):
        plan_lines = [
            f"Delete  (cost=0.00..5.00 rows=1 width=6)",
            f"  ->  Seq Scan  (cost=0.00..2.50 rows=1 width=6)",
        ]
        estimated_cost = 5.0
    else:
        plan_lines = [f"Utility Statement  (cost=0.00..0.00 rows=0 width=0)"]
        estimated_cost = 0.0
        warnings.append("Unsupported statement type for query plan estimation")

    if analyze:
        warnings.append("EXPLAIN ANALYZE was requested but was not executed")

    return QueryPlanResult(
        sql=sql,
        plan=plan_lines,
        estimated_cost=estimated_cost,
        plan_type=plan_type,
        warnings=warnings,
        provenance="synthetic",
        analyze_executed=False,
    )


async def explain_query_async(sql: str, analyze: bool = False) -> QueryPlanResult:
    """Run a live plan when a connected database exists, otherwise label fallback."""

    import re

    from aksara.db.engine import Database

    plan_type = "EXPLAIN ANALYZE" if analyze else "EXPLAIN"
    try:
        database = Database.get_instance()
    except RuntimeError:
        return _synthetic_plan(sql, analyze, "no database is configured")

    if database is None or database._pool is None:
        return _synthetic_plan(sql, analyze, "no live database connection is available")

    try:
        rows = await database.fetch(f"{plan_type} {sql}")
    except Exception as exc:
        return QueryPlanResult(
            sql=sql,
            plan=[],
            estimated_cost=None,
            plan_type=plan_type,
            warnings=[f"Live database EXPLAIN failed: {type(exc).__name__}: {exc}"],
            provenance="failed",
            analyze_executed=False,
        )

    plan_lines = [str(row[0]) for row in rows]
    estimated_cost = None
    for line in plan_lines:
        cost_match = re.search(r"cost=[\d.]+\.\.([\d.]+)", line)
        if cost_match:
            estimated_cost = float(cost_match.group(1))
            break
    return QueryPlanResult(
        sql=sql,
        plan=plan_lines,
        estimated_cost=estimated_cost,
        plan_type=plan_type,
        warnings=[],
        provenance="live",
        analyze_executed=analyze,
    )


def explain_query(sql: str, analyze: bool = False) -> QueryPlanResult:
    """Return a query plan from synchronous code with explicit provenance."""

    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(explain_query_async(sql, analyze=analyze))
    return _synthetic_plan(
        sql,
        analyze,
        "the synchronous API was called from an active event loop; use explain_query_async",
    )


def get_query_stats(limit_slow: int = 5) -> QueryStats:
    """
    Compute aggregate query statistics from the trace storage.

    Args:
        limit_slow: Number of top slow queries to include.

    Returns:
        QueryStats with totals, averages, and top-slow list.
    """
    from aksara.conf import settings
    from aksara.db.tracing import (
        get_trace_stats,
        get_top_slow_queries,
        _trace_storage,
    )

    raw = get_trace_stats()
    slow_threshold = getattr(settings, "db_trace_slow_threshold_ms", 100.0)

    # Gather all queries for average / max
    all_queries = _trace_storage.get_all_queries()
    avg_dur = 0.0
    max_dur = 0.0
    by_op: Dict[str, int] = {}

    if all_queries:
        durations = [q.duration_ms for q in all_queries]
        avg_dur = round(sum(durations) / len(durations), 3)
        max_dur = round(max(durations), 3)
        for q in all_queries:
            by_op[q.operation] = by_op.get(q.operation, 0) + 1

    top_slow_raw = get_top_slow_queries(limit_slow)
    top_slow = [
        {
            "sql": q.sql[:200],
            "duration_ms": round(q.duration_ms, 3),
            "table": q.table,
            "operation": q.operation,
        }
        for q in top_slow_raw
    ]

    return QueryStats(
        total_queries=raw.get("total_queries", 0),
        total_batches=raw.get("total_batches", 0),
        total_slow_queries=raw.get("total_slow_queries", 0),
        avg_duration_ms=avg_dur,
        max_duration_ms=max_dur,
        slow_threshold_ms=slow_threshold,
        top_slow=top_slow,
        n_plus_one_count=raw.get("requests_with_n_plus_one", 0),
        by_operation=by_op,
    )
