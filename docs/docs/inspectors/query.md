# Query inspection

`get_query_stats(limit_slow=5)` summarizes the current process's retained trace
storage. It is not PostgreSQL server statistics or a cross-worker history. Enable
and interpret tracing using the [query profiling guide](../debugging/query-profiling.md).
A separate CLI process may have no application traces to summarize.

## Summarize retained traces

This example runs without a database. In a fresh process the counts normally
start at zero; in an application process they reflect retained observations.

```python title="inspect_query_stats.py"
from aksara.inspectors import get_query_stats

stats = get_query_stats(limit_slow=5)
print(stats.total_queries)
print(stats.avg_duration_ms)
print(stats.top_slow)
```

The result also includes `total_batches`, `total_slow_queries`, `max_duration_ms`,
`slow_threshold_ms`, `n_plus_one_count`, and `by_operation`. Slow-query entries
contain SQL truncated to 200 characters, duration, table, and operation. Truncated
SQL may still contain sensitive values; limit access to this output.

## Query-plan limitations

`explain_query(sql, analyze=False)` is synchronous. It attempts a database call
through the configured pool, but catches exceptions and falls back to synthetic
output. With an active event loop it attempts the call in another thread/loop;
a connected pool alone does not establish that the returned plan came from
PostgreSQL.

The returned `QueryPlanResult` includes `sql`, `plan`, `estimated_cost`,
`plan_type`, and `warnings`. A synthetic SELECT plan uses a fixed cost of 35.50;
that is fabricated output, not a performance measurement or estimate for your
schema. Invalid SQL and database failures can therefore return a plan-shaped
result instead of raising.

!!! warning "EXPLAIN ANALYZE output does not prove execution"
    `analyze=True` requests execution when the database path succeeds, and can
    therefore perform writes or other SQL side effects. Yet the v0.7.0 fallback
    still labels synthetic output `EXPLAIN ANALYZE` and omits its usual synthetic
    warning. Neither that label nor an empty warning list proves execution.
    This diagnostic defect requires a separate runtime patch.

Do not use this helper as a SQL validation, read-only, authorization, or
performance gate. For measured plans, use the direct database-backed procedure
in [query profiling](../debugging/query-profiling.md), with controlled SQL and
appropriate database permissions. Never pass arbitrary user-provided SQL to a
privileged diagnostic connection.
