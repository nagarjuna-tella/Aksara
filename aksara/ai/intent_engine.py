"""
Aksara AI Intent Engine  (v0.5.41)

Thin orchestration entry point that wires together:

    1. **Intent Classifier** — classify the prompt
    2. **Execution Planner** — build the pipeline
    3. **Orchestrator** — execute the pipeline

Also provides Intent Engine v2 — structured intent classification with
entity extraction and confidence scoring (formerly ``intent_engine_v2``).

Usage::

    from aksara.ai.intent_engine import handle_prompt

    result = handle_prompt("why is /api/users slow?")
    print(result.summary)

    # Or run a full investigation:
    from aksara.ai.intent_engine import run_investigation
    result = run_investigation()

    # v2 classification:
    from aksara.ai.intent_engine import classify_intent_v2, IntentResult

    result = classify_intent_v2("Investigate slow API performance on /api/users")
    print(result.intent)       # "investigation"
    print(result.confidence)   # 0.95

The intent engine is the single entry point for all AI interactions
coming from the AI Console, CLI, or any external caller.

v0.5.41: Merged intent_engine_v2 into this module (classify_intent_v2,
         IntentResult, INTENTS, and related helpers now live here).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from aksara.ai.intent_classifier import IntentMatch, classify_intent
from aksara.ai.execution_planner import (
    ExecutionPlan,
    build_execution_plan,
    build_investigation_plan,
)
from aksara.ai.orchestrator import OrchestrationResult, execute_plan

logger = logging.getLogger("aksara.ai.intent_engine")

# =============================================================================
# Intent Engine v2 — structured classification (merged from intent_engine_v2)
# =============================================================================

# ─── Intent Labels ───────────────────────────────────────────────────────────

INTENT_INVESTIGATION = "investigation"
INTENT_DEBUG_ANALYSIS = "debug_analysis"
INTENT_PERFORMANCE_ANALYSIS = "performance_analysis"
INTENT_ARCHITECTURE_REVIEW = "architecture_review"
INTENT_SCHEMA_EXPLANATION = "schema_explanation"
INTENT_ROUTE_ANALYSIS = "route_analysis"
INTENT_UNKNOWN = "unknown"

# Ordered list of supported intents for documentation / export
INTENTS: List[str] = [
    INTENT_INVESTIGATION,
    INTENT_DEBUG_ANALYSIS,
    INTENT_PERFORMANCE_ANALYSIS,
    INTENT_ARCHITECTURE_REVIEW,
    INTENT_SCHEMA_EXPLANATION,
    INTENT_ROUTE_ANALYSIS,
    INTENT_UNKNOWN,
]


@dataclass
class IntentResult:
    """Structured result of intent classification with extracted entities.

    Attributes:
        intent: Classified intent label (one of ``INTENTS``).
        confidence: Confidence score in range [0.0, 1.0].
        entities: Extracted entities — models, routes, and signals.
        raw: The original user query string.
    """

    intent: str
    confidence: float
    entities: Dict[str, Any]
    raw: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-safe dictionary."""
        return {
            "intent": self.intent,
            "confidence": round(self.confidence, 4),
            "entities": self.entities,
            "raw": self.raw,
        }


# ─── Regex Patterns ───────────────────────────────────────────────────────────

_MODEL_NAME_RE = re.compile(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b")
_ROUTE_PATH_RE = re.compile(r"/[a-zA-Z0-9_\-/{}]+")

_INTENT_PATTERNS: Dict[str, re.Pattern[str]] = {
    INTENT_INVESTIGATION: re.compile(
        r"\b(investigate|investigation|analyze\s+system|system\s+analysis|"
        r"full\s+analysis|review\s+my\s+project|what.s\s+going\s+on|"
        r"explore|audit|scan|assess)\b",
        re.IGNORECASE,
    ),
    INTENT_DEBUG_ANALYSIS: re.compile(
        r"\b(bug|debug|error|crash|exception|traceback|fail|failing|broken|"
        r"stacktrace|why\s+is\s+it\s+failing|not\s+working|fix)\b",
        re.IGNORECASE,
    ),
    INTENT_PERFORMANCE_ANALYSIS: re.compile(
        r"\b(slow|performance|latency|n\+1|query|queries|optimize|bottleneck|"
        r"cache|fast|speed|timeout|throughput|memory|cpu|heavy)\b",
        re.IGNORECASE,
    ),
    INTENT_ARCHITECTURE_REVIEW: re.compile(
        r"\b(architecture|coupling|structure|design|modularity|dependency|"
        r"dependencies|pattern|review|refactor|technical\s+debt|complexity|"
        r"separation|concerns)\b",
        re.IGNORECASE,
    ),
    INTENT_SCHEMA_EXPLANATION: re.compile(
        r"\b(schema|model|field|table|column|explain|describe|what\s+is|"
        r"show\s+me|definition|definition|type|relationship|foreign\s+key|"
        r"primary\s+key)\b",
        re.IGNORECASE,
    ),
    INTENT_ROUTE_ANALYSIS: re.compile(
        r"\b(route|endpoint|api|view|path|url|method|GET|POST|PUT|PATCH|"
        r"DELETE|handler|controller)\b",
        re.IGNORECASE,
    ),
}

_SIGNAL_KEYWORDS: List[str] = [
    "slow", "performance", "debug", "architecture", "investigate",
    "error", "crash", "optimize", "bottleneck", "n+1", "latency",
    "coupling", "refactor", "schema", "model", "route", "query",
]
_SIGNAL_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _SIGNAL_KEYWORDS) + r")\b",
    re.IGNORECASE,
)


# ─── Entity Extraction ────────────────────────────────────────────────────────


def _extract_entities(query: str) -> Dict[str, Any]:
    """Extract structured entities from a natural-language query."""
    models: List[str] = list(dict.fromkeys(_MODEL_NAME_RE.findall(query)))
    routes: List[str] = list(dict.fromkeys(_ROUTE_PATH_RE.findall(query)))
    signals: List[str] = [
        m.lower() for m in dict.fromkeys(_SIGNAL_RE.findall(query))
    ]
    return {
        "models": models,
        "routes": routes,
        "signals": signals,
    }


def _score_intents(query: str) -> Dict[str, int]:
    """Count keyword hits for each intent against the query."""
    scores: Dict[str, int] = {}
    for intent, pattern in _INTENT_PATTERNS.items():
        scores[intent] = len(pattern.findall(query))
    return scores


def _compute_confidence(top_score: int, query_len: int) -> float:
    """Convert a raw keyword hit count to a [0.0, 1.0] confidence value."""
    if top_score == 0:
        return 0.0
    words = max(query_len, 1)
    raw = top_score / words * 3.5
    if top_score >= 2:
        raw += 0.15
    return round(min(raw, 1.0), 4)


def classify_intent_v2(query: str) -> IntentResult:
    """Classify a natural-language query using Intent Engine v2.

    Args:
        query: User input, e.g. ``"Investigate slow API performance"``.

    Returns:
        :class:`IntentResult` with ``intent``, ``confidence``, ``entities``,
        and ``raw`` fields populated.
    """
    if not query or not query.strip():
        return IntentResult(
            intent=INTENT_UNKNOWN,
            confidence=0.0,
            entities={"models": [], "routes": [], "signals": []},
            raw=query,
        )

    scores = _score_intents(query)
    best_intent = max(scores, key=lambda k: scores[k])
    top_score = scores[best_intent]

    word_count = len(query.split())
    confidence = _compute_confidence(top_score, word_count)

    if top_score == 0:
        best_intent = INTENT_UNKNOWN

    entities = _extract_entities(query)

    return IntentResult(
        intent=best_intent,
        confidence=confidence,
        entities=entities,
        raw=query,
    )


def get_supported_intents() -> List[str]:
    """Return the list of all supported intent labels."""
    return list(INTENTS)


# =============================================================================
# Intent Engine v1 — orchestration entry point
# =============================================================================

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
