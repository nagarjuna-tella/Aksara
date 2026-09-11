# AI integration

Aksara's stable AI-native integration is generated MCP execution. Provider
calls, natural-language query planning, and Studio AI remain experimental.
There is no public `QueryEngine`, `InsightGenerator`, `Planner`, or
`AgentRuntime` class.

## Stable path: expose an authorized tool

Define an AI-exposed model and `ModelViewSet`, configure server-side
`Principal` resolution, and connect an official MCP client to `/mcp/`. The
framework generates schemas and executes calls through the same permission,
policy, field, tenant, transaction, and ORM path as REST.

Follow the complete [MCP quickstart](../getting-started/mcp.md).

## Experimental structured query plans

An external model may produce an `AiQueryPlan`; Aksara can validate and execute
that structure:

```python
from aksara.ai.query import AiFilterCondition, AiQueryPlan, execute_ai_query_plan

plan = AiQueryPlan(
    model="Task",
    filters=[AiFilterCondition(field="done", lookup="exact", value=False)],
)
result = await execute_ai_query_plan(plan)
```

This low-level function does not resolve a request Principal. Keep it behind
application authorization and tenant context. It does not translate natural
language itself.

## Experimental prompt providers

Configure the current AI Hub path for optional provider-backed Studio or
prompt-pack features:

```bash
aksara ai-hub configure openai
aksara ai-hub status
aksara ai-hub doctor
```

```python
from aksara.ai.runtime import run_prompt_pack

result = await run_prompt_pack(
    {
        "system_prompt": "Answer concisely.",
        "user_prompt": "Summarize the supplied application context.",
        "provider": "ollama",
        "model": "llama3",
    }
)
```

Treat provider output as untrusted. Provider selection and quality, session
persistence, autonomous workflows, memory, and durable orchestration are not
stable v0.6 guarantees.
