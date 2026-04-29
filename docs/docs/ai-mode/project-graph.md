# Project Context Graph

The **Project Context Graph** is a structured representation of your entire
application — models, routes, queries, migrations, diagnostics, gap analysis
results, AI Hub configuration, and AI flow actions — assembled into a single
read-only data structure.  It gives the AI engine the full picture of your
project so it can reason about: application structure, dependencies, related
failures, likely causes, recent changes, and issue prioritisation.

## Quick Start

```python
from aksara.ai.project_graph import build_project_graph

# Cached for 5 seconds
graph = build_project_graph()

# Force a fresh rebuild
graph = build_project_graph(rebuild=True)

# Serialise
full  = graph.to_dict()
short = graph.to_summary_dict()
text  = graph.to_console_context()
```

## Architecture

```
┌──────────────┐     ┌───────────────┐     ┌────────────────┐
│  ModelRegistry│────▸│  project_graph │────▸│  graph_context  │
│  DB Tracing   │     │  (collector    │     │  (AI-friendly   │
│  Migrations   │     │   heuristics   │     │   payloads)     │
│  Diagnostics  │     │   + cache)     │     └────────────────┘
│  Gap Analysis │     └───────────────┘              │
│  AI Hub       │            ▲                       ▼
│  AI Flows     │            │               ┌──────────────┐
│  Graph Events │────────────┘               │ Console / CLI │
└──────────────┘                             │ Studio UI     │
                                             │ LLM Prompts   │
                                             └──────────────┘
```

### Core Modules

| Module | Purpose |
|--------|---------|
| `aksara.ai.project_graph` | Graph data models, builder, 9 collectors, heuristics, cache |
| `aksara.ai.graph_events`  | Lightweight in-memory event timeline (bounded deque, max 500) |
| `aksara.ai.graph_context`  | Transforms ProjectGraph into AI-friendly payloads |

## Node Types

The graph contains these node types:

- **ModelNode** — Registered models with fields, indexes, and FK relations
- **RouteNode** — HTTP routes with heuristic model linking
- **QueryNode** — Recent DB queries from tracing (if enabled)
- **MigrationNode** — Discovered migrations with inferred model touches
- **DiagnosticNode** — Issues from the last diagnostic report
- **GapNode** — Gap analysis results (security, performance, etc.)
- **AiHubNode** — AI provider configuration and status
- **AiFlowNode** — Registered AI flow actions

## Event Timeline

The event timeline records significant system events for AI correlation:

```python
from aksara.ai.graph_events import emit_graph_event, get_recent_graph_events

# Emit an event
emit_graph_event(
    "route_error", "route", "/api/users",
    severity="error",
    message="500 on GET /api/users",
    status_code=500,
)

# Retrieve recent events
events = get_recent_graph_events(limit=50)
```

### Event Kinds

| Kind | Emitted By |
|------|-----------|
| `route_error` | Route error handlers |
| `query_timeout` | DB tracing |
| `slow_query_detected` | DB tracing |
| `migration_applied` | Migration executor |
| `migration_failed` | Migration executor |
| `provider_unreachable` | AI runtime |
| `diagnostic_issue_detected` | Diagnostics engine |
| `gap_report_changed` | Gap analysis |
| `console_execution_failed` | Console engine |
| `ai_flow_executed` | AI flow executor |

## Context Builders

Four context builders transform the graph for different consumers:

```python
from aksara.ai.graph_context import (
    build_graph_summary_context,    # UI summary cards
    build_graph_console_context,    # Console prompts (with flow_type emphasis)
    build_graph_debug_context,      # Debug sessions
    build_graph_prompt_section,     # Formatted text for LLM prompts
)
```

## Studio Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /studio/ai/project-graph` | Full graph or summary (`?summary=true`, `?rebuild=true`) |
| `GET /studio/ai/project-graph/events` | Recent events (`?limit=N`) |
| `GET /studio/ai/project-graph/summary` | Compact summary for UI |

## CLI

```bash
# Text summary (default)
aksara ai graph

# Compact summary
aksara ai graph --summary

# Full JSON output
aksara ai graph --json

# Recent events only
aksara ai graph --events

# Force cache bypass
aksara ai graph --rebuild
```

## Graph Explorer UI

The Studio UI includes an **AI Graph Explorer** page accessible from the
sidebar navigation.  It displays:

- **Counts grid** — Model, route, query, diagnostic counts at a glance
- **Tabbed panels** — Models, Routes, Queries, Diagnostics, Migrations,
  Events, and Relationships
- **Rebuild button** — Force a fresh graph build
- **Use in Console** — Jump to the AI Console with graph context pre-loaded

## Console Integration

When a user submits a query to the AI Console, the console engine
automatically injects graph context into the prompt:

1. After context enrichment, `build_graph_console_context()` is called
   with the detected `flow_type`
2. The graph payload is added to the context as `_graph`
3. After execution, a graph event is emitted (`ai_flow_executed` or
   `console_execution_failed`)

This means the AI can reference the project structure, recent events,
and diagnostic issues when answering questions.

## Caching

The graph is cached for **5 seconds** by default.  The cache is
thread-safe and can be bypassed with `rebuild=True`.  The cache is
automatically invalidated when `_invalidate_cache()` is called.

## Safety

- The graph is **read-only** — it never modifies code, database, or
  configuration
- Event emission **never breaks** the main action — all hooks are
  wrapped in try/except
- The bounded deque ensures memory usage stays constant (max 500 events)
