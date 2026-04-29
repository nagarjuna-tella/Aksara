# AI Connectors

AI Connectors are pluggable adapters that translate Aksara prompt packs into
real API calls to LLM providers.  Each connector implements a common
`AIConnector` interface and returns a normalised response.

---

## Available Connectors

| Provider     | Connector Class       | Auth Env Var         | Notes |
|--------------|-----------------------|----------------------|-------|
| **OpenAI**   | `OpenAIConnector`     | `OPENAI_API_KEY`     | Also works for Azure OpenAI |
| **Anthropic**| `AnthropicConnector`  | `ANTHROPIC_API_KEY`  | Claude models, Messages API |
| **Ollama**   | `OllamaConnector`     | —                    | Local models, no auth needed |
| **HTTP**     | `HttpConnector`       | `AI_HTTP_API_KEY`    | Any OpenAI-compatible endpoint |

---

## Connector Interface

Every connector inherits from `AIConnector` and must implement at least `chat()`:

```python
from aksara.ai.connectors.base import AIConnector

class MyConnector(AIConnector):
    provider = "my_provider"

    async def chat(self, messages, model, temperature=0.2, max_tokens=1024, **kwargs):
        # Call your API and return a normalised dict
        return self._normalise_response(
            ok=True, provider=self.provider, model=model,
            text="...", tokens={"prompt": 10, "completion": 20, "total": 30},
        )
```

### Normalised Response Shape

Every `chat()` call returns this same shape:

```json
{
    "ok": true,
    "provider": "configured-provider",
    "model": "configured-model",
    "text": "The User model has 5 fields...",
    "tokens": {"prompt": 20, "completion": 50, "total": 70},
    "raw": {},
    "error": null,
    "elapsed_ms": 150.0
}
```

---

## Using Connectors

### Via the Registry

```python
from aksara.ai.connectors.registry import get_connector

# Uses AI Hub config or env vars
connector = get_connector("openai")
result = await connector.chat(
    messages=[{"role": "user", "content": "Hello"}],
    model="<provider-model-name>",
)
```

### With Explicit Credentials

```python
connector = get_connector("openai", api_key="sk-...", base_url="https://api.openai.com/v1")
```

### Listing Available Connectors

```python
from aksara.ai.connectors.registry import list_connectors
print(list_connectors())
# {'openai': 'OpenAIConnector', 'anthropic': 'AnthropicConnector', ...}
```

---

## Configuration

Connectors resolve credentials in this order:

1. **Explicit kwargs** — `api_key=`, `base_url=`
2. **AI Hub settings** — configured via Studio UI or `aihub.json`
3. **Environment variables** — `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.

### Environment Variables

| Variable              | Provider   | Description |
|-----------------------|------------|-------------|
| `OPENAI_API_KEY`      | OpenAI     | API key |
| `OPENAI_BASE_URL`     | OpenAI     | Base URL override |
| `OPENAI_ORGANIZATION` | OpenAI     | Organization ID |
| `ANTHROPIC_API_KEY`   | Anthropic  | API key |
| `ANTHROPIC_BASE_URL`  | Anthropic  | Base URL override |
| `OLLAMA_BASE_URL`     | Ollama     | Local URL (default: `http://localhost:11434`) |
| `AI_HTTP_ENDPOINT`    | HTTP       | Custom endpoint URL |
| `AI_HTTP_API_KEY`     | HTTP       | Custom API key |

---

## Safety

Connectors **never modify code automatically**.  They only return text responses
containing analysis, suggestions, and explanations.  Any suggested changes are
presented as CLI commands or code snippets for the developer to review and apply
manually.
