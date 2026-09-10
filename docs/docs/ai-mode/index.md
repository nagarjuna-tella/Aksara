# AI Mode

!!! warning "Experimental in v0.6"
    AI Console, AI Flows, investigation sessions, analysis engines, planners,
    provider-specific live calls, and autonomous runtimes are experimental.
    Session state is process-local: restart persistence and multi-worker
    continuity are not guaranteed. Keep human approval and application
    authorization around mutations.

AI Mode is the optional AI layer of an Aksara application. It powers Studio's
AI features, exposes generated tools through MCP, and adds analysis surfaces
such as Schema Doctor, AI Debugger, Architecture Review, and Performance
Analyzer.

---

## Start Here

Use this section in the same order you would adopt the features in a real project:

| Goal | Read First | Then Continue With |
|------|------------|--------------------|
| Explore your app in Studio | [Interactive Console](console.md) | [AI Flows](flows.md), [AI Debugger](debugger.md), [Architecture Review](architecture-review.md), [Performance Analyzer](performance-analyzer.md) |
| Adapt an external AI client | [MCP Integration](mcp.md) | [Tools](tools.md), [Providers](providers.md), [AI Connectors](connectors.md) |
| Automate larger tasks | [Agent Mode](agent.md) | [Agent Workflows](workflows.md), [Planner](planner.md), [Agent Runtime](agent-runtime.md) |
| Generate or refactor code safely | [CodeGen](codegen.md) | [Patch Engine](patch-engine.md), [Safety](safety.md) |
| Inspect schema and query health | [Schema Doctor](schema-doctor.md) | [Project Graph](project-graph.md), [Query Engine](query-engine.md) |

---

## Studio vs AI Mode Docs

The documentation is split by responsibility.

Read [Studio](../studio/index.md) when you need the built-in web UI, Studio endpoints, or Studio configuration. Read AI Mode when you need the AI surfaces that live inside Studio or when you want to connect external agents and model providers.

---

## Five-Minute Tour

Start your app:

```bash
aksara dev
```

Then try the three entry points that matter most:

1. Open **http://127.0.0.1:8000/studio/ui** and use the **AI Console**.
2. Connect an MCP client to **http://127.0.0.1:8000/mcp/**.
3. Run `aksara doctor fix-plan` to see the remediation workflow Aksara can generate from live diagnostics.

---

## Core Surfaces

| Surface | What It Does | Where to Learn More |
|---------|---------------|---------------------|
| **AI Console** | Natural-language interface inside Studio for asking questions about models, routes, queries, and migrations | [console.md](console.md) |
| **AI Flows** | Guided actions for model review, route review, query analysis, migration explanation, and diagnostics | [flows.md](flows.md) |
| **MCP server** | Negotiates MCP and discovers/invokes generated tools over Streamable HTTP at `/mcp/` | [mcp.md](mcp.md) |
| **Schema Doctor** | Finds schema health problems and pairs them with actionable remediation output | [schema-doctor.md](schema-doctor.md) |
| **AI Debugger** | Explains failures and points at likely root causes | [debugger.md](debugger.md) |
| **Architecture Review** | Reviews coupling, structure, and design pressure across the codebase | [architecture-review.md](architecture-review.md) |
| **Performance Analyzer** | Surfaces slow queries, missing indexes, and common ORM performance traps | [performance-analyzer.md](performance-analyzer.md) |

---

## Provider Configuration

AI Mode is provider-agnostic. Configure the provider and the model name that make sense for your environment.

```python
AKSARA = {
    "AI_PROVIDER": "anthropic",  # or "openai", "ollama", "custom_http"
    "AI_MODEL": "<provider-model-name>",
}
```

!!! warning "API key required"
    AI features that call an external LLM need a provider API key in the environment
    (e.g. `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`). Ollama runs locally and needs no key.
    If no key is set, Aksara still works — Studio, tool catalogs, and prompt packs are
    fully functional — but the AI Console and AI Flows cannot execute prompts.
    See [Connectors](connectors.md) for the full list of environment variables.

See [Providers](providers.md), [Bring Your Own LLM](bring-your-own-llm.md), and [Ollama](ollama.md) for concrete setups.

---

## Why Metadata Matters

AI Mode works best when the rest of your Aksara app is well described. Field metadata such as `ai_description`, `ai_sensitive`, and `ai_agent_writable` influences what the AI Console sees, what MCP exports expose, and what agent-driven write paths are allowed to change.

If you are new to those flags, start with [Fields](../orm/fields.md#ai-metadata-and-guardrails) before you wire external agents into a production app.

---

## Next Reads

- [Interactive Console](console.md)
- [MCP Integration](mcp.md)
- [Providers](providers.md)
- [Schema Doctor](schema-doctor.md)
- [AI Debugger](debugger.md)
- [Architecture Review](architecture-review.md)
- [Performance Analyzer](performance-analyzer.md)

See [Studio UI](../studio/ui.md#ai-helpers) for the visual interface.

---

## Related Documentation

- [Tools](tools.md) — AI-callable functions
- [Context Engine](context-engine.md) — Context gathering
- [Query Engine](query-engine.md) — Natural language queries
- [Codegen](codegen.md) — Code generation
- [Patch Engine](patch-engine.md) — Code modifications
- [Planner](planner.md) — Task planning
- [Agent Runtime](agent-runtime.md) — Agent execution
- [Schema Doctor](schema-doctor.md) — Schema analysis
- [Configuration](config.md) — AI Mode settings
- [Safety](safety.md) — Safety features
- [Studio AI Helpers](../studio/ui.md#ai-helpers) — Studio UI integration
