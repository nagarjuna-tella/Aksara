"""
AI Investigation Plan Builder  (v0.5.39)

Rule-based plan construction that maps a user's natural-language goal
to an ordered list of investigation steps.  No LLM calls — the builder
uses keyword matching to select a strategy and assemble steps.

Strategies
----------
- **performance**: Triggered by "slow", "performance", "latency", "n+1", "query".
- **architecture**: Triggered by "architecture", "coupling", "structure", "design".
- **debug**: Triggered by "bug", "error", "debug", "crash", "exception", "traceback".
- **generic**: Fallback — runs the full pipeline (graph → architecture → performance → debug).

Usage::

    from aksara.ai.plan_builder import build_plan
    plan = build_plan("Why is the app slow?")
    assert plan.strategy == "performance"
"""

from __future__ import annotations

import logging
import re
from typing import List

from aksara.ai.investigation import InvestigationPlan, InvestigationStep

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
