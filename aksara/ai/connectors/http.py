"""
Aksara AI Connector — Generic HTTP  (v0.5.30)

Generic connector for custom AI API endpoints.
Forwards messages using the OpenAI chat-completions shape.

Environment variables:
    AI_HTTP_ENDPOINT  — endpoint URL
    AI_HTTP_API_KEY   — optional API key
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from aksara.ai.connectors.base import AIConnector

logger = logging.getLogger("aksara.ai.connectors.http")


class HttpConnector(AIConnector):
    """Generic HTTP connector for custom LLM APIs."""

    provider: str = "http"

    def __init__(
        self,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> None:
        self.endpoint = (
            endpoint or os.environ.get("AI_HTTP_ENDPOINT", "")
            or "http://localhost:8080/v1/chat/completions"
        ).rstrip("/")
        self.api_key = api_key or os.environ.get("AI_HTTP_API_KEY", "")
        self.custom_headers = headers or {}
        self.extra = kwargs

    # -----------------------------------------------------------------
    # chat
    # -----------------------------------------------------------------

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        import httpx

        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            **self.custom_headers,
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # Send in OpenAI-compatible format (most custom endpoints expect this)
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }

        t0 = self._timer()
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    self.endpoint,
                    json=payload,
                    headers=headers,
                )
            elapsed = self._timer() - t0
            data = resp.json()

            if resp.status_code != 200:
                error_msg = ""
                if isinstance(data, dict):
                    error_msg = data.get("error", {}).get("message", "") if isinstance(data.get("error"), dict) else str(data.get("error", ""))
                return self._normalise_response(
                    ok=False,
                    provider=self.provider,
                    model=model,
                    error=error_msg or resp.text,
                    raw=data,
                    elapsed_ms=elapsed,
                )

            # Try OpenAI-compatible extraction first
            text = ""
            choices = data.get("choices", [])
            if choices:
                text = choices[0].get("message", {}).get("content", "")
            elif isinstance(data.get("content"), str):
                text = data["content"]
            elif isinstance(data.get("text"), str):
                text = data["text"]
            elif isinstance(data.get("response"), str):
                text = data["response"]

            usage = data.get("usage", {})
            tokens = {
                "prompt": usage.get("prompt_tokens", 0),
                "completion": usage.get("completion_tokens", 0),
                "total": usage.get("total_tokens", 0),
            }

            return self._normalise_response(
                ok=True,
                provider=self.provider,
                model=model,
                text=text,
                tokens=tokens,
                raw=data,
                elapsed_ms=elapsed,
            )
        except Exception as exc:
            elapsed = self._timer() - t0
            logger.warning("HTTP connector error: %s", exc)
            return self._normalise_response(
                ok=False,
                provider=self.provider,
                model=model,
                error=str(exc),
                elapsed_ms=elapsed,
            )

    # -----------------------------------------------------------------
    # health
    # -----------------------------------------------------------------

    async def health(self) -> Dict[str, Any]:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(self.endpoint.rsplit("/", 1)[0] + "/health")
            return {
                "ok": resp.status_code < 500,
                "provider": self.provider,
                "endpoint": self.endpoint,
                "status_code": resp.status_code,
            }
        except Exception as exc:
            return {"ok": False, "provider": self.provider, "error": str(exc)}
