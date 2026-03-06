"""
Aksara AI Execution Runtime  (v0.5.30)

The runtime layer between AI Flow prompt packs and AI connectors.
Responsibilities:

1. Load AI Hub config
2. Resolve provider + model
3. Select connector from registry
4. Execute prompt pack via connector.chat()
5. Return normalised result

Core entry point::

    from aksara.ai.runtime import run_prompt_pack
    result = await run_prompt_pack(pack)

Safety:
    The runtime NEVER modifies code automatically.  It only returns
    analysis / suggestions / explanations.  If changes are suggested,
    CLI commands are returned.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("aksara.ai.runtime")


async def run_prompt_pack(
    pack: Dict[str, Any],
    *,
    provider_override: Optional[str] = None,
    model_override: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute an AI flow prompt pack through a connector.

    Parameters
    ----------
    pack : dict
        A prompt pack (typically ``StudioAiFlowResponse.model_dump()``).
        Must contain ``system_prompt`` and ``user_prompt`` at minimum.
    provider_override : str, optional
        Override the provider from the pack.
    model_override : str, optional
        Override the model from the pack.

    Returns
    -------
    dict
        Normalised execution result::

            {
                "ok": True,
                "provider": "openai",
                "model": "gpt-4o",
                "response": "...",
                "tokens": {"prompt": ..., "completion": ..., "total": ...},
                "elapsed_ms": 1234.5,
                "error": None
            }
    """
    try:
        # 1. Resolve provider + model
        provider = provider_override or pack.get("provider", "")
        model = model_override or pack.get("model", "")

        if not provider:
            # Try to resolve from AI Hub
            provider, model = _resolve_from_hub(model)

        if not provider:
            return _error_response("No AI provider configured.  Configure in AI Hub first.", "AI_HUB_NOT_CONFIGURED")

        if not model:
            model = _default_model_for(provider)

        # 2. Get connector
        from aksara.ai.connectors.registry import get_connector

        try:
            connector = get_connector(provider)
        except ValueError as exc:
            return _error_response(str(exc), "UNKNOWN_PROVIDER")

        # 3. Build messages
        messages = _build_messages(pack)

        # 4. Execute
        t0 = time.monotonic()
        result = await connector.chat(
            messages=messages,
            model=model,
            temperature=pack.get("temperature", 0.2),
            max_tokens=pack.get("max_tokens", 1024),
        )
        elapsed = (time.monotonic() - t0) * 1000

        if not result.get("ok"):
            return {
                "ok": False,
                "provider": provider,
                "model": model,
                "response": "",
                "tokens": result.get("tokens", {}),
                "elapsed_ms": elapsed,
                "error": result.get("error", "Connector error"),
                "raw": result.get("raw", {}),
            }

        return {
            "ok": True,
            "provider": provider,
            "model": model,
            "response": result.get("text", ""),
            "tokens": result.get("tokens", {}),
            "elapsed_ms": elapsed,
            "error": None,
            "raw": result.get("raw", {}),
        }

    except Exception as exc:
        logger.exception("Runtime execution error")
        return _error_response(str(exc), "RUNTIME_ERROR")


def _resolve_from_hub(current_model: str) -> tuple:
    """Try to resolve provider + model from AI Hub settings."""
    try:
        from aksara.ai.hub_settings import load_aihub_settings
        hub = load_aihub_settings()
        hub.resolve_defaults()

        provider = hub.active_provider or ""
        if not provider:
            configured = hub.configured_providers()
            if configured:
                provider = configured[0].kind

        if not current_model:
            model = hub.defaults.chat_model or ""
        else:
            model = current_model

        return provider, model
    except Exception:
        return "", current_model


def _default_model_for(provider: str) -> str:
    """Return a sensible default model for a provider."""
    defaults = {
        "openai": "gpt-4o",
        "azure": "gpt-4o",
        "anthropic": "claude-3-5-sonnet-20241022",
        "ollama": "llama3",
        "http": "default",
        "custom": "default",
    }
    return defaults.get(provider, "default")


def _build_messages(pack: Dict[str, Any]) -> List[Dict[str, str]]:
    """Convert prompt pack fields into a messages list."""
    messages: List[Dict[str, str]] = []

    system_prompt = pack.get("system_prompt", "")
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    user_prompt = pack.get("user_prompt", "")
    if user_prompt:
        messages.append({"role": "user", "content": user_prompt})

    # Fallback if neither prompt is set
    if not messages:
        messages.append({"role": "user", "content": "Hello"})

    return messages


def _error_response(error: str, error_code: str = "RUNTIME_ERROR") -> Dict[str, Any]:
    """Build a standardised error dict."""
    return {
        "ok": False,
        "provider": "",
        "model": "",
        "response": "",
        "tokens": {},
        "elapsed_ms": 0,
        "error": error,
        "error_code": error_code,
    }
