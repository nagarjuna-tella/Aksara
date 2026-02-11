"""
OpenAI Adapter

v0.5.25: LLM client adapter for OpenAI API.
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

logger = logging.getLogger("aksara.ai.llm_clients.openai")


class OpenAIAdapter:
    """
    LLM client for OpenAI's API.

    Uses urllib for HTTP requests to avoid requiring the openai SDK as a dependency.
    """

    def __init__(self, provider: "UnifiedAiProvider"):
        self.api_key = provider.api_key or ""
        self.model = provider.model or "gpt-4o"
        self.base_url = (provider.base_url or "https://api.openai.com/v1").rstrip("/")
        self.extra = provider.extra

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Send a chat completion request."""
        import urllib.request
        import urllib.error

        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": kwargs.get("model", self.model),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 2048),
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read().decode())
                return body["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            status = e.code
            if status == 401:
                raise LlmAuthenticationError("Invalid OpenAI API key")
            if status == 429:
                raise LlmRateLimitError("OpenAI rate limit exceeded")
            raise LlmClientError(f"OpenAI API error: {status}")
        except urllib.error.URLError as e:
            raise LlmConnectionError(f"Cannot reach OpenAI: {e}")
        except Exception as e:
            raise LlmClientError(f"OpenAI error: {e}")

    def generate_stream(self, prompt: str, **kwargs: Any) -> Iterator[str]:
        """Stream a chat completion (simplified: yields full response)."""
        # Simplified streaming - for full SSE parsing, use openai SDK
        result = self.generate(prompt, **kwargs)
        yield result

    def is_available(self) -> bool:
        """Check if OpenAI API is reachable."""
        import urllib.request
        import urllib.error

        url = f"{self.base_url}/models"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        req = urllib.request.Request(url, headers=headers, method="GET")

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception:
            return False
