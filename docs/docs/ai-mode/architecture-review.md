# AI Architecture Review

!!! warning "Experimental development surface"
    This analysis, provider or Studio surface is outside the stable backend
    contract. Review its outputs and application integration before use. It is
    not required for REST, synchronous MCP or Durable Operations. See
    [stability labels](../concepts/stability.md).

The **AI Architecture Review** is an automated architectural analysis engine
that reads the Project Context Graph to detect anti-patterns, coupling risks,
schema design issues, API design problems, migration risks, and performance
concerns — then computes a health score and suggests improvements. It is
**read-only** and never modifies your code or database.

## Quick Start

```python
from aksara.ai.architecture_review import run_architecture_review

report = run_architecture_review()
print(f"Score: {report.score} ({report.grade})")

for f in report.findings:
    print(f"  [{f.severity}] {f.title}")
for s in report.suggestions:
    print(f"  → {s.title}")
```

## Architecture

The review runs a **9-step pipeline**:

```
┌─────────────┐     ┌────────────┐     ┌──────────────┐
│ 1. Load      │────▶│ 2. Compute │────▶│ 3. Detect    │
│ Project Graph│     │ Metrics    │     │ Coupling     │
└──────────────┘     └────────────┘     └──────────────┘
        │                                      │
        ▼                                      ▼
┌──────────────┐     ┌────────────┐     ┌──────────────┐
│ 6. Migration │◀────│ 5. API     │◀────│ 4. Schema    │
│ Risks        │     │ Design     │     │ Design       │
└──────────────┘     └────────────┘     └──────────────┘
        │
        ▼
┌──────────────┐     ┌────────────┐     ┌──────────────┐
│ 7. Perf      │────▶│ 8. Score   │────▶│ 9. Generate  │
│ Risks        │     │ & Grade    │     │ Suggestions  │
└──────────────┘     └────────────┘     └──────────────┘
```

1. **Load Project Graph** — builds the full application graph.
2. **Compute Metrics** — calculates model/route/query counts, averages, and
   coupling score.
3. **Detect Coupling** — routes with too many models, queries, or hotspot
   models referenced by many routes.
4. **Schema Design** — large models (>20 fields), excessive relations (>8),
   missing indexes.
5. **API Design** — route explosion (>100 routes), deep nesting (>4 segments).
6. **Migration Risks** — high migration churn, recent schema changes.
7. **Performance Risks** — slow queries, N+1 warnings, security diagnostics.
8. **Score & Grade** — penalty-based scoring (A–F grading scale).
9. **Generate Suggestions** — category-specific, deduplicated, sorted by impact.

## Data Models

### ArchitectureMetrics

| Field                  | Type    | Description                        |
|------------------------|---------|------------------------------------|
| `model_count`          | `int`   | Total registered models            |
| `route_count`          | `int`   | Total registered routes            |
| `query_count`          | `int`   | Total traced queries               |
| `migration_count`      | `int`   | Total migrations                   |
| `diagnostic_count`     | `int`   | Total diagnostics                  |
| `avg_models_per_route` | `float` | Average models referenced per route|
| `avg_queries_per_route`| `float` | Average queries per route          |
| `coupling_score`       | `float` | Overall coupling score (0–1)       |

### ArchitectureFinding

| Field           | Type        | Description                          |
|-----------------|-------------|--------------------------------------|
| `id`            | `str`       | Unique finding identifier            |
| `severity`      | `str`       | `critical`, `error`, `warning`, `info` |
| `title`         | `str`       | Short finding title                  |
| `description`   | `str`       | Detailed explanation                 |
| `related_nodes` | `list[str]` | Related graph nodes                  |
| `category`      | `str`       | Finding category (see below)         |

**Categories**: `coupling`, `complexity`, `performance`, `schema_design`,
`api_design`, `migration_risk`, `security`.

### ArchitectureSuggestion

| Field             | Type        | Description                        |
|-------------------|-------------|------------------------------------|
| `suggestion_id`   | `str`       | Unique suggestion identifier       |
| `title`           | `str`       | Short suggestion title             |
| `description`     | `str`       | Detailed improvement advice        |
| `impact`          | `str`       | `high`, `medium`, `low`           |
| `related_findings`| `list[str]` | Finding IDs this addresses         |

### ArchitectureReport

| Field              | Type                       | Description                |
|--------------------|----------------------------|----------------------------|
| `ok`               | `bool`                     | Whether the review ran     |
| `score`            | `int`                      | Health score (0–100)       |
| `grade`            | `str`                      | Letter grade (A–F)         |
| `findings`         | `list[ArchitectureFinding]` | Detected issues           |
| `suggestions`      | `list[ArchitectureSuggestion]` | Improvement suggestions |
| `metrics`          | `ArchitectureMetrics`      | Computed metrics           |
| `finding_count`    | `int`                      | Number of findings         |
| `suggestion_count` | `int`                      | Number of suggestions      |
| `elapsed_ms`       | `float`                    | Pipeline duration in ms    |
| `generated_at`     | `str`                      | ISO 8601 timestamp         |

## Scoring

The scoring engine starts at **100** and applies penalties per finding:

| Finding Type        | Penalty |
|---------------------|---------|
| High coupling       | −10     |
| Missing index       | −10     |
| Slow query          | −15     |
| Large model         | −5      |
| Route explosion     | −10     |
| Deep nesting        | −5      |
| Migration churn     | −5      |
| N+1 query           | −15     |
| Security issue      | −10     |

**Grading scale**: A (90–100), B (80–89), C (70–79), D (60–69), F (<60).

## Studio UI

The Architecture Review panel is available in the Aksara Studio at the
**Architecture** tab. Click **Run Review** to trigger an analysis.

The panel shows:
- **Score card** with letter grade and colour coding
- **Metrics grid** with model/route/query counts
- **Findings tab** with severity badges and category labels
- **Suggestions tab** with impact indicators

## CLI

```bash
# Run architecture review (text output)
aksara ai flows review

# JSON output
aksara ai flows review --json

# Summary only (compact)
aksara ai flows review --summary

# Show metrics
aksara ai flows review --metrics

# JSON summary
aksara ai flows review --json --summary
```

## Console Integration

The Interactive AI Console recognises architecture review intents:

```
> review my architecture
> how healthy is my system
> architecture analysis
> check anti-patterns
> coupling analysis
> refactoring advice
> design review
> health check
```

## API Endpoint

```
POST /studio/ai/architecture-review
```

Returns the full `ArchitectureReport` as JSON.
