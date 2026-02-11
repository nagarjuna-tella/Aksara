"""
Custom HTTP Adapter

v0.5.25: LLM client adapter for custom/self-hosted HTTP endpoints.

Fully configurable:
- base_url
- headers
- payload template
- response parser
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Iterator, TYPE_CHECKING

from aksara.ai.llm_clients.base import (
    LlmClientError,
    LlmConnectionError,
)

if TYPE_CHECKING:
    from aksara.ai.providers_unified import UnifiedAiProvider

logger = logging.getLogger("aksara.ai.llm_clients.custom")


class CustomHttpAdapter:
    """
    LLM client for custom HTTP endpoints.

    Configurable via the provider's extra dict:
        - headers: Dict[str, str] - additional headers
        - generate_path: str - endpoint path (default: /v1/completions)
        - models_path: str - models listing path (default: /v1/models)
        - prompt_field: str - field name for prompt (default: "prompt")
        - response_field: str - JSON path for response text (default: "text")
    """

    def __init__(self, provider: "UnifiedAiProvider"):
        self.api_key = provider.api_key or ""
        self.model = provider.model or "default"
        self.base_url = (provider.base_url or "http://localhost:8080").rstrip("/")
        self.extra = provider.extra

        # Configurable paths and field names
        self.generate_path = self.extra.get("generate_path", "/v1/completions")
        self.models_path = self.extra.get("models_path", "/v1/models")
        self.prompt_field = self.extra.get("prompt_field", "prompt")
        self.response_field = self.extra.get("response_field", "text")
        self.custom_headers: Dict[str, str] = self.extra.get("headers", {})

    def _build_headers(self) -> Dict[str, str]:
        """Build request headers."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        headers.update(self.custom_headers)
        return headers

    def _extract_response(self, body: Dict[str, Any]) -> str:
        """Extract text from response using configurable field path."""
        # Support dotted paths like "choices.0.text"
        parts = self.response_field.split(".")
        result: Any = body
        for part in parts:
            if isinstance(result, dict):
                result = result.get(part, "")
            elif isinstance(result, list):
                try:
                    result = result[int(part)]
                except (IndexError, ValueError):
                    return ""
            else:
                return str(result)
        return str(result) if result else ""

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Send a completion request to the custom endpoint."""
        import urllib.request
        import urllib.error

        url = f"{self.base_url}{self.generate_path}"
        payload: Dict[str, Any] = {
            self.prompt_field: prompt,
            "model": kwargs.get("model", self.model),
        }

        # Merge any extra payload fields
        payload_template = self.extra.get("payload_template", {})
        for k, v in payload_template.items():
            if k not in payload:
                payload[k] = v

        if "temperature" in kwargs:
            payload["temperature"] = kwargs["temperature"]
        if "max_tokens" in kwargs:
            payload["max_tokens"] = kwargs["max_tokens"]

        headers = self._build_headers()
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.loads(resp.read().decode())
                return self._extract_response(body)
        except urllib.error.URLError as e:
            raise LlmConnectionError(f"Cannot reach custom endpoint: {e}")
        except Exception as e:
            raise LlmClientError(f"Custom HTTP error: {e}")

    def generate_stream(self, prompt: str, **kwargs: Any) -> Iterator[str]:
        """Stream from custom endpoint (simplified)."""
        result = self.generate(prompt, **kwargs)
        yield result

    def is_available(self) -> bool:
        """Check if the custom endpoint is reachable."""
        import urllib.request
        import urllib.error

        url = f"{self.base_url}{self.models_path}"
        headers = self._build_headers()
        req = urllib.request.Request(url, headers=headers, method="GET")

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception:
            return False
