"""
Aksara AI Connector — Ollama  (v0.5.30)

Local Ollama instance connector — critical for OSS usage.
Default endpoint: ``http://localhost:11434/api/chat``

Environment variables:
    OLLAMA_BASE_URL  — override base URL (default: http://localhost:11434)
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from aksara.ai.connectors.base import AIConnector

logger = logging.getLogger("aksara.ai.connectors.ollama")


class OllamaConnector(AIConnector):
    """Connector for local Ollama instances."""

    provider: str = "ollama"

    def __init__(
        self,
        base_url: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        self.base_url = (
            base_url or os.environ.get("OLLAMA_BASE_URL", "")
            or "http://localhost:11434"
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

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        t0 = self._timer()
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                )
            elapsed = self._timer() - t0
            data = resp.json()

            if resp.status_code != 200:
                return self._normalise_response(
                    ok=False,
                    provider=self.provider,
                    model=model,
                    error=data.get("error", resp.text),
                    raw=data,
                    elapsed_ms=elapsed,
                )

            text = data.get("message", {}).get("content", "")
            tokens = {
                "prompt": data.get("prompt_eval_count", 0),
                "completion": data.get("eval_count", 0),
                "total": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
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
            logger.warning("Ollama connector error: %s", exc)
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

        results: List[List[float]] = []
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                for text in texts:
                    resp = await client.post(
                        f"{self.base_url}/api/embeddings",
                        json={"model": model, "prompt": text},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        results.append(data.get("embedding", []))
                    else:
                        results.append([])
        except Exception as exc:
            logger.warning("Ollama embed error: %s", exc)
        return results

    # -----------------------------------------------------------------
    # health
    # -----------------------------------------------------------------

    async def health(self) -> Dict[str, Any]:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
            return {
                "ok": resp.status_code == 200,
                "provider": self.provider,
                "base_url": self.base_url,
                "models": len(resp.json().get("models", [])) if resp.status_code == 200 else 0,
            }
        except Exception as exc:
            return {"ok": False, "provider": self.provider, "error": str(exc)}
