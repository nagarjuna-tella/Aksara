"""
Aksara AI Intent Engine  (v0.5.37)

Thin orchestration entry point that wires together:

    1. **Intent Classifier** — classify the prompt
    2. **Execution Planner** — build the pipeline
    3. **Orchestrator** — execute the pipeline

Usage::

    from aksara.ai.intent_engine import handle_prompt

    result = handle_prompt("why is /api/users slow?")
    print(result.summary)

    # Or run a full investigation:
    from aksara.ai.intent_engine import run_investigation
    result = run_investigation()

The intent engine is the single entry point for all AI interactions
coming from the AI Console, CLI, or any external caller.
"""

from __future__ import annotations

import logging
from typing import Optional

from aksara.ai.intent_classifier import IntentMatch, classify_intent
from aksara.ai.execution_planner import (
    ExecutionPlan,
    build_execution_plan,
    build_investigation_plan,
)
from aksara.ai.orchestrator import OrchestrationResult, execute_plan

logger = logging.getLogger("aksara.ai.intent_engine")


def handle_prompt(prompt: str) -> OrchestrationResult:
    """Process a natural-language prompt through the full pipeline.

    Flow::

        classify intent → build execution plan → execute plan → result

    Parameters
    ----------
    prompt : str
        User input, e.g. ``"why is /api/users slow?"``.

    Returns
    -------
    OrchestrationResult
        Unified result with report sections from each analyzer.
    """
    if not prompt or not prompt.strip():
        return OrchestrationResult(
            ok=False,
            intent="unknown",
            summary="Empty prompt provided.",
        )

    match = classify_intent(prompt)

    if match.intent == "unknown" or match.confidence < 0.30:
        return OrchestrationResult(
            ok=False,
            intent=match.intent,
            summary=(
                f"Could not understand: '{prompt}'. "
                "Try 'explain my architecture' or 'why is /api/users slow?'."
            ),
        )

    plan = build_execution_plan(match)
    result = execute_plan(plan)

    # Emit graph event for tracking
    _emit_engine_event(match, result)

    return result


def run_investigation() -> OrchestrationResult:
    """Run the full AI Investigation pipeline.

    Executes all analysis steps:
    - build_project_graph
    - run_architecture_review
    - run_performance_analysis
    - run_debugger
    - run_diagnostics

    Returns
    -------
    OrchestrationResult
        System Intelligence Report.
    """
    plan = build_investigation_plan()
    result = execute_plan(plan)

    _emit_engine_event(
        IntentMatch(intent="project_analysis", confidence=1.0, raw_prompt="investigate"),
        result,
    )

    return result


def classify_and_plan(prompt: str) -> tuple[IntentMatch, ExecutionPlan]:
    """Classify a prompt and build a plan without executing.

    Useful for previewing what the engine would do.

    Parameters
    ----------
    prompt : str

    Returns
    -------
    tuple[IntentMatch, ExecutionPlan]
    """
    match = classify_intent(prompt)
    plan = build_execution_plan(match)
    return match, plan


def _emit_engine_event(match: IntentMatch, result: OrchestrationResult) -> None:
    """Emit a graph event for the intent engine execution."""
    try:
        from aksara.ai.graph_events import emit_graph_event

        if result.ok:
            emit_graph_event(
                "ai_flow_executed",
                "intent_engine",
                match.intent,
                severity="info",
                message=f"Intent engine handled '{match.intent}' ({result.elapsed_ms:.0f}ms)",
                intent=match.intent,
                confidence=match.confidence,
            )
        else:
            emit_graph_event(
                "console_execution_failed",
                "intent_engine",
                match.intent,
                severity="warning",
                message=result.summary[:200],
                intent=match.intent,
            )
    except Exception:
        pass  # event emission must never break the orchestration
