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

    # ── 1c. Conversational handler (v0.5.43) ──────────────────────────────
    # Greetings, identity questions, and help requests are answered instantly
    # without involving the intent engine or any LLM provider.
    conv_result = _handle_conversational(message, t0)
    if conv_result is not None:
        return conv_result

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
        return _llm_freeform_fallback(message, provider_override, model_override, t0)

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
        extracted={**match.extracted_context, "action_key": match.action_key},
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


# ─── Conversational / Identity / Help patterns (v0.5.43) ─────────────────────

_GREET_RE = _re.compile(
    r"^\s*(?:hi|hey|hello|howdy|yo|greetings|hiya|heya)\b"
    r"|^(?:good\s+)?(?:morning|afternoon|evening|day)\b",
    _re.IGNORECASE,
)
_IDENTITY_RE = _re.compile(
    r"\b(?:who|what)\s+(?:are|r)\s+you\b"
    r"|\bintroduce\s+yourself\b"
    r"|\bwhat\s+(?:can|do)\s+you\s+(?:do|help|know)\b"
    r"|\byour\s+(?:name|purpose|role|job)\b",
    _re.IGNORECASE,
)
_HELP_RE = _re.compile(
    r"^\s*(?:help|commands|usage)\s*$"
    r"|\bshow\s+(?:me\s+)?commands\b"
    r"|\bwhat\s+commands\b"
    r"|\blist\s+(?:commands|capabilities|features|options)\b"
    r"|\bwhat\s+can\s+I\s+(?:do|ask|type)\b",
    _re.IGNORECASE,
)


def _console_conversational(
    content: str,
    intent_name: str,
    t0: float,
) -> Dict[str, Any]:
    """Build a successful conversational (non-LLM) response dict."""
    elapsed = (time.monotonic() - t0) * 1000
    return {
        "ok": True,
        "intent": intent_name,
        "flow_type": "conversational",
        "action_key": intent_name,
        "confidence": 1.0,
        "extracted_context": {},
        "prompt_pack": None,
        "execution": {"response": content, "mode": "conversational"},
        "suggestions": [],
        "elapsed_ms": round(elapsed, 1),
        "error": None,
        "error_code": None,
        "conversational": True,
    }


def _build_help_text() -> str:
    """Return markdown help text listing all available console commands."""
    return (
        "## Aksara AI — Available Commands\n\n"
        "### Exploration\n"
        "- `explain the User model` — deep dive into any model\n"
        "- `review GET /api/users` — analyze a specific route\n"
        "- `suggest indexes for users` — index recommendations\n"
        "- `explain migration impact` — understand migration effects\n\n"
        "### Architecture & Performance\n"
        "- `architecture review` — score your project A–F\n"
        "- `performance analysis` — find slow queries and N+1 issues\n"
        "- `debug analysis` — automated root cause analysis\n\n"
        "### Investigation\n"
        "- `investigate my project` — full multi-step deep investigation\n"
        "- `continue` or `next` — continue an active investigation\n\n"
        "### Freeform (requires AI provider)\n"
        "- Ask anything about your codebase in plain English\n"
        "- Set `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `OLLAMA_BASE_URL` to unlock\n\n"
        "_Type any of the above or describe what you need in plain English._"
    )


def _handle_conversational(
    message: str, t0: float
) -> Optional[Dict[str, Any]]:
    """Handle greetings, identity questions, and help requests without LLM.

    Returns a conversational response dict on match, or ``None`` to allow
    the caller to fall through to structured-intent pipelines.
    """
    msg = message.strip()

    if _GREET_RE.search(msg):
        return _console_conversational(
            "Hello! I'm **Aksara AI**, your embedded development assistant.\n\n"
            "I can help you:\n"
            "- **Explore** models, routes, and schema — `explain the User model`\n"
            "- **Review** architecture and performance — `architecture review`\n"
            "- **Debug** issues — `debug analysis`\n"
            "- **Investigate** your entire project — `investigate my project`\n"
            "- **Answer** anything about your codebase (with an AI provider configured)\n\n"
            "Type `help` to see all available commands.",
            "greet",
            t0,
        )

    if _IDENTITY_RE.search(msg):
        return _console_conversational(
            "I'm **Aksara AI** — an intelligent assistant built into the Aksara framework.\n\n"
            "I have full context of your project:\n"
            "- **Models** and database schema\n"
            "- **API routes** and endpoint definitions\n"
            "- **Migrations** and schema history\n"
            "- **Performance** metrics and architecture health\n\n"
            "I work in two modes:\n"
            "1. **Built-in analysis** — always available, no API key needed\n"
            "2. **Freeform AI** — answer any question using your project context "
            "(requires `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `OLLAMA_BASE_URL`)\n\n"
            "Type `help` to see everything I can do.",
            "identity",
            t0,
        )

    if _HELP_RE.search(msg):
        return _console_conversational(_build_help_text(), "help", t0)

    return None


# ─── LLM Freeform Fallback (v0.5.43) ─────────────────────────────────────────


def _build_aksara_system_prompt(registry_summary: Optional[str] = None) -> str:
    """Build the LLM system prompt for freeform Aksara AI queries."""
    lines = [
        "You are Aksara AI, an intelligent development assistant embedded inside the "
        "Aksara backend framework.",
        "You help developers understand, debug, optimize, and extend their backend "
        "applications built with Aksara (FastAPI + asyncpg + PostgreSQL).",
        "",
        "You have deep knowledge of:",
        "- The Aksara ORM (async, PostgreSQL-first, Django-inspired syntax)",
        "- FastAPI routes, middleware, and dependency injection",
        "- Pydantic v2 schemas and validation",
        "- Database migrations and schema management",
        "- REST API design best practices",
        "",
        "When answering:",
        "- Be concise, technical, and actionable",
        "- Use Python code examples when helpful",
        "- Reference specific models, routes, or files when you know them",
        "- If you are unsure about project specifics, say so clearly",
    ]
    if registry_summary:
        lines += ["", "Current project context:", registry_summary]
    return "\n".join(lines)


def _llm_freeform_fallback(
    message: str,
    provider_override: Optional[str],
    model_override: Optional[str],
    t0: float,
) -> Dict[str, Any]:
    """LLM-backed freeform handler — last resort before returning an error.

    When no structured intent matches, sends the user's message to the
    configured LLM provider with full project context as the system prompt.
    Falls back to a helpful NO_PROVIDER error when no provider is configured.
    """
    try:
        from aksara.ai.hub_settings import load_aihub_settings
        from aksara.ai.providers_unified import UnifiedAiProvider

        hub = load_aihub_settings()
        
        provider_name = provider_override
        if not provider_name:
            from aksara.studio.utils import _resolve_effective_chat_provider
            provider_name = _resolve_effective_chat_provider(hub)

        provider = None
        if provider_name:
            configured_kinds = {p.kind for p in hub.configured_providers()}
            if provider_name in configured_kinds:
                pc = hub.get_provider(provider_name)
                if pc:
                    provider = pc.to_unified_provider()

        if not provider or not provider.is_configured():
            return _console_error(
                f"I couldn't understand: '{message}'.\n\n"
                "Try built-in commands like `explain the User model`, "
                "`architecture review`, or `investigate my project`.\n\n"
                "**Unlock freeform AI** by setting one of:\n"
                "- `OPENAI_API_KEY` in your `.env`\n"
                "- `ANTHROPIC_API_KEY` in your `.env`\n"
                "- `OLLAMA_BASE_URL=http://localhost:11434` (local)\n\n"
                "Type `help` to see all available commands.",
                "NO_PROVIDER",
                intent="unknown",
                confidence=0.0,
            )

        # Gather minimal project context from the model registry.
        registry_summary: Optional[str] = None
        try:
            from aksara.registry import ModelRegistry

            models = list(ModelRegistry._models.keys())
            if models:
                registry_summary = f"Registered models: {', '.join(models[:20])}"
        except Exception:
            pass

        system_prompt = _build_aksara_system_prompt(registry_summary)
        client = provider.get_llm_client()
        full_prompt = f"{system_prompt}\n\nUser question: {message}\n\nAnswer:"

        kwargs: Dict[str, Any] = {"max_tokens": 1200}
        if model_override:
            kwargs["model"] = model_override
        response_text = client.generate(full_prompt, **kwargs)

        elapsed = (time.monotonic() - t0) * 1000
        return {
            "ok": True,
            "intent": "freeform",
            "flow_type": "freeform",
            "action_key": "freeform_query",
            "confidence": 0.5,
            "extracted_context": {},
            "prompt_pack": None,
            "execution": {"response": response_text, "mode": "freeform_llm"},
            "suggestions": [
                "explain the User model",
                "architecture review",
                "investigate my project",
            ],
            "elapsed_ms": round(elapsed, 1),
            "error": None,
            "error_code": None,
            "freeform": True,
        }
    except Exception as exc:
        return _console_error(
            f"Freeform query failed: {exc}. "
            "Try a structured command like `explain the User model` or `architecture review`.",
            "FREEFORM_ERROR",
        )
