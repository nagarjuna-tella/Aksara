# AI Execution Runtime

The execution runtime sits between AI Flow prompt packs and AI connectors.
It resolves the provider, model, and credentials, then executes the prompt
pack through the appropriate connector.

---

## Overview

```
Prompt Pack  ──►  Runtime  ──►  Connector  ──►  LLM Provider
                                                     │
                                                     ▼
                  Normalised Result  ◄──────────  API Response
```

| Component        | Responsibility |
|------------------|----------------|
| **Prompt Pack**  | Deterministic system + user prompt (from AI Flows) |
| **Runtime**      | Provider/model resolution, connector dispatch, error handling |
| **Connector**    | HTTP transport to the LLM API |

---

## Core API

### `run_prompt_pack()`

```python
from aksara.ai.runtime import run_prompt_pack

result = await run_prompt_pack(
    pack=prompt_pack_dict,
    provider_override="anthropic",     # optional
    model_override="claude-3-5-sonnet-20241022",  # optional
)
```

**Parameters:**

| Param              | Type   | Description |
|--------------------|--------|-------------|
| `pack`             | dict   | A prompt pack (from `StudioAiFlowResponse.model_dump()`) |
| `provider_override`| str?   | Override auto-detected provider |
| `model_override`   | str?   | Override auto-detected model |

**Returns:**

```json
{
    "ok": true,
    "provider": "configured-provider",
    "model": "configured-model",
    "response": "The User model has 5 fields...",
    "tokens": {"prompt": 20, "completion": 50, "total": 70},
    "elapsed_ms": 150.0,
    "error": null
}
```

---

## Resolution Order

The runtime resolves provider and model in this order:

1. **Explicit overrides** — `provider_override` / `model_override` args
2. **Pack metadata** — `pack["provider"]` / `pack["model"]`
3. **AI Hub defaults** — loaded from `aihub.json` settings
4. **Fallback defaults** — the connector's provider-specific default model

---

## Flow Execution

The runtime powers the `execute_flow()` family of functions in
`aksara/studio/ai_flows.py`:

```python
from aksara.studio.ai_flows import execute_model_flow

result = await execute_model_flow("User", "explain_model")
# result = {"ok": True, "prompt_pack": {...}, "execution": {...}}
```

### Available Functions

| Function                    | Description |
|-----------------------------|-------------|
| `execute_flow()`            | Generic dispatcher for any flow type |
| `execute_model_flow()`      | Execute a model action |
| `execute_route_flow()`      | Execute a route action |
| `execute_query_flow()`      | Execute a query action |
| `execute_migration_flow()`  | Execute a migration action |
| `execute_diagnostic_flow()` | Execute a diagnostic action |

---

## API Endpoint

```
POST /studio/ai/flows/run
```

**Request body:**

```json
{
    "flow_type": "model",
    "action_key": "explain_model",
    "context": {"model_name": "User"},
    "provider_override": null,
    "model_override": null
}
```

**Response:**

```json
{
    "ok": true,
    "prompt_pack": { "...": "..." },
    "execution": {
        "ok": true,
        "provider": "configured-provider",
        "model": "configured-model",
        "response": "...",
        "tokens": {"prompt": 20, "completion": 50, "total": 70},
        "elapsed_ms": 150.0
    }
}
```

---

## CLI

```bash
# Execute a model action
aksara ai run model User --action explain_model

# With provider/model overrides
aksara ai run model User --action explain_model --provider anthropic --model claude-3-5-sonnet-20241022

# JSON output
aksara ai run query --sql "SELECT 1" --action explain_plan --format json
```

---

## Safety

The runtime **never modifies code automatically**.  It only returns analysis,
suggestions, and explanations.  If code changes are suggested, they are presented
as CLI commands or snippets for the developer to review and apply manually.
