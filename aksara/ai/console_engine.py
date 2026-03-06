"""
Aksara AI Console Engine  (v0.5.31)

Orchestrates the Interactive AI Console pipeline:

    1. Receive natural-language message from user
    2. Detect intent via ``aksara.ai.intent_router``
    3. Build context via ``aksara.ai.console_context``
    4. Dispatch to the matching AI Flow builder
    5. Execute the prompt pack via ``aksara.ai.runtime``
    6. Return a structured ``ConsoleResponse``

Entry point::

    from aksara.ai.console_engine import run_console_query
    result = await run_console_query("explain the User model")

Safety:
    The engine NEVER modifies code automatically.  It only returns
    analysis / suggestions / explanations.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger("aksara.ai.console")


async def run_console_query(
    message: str,
    *,
    provider_override: Optional[str] = None,
    model_override: Optional[str] = None,
) -> Dict[str, Any]:
    """Run a natural-language console query through the full pipeline.

    Parameters
    ----------
    message : str
        The user's console input, e.g. ``"explain the User model"``.
    provider_override : str, optional
        Override the AI provider.
    model_override : str, optional
        Override the AI model.

    Returns
    -------
    dict
        Structured response::

            {
                "ok": True/False,
                "intent": "explain_model",
                "flow_type": "model",
                "action_key": "explain_model",
                "confidence": 0.91,
                "extracted_context": {"model_name": "User"},
                "prompt_pack": { ... },
                "execution": { ... },
                "suggestions": ["suggest_constraints", ...],
                "error": None,
                "error_code": None,
            }
    """
    t0 = time.monotonic()

    # ── 1. Validate input ─────────────────────────────────────────────────
    if not message or not message.strip():
        return _console_error(
            "Empty message. Type a command like 'explain the User model'.",
            "EMPTY_MESSAGE",
        )

    # ── 2. Detect intent ──────────────────────────────────────────────────
    from aksara.ai.intent_router import detect_intent

    match = detect_intent(message)

    if match.intent == "unknown" or match.confidence < 0.30:
        return _console_error(
            f"Could not understand: '{message}'. "
            "Try 'explain the User model' or 'review GET /api/users'.",
            "UNKNOWN_INTENT",
            intent=match.intent,
            confidence=match.confidence,
        )

    # ── 2b. Debug flow shortcut (v0.5.33) ─────────────────────────────────
    if match.flow_type == "debug":
        return _run_debug_flow(message, match)

    # ── 3. Build / enrich context ─────────────────────────────────────────
    from aksara.ai.console_context import enrich_context

    context = enrich_context(
        flow_type=match.flow_type,
        extracted=match.extracted_context,
    )

    # ── 3b. Inject project-graph context (v0.5.32) ────────────────────────
    try:
        from aksara.ai.graph_context import build_graph_console_context
        graph_ctx = build_graph_console_context(flow_type=match.flow_type)
        context["_graph"] = graph_ctx
    except Exception:
        pass  # graph unavailable — continue without it

    # ── 4. Execute flow ───────────────────────────────────────────────────
    from aksara.studio.ai_flows import execute_flow

    result = await execute_flow(
        flow_type=match.flow_type,
        action_key=match.action_key,
        context=context,
        provider_override=provider_override,
        model_override=model_override,
    )

    # ── 4b. Emit graph event (v0.5.32) ────────────────────────────────────
    _emit_console_event(match, result)

    elapsed = (time.monotonic() - t0) * 1000

    # ── 5. Build suggested next actions ───────────────────────────────────
    suggestions = _get_suggestions(match.action_key)

    ok = result.get("ok", False)
    return {
        "ok": ok,
        "intent": match.intent,
        "flow_type": match.flow_type,
        "action_key": match.action_key,
        "confidence": match.confidence,
        "extracted_context": match.extracted_context,
        "prompt_pack": result.get("prompt_pack"),
        "execution": result.get("execution"),
        "suggestions": suggestions,
        "elapsed_ms": round(elapsed, 1),
        "error": result.get("error") if not ok else None,
        "error_code": result.get("error_code") if not ok else None,
    }


def _get_suggestions(action_key: str) -> list:
    """Return recommended-next action keys for the given action."""
    try:
        from aksara.studio.ai_flows import AI_FLOW_ACTIONS

        meta = AI_FLOW_ACTIONS.get(action_key, {})
        return meta.get("recommended_next", [])
    except Exception:
        return []


def _emit_console_event(match, result: Dict[str, Any]) -> None:
    """Emit a graph event for the console execution (v0.5.32)."""
    try:
        from aksara.ai.graph_events import emit_graph_event

        ok = result.get("ok", False)
        if ok:
            emit_graph_event(
                "ai_flow_executed",
                "console",
                match.action_key,
                severity="info",
                message=f"Console executed {match.flow_type}/{match.action_key}",
                flow_type=match.flow_type,
                confidence=match.confidence,
            )
        else:
            emit_graph_event(
                "console_execution_failed",
                "console",
                match.action_key,
                severity="warning",
                message=result.get("error", "execution failed"),
                flow_type=match.flow_type,
            )
    except Exception:
        pass  # event emission must never break the main action


def _console_error(
    error: str,
    error_code: str,
    *,
    intent: str = "unknown",
    confidence: float = 0.0,
) -> Dict[str, Any]:
    """Build a standardised console error response."""
    return {
        "ok": False,
        "intent": intent,
        "flow_type": "",
        "action_key": "",
        "confidence": confidence,
        "extracted_context": {},
        "prompt_pack": None,
        "execution": None,
        "suggestions": [],
        "elapsed_ms": 0,
        "error": error,
        "error_code": error_code,
    }


def _run_debug_flow(message: str, match) -> Dict[str, Any]:
    """Run the AI Debugger pipeline for debug-intent queries (v0.5.33)."""
    try:
        from aksara.ai.debugger import run_debugger

        report = run_debugger(query=message)
        _emit_console_event(match, {"ok": report.ok})

        return {
            "ok": report.ok,
            "intent": match.intent,
            "flow_type": "debug",
            "action_key": match.action_key,
            "confidence": match.confidence,
            "extracted_context": match.extracted_context,
            "prompt_pack": None,
            "execution": {
                "debug_report": report.to_summary_dict(),
            },
            "suggestions": ["debug_analyze"],
            "elapsed_ms": report.elapsed_ms,
            "error": None if report.ok else report.summary,
            "error_code": None if report.ok else "DEBUG_FAILED",
        }
    except Exception as exc:
        return _console_error(
            f"Debug analysis failed: {exc}",
            "DEBUG_ERROR",
            intent=match.intent,
            confidence=match.confidence,
        )
