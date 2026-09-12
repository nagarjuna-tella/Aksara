# Custom HTTP Provider

!!! warning "Experimental development surface"
    This analysis, provider or Studio surface is outside the stable backend
    contract. Review its outputs and application integration before use. It is
    not required for REST, synchronous MCP or Durable Operations. See
    [stability labels](../concepts/stability.md).

The **Custom HTTP** adapter lets you connect Aksara to any LLM endpoint that speaks JSON over HTTP. No SDK required.

## Configuration

```bash
export CUSTOM_LLM_BASE_URL=https://my-llm.example.com
export CUSTOM_LLM_API_KEY=my-api-key              # see keyless note below
export CUSTOM_LLM_MODEL=my-model                  # optional
```

The HTTP adapter itself permits a keyless endpoint. The experimental
compatibility commands `aksara ai-provider detect` and `ping` currently classify
a custom provider as configured only when `CUSTOM_LLM_API_KEY` is non-empty.
Construct `UnifiedAiProvider` directly for a keyless endpoint; do not add a
dummy credential merely to satisfy the compatibility detector.

## Programmatic Usage

```python
from aksara.ai.providers_unified import UnifiedAiProvider

provider = UnifiedAiProvider(
    provider="custom",
    base_url="https://my-llm.example.com",
    api_key="my-key",
    model="my-model",
    extra={
        "generate_path": "/api/generate",    # default: /v1/completions
        "models_path": "/api/models",        # default: /v1/models
        "prompt_field": "prompt",            # default: prompt
        "response_field": "choices.0.text",  # default: text; dotted paths supported
        "headers": {"X-Custom": "value"},    # extra headers
    },
)

client = provider.get_llm_client()
response = client.generate("Hello!")
```

## Configurable Fields

| Field | Default | Description |
|-------|---------|-------------|
| `generate_path` | `/v1/completions` | Endpoint path for generation |
| `models_path` | `/v1/models` | Endpoint path for model listing |
| `prompt_field` | `prompt` | JSON field name for the prompt |
| `response_field` | `text` | Dotted path to extract response text |
| `headers` | `{}` | Extra HTTP headers |
| `payload_template` | `{}` | Extra fields merged into the request body |

## Response Field Paths

The `response_field` supports dotted notation for nested JSON:

- `"text"` → `response["text"]`
- `"choices.0.text"` → `response["choices"][0]["text"]`
- `"data.output"` → `response["data"]["output"]`

## Compatibility

Works with any HTTP endpoint that:

1. Accepts POST with JSON body
2. Returns JSON response
3. Has a text field in the response (configurable via `response_field`)

For vLLM, TGI, LocalAI, LM Studio, or another OpenAI-compatible server, set the
path, request field, response field, headers, and payload template to the exact
API that deployment exposes. The adapter does not translate every provider's
protocol automatically.
