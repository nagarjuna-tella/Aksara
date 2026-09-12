# Studio AI Flows

!!! warning "Experimental development surface"
    This analysis, provider or Studio surface is outside the stable backend
    contract. Review its outputs and application integration before use. It is
    not required for REST, synchronous MCP or Durable Operations. See
    [stability labels](../concepts/stability.md).

Studio AI Flows bring **in-context AI actions** to every Studio panel.  Select a
model, route, query, migration, or diagnostic issue and run an action — Aksara
builds a deterministic **prompt pack** (system prompt + user prompt) that you can
copy straight into your LLM of choice.

Flows can optionally be *executed* through a configured AI
connector.  Use the **Run AI** button in Studio, the `aksara ai run` CLI, or
the `POST /studio/ai/flows/run` endpoint.  See [Execution Runtime](runtime.md)
and [AI Connectors](connectors.md) for details.

---

## Overview

| Concept       | Description |
|---------------|-------------|
| **Flow**      | A deterministic builder that takes a Studio object + action key and returns a *prompt pack*. |
| **Action**    | A registered operation (e.g. `explain_model`, `suggest_indexes`) with a risk level. |
| **Prompt Pack** | `system_prompt` + `user_prompt` + metadata.  No external API call is made. |
| **Execution** | Optionally send the prompt pack to a connector for real AI analysis. |
| **Risk badge** | Each action is tagged `low`, `medium`, or `high` risk.  Displayed in Studio UI. |

### Architecture rule

> Flows return **prompt packs** — they never call an external LLM API *by default*.
> Execution is **opt-in** via the Run AI button, CLI, or API endpoint.
> The output is deterministic and fully copyable.

---

## Available Actions

### Model Actions

| Key | Risk | Description |
|-----|------|-------------|
| `explain_model` | low | Plain-English explanation of a model's purpose, fields, and relationships |
| `suggest_constraints` | medium | Suggest missing DB constraints, validators, or field improvements |
| `refactor_suggestions` | medium | Propose refactoring/normalisation opportunities |

### Route Actions

| Key | Risk | Description |
|-----|------|-------------|
| `review_endpoint` | low | Auth/permissions, input validation, response shape review |
| `harden_permissions` | medium | Permission-hardening recommendations |
| `generate_examples` | low | Generate example request/response pairs |

### Query Actions

| Key | Risk | Description |
|-----|------|-------------|
| `explain_plan` | low | Explain the query execution plan in plain English |
| `suggest_indexes` | medium | Suggest indexes that could improve performance |
| `rewrite_suggestions` | medium | Propose query rewrites for readability or performance |

### Migration Actions

| Key | Risk | Description |
|-----|------|-------------|
| `explain_migration` | low | Explain what a migration does and its impact |
| `safe_rollout_plan` | medium | Provide a safe rollout / rollback plan |

### Diagnostic Actions

| Key | Risk | Description |
|-----|------|-------------|
| `diagnostic_prioritize` | low | Explain, triage, and prioritise diagnostic issues |

---

## Studio UI

AI Flow buttons appear in each section header (Models, Routes, DB Queries,
Migrations, Diagnostics).  Buttons are **disabled** until the AI Hub is
configured.

Clicking an action opens the **AI Flow Panel** — a slide-over with three tabs:

| Tab | Contents |
|-----|----------|
| **Result** | Rendered markdown result + Copy + CLI command |
| **Prompt Pack** | System prompt and User prompt (both copyable) |
| **Raw JSON** | Full response JSON (copyable) |

**Keyboard shortcuts:**

- `Shift+A` — Navigate to AI Hub
- `Escape` — Close the AI Flow panel

---

## API Endpoints

### List actions

```
GET /studio/ai/flows/actions
```

Returns `StudioAiFlowActionsResponse` with all registered actions.

### Run a flow

```
POST /studio/ai/flows/model
POST /studio/ai/flows/route
POST /studio/ai/flows/query
POST /studio/ai/flows/migration
POST /studio/ai/flows/diagnostic
```

Each accepts a JSON body with `action_key` plus context-specific fields.
Returns `StudioAiFlowResponse`.

#### Example — Model flow

```bash
curl -X POST http://localhost:8000/studio/ai/flows/model \
  -H "Content-Type: application/json" \
  -d '{"action_key": "explain_model", "model_name": "User"}'
```

#### Response shape

```json
{
  "ok": true,
  "action_key": "explain_model",
  "risk": "low",
  "provider": "configured-provider",
  "model": "configured-model",
  "system_prompt": "...",
  "user_prompt": "...",
  "result_markdown": "**Prompt pack ready** ...",
  "result_json": { "model_name": "User", "action": "explain_model" },
  "suggested_next": ["suggest_constraints"],
  "what_it_does": "Generates a plain-English explanation ...",
  "what_it_cannot_do": "Cannot modify the database ...",
  "error_code": null,
  "error": null
}
```

---

## CLI

All flows are also available via the CLI:

```bash
# List all actions
aksara ai flows actions
aksara ai flows actions --format json

# Run flows
aksara ai flows model User --action explain_model
aksara ai flows route GET:/api/users --action review_endpoint
aksara ai flows query --sql "SELECT * FROM users" --action explain_plan
aksara ai flows migration --app blog --action explain_migration
aksara ai flows diagnostic --issue-id d-001 --action diagnostic_prioritize

# JSON output
aksara ai flows model User --action explain_model --format json
```

---

## Creating Custom Actions

The action registry lives in `aksara/studio/ai_flows.py`:

```python
AI_FLOW_ACTIONS = {
    "my_action": {
        "kind": "model",           # model | route | query | migration | diagnostic
        "title": "My Custom Action",
        "description": "What this action does",
        "risk": "low",             # low | medium | high
        "what_it_does": "...",
        "what_it_cannot_do": "...",
        "recommended_next": ["suggest_constraints"],
    },
}
```

Then add a matching system prompt in `_SYSTEM_PROMPTS` and the builder will
pick it up automatically.
