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

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from aksara.ai.limits import AgentRuntimeBudget, AgentRuntimeLimits

logger = logging.getLogger("aksara.ai.runtime")


async def run_prompt_pack(
    pack: Dict[str, Any],
    *,
    provider_override: Optional[str] = None,
    model_override: Optional[str] = None,
    limits: AgentRuntimeLimits | None = None,
    budget: AgentRuntimeBudget | None = None,
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
    from aksara.ai.limits import (
        AgentRuntimeBudget,
        AgentRuntimeLimits,
        RuntimeLimitExceeded,
    )

    active_limits = limits or AgentRuntimeLimits()
    active_budget = budget or AgentRuntimeBudget(active_limits)
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
        requested_tokens = int(pack.get("max_tokens", 1024))
        if active_limits.token_budget is not None:
            requested_tokens = min(requested_tokens, active_limits.token_budget - active_budget.tokens)
            if requested_tokens <= 0:
                raise RuntimeLimitExceeded("token_budget_exceeded", "Provider token budget exhausted.")
        try:
            async with asyncio.timeout(
                min(active_limits.run_timeout_seconds, active_limits.provider_timeout_seconds)
            ):
                result = await connector.chat(
                    messages=messages,
                    model=model,
                    temperature=pack.get("temperature", 0.2),
                    max_tokens=requested_tokens,
                )
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            return _error_response("AI provider call timed out.", "PROVIDER_TIMEOUT")
        except Exception as exc:
            logger.exception("AI provider call failed")
            return _error_response(str(exc), "PROVIDER_ERROR")
        elapsed = (time.monotonic() - t0) * 1000

        if not isinstance(result, dict) or not isinstance(result.get("ok"), bool):
            return _error_response("AI provider returned a malformed response.", "MALFORMED_PROVIDER_RESPONSE")

        if not result.get("ok"):
            # v0.5.32: Emit provider_unreachable event
            try:
                from aksara.ai.graph_events import emit_graph_event
                emit_graph_event(
                    "provider_unreachable", "ai_provider", provider,
                    severity="warning",
                    message=result.get("error", "Connector error"),
                    model=model,
                )
            except Exception:
                pass

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

        response_text = result.get("text", "")
        if not isinstance(response_text, str):
            return _error_response("AI provider returned a malformed text response.", "MALFORMED_PROVIDER_RESPONSE")
        tokens = result.get("tokens", {})
        if not isinstance(tokens, dict):
            return _error_response("AI provider returned malformed usage data.", "MALFORMED_PROVIDER_RESPONSE")
        total_tokens = tokens.get("total", 0)
        cost_usd = result.get("cost_usd", result.get("raw", {}).get("cost_usd", 0) if isinstance(result.get("raw"), dict) else 0)
        active_budget.consume_usage(tokens=int(total_tokens or 0), cost_usd=float(cost_usd or 0))
        tool_calls = result.get("tool_calls")
        if tool_calls is None and isinstance(result.get("raw"), dict):
            tool_calls = result["raw"].get("tool_calls", [])
        if tool_calls is not None:
            if not isinstance(tool_calls, list):
                return _error_response("AI provider returned malformed tool calls.", "MALFORMED_PROVIDER_RESPONSE")
            for index, tool_call in enumerate(tool_calls):
                call_id = tool_call.get("id") if isinstance(tool_call, dict) else str(index)
                active_budget.consume_tool_call(str(call_id) if call_id is not None else None)

        return {
            "ok": True,
            "provider": provider,
            "model": model,
            "response": response_text,
            "structured_response": result.get("structured"),
            "tool_calls": tool_calls or [],
            "tokens": tokens,
            "elapsed_ms": elapsed,
            "error": None,
            "raw": result.get("raw", {}),
        }

    except RuntimeLimitExceeded as exc:
        return _error_response(str(exc), exc.code.upper())
    except asyncio.CancelledError:
        raise
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
