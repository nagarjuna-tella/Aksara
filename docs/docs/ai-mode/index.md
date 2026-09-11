# AI Mode

!!! warning "Experimental in v0.7.0"
    Provider-backed prompt execution, AI Console and flows, planner quality,
    investigations, code/patch generation, autonomous behavior, and Studio AI
    internals are experimental. Session and budget state may be process-local.

Aksara includes useful experimental primitives for provider calls, bounded
prompt-pack execution, plan data structures, project context, declarative
patches, and query-plan validation. These APIs are documented so developers can
experiment with what the package actually exports; their presence does not make
them part of the stable v0.6 contract.

## Stable MCP is separate

Generated MCP tool execution is stable within the v0.6 execution boundary and
does not require provider-backed AI:

| Path | Purpose |
| --- | --- |
| `/mcp/` | official-client Streamable HTTP protocol endpoint |
| `/ai/tools/mcp` | HTTP JSON inspection catalog for generated tool metadata |

Start with the [MCP quickstart](../getting-started/mcp.md) for the model,
Principal, official client, and persisted database journey.

## Current experimental entry points

| Goal | Current documentation |
| --- | --- |
| Configure provider-backed prompts | [AI Hub](hub.md), [Providers](providers.md), [Bring Your Own LLM](bring-your-own-llm.md) |
| Run bounded prompt packs | [Execution runtime](runtime.md) |
| Describe and execute deterministic plans | [Planner primitives](planner.md) |
| Build project context | [Context engine](context-engine.md) |
| Validate query plans | [Query engine](query-engine.md) |
| Describe code or patch operations | [Code generation](codegen.md), [Patch engine](patch-engine.md), [Safety](safety.md) |
| Explore Studio AI | [Studio](../studio/index.md) |

There is no public `AgentRuntime` or `Planner` class in v0.7.0. Pages with those
historical names now describe the narrower real exports or label conceptual
architecture as pseudocode.

## Provider configuration

Use AI Hub for the current experimental provider path:

```bash
aksara ai-hub configure
aksara ai-hub status
aksara ai-hub doctor
```

Provider credentials stay in environment variables or application secret
storage. Compatibility profile fields remain available for existing v0.6 code,
but new setup should not use an `AKSARA = {...}` dictionary.

## Safety boundary

Experimental helpers do not grant authority. Applications still resolve the
Principal, authorize operations, constrain writable fields and tenants, and own
human-review workflow and durable external side-effect policy. Review
[AI/MCP security boundaries](../security/ai-mcp-boundaries.md) before connecting
agents to data-changing operations.
