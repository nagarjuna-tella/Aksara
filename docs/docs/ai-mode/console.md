# Interactive AI Console

!!! warning "Experimental development surface"
    This analysis, provider or Studio surface is outside the stable backend
    contract. Review its outputs and application integration before use. It is
    not required for REST, synchronous MCP or Durable Operations. See
    [stability labels](../concepts/stability.md).

The **Interactive AI Console** is the first AI-native development surface inside
Aksara Studio.  Developers type natural-language commands — like
*"explain the User model"* — and the console automatically detects intent,
builds context, routes to the correct AI Flow, executes via the runtime, and
returns a structured result.

## Quick Start

### Studio UI

1. Open **Aksara Studio** → click **AI Console** in the sidebar (or press
   <kbd>Ctrl+I</kbd> / <kbd>Cmd+I</kbd>).
2. Type a command in the input box, e.g. `explain the User model`.
3. Press <kbd>Enter</kbd> to send.
4. Review the AI response and follow suggested next actions.

### CLI

```bash
aksara ai chat "explain the User model"
aksara ai chat "review GET /api/users" --format json
aksara ai chat "suggest indexes" --provider <provider> --model <model-name>
```

Use any provider and model combination that your AI setup supports.

### HTTP API

```bash
# Send a console query
curl -X POST http://localhost:8000/studio/ai/console \
  -H "Content-Type: application/json" \
  -d '{"message": "explain the User model"}'

# Get autocomplete suggestions
curl "http://localhost:8000/studio/ai/console/suggest?q=explain"
```

## Architecture

```
User input
    │
    ▼
┌─────────────────┐
│  Intent Router   │  — rule-based pattern matching, no LLM call
│  (intent_router) │
└────────┬────────┘
         │ IntentMatch(intent, flow_type, action_key, confidence, context)
         ▼
┌─────────────────┐
│ Context Builder  │  — enriches with registry data (models, routes, etc.)
│ (console_context)│
└────────┬────────┘
         │ enriched context dict
         ▼
┌─────────────────┐
│  Console Engine  │  — orchestrates the full pipeline
│ (console_engine) │
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌──────────┐
│AI Flow │ │ Runtime   │  — builds prompt pack → executes via connector
│Builder │ │(run_pack) │
└────────┘ └──────────┘
```

## Supported Intents

The console recognises 11 intents, one for each AI Flow action:

| Intent | Flow Type | Example Command |
|--------|-----------|----------------|
| `explain_model` | model | "Explain the User model" |
| `suggest_constraints` | model | "Suggest constraints for Order" |
| `refactor_suggestions` | model | "Refactor the Product model" |
| `review_endpoint` | route | "Review GET /api/users" |
| `harden_permissions` | route | "Harden permissions on POST /api/admin" |
| `generate_examples` | route | "Generate example requests for GET /api/products" |
| `explain_plan` | query | "Explain the query plan" |
| `suggest_indexes` | query | "Suggest indexes" |
| `rewrite_suggestions` | query | "Rewrite query for performance" |
| `explain_migration` | migration | "Explain migration impact" |
| `safe_rollout_plan` | migration | "Safe rollout plan for migration" |
| `diagnostic_prioritize` | diagnostic | "Prioritize diagnostic issues" |

## Response Shape

All console responses follow this structure:

```json
{
  "ok": true,
  "intent": "explain_model",
  "flow_type": "model",
  "action_key": "explain_model",
  "confidence": 0.91,
  "extracted_context": {"model_name": "User"},
  "prompt_pack": { "..." },
  "execution": {
    "ok": true,
    "provider": "configured-provider",
    "model": "configured-model",
    "response": "The User model has 5 fields...",
    "tokens": {"prompt": 20, "completion": 50, "total": 70},
    "elapsed_ms": 1234.5
  },
  "suggestions": ["suggest_constraints", "refactor_suggestions"],
  "elapsed_ms": 1500.0,
  "error": null,
  "error_code": null
}
```

## Safety

The AI Console follows Aksara's core safety rule:

> **AI suggests, developer confirms.**

The console will **never**:

- Auto-modify source code
- Execute migrations
- Apply database changes
- Introduce autonomous agents

All output is analysis, suggestions, and explanations that the developer
reviews before taking any action.

## Command Suggestions

The console provides autocomplete suggestions as you type.  The suggestion
system is entirely local — no LLM calls are made for suggestions.

Suggestions are available via:

- **Studio UI**: typing in the console input field
- **API**: `GET /studio/ai/console/suggest?q=prefix`

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| <kbd>Ctrl+I</kbd> / <kbd>Cmd+I</kbd> | Open AI Console |
| <kbd>Enter</kbd> | Send message |
| <kbd>↑</kbd> / <kbd>↓</kbd> | Navigate history |
| <kbd>Escape</kbd> | Close suggestions |

## Configuration

The AI Console uses the same provider configuration as the AI Hub.
No additional configuration is needed — if AI Hub is configured with a
provider, the console will use it automatically.

To override the provider or model per-request:

```bash
aksara ai chat "explain the User model" --provider anthropic --model claude-3-5-sonnet
```

Or via the API:

```json
{
  "message": "explain the User model",
  "provider_override": "anthropic",
  "model_override": "claude-3-5-sonnet"
}
```
