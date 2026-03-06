"""
Aksara AI Connector — Anthropic / Claude  (v0.5.30)

Uses the Anthropic Messages API (REST).
No SDK dependency — uses ``httpx`` directly.

Environment variables:
    ANTHROPIC_API_KEY  — API key
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from aksara.ai.connectors.base import AIConnector

logger = logging.getLogger("aksara.ai.connectors.anthropic")


class AnthropicConnector(AIConnector):
    """Connector for Anthropic Messages API."""

    provider: str = "anthropic"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.base_url = (
            base_url or os.environ.get("ANTHROPIC_BASE_URL", "")
            or "https://api.anthropic.com"
        ).rstrip("/")
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
                error="ANTHROPIC_API_KEY not set",
            )

        # Anthropic expects system in a separate field, not in messages
        system_text = ""
        user_messages: List[Dict[str, str]] = []
        for msg in messages:
            if msg.get("role") == "system":
                system_text = msg.get("content", "")
            else:
                user_messages.append(msg)

        # Anthropic requires at least one user message
        if not user_messages:
            user_messages = [{"role": "user", "content": "(no content)"}]

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        payload: Dict[str, Any] = {
            "model": model,
            "messages": user_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_text:
            payload["system"] = system_text

        t0 = self._timer()
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self.base_url}/v1/messages",
                    json=payload,
                    headers=headers,
                )
            elapsed = self._timer() - t0
            data = resp.json()

            if resp.status_code != 200:
                error_msg = data.get("error", {}).get("message", resp.text)
                return self._normalise_response(
                    ok=False,
                    provider=self.provider,
                    model=model,
                    error=error_msg,
                    raw=data,
                    elapsed_ms=elapsed,
                )

            # Extract text from content blocks
            text = ""
            content_blocks = data.get("content", [])
            for block in content_blocks:
                if block.get("type") == "text":
                    text += block.get("text", "")

            usage = data.get("usage", {})
            tokens = {
                "prompt": usage.get("input_tokens", 0),
                "completion": usage.get("output_tokens", 0),
                "total": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
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
            logger.warning("Anthropic connector error: %s", exc)
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
        if not self.api_key:
            return {"ok": False, "provider": self.provider, "error": "No API key"}
        # Anthropic doesn't have a /models endpoint, so just validate key format
        return {
            "ok": bool(self.api_key),
            "provider": self.provider,
            "key_set": True,
        }
