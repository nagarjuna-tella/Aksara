# AI Performance Analyzer

!!! warning "Experimental development surface"
    This analysis, provider or Studio surface is outside the stable backend
    contract. Review its outputs and application integration before use. It is
    not required for REST, synchronous MCP or Durable Operations. See
    [stability labels](../concepts/stability.md).

The **AI Performance Analyzer** automatically analyses your application's
query patterns, detects performance issues, and recommends improvements —
all without modifying any code.

## Quick Start

```python
from aksara.ai.performance_analyzer import run_performance_analysis

report = run_performance_analysis()
print(f"Score: {report.score} ({report.grade})")
print(f"Issues: {report.issue_count}")
print(f"Recommendations: {report.recommendation_count}")
```

## CLI

```bash
aksara ai flows performance           # Text summary
aksara ai flows performance --json    # JSON output
aksara ai flows performance --summary # Summary only
aksara ai flows performance --metrics # Include metrics
aksara ai flows performance --issues  # Include issues list
```

## Studio UI

Open Aksara Studio and navigate to the **Performance** panel in the sidebar.
Click **Run Analysis** to execute the full pipeline.

## Pipeline Steps

| Step | Description |
|------|-------------|
| 1 | Load the Project Context Graph |
| 2 | Collect query data from graph queries, events, and diagnostics |
| 3 | Detect slow queries (execution time > 200 ms) |
| 4 | Detect N+1 patterns (repeated param-only queries > 5) |
| 5 | Detect query explosions (routes with > 10 queries) |
| 6 | Detect missing indexes (table-scan / seq-scan diagnostics) |
| 7 | Detect heavy joins (JOIN count > 3) |
| 8 | Detect route hotspots (routes with ≥ 2 slow queries) |
| 9 | Compute metrics (totals, averages, max queries per route) |
| 10 | Score and grade (penalty-based scoring, A–F grading) |

## Scoring

Starting from 100, each detected issue applies a penalty:

| Category | Penalty |
|----------|---------|
| Slow query | −10 |
| N+1 pattern | −15 |
| Missing index | −10 |
| Query explosion | −10 |
| Heavy join | −5 |
| Large payload | −5 |
| Route hotspot | −10 |

**Grades:** A (90–100), B (80–89), C (70–79), D (60–69), F (< 60)

## Data Models

- **`PerformanceReport`** — Top-level report with `score`, `grade`, `issues`,
  `recommendations`, `metrics`, `ok`, `elapsed_ms`, `generated_at`.
- **`PerformanceIssue`** — A detected issue with `issue_id`, `severity`,
  `title`, `description`, `route`, `model`, `query`, `category`.
- **`PerformanceRecommendation`** — An improvement suggestion with
  `recommendation_id`, `title`, `description`, `impact`, `related_issue_ids`.
- **`PerformanceMetrics`** — Computed metrics: `total_routes`, `total_queries`,
  `slow_queries`, `n_plus_one_candidates`, `missing_indexes`,
  `avg_queries_per_route`, `max_queries_route`.

## Console Integration

Ask the AI console about performance:

- *"analyze performance"*
- *"why is my app slow"*
- *"find slow queries"*
- *"n+1 query patterns"*
- *"missing indexes"*

## Safety

The Performance Analyzer **never** modifies code, database, or files. It only
returns analysis, issues, and recommendations.
