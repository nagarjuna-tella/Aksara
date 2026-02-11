"""
Anthropic Adapter

v0.5.25: LLM client adapter for Anthropic's Claude API.
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

logger = logging.getLogger("aksara.ai.llm_clients.anthropic")


class AnthropicAdapter:
    """
    LLM client for Anthropic's Messages API.

    Uses urllib to avoid requiring the anthropic SDK.
    """

    def __init__(self, provider: "UnifiedAiProvider"):
        self.api_key = provider.api_key or ""
        self.model = provider.model or "claude-3-5-sonnet-20241022"
        self.base_url = (provider.base_url or "https://api.anthropic.com").rstrip("/")
        self.extra = provider.extra

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Send a messages request to Anthropic."""
        import urllib.request
        import urllib.error

        url = f"{self.base_url}/v1/messages"
        payload = {
            "model": kwargs.get("model", self.model),
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": kwargs.get("max_tokens", 2048),
        }

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read().decode())
                # Anthropic returns content as a list of blocks
                content_blocks = body.get("content", [])
                return "".join(
                    block.get("text", "") for block in content_blocks
                    if block.get("type") == "text"
                )
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise LlmAuthenticationError("Invalid Anthropic API key")
            if e.code == 429:
                raise LlmRateLimitError("Anthropic rate limit exceeded")
            raise LlmClientError(f"Anthropic API error: {e.code}")
        except urllib.error.URLError as e:
            raise LlmConnectionError(f"Cannot reach Anthropic: {e}")
        except Exception as e:
            raise LlmClientError(f"Anthropic error: {e}")

    def generate_stream(self, prompt: str, **kwargs: Any) -> Iterator[str]:
        """Stream a messages response."""
        result = self.generate(prompt, **kwargs)
        yield result

    def is_available(self) -> bool:
        """Check if Anthropic API is reachable."""
        # Anthropic doesn't have a simple health/models endpoint
        # We send a minimal request and check for auth success
        if not self.api_key:
            return False

        import urllib.request
        import urllib.error

        url = f"{self.base_url}/v1/messages"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
        }
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except urllib.error.HTTPError as e:
            # 401 = bad key, anything else means API is up
            return e.code != 401
        except Exception:
            return False
