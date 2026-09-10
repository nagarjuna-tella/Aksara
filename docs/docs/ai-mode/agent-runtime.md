# Agent runtime

!!! warning "Experimental"
    Aksara 0.6.1 does not expose an `AgentRuntime` class. Planner quality,
    autonomous loops, persistent sessions, memory, and provider-specific
    behavior are outside the stable v0.6 contract.

Aksara ships two narrower runtime building blocks:

- `run_prompt_pack()` sends one prompt pack through the configured experimental
  provider connector.
- `AgentRuntimeLimits` and `AgentRuntimeBudget` bound work in the current
  process. Their counters do not survive restart and are not a durable usage
  ledger.

## Execute one prompt pack

```python
from aksara.ai.limits import AgentRuntimeBudget, AgentRuntimeLimits
from aksara.ai.runtime import run_prompt_pack

limits = AgentRuntimeLimits(
    run_timeout_seconds=30,
    provider_timeout_seconds=20,
    token_budget=2_000,
)
budget = AgentRuntimeBudget(limits)

result = await run_prompt_pack(
    {
        "system_prompt": "Answer with concise operational guidance.",
        "user_prompt": "Explain the current migration status.",
        "provider": "ollama",
        "model": "llama3",
        "max_tokens": 500,
    },
    limits=limits,
    budget=budget,
)

if result["ok"]:
    print(result["response"])
else:
    print(result["error"])
```

This example uses real exported modules. It still needs a configured provider
connector; Aksara does not certify live-provider quality in v0.6.1.

## Agent request models

`aksara.ai.agent` contains request and context data models such as
`AgentIntent`, `AgentContextBundle`, and `AgentPlanExecutionRequest`. It can
build framework context for an external agent. It does not implement a model
calling loop, durable session, or autonomous runtime.

## Stable execution boundary

The stable AI-native surface in v0.6 is generated MCP execution at `/mcp/`:
server-resolved `Principal`, execution-time permission and policy checks,
tenant and field enforcement, transactions, structured failures, audit events,
and in-process runtime limits. See the [MCP quickstart](../getting-started/mcp.md).

## Lifetime limits

Runtime budgets, prompt-pack calls, investigation sessions, and replay state are
process-local. A restart loses them. Durable operations, persistent Agent
sessions, memory, and cross-worker recovery remain deferred to v0.7.
