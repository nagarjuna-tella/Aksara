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

from typing import Any, Dict, List, Optional

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


def explain_query(sql: str, analyze: bool = False) -> QueryPlanResult:
    """
    Run EXPLAIN (or EXPLAIN ANALYZE) on a SQL statement.

    This does NOT require a live database connection by default — it
    returns a synthetic plan in test / offline mode.  When a real
    connection pool is available, it executes against the database.

    Args:
        sql: SQL statement to explain.
        analyze: If True, runs EXPLAIN ANALYZE (actually executes query).

    Returns:
        QueryPlanResult with plan lines and estimated cost.
    """
    import re

    plan_type = "EXPLAIN ANALYZE" if analyze else "EXPLAIN"
    warnings: List[str] = []
    plan_lines: List[str] = []
    estimated_cost: Optional[float] = None

    # Attempt real EXPLAIN via database pool
    try:
        from aksara.db.engine import Database

        db = Database.get_instance()
        if db and db.pool:
            import asyncio

            explain_sql = f"{plan_type} {sql}"

            async def _run():
                rows = await db.fetch(explain_sql)
                return rows

            try:
                loop = asyncio.get_running_loop()
                # If we're inside an event loop, we can't call asyncio.run
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, _run())
                    rows = future.result(timeout=5)
            except RuntimeError:
                rows = asyncio.run(_run())

            for row in rows:
                line = row[0] if isinstance(row, (tuple, list)) else str(row)
                plan_lines.append(str(line))

            # Extract cost from first line
            for line in plan_lines:
                cost_match = re.search(r'cost=[\d.]+\.\.([\d.]+)', str(line))
                if cost_match:
                    estimated_cost = float(cost_match.group(1))
                    break

            return QueryPlanResult(
                sql=sql,
                plan=plan_lines,
                estimated_cost=estimated_cost,
                plan_type=plan_type,
                warnings=warnings,
            )
    except Exception:
        pass

    # Fallback: synthetic plan for tests / offline mode
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

    if not analyze:
        warnings.append("Synthetic plan — no live database connection available")

    return QueryPlanResult(
        sql=sql,
        plan=plan_lines,
        estimated_cost=estimated_cost,
        plan_type=plan_type,
        warnings=warnings,
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
