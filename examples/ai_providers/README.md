# AI Providers Example

Demonstrates how to wire Aksara's AI contracts to popular LLM providers without adding hard dependencies.

## Overview

This package shows the **adapter pattern** for BYO (Bring Your Own) LLM integration:

- **Protocol-based interface** — `LlmClient` protocol with `complete()` and `chat()` methods
- **Three provider adapters** — OpenAI, Azure OpenAI, Anthropic
- **Soft SDK imports** — Provider SDKs are optional; clear errors when missing
- **Prompt building from AI metadata** — Uses `@ai_route_hint` decorators
- **Settings from environment** — All secrets via env vars, never hardcoded

## AI Metadata in This Example

The `DemoPost` model demonstrates all three AI metadata attributes:

| Attribute | Used On | Effect |
|-----------|---------|--------|
| `ai_description` | Every field | Appears in AI Console context and MCP tool catalog |
| `ai_sensitive=True` | `author_email` | Excluded from AI context and `/ai/tools/mcp` exports |
| `ai_agent_writable=False` | `is_featured` | AI agents can read but cannot modify this field |

These attributes flow through to:
- `/ai/tools` — AI tools discovery endpoint
- `/ai/tools/mcp` — MCP (Model Context Protocol) tool catalog for AI agents
- Studio AI Console — context provided to the interactive AI assistant

## How to Use in Your Project

### 1. Copy the adapters

```bash
# Copy adapters.py to your project
cp examples/ai_providers/adapters.py your_project/ai_adapters.py
```

### 2. Install a provider SDK

```bash
pip install openai       # For OpenAI / Azure OpenAI
pip install anthropic    # For Anthropic Claude
```

### 3. Set environment variables

```bash
# .env
OPENAI_API_KEY=sk-...
AI_DEFAULT_PROVIDER=openai
```

### 4. Use in your views

```python
from your_project.ai_adapters import get_llm_client_from_settings
from aksara.ai.providers import AiModelProfile

client = get_llm_client_from_settings(settings)
profile = AiModelProfile(model_name="gpt-4o-mini", model_kind="chat", provider="openai")

response = await client.complete("Summarize this post.", model=profile)
```

## Module Structure

| File | Purpose |
|------|---------|
| `adapters.py` | `LlmClient` protocol + OpenAI/Azure/Anthropic adapters |
| `prompting.py` | Prompt builders using `AiRouteHint` metadata |
| `settings.py` | Environment-based provider configuration |
| `views.py` | Example ViewSet with AI-powered actions |
| `main.py` | App entry point |

## Supported Providers

| Provider | SDK | Env Vars Required |
|----------|-----|-------------------|
| OpenAI | `openai` | `OPENAI_API_KEY` |
| Azure OpenAI | `openai` | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT` |
| Anthropic | `anthropic` | `ANTHROPIC_API_KEY` |

## Example AI Actions

The `DemoPostViewSet` includes three AI-powered actions:

1. **`ai_suggest_tags`** — Analyze post content and suggest tags
2. **`ai_generate_summary`** — Create a concise summary
3. **`ai_analyze`** — Full content analysis (readability, topics, suggestions)

Each uses `@ai_route_hint` to document the action for AI agents.

## MCP Integration

When Aksara's AI Mode is enabled, the `DemoPost` model and its ViewSet actions are automatically exported as MCP tools at `/ai/tools/mcp`. Any MCP-compatible AI agent (Claude, Cursor, etc.) can discover and call these tools.

The `ai_sensitive` and `ai_agent_writable` metadata flows into the MCP tool schema, so agents know which fields they can/cannot read or write — no second schema required.
