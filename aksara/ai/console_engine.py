"""
Aksara AI Console Engine  (v0.5.37)

Orchestrates the Interactive AI Console pipeline:

    1. Receive natural-language message from user
    2. Route through the Intent Engine (v0.5.37)
    3. For orchestrable intents, delegate to the intent engine
    4. For legacy flow intents, use the original flow pipeline
    5. Return a structured ``ConsoleResponse``

Entry point::

    from aksara.ai.console_engine import run_console_query
    result = await run_console_query("explain the User model")

v0.5.37: All prompts now route through ``aksara.ai.intent_engine``
first.  The intent engine classifies intents, builds execution plans,
and orchestrates the analysis pipeline.  Legacy flow-based intents
(model explain, route review, etc.) still fall through to the original
AI Flow execution path.

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

    # ── 1a. Continuation shortcut (v0.5.40) ──────────────────────────────
    # If the user types "continue" or "next", resume the most-recent active
    # investigation session rather than starting a new one.
    if message.strip().lower() in ("continue", "next"):
        try:
            cont_result = _continue_investigation(t0)
            if cont_result is not None:
                return cont_result
        except Exception:
            pass  # fall through if no active session

    # ── 1b. Investigation intent detection (v0.5.39) ─────────────────────
    # If the user asks to "investigate", "analyze the system", or "review
    # my project", create a persistent investigation session with a plan,
    # execute it, and return the full session.  This is an *enhancement*
    # that does not replace any existing flow.
    try:
        inv_result = _try_investigation_flow(message, t0)
        if inv_result is not None:
            return inv_result
    except Exception:
        pass  # fall through to existing pipeline

    # ── 2. Route through Intent Engine (v0.5.37) ─────────────────────────
    # The intent engine handles *heavy* orchestrable intents (architecture,
    # performance, debug, project analysis) that run multiple analyzers.
    # Schema-explanation and route-analysis prompts are better served by the
    # legacy provider-backed pipeline, so those fall through.
    _ORCHESTRABLE_INTENTS = {
        "architecture_review",
        "performance_investigation",
        "debug_analysis",
        "project_analysis",
    }
    # Map intent engine names → legacy flow_type names for compatibility.
    _INTENT_TO_FLOW_TYPE = {
        "debug_analysis": "debug",
        "architecture_review": "architecture_review",
        "performance_investigation": "performance_analysis",
        "project_analysis": "project_analysis",
    }
    try:
        from aksara.ai.intent_classifier import classify_intent

        intent_match = classify_intent(message)
        if (
            intent_match.intent in _ORCHESTRABLE_INTENTS
            and intent_match.confidence >= 0.70
        ):
            from aksara.ai.intent_engine import handle_prompt

            engine_result = handle_prompt(message)
            if engine_result.ok:
                flow = _INTENT_TO_FLOW_TYPE.get(
                    engine_result.intent, engine_result.intent
                )
                elapsed = (time.monotonic() - t0) * 1000
                return {
                    "ok": True,
                    "intent": engine_result.intent,
                    "flow_type": flow,
                    "action_key": engine_result.intent,
                    "confidence": 1.0,
                    "extracted_context": {},
                    "prompt_pack": None,
                    "execution": engine_result.report,
                    "suggestions": [],
                    "elapsed_ms": round(elapsed, 1),
                    "error": None,
                    "error_code": None,
                    "orchestrated": True,
                    "summary": engine_result.summary,
                }
    except Exception:
        pass  # fall through to legacy pipeline

    # ── 3. Legacy intent detection (pre-v0.5.37) ─────────────────────────
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

    # ── 3b. Debug flow shortcut (v0.5.33) ─────────────────────────────────
    if match.flow_type == "debug":
        return _run_debug_flow(message, match)
    # ── 3c. Architecture review shortcut (v0.5.34) ─────────────────
    if match.flow_type == "architecture_review":
        return _run_architecture_review_flow(message, match)
    # ── 3d. Performance analysis shortcut (v0.5.35) ────────────────
    if match.flow_type == "performance_analysis":
        return _run_performance_analysis_flow(message, match)
    # ── 4. Build / enrich context ─────────────────────────────────────────
    from aksara.ai.console_context import enrich_context

    context = enrich_context(
        flow_type=match.flow_type,
        extracted=match.extracted_context,
    )

    # ── 4b. Inject project-graph context (v0.5.32) ────────────────────────
    try:
        from aksara.ai.graph_context import build_graph_console_context
        graph_ctx = build_graph_console_context(flow_type=match.flow_type)
        context["_graph"] = graph_ctx
    except Exception:
        pass  # graph unavailable — continue without it

    # ── 5. Execute flow ───────────────────────────────────────────────────
    from aksara.studio.ai_flows import execute_flow

    result = await execute_flow(
        flow_type=match.flow_type,
        action_key=match.action_key,
        context=context,
        provider_override=provider_override,
        model_override=model_override,
    )

    # ── 5b. Emit graph event (v0.5.32) ────────────────────────────────────
    _emit_console_event(match, result)

    elapsed = (time.monotonic() - t0) * 1000

    # ── 6. Build suggested next actions ───────────────────────────────────
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


# ─── Investigation Flow (v0.5.39) ────────────────────────────────────────────

import re as _re

_INVESTIGATE_RE = _re.compile(
    r"\b(investigate|investigation|analyze\s+(?:the\s+)?(?:system|project|app|codebase)"
    r"|review\s+(?:my\s+)?(?:project|system|app|codebase)"
    r"|deep\s+(?:dive|analysis)"
    r"|full\s+(?:analysis|review|investigation))\b",
    _re.IGNORECASE,
)


def _try_investigation_flow(
    message: str, t0: float
) -> Optional[Dict[str, Any]]:
    """Detect investigation intent and run a full investigation session.

    Returns ``None`` if the message is not an investigation request,
    allowing the caller to fall through to other pipelines.
    """
    if not _INVESTIGATE_RE.search(message):
        return None

    from aksara.ai.session_store import create_session
    from aksara.ai.plan_builder import build_plan
    from aksara.ai.investigation_runner import execute_investigation

    session = create_session(message)
    session.status = "planning"
    plan = build_plan(message)
    session.plan = plan
    session.status = "running"

    session = execute_investigation(session)

    elapsed = (time.monotonic() - t0) * 1000
    return {
        "ok": session.status == "completed",
        "intent": "investigation",
        "flow_type": "investigation",
        "action_key": "investigate",
        "confidence": 1.0,
        "extracted_context": {"goal": message},
        "prompt_pack": None,
        "execution": {
            "investigation_session": session.to_dict(),
        },
        "suggestions": ["investigate"],
        "elapsed_ms": round(elapsed, 1),
        "error": None if session.status == "completed" else "Investigation failed",
        "error_code": None if session.status == "completed" else "INVESTIGATION_FAILED",
        "investigation": True,
        "session_id": session.id,
    }


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
            "suggestions": ["architecture_review", "performance_analyze"],
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


def _run_architecture_review_flow(message: str, match) -> Dict[str, Any]:
    """Run the AI Architecture Review pipeline for review-intent queries (v0.5.34)."""
    try:
        from aksara.ai.architecture_review import run_architecture_review

        report = run_architecture_review()
        _emit_console_event(match, {"ok": report.ok})

        return {
            "ok": report.ok,
            "intent": match.intent,
            "flow_type": "architecture_review",
            "action_key": match.action_key,
            "confidence": match.confidence,
            "extracted_context": match.extracted_context,
            "prompt_pack": None,
            "execution": {
                "architecture_report": report.to_summary_dict(),
            },
            "suggestions": ["debug_analyze", "performance_analyze"],
            "elapsed_ms": report.elapsed_ms,
            "error": None if report.ok else "Architecture review failed",
            "error_code": None if report.ok else "REVIEW_FAILED",
        }
    except Exception as exc:
        return _console_error(
            f"Architecture review failed: {exc}",
            "REVIEW_ERROR",
            intent=match.intent,
            confidence=match.confidence,
        )


def _run_performance_analysis_flow(message: str, match) -> Dict[str, Any]:
    """Run the AI Performance Analyzer pipeline for perf-intent queries (v0.5.35)."""
    try:
        from aksara.ai.performance_analyzer import run_performance_analysis

        report = run_performance_analysis()
        _emit_console_event(match, {"ok": report.ok})

        return {
            "ok": report.ok,
            "intent": match.intent,
            "flow_type": "performance_analysis",
            "action_key": match.action_key,
            "confidence": match.confidence,
            "extracted_context": match.extracted_context,
            "prompt_pack": None,
            "execution": {
                "performance_report": report.to_summary_dict(),
            },
            "suggestions": ["debug_analyze", "architecture_review"],
            "elapsed_ms": report.elapsed_ms,
            "error": None if report.ok else "Performance analysis failed",
            "error_code": None if report.ok else "ANALYSIS_FAILED",
        }
    except Exception as exc:
        return _console_error(
            f"Performance analysis failed: {exc}",
            "ANALYSIS_ERROR",
            intent=match.intent,
            confidence=match.confidence,
        )


# ─── Investigation Continuation (v0.5.40) ────────────────────────────────────


def _continue_investigation(t0: float) -> Optional[Dict[str, Any]]:
    """Resume the most-recent active investigation session.

    Finds the active session via the session store, executes its next
    pending step, and returns the updated session as a console response.

    Returns ``None`` if there is no active session to continue.
    """
    from aksara.ai.session_store import get_active_session
    from aksara.ai.investigation_runner import execute_next_step

    session = get_active_session()
    if session is None:
        return None

    session = execute_next_step(session)

    elapsed = (time.monotonic() - t0) * 1000

    # Determine progress info
    pending = 0
    done = 0
    if session.plan and session.plan.steps:
        for step in session.plan.steps:
            if step.status == "pending":
                pending += 1
            elif step.status == "done":
                done += 1

    return {
        "ok": session.status != "failed",
        "intent": "investigation_continue",
        "flow_type": "investigation",
        "action_key": "continue_investigation",
        "confidence": 1.0,
        "extracted_context": {"goal": session.goal},
        "prompt_pack": None,
        "execution": {
            "investigation_session": session.to_dict(),
            "steps_done": done,
            "steps_pending": pending,
        },
        "suggestions": ["continue"] if pending > 0 else ["investigate"],
        "elapsed_ms": round(elapsed, 1),
        "error": None if session.status != "failed" else "Investigation step failed",
        "error_code": None if session.status != "failed" else "INVESTIGATION_STEP_FAILED",
        "investigation": True,
        "session_id": session.id,
    }
