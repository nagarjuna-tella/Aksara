"""
AI Investigation Plan Builder  (v0.5.40)

Rule-based plan construction that maps a user's natural-language goal
(or a structured ``IntentResult``) to an ordered list of investigation
steps.  No LLM calls — the builder uses keyword matching to select a
strategy and assemble steps.

Strategies
----------
- **performance**: Triggered by "slow", "performance", "latency", "n+1", "query".
- **architecture**: Triggered by "architecture", "coupling", "structure", "design".
- **debug**: Triggered by "bug", "error", "debug", "crash", "exception", "traceback".
- **generic**: Fallback — runs the full pipeline (graph → architecture → performance → debug).

v0.5.40: Added ``build_plan_from_intent()`` that accepts an ``IntentResult``
from Intent Engine v2, with step priority and dependency metadata.

Usage::

    from aksara.ai.plan_builder import build_plan, build_plan_from_intent
    plan = build_plan("Why is the app slow?")
    assert plan.strategy == "performance"

    from aksara.ai.intent_engine import classify_intent_v2
    intent = classify_intent_v2("Investigate slow API performance")
    plan = build_plan_from_intent(intent)
    assert plan.strategy == "performance"
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Dict, List, Optional

from aksara.ai.investigation import InvestigationPlan, InvestigationStep

if TYPE_CHECKING:
    from aksara.ai.intent_engine import IntentResult

logger = logging.getLogger("aksara.ai.plan_builder")

# ─── Keyword Patterns ────────────────────────────────────────────────────────

_PERFORMANCE_RE = re.compile(
    r"\b(slow|performance|latency|n\+1|query|queries|optimize|bottleneck|cache)\b",
    re.IGNORECASE,
)
_ARCHITECTURE_RE = re.compile(
    r"\b(architecture|coupling|structure|design|modularity|dependency|dependencies)\b",
    re.IGNORECASE,
)
_DEBUG_RE = re.compile(
    r"\b(bug|error|debug|crash|exception|traceback|fail|failing|broken)\b",
    re.IGNORECASE,
)

# ─── Step Templates ──────────────────────────────────────────────────────────

# Canonical step names understood by the investigation runner.
STEP_PROJECT_GRAPH = "project_graph"
STEP_PERFORMANCE = "performance_analysis"
STEP_ARCHITECTURE = "architecture_review"
STEP_DEBUG = "debug_analysis"
STEP_SUMMARISE = "summarise"


def _make_step(name: str) -> InvestigationStep:
    """Create a step with a fresh ID from a canonical name."""
    return InvestigationStep(name=name)


# ─── Strategy Blueprints ─────────────────────────────────────────────────────

_STRATEGIES: dict[str, List[str]] = {
    "performance": [
        STEP_PROJECT_GRAPH,
        STEP_PERFORMANCE,
        STEP_SUMMARISE,
    ],
    "architecture": [
        STEP_PROJECT_GRAPH,
        STEP_ARCHITECTURE,
        STEP_SUMMARISE,
    ],
    "debug": [
        STEP_PROJECT_GRAPH,
        STEP_DEBUG,
        STEP_SUMMARISE,
    ],
    "generic": [
        STEP_PROJECT_GRAPH,
        STEP_ARCHITECTURE,
        STEP_PERFORMANCE,
        STEP_DEBUG,
        STEP_SUMMARISE,
    ],
}

# ─── Public API ──────────────────────────────────────────────────────────────


def build_plan(goal: str) -> InvestigationPlan:
    """Build an investigation plan from a natural-language goal.

    The builder scores each strategy by counting keyword hits and picks
    the best match.  If no keywords match, the ``"generic"`` fallback
    runs the full pipeline.

    Args:
        goal: The user's investigation goal (e.g. ``"Why is the app slow?"``).

    Returns:
        An ``InvestigationPlan`` with ordered steps and a strategy label.
    """
    goal_lower = goal.lower()

    scores: dict[str, int] = {
        "performance": len(_PERFORMANCE_RE.findall(goal_lower)),
        "architecture": len(_ARCHITECTURE_RE.findall(goal_lower)),
        "debug": len(_DEBUG_RE.findall(goal_lower)),
    }

    best = max(scores, key=lambda k: scores[k])
    strategy = best if scores[best] > 0 else "generic"

    step_names = _STRATEGIES[strategy]
    steps = [_make_step(name) for name in step_names]

    logger.debug(
        "Plan for %r: strategy=%s, steps=%s", goal, strategy, step_names
    )
    return InvestigationPlan(goal=goal, steps=steps, strategy=strategy)


# ─── Intent-Based Plan Builder (v0.5.40) ────────────────────────────────────

# Maps intent labels from Intent Engine v2 to plan strategies.
_INTENT_TO_STRATEGY: Dict[str, str] = {
    "performance_analysis": "performance",
    "debug_analysis": "debug",
    "architecture_review": "architecture",
    "investigation": "generic",
    "schema_explanation": "architecture",
    "route_analysis": "performance",
}

# Step priorities — lower number = higher priority / executes earlier.
# Used by the UI to sort and display timeline clearly.
_STEP_PRIORITIES: Dict[str, int] = {
    STEP_PROJECT_GRAPH: 1,
    STEP_ARCHITECTURE: 2,
    STEP_PERFORMANCE: 2,
    STEP_DEBUG: 2,
    STEP_SUMMARISE: 99,
}

# Step dependencies — which steps must complete before this step can run.
_STEP_DEPENDENCIES: Dict[str, List[str]] = {
    STEP_PROJECT_GRAPH: [],
    STEP_ARCHITECTURE: [STEP_PROJECT_GRAPH],
    STEP_PERFORMANCE: [STEP_PROJECT_GRAPH],
    STEP_DEBUG: [STEP_PROJECT_GRAPH],
    STEP_SUMMARISE: [STEP_ARCHITECTURE, STEP_PERFORMANCE, STEP_DEBUG],
}


def _make_step_with_meta(name: str, priority: Optional[int] = None) -> InvestigationStep:
    """Create a step with priority metadata embedded in the label."""
    step = _make_step(name)
    p = priority if priority is not None else _STEP_PRIORITIES.get(name, 5)
    # Store priority in label as structured hint for the runner/UI
    step.label = f"{step.label} [priority={p}]"
    return step


def build_plan_from_intent(intent: "IntentResult") -> InvestigationPlan:
    """Build an investigation plan from a structured ``IntentResult``.

    This is the v0.5.40 upgrade over :func:`build_plan` — it accepts the
    richer context from Intent Engine v2 and applies smarter ordering:

    1. Maps the intent label to a plan strategy.
    2. Selects steps based on the strategy.
    3. Attaches priority and dependency metadata to each step.
    4. Orders steps by priority (lowest number first).
    5. Falls back to ``"generic"`` for unknown intents.

    Args:
        intent: :class:`~aksara.ai.intent_engine.IntentResult` from
                :func:`~aksara.ai.intent_engine.classify_intent_v2`.

    Returns:
        An :class:`~aksara.ai.investigation.InvestigationPlan` with ordered
        steps and a strategy label.

    Example::

        from aksara.ai.intent_engine import classify_intent_v2
        result = classify_intent_v2("Investigate slow API performance")
        plan = build_plan_from_intent(result)
        # plan.strategy == "performance"
        # plan.steps == [project_graph, performance_analysis, summarise]
    """
    strategy = _INTENT_TO_STRATEGY.get(intent.intent, "generic")

    # If entities contain routes, bias towards performance analysis
    if (
        strategy == "generic"
        and intent.entities.get("routes")
        and "slow" in " ".join(intent.entities.get("signals", []))
    ):
        strategy = "performance"

    step_names = _STRATEGIES.get(strategy, _STRATEGIES["generic"])

    # Build steps with priorities and sort by priority
    steps_with_priority = []
    for name in step_names:
        priority = _STEP_PRIORITIES.get(name, 5)
        step = _make_step(name)
        steps_with_priority.append((priority, step))

    steps_with_priority.sort(key=lambda x: x[0])
    steps = [s for _, s in steps_with_priority]

    logger.debug(
        "Intent-based plan: intent=%s strategy=%s steps=%s entities=%s",
        intent.intent,
        strategy,
        step_names,
        intent.entities,
    )
    return InvestigationPlan(goal=intent.raw or strategy, steps=steps, strategy=strategy)


def get_step_dependencies(step_name: str) -> List[str]:
    """Return the list of step names that must complete before ``step_name``.

    Args:
        step_name: Canonical step name (e.g. ``"performance_analysis"``).

    Returns:
        List of prerequisite step names.  Empty list if none or unknown.
    """
    return list(_STEP_DEPENDENCIES.get(step_name, []))


def get_step_priority(step_name: str) -> int:
    """Return the execution priority for ``step_name``.

    Lower numbers run first.  Steps with the same priority may run in
    parallel (future enhancement).

    Args:
        step_name: Canonical step name.

    Returns:
        Integer priority (1 = highest, 99 = summarise).
    """
    return _STEP_PRIORITIES.get(step_name, 5)
