# Experimental AI quickstart

!!! warning "Experimental in v0.6.1"
    Provider-backed prompts, planners, investigations, and Studio AI internals
    are outside the stable v0.6 contract. MCP generated-tool execution is a
    separate stable surface and does not require a model provider.

Inspect the current AI Hub configuration:

```bash
aksara ai-hub status
aksara ai-hub doctor
aksara ai-hub configure
```

Provider credentials belong in environment variables or the provider's secret
store. Do not commit them. For example:

```dotenv
OPENAI_API_KEY=replace-with-your-key
ANTHROPIC_API_KEY=replace-with-your-key
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

Ollama can be used for local experiments:

```bash
ollama serve
ollama pull llama3
aksara ai-hub configure
```

Aksara v0.6.1 does not export a stable `AgentRuntime` or `Planner` class. Use the
real primitives documented under [AI Mode](../ai-mode/index.md), expect their
contracts to evolve, and keep human approval and application authorization
around mutations.

For the stable official-client path, follow the [MCP quickstart](mcp.md) and
connect to `/mcp/`.
