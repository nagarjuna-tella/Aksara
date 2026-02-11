# AI Profiles & Provider Contracts

!!! info "v0.5.11 Feature"
    This feature was added in Aksara v0.5.11.

Aksara's AI Profiles system provides a **vendor-agnostic, pluggable description layer** for AI providers and models. This enables external agents and tools to discover your AI configuration without Aksara depending on any vendor SDKs.

## Overview

AI Profiles answers the question: "What AI capabilities does this Aksara application have?"

Key principles:

- **No Vendor Dependencies**: Aksara doesn't import OpenAI, Anthropic, or any AI SDK
- **No Network Calls**: This is purely a configuration/metadata layer
- **No Actual Completions**: External agents handle actual AI operations
- **Discovery-First**: Studio and CLI can inspect and export your AI configuration

## Core Concepts

### Model Profile

An `AiModelProfile` describes a single AI model:

```python
from aksara.ai.providers import AiModelProfile

gpt4 = AiModelProfile(
    name="gpt-4o",
    display_name="GPT-4 Omni",
    kind="chat",
    max_input_tokens=128000,
    max_output_tokens=4096,
    supports_tools=True,
    supports_streaming=True,
    tags=["fast", "multimodal"],
)
```

Model kinds include: `chat`, `completion`, `embedding`, `tool-calling`, `rerank`, `vision`, `audio`, `code`.

### Provider Profile

An `AiProviderProfile` groups models under a provider:

```python
from aksara.ai.providers import AiProviderProfile, AiModelProfile

openai = AiProviderProfile(
    name="openai",
    display_name="OpenAI",
    kind="openai",
    default_model="gpt-4o",
    models=[
        AiModelProfile(name="gpt-4o", ...),
        AiModelProfile(name="gpt-4o-mini", ...),
    ],
)
```

Provider kinds include: `openai`, `azure_openai`, `anthropic`, `google`, `cohere`, `local`, `other`.

### Profile Set

An `AiProfileSet` is a collection of providers:

```python
from aksara.ai.providers import AiProfileSet

profile_set = AiProfileSet(
    providers=[openai, anthropic, local],
    default_provider="openai",
    environment="production",
    version="1.0.0",
)
```

## Configuration

### Via Settings

Configure providers in your settings:

```python
# settings.py or environment variables

# Enable/disable AI profiles (default: True)
ai_profiles_enabled = True
# or AKSARA_AI_PROFILES_ENABLED=true

# Set default provider
ai_default_provider = "openai"
# or AKSARA_AI_DEFAULT_PROVIDER=openai

# Explicit provider configurations (JSON)
ai_providers = [
    {
        "name": "openai",
        "display_name": "OpenAI",
        "kind": "openai",
        "default_model": "gpt-4o",
        "models": [
            {
                "name": "gpt-4o",
                "display_name": "GPT-4 Omni",
                "kind": "chat",
                "max_input_tokens": 128000,
                "supports_tools": True,
            }
        ]
    }
]
# or AKSARA_AI_PROVIDERS='[{"name": "openai", ...}]'
```

### Via Registry

Programmatically register providers:

```python
from aksara.ai.providers import (
    AiProviderRegistry,
    AiProviderProfile,
    AiModelProfile,
    get_ai_provider_registry,
)

# Get or create registry
registry = get_ai_provider_registry(app)

# Create a provider profile
my_provider = AiProviderProfile(
    name="my_custom_provider",
    display_name="My Custom AI",
    kind="local",
    models=[
        AiModelProfile(
            name="local-llama",
            display_name="Local Llama 3",
            kind="chat",
        )
    ],
)

# Register it
registry.register_provider(my_provider)

# Set as default
registry.set_default_provider("my_custom_provider")
```

## Secret Hints

AI Profiles includes a safe way to indicate which secrets are needed:

```python
from aksara.ai.providers import AiProviderSecretHint

hints = [
    AiProviderSecretHint(
        provider_name="openai",
        env_var="OPENAI_API_KEY",
        required=True,
        description="OpenAI API key for GPT models",
    ),
    AiProviderSecretHint(
        provider_name="anthropic",
        env_var="ANTHROPIC_API_KEY",
        required=True,
        description="Anthropic API key for Claude models",
    ),
]
```

!!! warning "Security"
    Secret hints **only** expose environment variable names and whether they are configured.
    Actual secret values are **never** exposed via Studio, CLI, or any API.

## Studio Integration

### Profiles Endpoint

```bash
GET /studio/ai/profiles
```

Returns:

```json
{
  "enabled": true,
  "providers": [
    {
      "name": "openai",
      "display_name": "OpenAI",
      "kind": "openai",
      "model_count": 3,
      "default_model": "gpt-4o",
      "is_example": false,
      "models": [
        {
          "name": "gpt-4o",
          "display_name": "GPT-4 Omni",
          "kind": "chat",
          "supports_tools": true,
          "supports_streaming": true,
          "max_input_tokens": 128000,
          "max_output_tokens": 4096
        }
      ]
    }
  ],
  "default_provider": "openai",
  "total_models": 6,
  "environment": "production"
}
```

### Secrets Endpoint

```bash
GET /studio/ai/secrets
```

Returns:

```json
{
  "secrets": [
    {
      "provider_name": "openai",
      "env_var": "OPENAI_API_KEY",
      "required": true,
      "description": "OpenAI API key",
      "is_configured": true
    },
    {
      "provider_name": "anthropic",
      "env_var": "ANTHROPIC_API_KEY",
      "required": true,
      "description": "Anthropic API key",
      "is_configured": false
    }
  ],
  "configured_count": 1,
  "total_count": 2
}
```

### Studio UI

The Studio UI includes an "AI Profiles" panel showing:

- Provider cards with model lists
- Capability badges (tools, streaming, vision)
- Token limit information
- Secret configuration status
- Export button for JSON configuration

## CLI Commands

### List Providers

```bash
aksara ai providers
aksara ai providers --format json
```

### List Models

```bash
aksara ai models
aksara ai models --provider openai
aksara ai models --format json
```

### Check Secrets

```bash
aksara ai secrets
aksara ai secrets --format json
```

## Example Profiles

When no explicit configuration is provided, Aksara includes example profiles for testing:

- `example_openai_like` - Demo OpenAI-style provider
- `example_anthropic_like` - Demo Anthropic-style provider
- `example_local` - Demo local/Ollama-style provider

These are marked with `is_example: true` and should be replaced in production.

## Integration with External Agents

External AI agents (like GitHub Copilot, Cursor, or custom tools) can:

1. Fetch `/studio/ai/profiles` to discover available providers
2. Fetch `/studio/ai/secrets` to check which credentials are configured
3. Use this information to make appropriate AI calls
4. Respect `default_provider` and `default_model` preferences

This enables a clean separation:

- **Aksara**: Declares "these are my AI capabilities"
- **External Agent**: Handles actual API calls and completions

## Best Practices

1. **Always set a default provider** for consistent behavior
2. **Use meaningful display names** for UI clarity
3. **Tag models appropriately** (fast, flagship, cheap, etc.)
4. **Document token limits** for proper request sizing
5. **Set `supports_tools: true`** only for models that actually support it
6. **Use `environment`** to distinguish dev/staging/prod profiles


---

## Unified AI Provider System (v0.5.25)

!!! info "v0.5.25 Feature"
    The Unified Provider System was added in Aksara v0.5.25.

Starting in v0.5.25, Aksara provides a **UnifiedAiProvider** class that replaces ad-hoc
environment variable handling with a single configuration object. See [AI Hub](hub.md)
for the full documentation.

### Quick Example

```python
from aksara.ai.providers_unified import UnifiedAiProvider, get_active_provider

# Auto-detect from environment
provider = get_active_provider()
if provider and provider.is_configured():
    client = provider.get_llm_client()
    response = client.generate("Hello!")
```

### Supported Providers

| Provider | Env Var | Zero-Dependency |
|----------|---------|-----------------|
| OpenAI | `OPENAI_API_KEY` | Yes (urllib) |
| Anthropic | `ANTHROPIC_API_KEY` | Yes (urllib) |
| Azure OpenAI | `AZURE_OPENAI_API_KEY` | Yes (urllib) |
| Ollama | `OLLAMA_HOST` | Yes (urllib) |
| Custom HTTP | `AKSARA_CUSTOM_LLM_URL` | Yes (urllib) |
