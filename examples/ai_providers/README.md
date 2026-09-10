# Aksara Example: AI Providers

This example demonstrates:
- AI Hub provider configuration
- Ollama local-first setup
- OpenAI/Anthropic/Azure environment examples
- Studio
- MCP tools
- AI Console usage

Provider wiring demo. It shows the adapter pattern without making the first-user flow require OpenAI, Anthropic, Azure, or Ollama.

## Run

```bash
cd examples/ai_providers
python -m venv .venv
source .venv/bin/activate
pip install -e ../..
aksara doctor launch-check
aksara migrate
aksara dev
```

The `aksara migrate` step is safe to run even if you only inspect provider wiring. Add real migrations if you turn this into a persistent app.

## Seed

No seed command is required. This example focuses on provider configuration and adapter structure.

## Open

* API docs: http://127.0.0.1:8000/docs
* Studio: http://127.0.0.1:8000/studio/ui
* Tool inspection catalog: http://127.0.0.1:8000/ai/tools/mcp (HTTP JSON; protocol clients use `/mcp/` when enabled)

## Test API

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/ai/status
curl http://127.0.0.1:8000/ai/providers
```

## Inspect generated tool metadata

```bash
curl http://127.0.0.1:8000/ai/tools/mcp
```

This curl request does not exercise the MCP protocol. Use the official client against `/mcp/` after the application installs server-side Principal resolution.

Confirm demo ViewSet actions appear without committing provider secrets.

## Local-First AI With Ollama

```bash
ollama serve
ollama pull llama3
export AI_DEFAULT_PROVIDER=ollama
export OLLAMA_BASE_URL=http://127.0.0.1:11434
aksara ai-hub status
aksara ai-hub configure
```

No test in this repository requires the model to exist. The commands document the local path for users who want AI features without a paid provider.

## Remote Provider Environment Examples

Use placeholders only:

```bash
export OPENAI_API_KEY=<OPENAI_API_KEY>
export ANTHROPIC_API_KEY=your-key-here
export AZURE_OPENAI_API_KEY=<AZURE_OPENAI_API_KEY>
export AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
```

Do not commit real secrets.

## Try in AI Console

Ask:

```text
Explain the provider adapter pattern
Review this AI provider configuration
Investigate this project
```

AI provider setup is optional for first launch. Studio, API docs, and MCP inspection can still be used before a provider is configured.
