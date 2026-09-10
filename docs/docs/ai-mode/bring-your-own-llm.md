# Bring Your Own LLM

Wire Aksara's AI contracts to your preferred LLM provider.

## Overview

Aksara provides **vendor-agnostic AI contracts** (profiles, hints, tools) without depending on any provider SDK. This page shows how to wire those contracts to real providers like OpenAI, Azure, or Anthropic.

**Key Principles:**

1. **No hard dependencies** - Provider SDKs stay in YOUR project, not Aksara core
2. **No secrets in code** - Always use environment variables
3. **Protocol-based adapters** - Swap providers without changing app code
4. **Soft imports** - Gracefully handle missing SDKs

## Quick Start

### 1. Copy Example Adapters

```bash
aksara ai examples -o ./ai_adapters
```

This copies:
- `settings.py` - Environment-based configuration
- `adapters.py` - LLM client adapters
- `prompting.py` - Prompt building utilities
- `views.py` - Example views with AI actions

### 2. Install Provider SDK

```bash
# Choose one:
pip install openai      # For OpenAI or Azure
pip install anthropic   # For Anthropic Claude
```

### 3. Set Environment Variables

```bash
# OpenAI
export OPENAI_API_KEY=<OPENAI_API_KEY>

# OR Azure OpenAI
export AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
export AZURE_OPENAI_API_KEY=<AZURE_OPENAI_API_KEY>
export AZURE_OPENAI_DEPLOYMENT=your-deployment-name

# OR Anthropic
export ANTHROPIC_API_KEY=<ANTHROPIC_API_KEY>
```

### 4. Use in Your Views

**Conceptual or legacy pseudocode (not an installed-package API):**

```text title="Conceptual or legacy pseudocode"
from your_project.ai_adapters import get_llm_client_from_settings, build_prompt_for_route
from aksara.ai import ai_route_hint, get_ai_route_hint
from aksara.api import AksaraViewSet, action

class PostViewSet(AksaraViewSet):
    @action(detail=True, methods=["post"])
    @ai_route_hint(
        title="Suggest tags for a post",
        description="Analyzes content and suggests relevant tags",
        usage_kind="read_only",
        risk_level="low",
    )
    async def ai_suggest_tags(self, request, id: int):
        hint = get_ai_route_hint(self.ai_suggest_tags)
        prompt = build_prompt_for_route(hint, user_input={"content": "..."})
        
        client = get_llm_client_from_settings(settings)
        response = await client.complete(prompt, model=profile)
        
        return {"tags": parse_tags(response)}
```

## The Adapter Pattern

### LlmClient Protocol

The adapters use Python's `Protocol` type for a clean interface:

```python
from typing import Protocol

class LlmClient(Protocol):
    """Protocol for LLM clients."""
    
    async def complete(
        self,
        prompt: str,
        model: AiModelProfile,
        **kwargs,
    ) -> str:
        """Generate a completion."""
        ...
    
    async def chat(
        self,
        messages: list[dict[str, str]],
        model: AiModelProfile,
        **kwargs,
    ) -> str:
        """Generate a chat response."""
        ...
```

### Soft SDK Imports

To avoid ImportError when SDK isn't installed:

```python
# Soft import pattern
try:
    import openai
except ImportError:
    openai = None  # type: ignore

class OpenAIClient:
    def __init__(self, api_key: str):
        if openai is None:
            raise RuntimeError(
                "OpenAI SDK not installed. Run: pip install openai"
            )
        self.client = openai.AsyncOpenAI(api_key=api_key)
```

### Provider-Specific Adapters

**OpenAI:**
```python
class OpenAIClient(BaseLlmClient):
    async def complete(self, prompt: str, model: AiModelProfile, **kwargs) -> str:
        response = await self.client.chat.completions.create(
            model=model.model_name,
            messages=[{"role": "user", "content": prompt}],
            **kwargs,
        )
        return response.choices[0].message.content
```

**Azure OpenAI:**
```python
class AzureOpenAIClient(BaseLlmClient):
    def __init__(self, endpoint: str, api_key: str, deployment: str):
        self.client = openai.AsyncAzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version="2024-02-01",
        )
        self.deployment = deployment
    
    async def complete(self, prompt: str, model: AiModelProfile, **kwargs) -> str:
        # Azure uses deployment name instead of model name
        response = await self.client.chat.completions.create(
            model=self.deployment,
            messages=[{"role": "user", "content": prompt}],
            **kwargs,
        )
        return response.choices[0].message.content
```

**Anthropic:**
```python
class AnthropicClient(BaseLlmClient):
    async def complete(self, prompt: str, model: AiModelProfile, **kwargs) -> str:
        response = await self.client.messages.create(
            model=model.model_name,
            max_tokens=kwargs.get("max_tokens", 1024),
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
```

## Building Prompts from Hints

Use `@ai_route_hint` to annotate your routes, then build prompts:

```python
from aksara.ai import ai_route_hint
from aksara.ai.hints import get_ai_route_hint
from your_adapters.prompting import build_prompt_for_route

@ai_route_hint(
    title="Summarize content",
    description="Creates a concise summary",
    example_prompt="Summarize this article about AI",
    example_output={"summary": "..."},
)
async def summarize(request):
    hint = get_ai_route_hint(summarize)
    
    # Build prompt incorporating hint metadata
    prompt = build_prompt_for_route(
        hint=hint,
        user_input={"content": request.content},
    )
    
    # Call LLM
    ...
```

The `build_prompt_for_route()` function creates structured prompts that include:
- Route title and description from the hint
- Expected input/output formats
- Risk level and usage kind context
- User-provided input

## Settings Configuration

**Conceptual or legacy pseudocode (not an installed-package API):**

```text title="Conceptual or legacy pseudocode"
# settings.py
from aksara.conf import AksaraSettings

class Settings(AksaraSettings):
    # Default provider
    AI_DEFAULT_PROVIDER: str = "openai"
    
    # OpenAI
    OPENAI_API_KEY: str | None = None
    OPENAI_DEFAULT_MODEL: str = "gpt-4o-mini"
    
    # Azure OpenAI
    AZURE_OPENAI_ENDPOINT: str | None = None
    AZURE_OPENAI_API_KEY: str | None = None
    AZURE_OPENAI_DEPLOYMENT: str | None = None
    
    # Anthropic
    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_DEFAULT_MODEL: str = "claude-3-sonnet-20240229"
    
    def is_provider_configured(self, provider: str) -> bool:
        """Check if a provider has credentials configured."""
        if provider == "openai":
            return bool(self.OPENAI_API_KEY)
        elif provider == "azure":
            return all([
                self.AZURE_OPENAI_ENDPOINT,
                self.AZURE_OPENAI_API_KEY,
                self.AZURE_OPENAI_DEPLOYMENT,
            ])
        elif provider == "anthropic":
            return bool(self.ANTHROPIC_API_KEY)
        return False
```

## CLI: Provider Examples

```bash
# Show overview
aksara ai examples

# Provider-specific setup info
aksara ai examples --provider openai
aksara ai examples --provider azure
aksara ai examples --provider anthropic

# List example files
aksara ai examples --list

# Copy to your project
aksara ai examples -o ./ai_adapters
```

## Studio: Provider Status

In Aksara Studio, the AI Profiles panel now shows a **"Client Ready?"** column:

- ✅ **Ready** - SDK installed and credentials configured
- ⚠️ **SDK Missing** - Need to `pip install` the provider SDK
- ⚠️ **No Credentials** - Need to set environment variables

Access at: `GET /studio/ai/profiles`

```json
{
  "providers": [
    {
      "name": "openai",
      "display_name": "OpenAI",
      "kind": "openai",
      "client_ready": true,
      "models": [...]
    }
  ]
}
```

## Testing Without Credentials

For testing, create mock adapters:

```python
class MockLlmClient:
    """Mock client for testing."""
    
    async def complete(self, prompt: str, model: AiModelProfile, **kwargs) -> str:
        return f"Mock response for: {prompt[:50]}..."
    
    async def chat(self, messages: list, model: AiModelProfile, **kwargs) -> str:
        return "Mock chat response"

# In tests
@pytest.fixture
def mock_llm_client():
    return MockLlmClient()
```

## Security Best Practices

1. **Never commit API keys** - Use `.env` files excluded from git
2. **Use environment variables** - `OPENAI_API_KEY`, not hardcoded strings
3. **Validate credentials at startup** - Fail fast with clear messages
4. **Mask keys in logs** - Settings helpers mask sensitive values

```dotenv
# .env (add to .gitignore!)
OPENAI_API_KEY=<OPENAI_API_KEY>
ANTHROPIC_API_KEY=<ANTHROPIC_API_KEY>
```

```python
# Load with python-dotenv
from dotenv import load_dotenv
load_dotenv()
```

## Troubleshooting

### "SDK not installed"
```bash
pip install openai  # or anthropic
```

### "API key not configured"
```bash
export OPENAI_API_KEY=<OPENAI_API_KEY>  # Check it's in your shell
```

### "Invalid API key"
- Verify key at provider dashboard (platform.openai.com, etc.)
- Check for extra whitespace when copying

### "Model not found" (Azure)
- Verify deployment name matches `AZURE_OPENAI_DEPLOYMENT`
- Check deployment is active in Azure portal

## See Also

- [AI Profiles & Providers](providers.md) - Core AI profile system
- [AI Route Hints](hints.md) - Per-route AI metadata
- [AI Commands CLI](../cli/ai-commands.md) - Copy command examples
