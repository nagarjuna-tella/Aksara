# AI execution runtime

!!! warning "Experimental"
    Prompt-pack execution and provider connectors are functional but evolving.
    They are separate from the stable MCP execution boundary.

`run_prompt_pack()` resolves an experimental provider connector, sends one
system/user prompt pair, and returns a normalized dictionary.

```python
from aksara.ai.limits import AgentRuntimeLimits
from aksara.ai.runtime import run_prompt_pack

result = await run_prompt_pack(
    {
        "system_prompt": "Answer concisely.",
        "user_prompt": "Explain this migration plan.",
        "provider": "ollama",
        "model": "llama3",
        "max_tokens": 500,
    },
    limits=AgentRuntimeLimits(
        run_timeout_seconds=30,
        provider_timeout_seconds=20,
        token_budget=2_000,
    ),
)
```

The result contains `ok`, `provider`, `model`, `response`, `tokens`,
`elapsed_ms`, and `error`. Provider and model resolution uses explicit function
overrides, prompt-pack values, AI Hub configuration, then provider defaults.

The runtime does not define an `AgentRuntime` class, persist sessions, resume
calls, or make provider quality stable. See [Agent runtime](agent-runtime.md)
for the exact boundary and [AI providers](providers.md) for configuration.
