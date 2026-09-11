# Ollama Provider

!!! warning "Experimental development surface"
    This analysis, provider or Studio surface is outside the stable backend
    contract. Review its outputs and application integration before use. It is
    not required for REST, synchronous MCP or Durable Operations. See
    [stability labels](../concepts/stability.md).

[Ollama](https://ollama.ai) lets you run LLMs locally. Aksara's Ollama adapter connects directly — no SDK needed.

## Setup

1. Install Ollama: `curl -fsSL https://ollama.ai/install.sh | sh`
2. Pull a model: `ollama pull llama3`
3. Start serving: `ollama serve`

## Configuration

```bash
# Optional — defaults to localhost:11434
export OLLAMA_HOST=http://localhost:11434
export OLLAMA_MODEL=llama3
```

## Usage

```python
from aksara.ai.providers_unified import UnifiedAiProvider

provider = UnifiedAiProvider(provider="ollama", model="llama3")
client = provider.get_llm_client()

# Generate text
response = client.generate("Explain this database schema")

# List available models
from aksara.ai.llm_clients.ollama_adapter import OllamaAdapter
adapter = OllamaAdapter(model="llama3")
models = adapter.list_models()  # ["llama3", "codellama", ...]
```

## CLI

```bash
aksara ai-provider configure ollama --model llama3
aksara ai-provider ping --provider ollama
```

## Streaming

```python
adapter = OllamaAdapter(model="llama3")
for chunk in adapter.generate_stream("Tell me a story"):
    print(chunk, end="", flush=True)
```

## Notes

- No API key required
- Default base URL: `http://localhost:11434`
- Uses `/api/generate` endpoint (not the OpenAI-compatible endpoint)
- Streaming uses newline-delimited JSON
