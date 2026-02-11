"""
Base LLM Client Protocol

v0.5.25: Defines the interface all LLM adapters must implement.
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, Protocol, runtime_checkable


@runtime_checkable
class BaseLlmClient(Protocol):
    """
    Protocol for LLM client adapters.

    All adapters (OpenAI, Anthropic, Ollama, Custom) must implement
    these three methods.
    """

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """
        Generate a completion from the LLM.

        Args:
            prompt: The input prompt.
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            The generated text response.
        """
        ...

    def generate_stream(self, prompt: str, **kwargs: Any) -> Iterator[str]:
        """
        Stream a completion from the LLM.

        Args:
            prompt: The input prompt.
            **kwargs: Additional parameters.

        Yields:
            Text chunks as they arrive.
        """
        ...

    def is_available(self) -> bool:
        """
        Check if the provider is reachable and configured.

        Returns:
            True if the provider can accept requests.
        """
        ...


class LlmClientError(Exception):
    """Base exception for LLM client errors."""
    pass


class LlmConnectionError(LlmClientError):
    """Provider is unreachable."""
    pass


class LlmAuthenticationError(LlmClientError):
    """API key is invalid or missing."""
    pass


class LlmRateLimitError(LlmClientError):
    """Rate limit exceeded."""
    pass
