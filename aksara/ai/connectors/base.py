"""
Aksara AI Connector — Base Interface  (v0.5.30)

All AI connectors must inherit from ``AIConnector`` and implement
``chat()`` at minimum.  ``embed()`` and ``health()`` have default stubs.

The base class enforces a normalised response shape::

    {
        "ok": True,
        "provider": "openai",
        "model": "gpt-4o",
        "text": "...",
        "tokens": {"prompt": 42, "completion": 80, "total": 122},
        "raw": {...}
    }
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional


class AIConnector:
    """Abstract base for all Aksara AI connectors."""

    provider: str = "base"

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Send a chat-completion request and return normalised output.

        Subclasses **must** override this method.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement chat()"
        )

    async def embed(
        self,
        texts: List[str],
        model: str,
        **kwargs: Any,
    ) -> List[List[float]]:
        """Return embedding vectors for *texts*.

        Optional — not all providers support embeddings.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement embed()"
        )

    async def health(self) -> Dict[str, Any]:
        """Quick reachability check — returns ``{"ok": True}`` by default."""
        return {"ok": True, "provider": self.provider}

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _normalise_response(
        *,
        ok: bool,
        provider: str,
        model: str,
        text: str = "",
        tokens: Optional[Dict[str, int]] = None,
        raw: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        elapsed_ms: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Build the standard connector response envelope."""
        return {
            "ok": ok,
            "provider": provider,
            "model": model,
            "text": text,
            "tokens": tokens or {},
            "raw": raw or {},
            "error": error,
            "elapsed_ms": elapsed_ms,
        }

    @staticmethod
    def _timer() -> float:
        """Return a monotonic timestamp (ms)."""
        return time.monotonic() * 1000
