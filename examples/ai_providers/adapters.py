"""
AI Providers Example - Adapters

v0.5.14: Protocol-based adapter pattern for LLM providers.

This module demonstrates how to create adapters that:
- Use Aksara's AiModelProfile for configuration
- Support multiple providers via a common interface
- Guard SDK imports with try/except (no hard dependencies)
- Raise clear errors when SDKs are missing

IMPORTANT: Install provider SDKs in YOUR project, not in Aksara:
    pip install openai      # For OpenAI/Azure
    pip install anthropic   # For Anthropic

Copy this file to your project and customize as needed.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from aksara.ai.providers import AiModelProfile, AiProviderProfile

logger = logging.getLogger("ai_providers.adapters")


# =============================================================================
# Optional SDK Imports (soft dependencies)
# =============================================================================

# OpenAI SDK (works for both OpenAI and Azure OpenAI)
try:
    import openai
    from openai import AsyncOpenAI, AsyncAzureOpenAI
    OPENAI_AVAILABLE = True
except ImportError:  # pragma: no cover
    openai = None  # type: ignore
    AsyncOpenAI = None  # type: ignore
    AsyncAzureOpenAI = None  # type: ignore
    OPENAI_AVAILABLE = False

# Anthropic SDK
try:
    import anthropic
    from anthropic import AsyncAnthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:  # pragma: no cover
    anthropic = None  # type: ignore
    AsyncAnthropic = None  # type: ignore
    ANTHROPIC_AVAILABLE = False


# =============================================================================
# LLM Client Protocol
# =============================================================================

class LlmClient(Protocol):
    """
    Protocol defining the interface for LLM clients.
    
    Implement this protocol to create adapters for any LLM provider.
    The protocol supports both simple completion and chat-style APIs.
    
    Example:
        class MyCustomClient(LlmClient):
            async def complete(self, prompt, *, model):
                # Call your provider's API
                ...
    """
    
    async def complete(
        self,
        prompt: str,
        *,
        model: "AiModelProfile",
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """
        Complete a single prompt and return the response text.
        
        Args:
            prompt: The prompt text to complete
            model: AiModelProfile with model configuration
            max_tokens: Maximum tokens in response (optional)
            temperature: Sampling temperature (optional)
            
        Returns:
            The completion text from the model
        """
        ...
    
    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        model: "AiModelProfile",
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """
        Chat with the model using a list of messages.
        
        Args:
            messages: List of message dicts with "role" and "content"
            model: AiModelProfile with model configuration
            max_tokens: Maximum tokens in response (optional)
            temperature: Sampling temperature (optional)
            
        Returns:
            The assistant's response text
        """
        ...


# =============================================================================
# Base Adapter Class
# =============================================================================

class BaseLlmClient(ABC):
    """
    Base class for LLM client implementations.
    
    Provides common functionality and enforces the LlmClient interface.
    """
    
    provider_name: str = "base"
    
    def __init__(self, api_key: Optional[str] = None, **kwargs: Any):
        """
        Initialize the client with credentials.
        
        Args:
            api_key: API key for authentication
            **kwargs: Additional provider-specific options
        """
        self.api_key = api_key
        self.options = kwargs
    
    @abstractmethod
    async def complete(
        self,
        prompt: str,
        *,
        model: "AiModelProfile",
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Complete a prompt."""
        ...
    
    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        model: "AiModelProfile",
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Chat with messages."""
        ...


# =============================================================================
# OpenAI Client Adapter
# =============================================================================

class OpenAIClient(BaseLlmClient):
    """
    OpenAI API client adapter.
    
    Requires: pip install openai
    
    Environment Variables:
        OPENAI_API_KEY  - Your OpenAI API key
        OPENAI_ORG_ID   - (Optional) Organization ID
    
    Example:
        from aksara.ai.providers import AiModelProfile
        
        client = OpenAIClient(api_key="sk-...")
        profile = AiModelProfile(model_name="gpt-4o-mini", ...)
        
        response = await client.complete("Hello!", model=profile)
    """
    
    provider_name = "openai"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        organization: Optional[str] = None,
        **kwargs: Any,
    ):
        if not OPENAI_AVAILABLE:
            raise RuntimeError(
                "openai package is not installed. "
                "Install it in your project: pip install openai"
            )
        
        super().__init__(api_key=api_key, **kwargs)
        self.organization = organization
        self._client: Optional[AsyncOpenAI] = None
    
    @property
    def client(self) -> "AsyncOpenAI":
        """Lazily initialize the OpenAI client."""
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.api_key,
                organization=self.organization,
            )
        return self._client
    
    async def complete(
        self,
        prompt: str,
        *,
        model: "AiModelProfile",
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """
        Complete a prompt using OpenAI's chat completions API.
        
        Note: Modern OpenAI models use chat API even for simple completions.
        """
        messages = [{"role": "user", "content": prompt}]
        return await self.chat(
            messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    
    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        model: "AiModelProfile",
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Chat with OpenAI using the chat completions API."""
        response = await self.client.chat.completions.create(
            model=model.model_name,
            messages=messages,  # type: ignore
            max_tokens=max_tokens or 1024,
            temperature=temperature or 0.7,
        )
        
        return response.choices[0].message.content or ""


# =============================================================================
# Azure OpenAI Client Adapter
# =============================================================================

class AzureOpenAIClient(BaseLlmClient):
    """
    Azure OpenAI Service client adapter.
    
    Requires: pip install openai
    
    Environment Variables:
        AZURE_OPENAI_ENDPOINT    - Your Azure OpenAI endpoint URL
        AZURE_OPENAI_API_KEY     - Your Azure OpenAI API key
        AZURE_OPENAI_DEPLOYMENT  - Deployment name for your model
        AZURE_OPENAI_API_VERSION - API version (default: 2024-02-01)
    
    Example:
        client = AzureOpenAIClient(
            azure_endpoint="https://myresource.openai.azure.com",
            api_key="your-key",
            deployment_name="gpt-4o-mini",
        )
        response = await client.complete("Hello!", model=profile)
    """
    
    provider_name = "azure"
    
    def __init__(
        self,
        azure_endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        deployment_name: Optional[str] = None,
        api_version: str = "2024-02-01",
        **kwargs: Any,
    ):
        if not OPENAI_AVAILABLE:
            raise RuntimeError(
                "openai package is not installed. "
                "Install it in your project: pip install openai"
            )
        
        super().__init__(api_key=api_key, **kwargs)
        self.azure_endpoint = azure_endpoint
        self.deployment_name = deployment_name
        self.api_version = api_version
        self._client: Optional[AsyncAzureOpenAI] = None
    
    @property
    def client(self) -> "AsyncAzureOpenAI":
        """Lazily initialize the Azure OpenAI client."""
        if self._client is None:
            self._client = AsyncAzureOpenAI(
                azure_endpoint=self.azure_endpoint,
                api_key=self.api_key,
                api_version=self.api_version,
            )
        return self._client
    
    async def complete(
        self,
        prompt: str,
        *,
        model: "AiModelProfile",
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Complete a prompt using Azure OpenAI."""
        messages = [{"role": "user", "content": prompt}]
        return await self.chat(
            messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    
    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        model: "AiModelProfile",
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Chat with Azure OpenAI."""
        # Azure uses deployment name instead of model name
        deployment = self.deployment_name or model.model_name
        
        response = await self.client.chat.completions.create(
            model=deployment,
            messages=messages,  # type: ignore
            max_tokens=max_tokens or 1024,
            temperature=temperature or 0.7,
        )
        
        return response.choices[0].message.content or ""


# =============================================================================
# Anthropic Client Adapter
# =============================================================================

class AnthropicClient(BaseLlmClient):
    """
    Anthropic Claude client adapter.
    
    Requires: pip install anthropic
    
    Environment Variables:
        ANTHROPIC_API_KEY - Your Anthropic API key
    
    Example:
        client = AnthropicClient(api_key="sk-ant-...")
        profile = AiModelProfile(model_name="claude-3-5-sonnet-20241022", ...)
        
        response = await client.complete("Hello!", model=profile)
    """
    
    provider_name = "anthropic"
    
    def __init__(self, api_key: Optional[str] = None, **kwargs: Any):
        if not ANTHROPIC_AVAILABLE:
            raise RuntimeError(
                "anthropic package is not installed. "
                "Install it in your project: pip install anthropic"
            )
        
        super().__init__(api_key=api_key, **kwargs)
        self._client: Optional[AsyncAnthropic] = None
    
    @property
    def client(self) -> "AsyncAnthropic":
        """Lazily initialize the Anthropic client."""
        if self._client is None:
            self._client = AsyncAnthropic(api_key=self.api_key)
        return self._client
    
    async def complete(
        self,
        prompt: str,
        *,
        model: "AiModelProfile",
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Complete a prompt using Anthropic's messages API."""
        messages = [{"role": "user", "content": prompt}]
        return await self.chat(
            messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    
    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        model: "AiModelProfile",
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Chat with Anthropic Claude."""
        response = await self.client.messages.create(
            model=model.model_name,
            messages=messages,  # type: ignore
            max_tokens=max_tokens or 1024,
            temperature=temperature or 0.7,
        )
        
        # Anthropic returns content blocks
        content = response.content[0]
        if hasattr(content, "text"):
            return content.text
        return str(content)


# =============================================================================
# Factory Function
# =============================================================================

def get_llm_client(
    provider: str,
    *,
    api_key: Optional[str] = None,
    # OpenAI options
    organization: Optional[str] = None,
    # Azure options
    azure_endpoint: Optional[str] = None,
    deployment_name: Optional[str] = None,
    api_version: str = "2024-02-01",
    **kwargs: Any,
) -> LlmClient:
    """
    Factory function to get an LLM client for a specific provider.
    
    Args:
        provider: Provider name ("openai", "azure", "anthropic")
        api_key: API key for the provider
        organization: (OpenAI) Organization ID
        azure_endpoint: (Azure) Endpoint URL
        deployment_name: (Azure) Model deployment name
        api_version: (Azure) API version
        **kwargs: Additional provider-specific options
        
    Returns:
        LlmClient instance for the specified provider
        
    Raises:
        ValueError: If provider is not supported
        RuntimeError: If required SDK is not installed
        
    Example:
        from .settings import settings
        
        client = get_llm_client(
            "openai",
            api_key=settings.OPENAI_API_KEY,
        )
    """
    provider = provider.lower()
    
    if provider == "openai":
        return OpenAIClient(
            api_key=api_key,
            organization=organization,
            **kwargs,
        )
    elif provider == "azure":
        return AzureOpenAIClient(
            azure_endpoint=azure_endpoint,
            api_key=api_key,
            deployment_name=deployment_name,
            api_version=api_version,
            **kwargs,
        )
    elif provider == "anthropic":
        return AnthropicClient(
            api_key=api_key,
            **kwargs,
        )
    else:
        raise ValueError(
            f"Unsupported provider: {provider}. "
            f"Supported providers: openai, azure, anthropic"
        )


def get_llm_client_from_settings(settings: Any) -> LlmClient:
    """
    Get an LLM client based on the current settings configuration.
    
    Reads provider selection and credentials from settings.
    
    Args:
        settings: Settings object with AI provider configuration
        
    Returns:
        LlmClient instance configured from settings
        
    Example:
        from .settings import settings
        
        client = get_llm_client_from_settings(settings)
        response = await client.complete("Hello!", model=profile)
    """
    provider = getattr(settings, "AI_DEFAULT_PROVIDER", "openai")
    
    if provider == "openai":
        return get_llm_client(
            "openai",
            api_key=getattr(settings, "OPENAI_API_KEY", None),
            organization=getattr(settings, "OPENAI_ORG_ID", None),
        )
    elif provider == "azure":
        return get_llm_client(
            "azure",
            api_key=getattr(settings, "AZURE_OPENAI_API_KEY", None),
            azure_endpoint=getattr(settings, "AZURE_OPENAI_ENDPOINT", None),
            deployment_name=getattr(settings, "AZURE_OPENAI_DEPLOYMENT", None),
            api_version=getattr(settings, "AZURE_OPENAI_API_VERSION", "2024-02-01"),
        )
    elif provider == "anthropic":
        return get_llm_client(
            "anthropic",
            api_key=getattr(settings, "ANTHROPIC_API_KEY", None),
        )
    else:
        raise ValueError(f"Unsupported provider in settings: {provider}")


# =============================================================================
# Availability Checks
# =============================================================================

def check_sdk_availability() -> dict[str, bool]:
    """
    Check which provider SDKs are available.
    
    Returns:
        Dict mapping provider names to availability status
    """
    return {
        "openai": OPENAI_AVAILABLE,
        "azure": OPENAI_AVAILABLE,  # Uses same SDK as OpenAI
        "anthropic": ANTHROPIC_AVAILABLE,
    }
