# Query Inspector

> **v0.5.21** — Deep SQL plan analysis and aggregate query statistics.

The **Query Inspector** provides two main capabilities:

1. **EXPLAIN Plan Generation** — Get the query plan for any SQL statement
2. **Aggregate Query Statistics** — Summarize slow queries, durations, and N+1 detections

---

## Quick Start

### Python API

```python
from aksara.inspectors.queries import explain_query, get_query_stats

# Get an EXPLAIN plan
plan = explain_query("SELECT * FROM users WHERE active = true")
print(plan.plan)             # ['Seq Scan  (cost=0.00..35.50 ...)']
print(plan.estimated_cost)   # 35.50

# Aggregate statistics
stats = get_query_stats(limit_slow=5)
print(stats.total_queries)        # 42
print(stats.total_slow_queries)   # 3
print(stats.avg_duration_ms)      # 12.5
```

### CLI

```bash
# View query statistics
aksara inspect queries

# Top 5 slow queries as JSON
aksara inspect queries --limit 5 --json

# Pipe to agent for optimization suggestions
aksara inspect queries --json | aksara agent prompt -g "Optimize slow queries"
```

### Studio API

```bash
# POST /studio/db/plan
curl -X POST http://localhost:8000/studio/db/plan \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT * FROM users", "analyze": false}'
```

---

## Models

### `QueryPlanRequest`

| Field     | Type   | Default | Description                    |
|-----------|--------|---------|--------------------------------|
| `sql`     | `str`  | —       | SQL statement to explain       |
| `analyze` | `bool` | `False` | Run EXPLAIN ANALYZE (executes) |

### `QueryPlanResult`

| Field            | Type           | Description                       |
|------------------|----------------|-----------------------------------|
| `sql`            | `str`          | Original SQL                      |
| `plan`           | `List[str]`    | EXPLAIN output lines              |
| `estimated_cost` | `float | None` | Planner cost estimate             |
| `plan_type`      | `str`          | `"EXPLAIN"` or `"EXPLAIN ANALYZE"`|
| `warnings`       | `List[str]`    | Notes about the plan              |

### `QueryStats`

| Field                | Type              | Description                        |
|----------------------|-------------------|------------------------------------|
| `total_queries`      | `int`             | Total tracked queries              |
| `total_batches`      | `int`             | Total request batches              |
| `total_slow_queries` | `int`             | Queries above slow threshold       |
| `avg_duration_ms`    | `float`           | Average query time                 |
| `max_duration_ms`    | `float`           | Slowest query time                 |
| `slow_threshold_ms`  | `float`           | Current threshold (default 100ms)  |
| `top_slow`           | `List[dict]`      | Top slow queries with SQL + timing |
| `n_plus_one_count`   | `int`             | Requests with N+1 suspicion        |
| `by_operation`       | `Dict[str, int]`  | Count per operation type           |

---

## Functions

### `explain_query(sql, analyze=False)`

Generates an EXPLAIN plan for the given SQL. When a live database connection is available, it runs a real `EXPLAIN` against PostgreSQL. Otherwise, it returns a **synthetic plan** for offline/test usage.

**Synthetic plan types:**

| Statement | Plan                            | Cost  |
|-----------|---------------------------------|-------|
| SELECT    | Seq Scan with Filter            | 35.50 |
| INSERT    | Insert                          | 1.00  |
| UPDATE    | Update → Seq Scan               | 10.00 |
| DELETE    | Delete → Seq Scan               | 5.00  |
| Other     | Utility Statement               | 0.00  |

### `get_query_stats(limit_slow=5)`

Computes aggregate statistics from the trace storage. Requires `db_trace_enabled = True` in settings.

---

## Studio Integration

The Query Inspector is integrated into Studio in two ways:

1. **Explain Plan Button** — Slow queries in the DB Queries panel now show an "Explain Plan" button
2. **Agent Context** — The `query_stats` section is included in agent context (section 10 of 11)

---

## Configuration

| Setting                       | Default | Description                    |
|-------------------------------|---------|--------------------------------|
| `db_trace_enabled`            | `False` | Enable query tracing           |
| `db_trace_slow_threshold_ms`  | `100.0` | Threshold for "slow" queries   |
| `db_trace_max_queries`        | `500`   | Max queries kept in storage    |
