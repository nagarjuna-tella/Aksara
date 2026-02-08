# Agent Mode

> *v0.5.19 — Build LLM-ready system prompts from project context.*
> *v0.5.20 — Agent Playbooks: reusable recipes for common tasks.*

Agent Mode gathers structured context from your entire Aksara project and
assembles it into a system prompt that any LLM can consume. It covers
models, routes, migrations, diagnostics, AI profiles, AI hints, DB
queries, and schema checksums — all in one shot.

**Playbooks** (v0.5.20) are opinionated, step-by-step recipes that
pre-configure the goal, context sections, and prompt structure for common
development tasks like adding a field, fixing migrations, or hardening
permissions.

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

---

## Playbooks (v0.5.20)

Playbooks are pre-built recipes for common LLM-assisted tasks. Each
playbook defines a kind, category, risk level, default goal template,
recommended context sections, and ordered steps.

### Built-in Playbooks

| Key | Label | Category | Risk | Usage |
|-----|-------|----------|------|-------|
| `add_field_to_model` | Add Field to Model | schema | medium | write |
| `add_api_action_to_viewset` | Add API Action | api | medium | write |
| `fix_migration_conflicts` | Fix Migration Conflicts | migrations | high | admin |
| `add_validation_rule` | Add Validation Rule | schema | low | write |
| `harden_endpoint_permissions` | Harden Permissions | api | medium | admin |
| `debug_slow_queries` | Debug Slow Queries | diagnostics | low | read_only |
| `refactor_model_and_serializer` | Refactor Model & Serializer | schema | medium | write |

### Studio UI

Press **Shift+P** to jump to the playbook search. Click a playbook card
to auto-prefill the goal template and select recommended sections, then
click **Generate Prompt**. Use the category filter pills or search to
narrow the list.

### CLI

```bash
# List all playbooks
aksara agent playbooks

# Filter by category
aksara agent playbooks --category schema

# Run a playbook
aksara agent playbook-run add_field_to_model \
  --goal "Add an email field to the User model"

# Run with JSON output
aksara agent playbook-run debug_slow_queries -f json
```

### Python API

```python
from aksara.ai.playbooks import get_builtin_playbooks, get_playbook_by_key
from aksara.studio.utils import build_agent_prompt_from_playbook

# List all playbooks
playbook_set = get_builtin_playbooks()
print(playbook_set.total_count)  # 7

# Filter by category
schema_playbooks = get_builtin_playbooks(category="schema")

# Get a specific playbook and generate a prompt
playbook = get_playbook_by_key("add_field_to_model")
context = await build_agent_context(app)
response = build_agent_prompt_from_playbook(
    playbook=playbook,
    user_goal="Add a verified_at timestamp to User",
    selected_sections=None,  # use playbook defaults
    custom_system_prompt=None,
    context=context,
)
print(response.system_prompt)
```

### Playbooks Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/studio/agent/playbooks` | List playbooks (supports `?category=`, `?risk_level=`, `?usage_kind=` filters) |
| `POST` | `/studio/agent/playbooks/prompt` | Generate playbook-driven prompt |

### CLI Commands

#### `aksara agent playbooks`

| Flag | Description |
|------|-------------|
| `--format`, `-f` | `pretty` (default) or `json` |
| `--category`, `-c` | Filter by category |
| `--risk`, `-r` | Filter by risk level |
| `--usage`, `-u` | Filter by usage kind |

#### `aksara agent playbook-run <KEY>`

| Flag | Description |
|------|-------------|
| `--goal`, `-g` | Override the playbook's default goal template |
| `--sections`, `-s` | Comma-separated section keys (default: playbook defaults) |
| `--format`, `-f` | `text` (default) or `json` |
