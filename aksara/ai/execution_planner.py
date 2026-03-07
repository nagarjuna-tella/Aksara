"""
Aksara AI Execution Planner  (v0.5.37)

Converts an ``IntentMatch`` into an ``ExecutionPlan`` — an ordered list
of pipeline steps the Orchestrator should execute.

The planner defines *what* to run and in *what order*, but does NOT
execute anything itself.

Usage::

    from aksara.ai.intent_classifier import classify_intent
    from aksara.ai.execution_planner import build_execution_plan

    match = classify_intent("analyze my project")
    plan  = build_execution_plan(match)
    # ExecutionPlan(
    #     intent="project_analysis",
    #     steps=[
    #         "build_project_graph",
    #         "run_architecture_review",
    #         "run_performance_analysis",
    #         "run_debugger",
    #         "run_diagnostics",
    #     ],
    # )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from aksara.ai.intent_classifier import (
    ARCHITECTURE_REVIEW,
    DEBUG_ANALYSIS,
    PERFORMANCE_INVESTIGATION,
    PROJECT_ANALYSIS,
    ROUTE_ANALYSIS,
    SCHEMA_EXPLANATION,
    IntentMatch,
)


# ─── Step Constants ──────────────────────────────────────────────────────────
# Canonical step names used throughout the orchestration layer.

STEP_BUILD_PROJECT_GRAPH = "build_project_graph"
STEP_RUN_ARCHITECTURE_REVIEW = "run_architecture_review"
STEP_RUN_PERFORMANCE_ANALYSIS = "run_performance_analysis"
STEP_RUN_DEBUGGER = "run_debugger"
STEP_RUN_DIAGNOSTICS = "run_diagnostics"
STEP_EXPLAIN_SCHEMA = "explain_schema"
STEP_ANALYZE_ROUTE = "analyze_route"


# ─── ExecutionPlan ───────────────────────────────────────────────────────────

@dataclass
class ExecutionPlan:
    """An ordered list of pipeline steps for the Orchestrator.

    Attributes
    ----------
    intent : str
        The classified intent that produced this plan.
    steps : list[str]
        Ordered step identifiers.
    context : dict
        Entities and metadata forwarded from the intent match.
    """

    intent: str = "unknown"
    steps: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)


# ─── Intent → Steps Mapping ─────────────────────────────────────────────────

_INTENT_PIPELINES: Dict[str, List[str]] = {
    ARCHITECTURE_REVIEW: [
        STEP_BUILD_PROJECT_GRAPH,
        STEP_RUN_ARCHITECTURE_REVIEW,
    ],
    PERFORMANCE_INVESTIGATION: [
        STEP_BUILD_PROJECT_GRAPH,
        STEP_RUN_PERFORMANCE_ANALYSIS,
    ],
    DEBUG_ANALYSIS: [
        STEP_BUILD_PROJECT_GRAPH,
        STEP_RUN_DEBUGGER,
    ],
    PROJECT_ANALYSIS: [
        STEP_BUILD_PROJECT_GRAPH,
        STEP_RUN_ARCHITECTURE_REVIEW,
        STEP_RUN_PERFORMANCE_ANALYSIS,
        STEP_RUN_DEBUGGER,
        STEP_RUN_DIAGNOSTICS,
    ],
    SCHEMA_EXPLANATION: [
        STEP_BUILD_PROJECT_GRAPH,
        STEP_EXPLAIN_SCHEMA,
    ],
    ROUTE_ANALYSIS: [
        STEP_BUILD_PROJECT_GRAPH,
        STEP_ANALYZE_ROUTE,
    ],
}

# Full investigation pipeline (used by ``aksara ai investigate``)
INVESTIGATION_PIPELINE: List[str] = [
    STEP_BUILD_PROJECT_GRAPH,
    STEP_RUN_ARCHITECTURE_REVIEW,
    STEP_RUN_PERFORMANCE_ANALYSIS,
    STEP_RUN_DEBUGGER,
    STEP_RUN_DIAGNOSTICS,
]


# ─── Public API ──────────────────────────────────────────────────────────────

def build_execution_plan(match: IntentMatch) -> ExecutionPlan:
    """Convert an ``IntentMatch`` into an ``ExecutionPlan``.

    Parameters
    ----------
    match : IntentMatch
        The classified intent.

    Returns
    -------
    ExecutionPlan
        Ordered steps the orchestrator should execute.
    """
    steps = _INTENT_PIPELINES.get(match.intent, [])

    # Unknown intents get a minimal graph-only plan
    if not steps and match.intent != "unknown":
        steps = [STEP_BUILD_PROJECT_GRAPH]

    return ExecutionPlan(
        intent=match.intent,
        steps=list(steps),  # copy to avoid mutating the template
        context=dict(match.entities),
    )


def build_investigation_plan() -> ExecutionPlan:
    """Build the full investigation pipeline plan.

    This is used by ``aksara ai investigate`` and the *Investigate Project*
    action in the UI.

    Returns
    -------
    ExecutionPlan
    """
    return ExecutionPlan(
        intent=PROJECT_ANALYSIS,
        steps=list(INVESTIGATION_PIPELINE),
        context={},
    )
