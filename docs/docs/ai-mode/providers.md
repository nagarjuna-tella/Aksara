# AI providers

!!! warning "Experimental"
    Provider selection, connector behavior, model quality, and live-provider
    accounting are not part of the stable v0.6 contract.

Aksara contains two provider layers because newer execution configuration was
added without deleting the older discovery contract.

| Layer | Use | Status |
| --- | --- | --- |
| AI Hub (`aksara.ai.hub_settings`, `aksara ai-hub ...`) | Current configuration for provider-backed Studio and prompt-pack execution | experimental, recommended for new provider setup |
| `UnifiedAiProvider` and connectors | Runtime adapter used beneath AI Hub and by compatibility callers | experimental compatibility bridge |
| `AiProviderProfile` / `AiProviderRegistry` | Provider and model metadata discovery without making completions | compatibility-only metadata API |
| `Settings.ai_default_provider`, `ai_providers`, `ai_secret_hints` | Older profile configuration fields | deprecated compatibility fields |

## Recommended setup

Use the AI Hub CLI, which writes the current AI Hub configuration model:

```bash
aksara ai-hub status
aksara ai-hub configure openai
aksara ai-hub doctor
```

Environment credentials remain provider-specific:

| Provider | Main variables |
| --- | --- |
| OpenAI | `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_BASE_URL` |
| Anthropic | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `ANTHROPIC_BASE_URL` |
| Azure OpenAI | `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION` |
| Ollama | `OLLAMA_BASE_URL`, `OLLAMA_MODEL` |
| Custom HTTP | `CUSTOM_LLM_API_KEY`, `CUSTOM_LLM_BASE_URL`, `CUSTOM_LLM_MODEL` |

For example, a local Ollama setup is:

```bash
ollama serve
ollama pull llama3
export OLLAMA_BASE_URL=http://localhost:11434
export OLLAMA_MODEL=llama3
aksara ai-hub status
```

## Programmatic inspection

New code that needs to inspect the current AI Hub model can load it directly:

```python
from aksara.ai.hub_settings import load_aihub_settings

hub = load_aihub_settings().resolve_defaults()
print(hub.active_provider)
print(hub.provider_status_summary())
```

`UnifiedAiProvider` remains usable when an integration needs the runtime
adapter explicitly:

```python
from aksara.ai.providers_unified import UnifiedAiProvider

provider = UnifiedAiProvider.from_env("ollama")
assert provider.provider == "ollama"
```

Do not put API keys in `AiProviderProfile`. That older API describes capability
metadata and secret *names*; it is not the recommended execution configuration.
Existing profile imports remain available for compatibility.

A provider being configured or reachable does not certify output quality,
tool-call accuracy, cost accounting, or production suitability. Test those
properties in the application using the selected model.
