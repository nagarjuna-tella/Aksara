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

`explain_query(sql, analyze=False)` is synchronous. Use
`await explain_query_async(...)` when an application event loop is already
running. Both forms use the configured pool when it is connected and return a
clearly labelled synthetic result when live execution is unavailable. A live
database error produces a failed result instead of a fabricated plan.

The returned `QueryPlanResult` includes `sql`, `plan`, `estimated_cost`,
`plan_type`, `warnings`, `provenance`, and `analyze_executed`. Provenance is
`live`, `synthetic`, `failed`, or `unavailable`. A synthetic SELECT plan uses a
fixed cost of 35.50; that is fabricated output, not a performance measurement or
estimate for your schema.

!!! warning "EXPLAIN ANALYZE executes SQL only for live results"
    `analyze=True` can perform writes or other SQL side effects. Treat it as
    executed only when `provenance == "live"` and `analyze_executed` is true.
    Synthetic results always retain a warning and report
    `analyze_executed == false`.

Do not use this helper as a SQL validation, read-only, authorization, or
performance gate. For measured plans, use the direct database-backed procedure
in [query profiling](../debugging/query-profiling.md), with controlled SQL and
appropriate database permissions. Never pass arbitrary user-provided SQL to a
privileged diagnostic connection.
