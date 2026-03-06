"""
Aksara AI Connector — OpenAI / Azure OpenAI  (v0.5.30)

Supports both OpenAI and Azure OpenAI (same REST shape).
Uses ``httpx`` — no heavy SDK dependency.

Environment variables:
    OPENAI_API_KEY   — API key
    OPENAI_BASE_URL  — optional base URL override (default: https://api.openai.com/v1)
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from aksara.ai.connectors.base import AIConnector

logger = logging.getLogger("aksara.ai.connectors.openai")


class OpenAIConnector(AIConnector):
    """Connector for OpenAI-compatible chat-completion APIs."""

    provider: str = "openai"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        organization: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = (
            base_url
            or os.environ.get("OPENAI_BASE_URL", "")
            or "https://api.openai.com/v1"
        ).rstrip("/")
        self.organization = organization or os.environ.get("OPENAI_ORGANIZATION")
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

        if not self.api_key:
            return self._normalise_response(
                ok=False,
                provider=self.provider,
                model=model,
                error="OPENAI_API_KEY not set",
            )

        headers: Dict[str, str] = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.organization:
            headers["OpenAI-Organization"] = self.organization

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
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
            elapsed = self._timer() - t0
            data = resp.json()

            if resp.status_code != 200:
                return self._normalise_response(
                    ok=False,
                    provider=self.provider,
                    model=model,
                    error=data.get("error", {}).get("message", resp.text),
                    raw=data,
                    elapsed_ms=elapsed,
                )

            text = ""
            choices = data.get("choices", [])
            if choices:
                text = choices[0].get("message", {}).get("content", "")

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
            logger.warning("OpenAI connector error: %s", exc)
            return self._normalise_response(
                ok=False,
                provider=self.provider,
                model=model,
                error=str(exc),
                elapsed_ms=elapsed,
            )

    # -----------------------------------------------------------------
    # embed
    # -----------------------------------------------------------------

    async def embed(
        self,
        texts: List[str],
        model: str,
        **kwargs: Any,
    ) -> List[List[float]]:
        import httpx

        if not self.api_key:
            return []

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {"model": model, "input": texts, **kwargs}

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self.base_url}/embeddings",
                    json=payload,
                    headers=headers,
                )
            data = resp.json()
            if resp.status_code == 200:
                return [item["embedding"] for item in data.get("data", [])]
        except Exception as exc:
            logger.warning("OpenAI embed error: %s", exc)
        return []

    # -----------------------------------------------------------------
    # health
    # -----------------------------------------------------------------

    async def health(self) -> Dict[str, Any]:
        import httpx

        if not self.api_key:
            return {"ok": False, "provider": self.provider, "error": "No API key"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
            return {
                "ok": resp.status_code == 200,
                "provider": self.provider,
                "status_code": resp.status_code,
            }
        except Exception as exc:
            return {"ok": False, "provider": self.provider, "error": str(exc)}
