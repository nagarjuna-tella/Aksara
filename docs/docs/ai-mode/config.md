# AI Mode configuration

!!! warning "Experimental"
    Provider-backed AI, Planner behavior, investigation sessions, code patches,
    memory, and Studio AI internals are experimental in v0.7.0-rc1.

Aksara configuration uses the global `aksara.conf.settings` object. Do not add
an `AKSARA = {...}` dictionary; the runtime does not read that pattern.

Enable provider-backed AI explicitly:

```dotenv
AKSARA_AI_ENABLED=true
```

Then configure a provider with the current AI Hub path:

```bash
aksara ai-hub configure
aksara ai-hub status
aksara ai-hub doctor
```

See [AI providers](providers.md) for current, compatibility, and deprecated
provider layers.

## Runtime limits

The real prompt-pack runtime accepts in-process limits per call:

```python
from aksara.ai.limits import AgentRuntimeLimits
from aksara.ai.runtime import run_prompt_pack

result = await run_prompt_pack(
    prompt_pack,
    limits=AgentRuntimeLimits(
        run_timeout_seconds=30,
        provider_timeout_seconds=20,
        token_budget=2_000,
    ),
)
```

These limits reset with the process. There is no `AI_AGENT_RUNTIME` dictionary,
stable `AgentRuntime` class, or durable provider budget in v0.7.0-rc1.

## MCP is separate

MCP tool execution is a stable v0.6 boundary and does not require a model
provider. Enable its Streamable HTTP server separately:

```dotenv
AKSARA_MCP_ENABLED=true
AKSARA_MCP_TOKEN_AUDIENCE=my-app
```

MCP clients connect to `/mcp/`. The `/ai/tools/mcp` route is an HTTP JSON
inspection catalog. Follow the [MCP quickstart](../getting-started/mcp.md) to
add server-side Principal resolution before enabling tool execution.
