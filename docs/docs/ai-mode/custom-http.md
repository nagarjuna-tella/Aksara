# Custom HTTP Provider

The **Custom HTTP** adapter lets you connect Aksara to any LLM endpoint that speaks JSON over HTTP. No SDK required.

## Configuration

```bash
export AKSARA_CUSTOM_LLM_URL=https://my-llm.example.com
export AKSARA_CUSTOM_LLM_KEY=my-api-key           # optional
export AKSARA_CUSTOM_LLM_MODEL=my-model            # optional
```

## Programmatic Usage

```python
from aksara.ai.providers_unified import UnifiedAiProvider

provider = UnifiedAiProvider(
    provider="custom",
    base_url="https://my-llm.example.com",
    api_key="my-key",
    model="my-model",
    extra={
        "generate_path": "/api/generate",    # default: /v1/chat/completions
        "models_path": "/api/models",        # default: /v1/models
        "prompt_field": "prompt",            # default: prompt
        "response_field": "choices.0.text",  # supports dotted paths
        "headers": {"X-Custom": "value"},    # extra headers
    },
)

client = provider.get_llm_client()
response = client.generate("Hello!")
```

## Configurable Fields

| Field | Default | Description |
|-------|---------|-------------|
| `generate_path` | `/v1/chat/completions` | Endpoint path for generation |
| `models_path` | `/v1/models` | Endpoint path for model listing |
| `prompt_field` | `prompt` | JSON field name for the prompt |
| `response_field` | `choices.0.message.content` | Dotted path to extract response text |
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

Examples: vLLM, TGI, LocalAI, LM Studio, any OpenAI-compatible server.
