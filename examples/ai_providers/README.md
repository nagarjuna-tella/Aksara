# Aksara example: AI provider adapters

**Experimental application-owned adapter demo.** This example shows local
Python adapter classes for OpenAI, Azure OpenAI and Anthropic. It is not the
framework's authoritative configuration interface and does not prove provider
quality, credential validity or model availability.

Its custom Settings subclass supplies values to its adapter code. Do not copy
it as a way to configure Aksara's global settings object; use the
[configuration reference](../../docs/docs/reference/settings-reference.md).
The adapter-specific `AI_DEFAULT_PROVIDER` is distinct from framework AI Hub
configuration. This example does not provide an Ollama adapter.

## Run without calling a provider

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
aksara run examples.ai_providers.main:app --host 127.0.0.1 --port 8000
```

The explicit package path avoids relying on `aksara dev` discovery. No database
migration is needed for the status probes below; `aksara migrate` is not a
provider-setup step. `aksara doctor launch-check` is a general project diagnostic,
not a test of these adapters.

```bash
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/ai/status
curl --fail http://127.0.0.1:8000/ai/providers
```

These endpoints report configuration and installed SDK availability. A provider
reported as ready has not necessarily authenticated successfully or generated
a response. Live provider calls need the corresponding optional SDK, credentials
and a currently available model. No live provider was called in the startup audit.

## Seed and persistence

No seed command is required for configuration inspection. Demo model and ViewSet
code is illustrative; this README does not supply a persistent CRUD application.
Use the [ticket desk](../../docs/docs/getting-started/first-project.md) for that.

## Optional framework tools

Studio at `/studio/ui` and the AI Console are experimental framework surfaces;
this adapter demo is not their configuration guide. The `/ai/tools/mcp` catalog
is HTTP JSON inspection, not the official protocol transport. The
[MCP tutorial](../../docs/docs/tutorials/ticket-desk-mcp.md) shows a complete
authenticated official-client journey without requiring a model provider.

Keep provider secrets in your environment or secret store. Do not commit them
or treat the historical default model names in the adapter as availability guarantees.
