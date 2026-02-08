# Inspectors

> **v0.5.21** — Query & Model Inspector

The **Inspectors** module provides deep introspection tools for analyzing your database schema and query performance.

## Modules

- **[Query Inspector](query.md)** — EXPLAIN plan generation, aggregate query statistics, slow query analysis
- **[Model Inspector](models.md)** — Field metadata, relationship mapping, constraint detection, auto-generated comments

## Usage

Inspectors are available through three interfaces:

| Interface     | Query Inspector                          | Model Inspector                         |
|---------------|------------------------------------------|-----------------------------------------|
| **Python**    | `explain_query()`, `get_query_stats()`   | `inspect_model()`, `inspect_all_models()` |
| **CLI**       | `aksara inspect queries`                 | `aksara inspect models`                 |
| **Studio API**| `POST /studio/db/plan`                   | `GET /studio/models/inspect/{name}`     |
| **Studio UI** | Explain Plan button on slow queries      | Inspector tab (shortcut: `9`)           |
| **Agent**     | `query_stats` context section            | `schema_analysis` context section       |

## Package

```python
from aksara.inspectors import (
    # Query Inspector
    QueryPlanRequest,
    QueryPlanResult,
    QueryStats,
    explain_query,
    get_query_stats,
    # Model Inspector
    ModelInspectorField,
    ModelInspectorRelationship,
    ModelInspectorConstraint,
    ModelInspectorSummary,
    inspect_model,
    inspect_all_models,
)
```
