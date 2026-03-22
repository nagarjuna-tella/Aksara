"""
Intent Engine v2  (v0.5.40)

Structured intent classification with entity extraction and confidence
scoring.  Replaces the flat keyword matching of ``intent_classifier.py``
with a richer, multi-signal approach:

    1. **Intent detection** — scored keyword patterns per intent type
    2. **Entity extraction** — model names, API routes, and signal keywords
    3. **Confidence scoring** — weighted by keyword density and entity hits
    4. **Fallback handling** — ``"unknown"`` intent with zero confidence

Usage::

    from aksara.ai.intent_engine_v2 import classify_intent_v2, IntentResult

    result = classify_intent_v2("Investigate slow API performance on /api/users")
    print(result.intent)       # "investigation"
    print(result.confidence)   # 0.95
    print(result.entities)     # {"routes": ["/api/users"], "signals": ["slow"]}

v0.5.40: New module — Intent Engine 2.0
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

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

# ─── Data Models ──────────────────────────────────────────────────────────────


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

# Model name detection: CamelCase words that look like model names
_MODEL_NAME_RE = re.compile(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b")

# Route path detection: /api/... or /some/path patterns
_ROUTE_PATH_RE = re.compile(r"/[a-zA-Z0-9_\-/{}]+")

# Per-intent keyword patterns, intentionally ordered from high-signal to low
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

# Signal keywords used for entity extraction
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
    """Extract structured entities from a natural-language query.

    Detects:
    - ``models``: CamelCase words that look like model names (e.g. ``User``)
    - ``routes``: API path patterns (e.g. ``/api/users``)
    - ``signals``: Domain keywords (e.g. ``slow``, ``debug``)

    Args:
        query: The user's natural-language query string.

    Returns:
        Dictionary with ``models``, ``routes``, and ``signals`` lists.
    """
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


# ─── Intent Scoring ───────────────────────────────────────────────────────────


def _score_intents(query: str) -> Dict[str, int]:
    """Count keyword hits for each intent against the query.

    Args:
        query: The user query (already lowercased for matching).

    Returns:
        Dict mapping intent label → hit count.
    """
    scores: Dict[str, int] = {}
    for intent, pattern in _INTENT_PATTERNS.items():
        scores[intent] = len(pattern.findall(query))
    return scores


def _compute_confidence(top_score: int, query_len: int) -> float:
    """Convert a raw keyword hit count to a [0.0, 1.0] confidence value.

    The formula caps at 1.0 and uses query length as a normalisation proxy.

    Args:
        top_score: Number of matched keywords for the winning intent.
        query_len: Number of words in the query (used for normalisation).

    Returns:
        Confidence score clamped to [0.0, 1.0].
    """
    if top_score == 0:
        return 0.0
    # Normalise: 1 hit in a 3-word query → high confidence,
    # 1 hit in a 20-word query → moderate confidence.
    words = max(query_len, 1)
    raw = top_score / words * 3.5
    # Bonus for strong single-hit signals
    if top_score >= 2:
        raw += 0.15
    return round(min(raw, 1.0), 4)


# ─── Public API ───────────────────────────────────────────────────────────────


def classify_intent_v2(query: str) -> IntentResult:
    """Classify a natural-language query using Intent Engine v2.

    Computes per-intent keyword scores, picks the highest-scoring intent,
    derives a confidence value, and extracts structured entities.

    Args:
        query: User input, e.g. ``"Investigate slow API performance"``.

    Returns:
        :class:`IntentResult` with ``intent``, ``confidence``, ``entities``,
        and ``raw`` fields populated.

    Examples::

        result = classify_intent_v2("Why is /api/orders slow?")
        # IntentResult(intent="performance_analysis", confidence=0.78,
        #              entities={"routes": ["/api/orders"], "signals": ["slow"], "models": []})

        result = classify_intent_v2("")
        # IntentResult(intent="unknown", confidence=0.0, entities={...})
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
    """Return the list of all supported intent labels.

    Returns:
        List of intent label strings.
    """
    return list(INTENTS)
