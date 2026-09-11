# AI Debugger

!!! warning "Experimental development surface"
    This analysis, provider or Studio surface is outside the stable backend
    contract. Review its outputs and application integration before use. It is
    not required for REST, synchronous MCP or Durable Operations. See
    [stability labels](../concepts/stability.md).

The **AI Debugger** is an automated root-cause analysis engine that examines
your entire application — the Project Graph, event timeline, diagnostics, and
gap analysis — to identify, cluster, and rank issues, then suggest safe fixes.
It is **read-only** and never modifies your code or database.

## Quick Start

```python
from aksara.ai.debugger import run_debugger

report = run_debugger()                    # full analysis
report = run_debugger(query="login fails") # focused analysis

print(report.summary)
for rc in report.root_causes:
    print(f"  [{rc.confidence:.0%}] {rc.title}")
```

## Architecture

The debugger runs a **6-step pipeline**:

```
┌─────────────┐     ┌────────────┐     ┌──────────┐
│ 1. Load      │────▶│ 2. Extract │────▶│ 3. Filter│
│ Project Graph│     │ Issue Pool │     │ by Query  │
└──────────────┘     └────────────┘     └──────────┘
        │                                     │
        ▼                                     ▼
┌──────────────┐     ┌────────────┐     ┌──────────┐
│ 6. Suggest   │◀────│ 5. Rank    │◀────│ 4.Cluster│
│ Safe Fixes   │     │ Root Causes│     │ & Detect │
└──────────────┘     └────────────┘     └──────────┘
```

1. **Load Project Graph** — builds the full application graph (models, routes,
   queries, diagnostics, migrations, events).
2. **Extract Issue Pool** — converts diagnostics, gap items, and error events
   into normalised `DebugIssue` objects.
3. **Filter by Query** — if a query string is provided, keeps only issues
   matching the keywords.
4. **Cluster & Detect** — groups issues by shared component (model, route,
   query) and detects root causes using 6 heuristic patterns.
5. **Rank Root Causes** — scores each root cause by severity, evidence count,
   related clusters, and affected issues.  Confidence is normalised to 0–1.
6. **Suggest Safe Fixes** — generates actionable, category-specific
   suggestions (never auto-applies them).

## Data Models

### DebugIssue

| Field              | Type        | Description                          |
|--------------------|-------------|--------------------------------------|
| `id`               | `str`       | Unique issue identifier              |
| `source`           | `str`       | Origin: `diagnostic`, `gap`, `event` |
| `severity`         | `str`       | `critical`, `error`, `warning`, `info` |
| `title`            | `str`       | Short description                    |
| `message`          | `str`       | Detailed explanation                 |
| `related_models`   | `list[str]` | Affected model names                 |
| `related_routes`   | `list[str]` | Affected route paths                 |
| `related_queries`  | `list[str]` | Affected SQL patterns                |

### IssueCluster

| Field             | Type        | Description                          |
|-------------------|-------------|--------------------------------------|
| `cluster_id`      | `str`       | Unique cluster identifier            |
| `label`           | `str`       | Human-readable cluster name          |
| `component_type`  | `str`       | `model`, `route`, or `query`         |
| `component_name`  | `str`       | Specific component name              |
| `issue_ids`       | `list[str]` | Member issue IDs                     |
| `severity`        | `str`       | Worst severity in the cluster        |

### RootCause

| Field              | Type        | Description                          |
|--------------------|-------------|--------------------------------------|
| `cause_id`         | `str`       | Unique cause identifier              |
| `title`            | `str`       | Root cause title                     |
| `description`      | `str`       | Detailed explanation                 |
| `confidence`       | `float`     | 0.0–1.0 confidence score            |
| `severity`         | `str`       | Worst severity of related issues     |
| `evidence`         | `list[str]` | Supporting evidence strings          |
| `related_issues`   | `list[str]` | Contributing issue IDs               |
| `related_clusters` | `list[str]` | Contributing cluster IDs             |
| `category`         | `str`       | `database`, `migration`, `ai_provider`, `route_errors`, `security`, `general` |
| `fix_suggestions`  | `list[str]` | Safe remediation steps               |

### DebugReport

| Field          | Type             | Description                          |
|----------------|------------------|--------------------------------------|
| `issues`       | `list[DebugIssue]` | All extracted issues               |
| `clusters`     | `list[IssueCluster]` | Grouped clusters                 |
| `root_causes`  | `list[RootCause]`  | Ranked root causes                 |
| `summary`      | `str`            | Human-readable summary               |
| `query`        | `str | None`     | Original query if provided           |
| `elapsed_ms`   | `float`          | Pipeline duration in milliseconds    |
| `generated_at` | `str`            | ISO 8601 timestamp                   |

## Root Cause Detection

The debugger uses 6 heuristic patterns to detect root causes:

| Category         | Detects                                          |
|------------------|--------------------------------------------------|
| `database`       | Multiple DB-related issues (connection, query, tracing) |
| `migration`      | Pending or failed migrations                     |
| `ai_provider`    | AI provider configuration or connectivity issues |
| `route_errors`   | Routes with repeated errors                      |
| `security`       | Security warnings across models                  |
| `general`        | Large clusters suggesting systemic problems      |

## Studio Integration

### API Endpoint

```
POST /studio/ai/debug
Content-Type: application/json

{"query": "login fails"}     # optional
```

Response:

```json
{
  "ok": true,
  "query": "login fails",
  "issues": [...],
  "clusters": [...],
  "root_causes": [...],
  "summary": "Found 12 issues in 4 clusters with 2 root causes.",
  "counts": {"issues": 12, "clusters": 4, "root_causes": 2},
  "elapsed_ms": 42.3,
  "generated_at": "2026-03-01T12:00:00Z"
}
```

### UI Panel

The Studio sidebar includes an **AI Debugger** panel with:

- **Query toolbar** — type a question and click Run
- **Summary grid** — issue, cluster, and root cause counts at a glance
- **4 tabs**: Root Causes, Clusters, Issues, Fix Plan
- Severity colour-coding and confidence badges

## Console Integration

The AI Console recognises debug-related natural language:

```
aksara> debug my app
aksara> why is login failing?
aksara> find bugs in User model
aksara> diagnose database issues
aksara> troubleshoot authentication
```

The intent router maps these to the `debug` flow, which executes the
full debugger pipeline and returns a structured report.

## CLI Command

```bash
# Full analysis
aksara ai flows debug

# Focused analysis
aksara ai flows debug --query "login fails"

# JSON output
aksara ai flows debug --json

# Summary only
aksara ai flows debug --summary

# Filter by model or route
aksara ai flows debug --model User
aksara ai flows debug --route /api/login

# Combine options
aksara ai flows debug --query "auth" --json --summary
```

## Safety Guarantees

The AI Debugger is **read-only by design**:

- Never modifies source code files
- Never alters database state
- Never reconfigures services
- All fix suggestions are informational only
- Users must manually apply any recommended changes

## Best Practices

1. **Start broad, then focus** — run without a query first, then drill down
   with specific queries based on the results.
2. **Check root causes first** — they are ranked by confidence; the top cause
   is most likely the primary issue.
3. **Use the Fix Plan tab** — it groups suggestions by root cause in priority
   order.
4. **Run after changes** — re-run the debugger after applying fixes to verify
   improvement.
5. **Combine with other tools** — use the Project Graph to understand
   relationships and the Event Timeline to see recent changes.
