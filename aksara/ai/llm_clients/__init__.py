"""
Aksara LLM Client Adapters

v0.5.25: Unified adapter layer for AI providers.

Provides concrete implementations of BaseLlmClient for:
- OpenAI
- Azure OpenAI
- Anthropic
- Ollama (local)
- Custom HTTP endpoints

All adapters implement the same protocol: generate(), generate_stream(), is_available().
"""

from aksara.ai.llm_clients.base import BaseLlmClient
from aksara.ai.llm_clients.openai_adapter import OpenAIAdapter
from aksara.ai.llm_clients.azure_adapter import AzureOpenAIAdapter
from aksara.ai.llm_clients.anthropic_adapter import AnthropicAdapter
from aksara.ai.llm_clients.ollama_adapter import OllamaAdapter
from aksara.ai.llm_clients.custom_adapter import CustomHttpAdapter


def get_client_for_provider(provider) -> BaseLlmClient:
    """
    Factory: return the correct adapter for a UnifiedAiProvider.

    Args:
        provider: A UnifiedAiProvider instance.

    Returns:
        A BaseLlmClient implementation.

    Raises:
        ValueError: If provider type is unknown.
    """
    adapters = {
        "openai": OpenAIAdapter,
        "azure": AzureOpenAIAdapter,
        "anthropic": AnthropicAdapter,
        "ollama": OllamaAdapter,
        "custom": CustomHttpAdapter,
    }

    adapter_cls = adapters.get(provider.provider)
    if adapter_cls is None:
        raise ValueError(f"Unknown provider type: {provider.provider}")

    return adapter_cls(provider)


__all__ = [
    "BaseLlmClient",
    "OpenAIAdapter",
    "AzureOpenAIAdapter",
    "AnthropicAdapter",
    "OllamaAdapter",
    "CustomHttpAdapter",
    "get_client_for_provider",
]
