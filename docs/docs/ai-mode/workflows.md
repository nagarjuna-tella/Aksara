# Agent Workflows

!!! warning "Experimental development surface"
    This analysis, provider or Studio surface is outside the stable backend
    contract. Review its outputs and application integration before use. It is
    not required for REST, synchronous MCP or Durable Operations. See
    [stability labels](../concepts/stability.md).

Agent Workflows transform a free-text goal into a **structured,
step-by-step execution plan** that combines diagnostics, search,
inspectors, and playbooks into a single ordered timeline. Nothing is
auto-mutated — the workflow is a plan the developer (or an LLM) can
review, approve, and execute incrementally.

---

## Concepts

| Term | Description |
|------|-------------|
| **Workflow** | An ordered list of steps derived from a goal |
| **Step** | A single actionable item with kind, title, commands, risk, and effort |
| **Step Kind** | One of: `inspect`, `search`, `edit_file`, `run_migration`, `run_query`, `run_test`, `environment`, `config`, `diagnostics`, `doc_reading` |
| **Source** | Where the steps came from: `doctor` (diagnostics only), `search`, `manual`, or `mixed` |

### How It Differs from Other Features

| Feature | Purpose |
|---------|---------|
| **Doctor Fix-Plan** | Diagnose and suggest fixes for known issues |
| **Playbooks** | Step-by-step recipes for a single task category |
| **Agent Context** | Gather project context for an LLM prompt |
| **Workflows** | Combine all of the above into one ordered plan |

---

## Quick Start

### Studio UI

1. Open the Agent panel (press **8** in Studio).
2. Type a goal in the text area (e.g. "Fix slow queries on /api/posts/").
3. Toggle **Include diagnostics** / **Include search** checkboxes as needed.
4. Click **Generate Workflow**.
5. Switch to the **Workflow** tab to see the plan.

Each step shows its **kind**, **risk** level, **estimated effort**,
suggested commands (with copy buttons), and notes.

### CLI

```bash
# Basic workflow
aksara agent workflow "Fix slow queries on /api/posts/"

# With a playbook
aksara agent workflow "Add email to User model" --playbook add_field_to_model

# Skip diagnostics
aksara agent workflow "Refactor auth" --no-diagnostics

# JSON output (for piping to LLMs)
aksara agent workflow "Fix login" --format json
```

### Python API

```python
from aksara.ai.workflows import (
    build_agent_workflow,
    summarize_agent_workflow,
    workflow_stats,
)

wf = build_agent_workflow(
    "Fix slow queries on /api/posts/",
    include_diagnostics=True,
    include_search=True,
    search_query="slow query posts",
)

print(summarize_agent_workflow(wf))
print(workflow_stats(wf))

for step in wf.steps:
    print(f"[{step.order}] {step.kind}: {step.title}")
    for cmd in step.commands:
        print(f"  $ {cmd}")
```

---

## Step Kinds Reference

| Kind | Emoji | Description |
|------|-------|-------------|
| `inspect` | 🔍 | Model or query inspection |
| `search` | 🔎 | Semantic search across project artifacts |
| `edit_file` | ✏️ | Edit a source file |
| `run_migration` | 🗃️ | Generate or run a migration |
| `run_query` | 📊 | Execute or analyse a query |
| `run_test` | 🧪 | Run the test suite |
| `environment` | ⚙️ | Environment or dependency setup |
| `config` | 🔧 | Configuration change |
| `diagnostics` | 🩺 | Run diagnostic checks |
| `doc_reading` | 📖 | Read documentation |

---

## Workflow Builder Pipeline

The builder assembles steps in a deterministic order:

1. **Diagnostics** (order 1–49) — Runs `aksara doctor` checks and
   converts issues + auto-remediation actions into steps.
2. **Inspectors** (order 50–99) — Always adds model inspection;
   conditionally adds query inspection if the goal mentions queries.
3. **Search** (order 100–199) — Builds the semantic index and searches
   for relevant artifacts, generating kind-specific commands.
4. **Playbook** (order 200–299) — If a playbook key is provided,
   converts playbook steps into workflow steps.
5. **Test** (order 300) — Always appends a final "run tests" step.

### Risk & Effort

- **Risk** is derived from diagnostic severity (`error` → high,
  `warning` → medium, `info` → low) or playbook risk level.
- **Effort** is inferred from step kind (`run_migration` and `edit_file`
  → high; `run_query` and `config` → medium; everything else → low).

---

## Studio API

### `POST /studio/agent/workflow`

Generate a workflow from a goal.

**Request body** (`AgentWorkflowRequest`):

```json
{
  "goal": "Fix slow queries on /api/posts/",
  "playbook": null,
  "include_diagnostics": true,
  "include_search": true,
  "search_query": null,
  "limit_search_results": 10,
  "limit_diagnostics": 10
}
```

**Response** (`AgentWorkflowResponse`):

```json
{
  "workflow": {
    "id": "wf-abc123",
    "goal": "Fix slow queries on /api/posts/",
    "playbook": null,
    "source": "mixed",
    "steps": [ ... ],
    "metadata": { ... }
  },
  "summary": "Workflow for \"Fix slow queries on /api/posts/\" with 5 steps...",
  "stats": {
    "total_steps": 5,
    "by_kind": { "inspect": 2, "search": 1, "run_test": 1, "diagnostics": 1 },
    "by_risk": { "low": 3, "medium": 2 },
    "by_effort": { "low": 3, "medium": 2 },
    "has_high_risk": false,
    "source": "mixed"
  }
}
```

### `GET /studio/agent/workflow/sample`

Returns a sample workflow for demonstration purposes.

---

## CLI Reference

```
aksara agent workflow GOAL [OPTIONS]

Arguments:
  GOAL  The goal to build a workflow for

Options:
  --playbook TEXT           Playbook key to include
  --no-diagnostics          Skip diagnostic checks
  --no-search               Skip semantic search
  --search-query TEXT       Override the search query
  --limit-search INT        Max search results (default: 10)
  --limit-diagnostics INT   Max diagnostic issues (default: 10)
  --format [text|json]      Output format (default: text)
```

---

## Models

All models are Pydantic v2 dataclasses exported from `aksara.studio.models`:

- **`AgentWorkflowStep`** — A single step in the plan
- **`AgentWorkflow`** — The complete workflow with steps and metadata
- **`AgentWorkflowRequest`** — Request body for the API endpoint
- **`AgentWorkflowResponse`** — Response with workflow, summary, and stats
- **`AgentWorkflowStepKind`** — Literal type for valid step kinds
