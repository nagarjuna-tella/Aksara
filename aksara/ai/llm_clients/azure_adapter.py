"""
Azure OpenAI Adapter

v0.5.25: LLM client adapter for Azure OpenAI Service.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Iterator, TYPE_CHECKING

from aksara.ai.llm_clients.base import (
    LlmAuthenticationError,
    LlmClientError,
    LlmConnectionError,
    LlmRateLimitError,
)

if TYPE_CHECKING:
    from aksara.ai.providers_unified import UnifiedAiProvider

logger = logging.getLogger("aksara.ai.llm_clients.azure")


class AzureOpenAIAdapter:
    """
    LLM client for Azure OpenAI Service.

    Requires base_url (endpoint), api_key, and deployment name.
    """

    def __init__(self, provider: "UnifiedAiProvider"):
        self.api_key = provider.api_key or ""
        self.model = provider.model or "gpt-4o"
        self.base_url = (provider.base_url or "").rstrip("/")
        self.api_version = provider.extra.get("api_version", "2024-02-15-preview")
        self.deployment = provider.extra.get("deployment", self.model)

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Send a chat completion request to Azure OpenAI."""
        import urllib.request
        import urllib.error

        deployment = kwargs.get("deployment", self.deployment)
        url = (
            f"{self.base_url}/openai/deployments/{deployment}"
            f"/chat/completions?api-version={self.api_version}"
        )
        payload = {
            "messages": [{"role": "user", "content": prompt}],
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 2048),
        }

        headers = {
            "Content-Type": "application/json",
            "api-key": self.api_key,
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read().decode())
                return body["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise LlmAuthenticationError("Invalid Azure OpenAI API key")
            if e.code == 429:
                raise LlmRateLimitError("Azure OpenAI rate limit exceeded")
            raise LlmClientError(f"Azure OpenAI error: {e.code}")
        except urllib.error.URLError as e:
            raise LlmConnectionError(f"Cannot reach Azure OpenAI: {e}")
        except Exception as e:
            raise LlmClientError(f"Azure OpenAI error: {e}")

    def generate_stream(self, prompt: str, **kwargs: Any) -> Iterator[str]:
        """Stream a chat completion."""
        result = self.generate(prompt, **kwargs)
        yield result

    def is_available(self) -> bool:
        """Check if Azure OpenAI endpoint is reachable."""
        if not self.base_url:
            return False

        import urllib.request
        import urllib.error

        url = f"{self.base_url}/openai/models?api-version={self.api_version}"
        headers = {"api-key": self.api_key}
        req = urllib.request.Request(url, headers=headers, method="GET")

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception:
            return False
