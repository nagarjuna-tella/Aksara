"""
Ollama Adapter

v0.5.25: LLM client adapter for Ollama (local LLM server).

Default base URL: http://localhost:11434
Supports:
- /api/generate – text generation
- /api/tags – list available models
- Streaming responses
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Iterator, List, TYPE_CHECKING

from aksara.ai.llm_clients.base import (
    LlmClientError,
    LlmConnectionError,
)

if TYPE_CHECKING:
    from aksara.ai.providers_unified import UnifiedAiProvider

logger = logging.getLogger("aksara.ai.llm_clients.ollama")


class OllamaAdapter:
    """
    LLM client for Ollama local server.

    No API key required. Communicates directly with the Ollama REST API.
    """

    def __init__(self, provider: "UnifiedAiProvider"):
        self.model = provider.model or "llama3"
        self.base_url = (provider.base_url or "http://localhost:11434").rstrip("/")
        self.extra = provider.extra

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate text using Ollama's /api/generate endpoint."""
        import urllib.request
        import urllib.error

        url = f"{self.base_url}/api/generate"
        payload = {
            "model": kwargs.get("model", self.model),
            "prompt": prompt,
            "stream": False,
        }

        # Optional parameters
        if "temperature" in kwargs:
            payload.setdefault("options", {})["temperature"] = kwargs["temperature"]
        if "max_tokens" in kwargs:
            payload.setdefault("options", {})["num_predict"] = kwargs["max_tokens"]

        headers = {"Content-Type": "application/json"}
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.loads(resp.read().decode())
                return body.get("response", "")
        except urllib.error.URLError as e:
            raise LlmConnectionError(
                f"Cannot reach Ollama at {self.base_url}. "
                f"Make sure Ollama is running: {e}"
            )
        except Exception as e:
            raise LlmClientError(f"Ollama error: {e}")

    def generate_stream(self, prompt: str, **kwargs: Any) -> Iterator[str]:
        """Stream text from Ollama's /api/generate endpoint."""
        import urllib.request
        import urllib.error

        url = f"{self.base_url}/api/generate"
        payload = {
            "model": kwargs.get("model", self.model),
            "prompt": prompt,
            "stream": True,
        }

        if "temperature" in kwargs:
            payload.setdefault("options", {})["temperature"] = kwargs["temperature"]

        headers = {"Content-Type": "application/json"}
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                for line in resp:
                    line_str = line.decode("utf-8").strip()
                    if not line_str:
                        continue
                    try:
                        chunk = json.loads(line_str)
                        text = chunk.get("response", "")
                        if text:
                            yield text
                        if chunk.get("done", False):
                            break
                    except json.JSONDecodeError:
                        continue
        except urllib.error.URLError as e:
            raise LlmConnectionError(f"Cannot reach Ollama: {e}")
        except Exception as e:
            raise LlmClientError(f"Ollama streaming error: {e}")

    def is_available(self) -> bool:
        """Check if Ollama is running by hitting /api/tags."""
        import urllib.request
        import urllib.error

        url = f"{self.base_url}/api/tags"
        req = urllib.request.Request(url, method="GET")

        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except Exception:
            return False

    def list_models(self) -> List[str]:
        """List available models from Ollama."""
        import urllib.request
        import urllib.error

        url = f"{self.base_url}/api/tags"
        req = urllib.request.Request(url, method="GET")

        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                body = json.loads(resp.read().decode())
                models = body.get("models", [])
                return [m.get("name", "") for m in models if m.get("name")]
        except Exception:
            return []
