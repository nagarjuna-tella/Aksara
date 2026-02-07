# Agent Mode

> *v0.5.19 — Build LLM-ready system prompts from project context.*

Agent Mode gathers structured context from your entire Aksara project and
assembles it into a system prompt that any LLM can consume. It covers
models, routes, migrations, diagnostics, AI profiles, AI hints, DB
queries, and schema checksums — all in one shot.

---

## Quick Start

### Studio UI

Press **8** to open the Agent panel, select the context sections you need,
type a goal, and click **Generate Prompt** (or press **⌘G / Ctrl+G**).

### CLI

```bash
# See all available context sections
aksara agent context --summary

# Generate a prompt for a specific goal
aksara agent prompt --goal "Add a paginated /api/orders endpoint"

# Filter to only model + route context, output JSON
aksara agent prompt --goal "Audit permissions" \
  --sections models,routes --format json
```

### Python API

```python
from aksara.studio.utils import build_agent_context, build_agent_prompt
from aksara.studio.models import StudioAgentPromptRequest

# Gather full context
context = await build_agent_context(app)

# Build a prompt
request = StudioAgentPromptRequest(
    goal="Refactor the User model to add email verification",
    selected_sections=["models", "migrations", "diagnostics"],
)
response = build_agent_prompt(request, context)

print(response.system_prompt)
print(f"Model: {response.recommended_model}")
print(f"Temperature: {response.recommended_temperature}")
print(f"Estimated tokens: {response.tokens_estimate}")
```

---

## Context Sections

| Key | Title | Description |
|-----|-------|-------------|
| `project_info` | Project Info | App name, version, environment, debug flag |
| `models` | Models | Registered models with fields and relations |
| `routes` | Routes | All API endpoints with methods |
| `migrations` | Migrations | Per-app migration status |
| `diagnostics` | Diagnostics | Latest self-diagnostics report |
| `ai_profiles` | AI Profiles | Configured providers and models |
| `ai_hints` | AI Hints | Per-route risk levels and example prompts |
| `db_queries` | DB Queries | Recent query stats and slow-query counts |
| `schema_checksum` | Schema Checksum | SHA-256 fingerprint of current schema |

---

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/studio/agent/context` | Returns `StudioAgentContext` |
| `POST` | `/studio/agent/prompt` | Accepts `StudioAgentPromptRequest`, returns `StudioAgentPromptResponse` |

Both endpoints share the same `verify_studio_origin` security as all
other Studio endpoints.

---

## CLI Commands

### `aksara agent context`

| Flag | Description |
|------|-------------|
| `--sections`, `-s` | Comma-separated section keys to include |
| `--output`, `-o` | `pretty` (default) or `json` |
| `--summary` | Show only section titles and sizes |
| `--size` | Show total size in KB |

### `aksara agent prompt`

| Flag | Description |
|------|-------------|
| `--goal`, `-g` | **(required)** What the agent should accomplish |
| `--sections`, `-s` | Comma-separated section keys |
| `--custom-system-prompt`, `-c` | Custom prefix prepended to the prompt |
| `--format`, `-f` | `text` (default) or `json` |

---

## Temperature & Model Selection

- **Temperature** defaults to `0.5`. It drops to `0.3` when:
  - Any selected `ai_hints` section reports `high_risk_count > 0`
  - The `diagnostics` section has `errors > 0`
- **Model** defaults to `gpt-4o`. If an AI profile with `client_ready: true`
  is configured, the first ready model is recommended instead.
