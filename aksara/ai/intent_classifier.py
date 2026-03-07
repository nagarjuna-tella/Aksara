"""
Aksara AI Intent Classifier  (v0.5.37)

Classifies natural-language prompts into structured ``IntentMatch``
objects for the orchestration pipeline.

This module is a pure classifier — it does NOT reference any analyzers,
does NOT make network calls, and has NO side effects.

Usage::

    from aksara.ai.intent_classifier import classify_intent

    match = classify_intent("why is /api/users slow?")
    # IntentMatch(
    #     intent="performance_investigation",
    #     confidence=0.92,
    #     entities={"route": "/api/users"},
    # )

Supported intents (v0.5.37):
    ARCHITECTURE_REVIEW
    PERFORMANCE_INVESTIGATION
    DEBUG_ANALYSIS
    PROJECT_ANALYSIS
    SCHEMA_EXPLANATION
    ROUTE_ANALYSIS
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ─── Intent Enum ─────────────────────────────────────────────────────────────

ARCHITECTURE_REVIEW = "architecture_review"
PERFORMANCE_INVESTIGATION = "performance_investigation"
DEBUG_ANALYSIS = "debug_analysis"
PROJECT_ANALYSIS = "project_analysis"
SCHEMA_EXPLANATION = "schema_explanation"
ROUTE_ANALYSIS = "route_analysis"

SUPPORTED_INTENTS: List[str] = [
    ARCHITECTURE_REVIEW,
    PERFORMANCE_INVESTIGATION,
    DEBUG_ANALYSIS,
    PROJECT_ANALYSIS,
    SCHEMA_EXPLANATION,
    ROUTE_ANALYSIS,
]


# ─── IntentMatch ─────────────────────────────────────────────────────────────

@dataclass
class IntentMatch:
    """Result of intent classification.

    Attributes
    ----------
    intent : str
        One of SUPPORTED_INTENTS, or ``"unknown"``.
    confidence : float
        0.0–1.0 confidence score.
    entities : dict
        Extracted entities (route, model, query, etc.).
    raw_prompt : str
        The original user prompt.
    """

    intent: str = "unknown"
    confidence: float = 0.0
    entities: Dict[str, Any] = field(default_factory=dict)
    raw_prompt: str = ""


# ─── Classification Rules ───────────────────────────────────────────────────
# Each rule maps a regex pattern to an intent with a base confidence.
# Rules are evaluated exhaustively; the best match wins.

_RULES: List[Tuple[re.Pattern, str, float]] = []


def _r(pattern: str, intent: str, confidence: float = 0.85) -> None:
    """Register a classification rule."""
    _RULES.append((re.compile(pattern, re.IGNORECASE), intent, confidence))


# ── Architecture review ──────────────────────────────────────────────────────
_r(r"\barchitecture\b.*\breview\b", ARCHITECTURE_REVIEW, 0.93)
_r(r"\breview\b.*\barchitecture\b", ARCHITECTURE_REVIEW, 0.93)
_r(r"\bexplain\b.*\barchitecture\b", ARCHITECTURE_REVIEW, 0.90)
_r(r"\barchitectur", ARCHITECTURE_REVIEW, 0.88)
_r(r"\bhow\s+healthy\b", ARCHITECTURE_REVIEW, 0.87)
_r(r"\bhealth\s*(score|check)\b", ARCHITECTURE_REVIEW, 0.88)
_r(r"\banti.?pattern", ARCHITECTURE_REVIEW, 0.86)
_r(r"\bcoupling\b", ARCHITECTURE_REVIEW, 0.85)
_r(r"\bcode\s*quality\b", ARCHITECTURE_REVIEW, 0.83)
_r(r"\bdesign\s*(review|issue|risk)\b", ARCHITECTURE_REVIEW, 0.84)
_r(r"\bsystem\s*design\b", ARCHITECTURE_REVIEW, 0.86)

# ── Performance investigation ────────────────────────────────────────────────
_r(r"\bperformance\b", PERFORMANCE_INVESTIGATION, 0.88)
_r(r"\bwhy\b.*\bslow\b", PERFORMANCE_INVESTIGATION, 0.90)
_r(r"\bslow\b.*\b(endpoint|route|api|query)\b", PERFORMANCE_INVESTIGATION, 0.91)
_r(r"\bn\+1\b", PERFORMANCE_INVESTIGATION, 0.90)
_r(r"\bn\s+plus\s+one\b", PERFORMANCE_INVESTIGATION, 0.88)
_r(r"\bquery\s*explosion\b", PERFORMANCE_INVESTIGATION, 0.92)
_r(r"\bmissing\b.*\bindex", PERFORMANCE_INVESTIGATION, 0.87)
_r(r"\boptimize\b", PERFORMANCE_INVESTIGATION, 0.82)
_r(r"\boptimise\b", PERFORMANCE_INVESTIGATION, 0.82)
_r(r"\bbottleneck\b", PERFORMANCE_INVESTIGATION, 0.89)
_r(r"\blatency\b", PERFORMANCE_INVESTIGATION, 0.86)

# ── Debug analysis ───────────────────────────────────────────────────────────
_r(r"\bdebug\b", DEBUG_ANALYSIS, 0.88)
_r(r"\broot\s*cause\b", DEBUG_ANALYSIS, 0.92)
_r(r"\bwhy\b.*\bfail", DEBUG_ANALYSIS, 0.88)
_r(r"\bwhy\b.*\bbroken\b", DEBUG_ANALYSIS, 0.88)
_r(r"\bwhy\b.*\berror\b", DEBUG_ANALYSIS, 0.86)
_r(r"\bwhat\b.*\bbroke\b", DEBUG_ANALYSIS, 0.89)
_r(r"\bwhat\b.*\bwrong\b", DEBUG_ANALYSIS, 0.83)
_r(r"\btroubleshoot\b", DEBUG_ANALYSIS, 0.87)
_r(r"\bdiagnose\b", DEBUG_ANALYSIS, 0.87)
_r(r"\bfind\b.*\bbug\b", DEBUG_ANALYSIS, 0.84)

# ── Project analysis ─────────────────────────────────────────────────────────
_r(r"\banalyze\b.*\b(project|system|app)\b", PROJECT_ANALYSIS, 0.91)
_r(r"\banalyse\b.*\b(project|system|app)\b", PROJECT_ANALYSIS, 0.91)
_r(r"\binvestigate\b.*\b(project|system)\b", PROJECT_ANALYSIS, 0.92)
_r(r"\binvestigate\b", PROJECT_ANALYSIS, 0.85)
_r(r"\bfull\s*(analysis|review|report)\b", PROJECT_ANALYSIS, 0.90)
_r(r"\bsystem\s*report\b", PROJECT_ANALYSIS, 0.89)
_r(r"\bproject\b.*\b(overview|summary|status)\b", PROJECT_ANALYSIS, 0.88)
_r(r"\bhow\b.*\bmy\b.*\b(project|app|system)\b", PROJECT_ANALYSIS, 0.84)

# ── Schema explanation ───────────────────────────────────────────────────────
_r(r"\bexplain\b.*\bschema\b", SCHEMA_EXPLANATION, 0.92)
_r(r"\bschema\b.*\bexplain\b", SCHEMA_EXPLANATION, 0.92)
_r(r"\bdatabase\s*schema\b", SCHEMA_EXPLANATION, 0.90)
_r(r"\bexplain\b.*\bmodel\b", SCHEMA_EXPLANATION, 0.85)
_r(r"\bmodel\b.*\bexplain\b", SCHEMA_EXPLANATION, 0.83)
_r(r"\bdescribe\b.*\bmodel\b", SCHEMA_EXPLANATION, 0.83)
_r(r"\bschema\b.*\b(design|review|health)\b", SCHEMA_EXPLANATION, 0.88)
_r(r"\btable\b.*\bstructure\b", SCHEMA_EXPLANATION, 0.86)

# ── Route analysis ───────────────────────────────────────────────────────────
_r(r"\breview\b.*\b(endpoint|route|api)\b", ROUTE_ANALYSIS, 0.90)
_r(r"\b(endpoint|route|api)\b.*\breview\b", ROUTE_ANALYSIS, 0.88)
_r(r"\bcheck\b.*\b(endpoint|route)\b", ROUTE_ANALYSIS, 0.84)
_r(r"\b(GET|POST|PUT|PATCH|DELETE)\b\s+/", ROUTE_ANALYSIS, 0.92)
_r(r"\bharden\b.*\bpermission", ROUTE_ANALYSIS, 0.88)
_r(r"\bsecure\b.*\bendpoint\b", ROUTE_ANALYSIS, 0.85)


# ─── Entity Extraction ──────────────────────────────────────────────────────

_ROUTE_RE = re.compile(
    r"\b(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b\s+([/\w\-{}\.:]+)",
    re.IGNORECASE,
)
_MODEL_NAME_RE = re.compile(
    r"(?:the\s+)?(\b[A-Z][A-Za-z0-9_]*)\b\s*(?:model|table)?",
)
_PATH_RE = re.compile(r"(/[/\w\-{}\.:]+)")

_SKIP_WORDS = {
    "The", "This", "That", "What", "How", "Can", "Could",
    "Should", "Would", "My", "Your", "Our", "All", "Any",
    "Some", "Each", "Every", "About", "For", "With",
    "Explain", "Describe", "Tell", "Review", "Check",
    "Suggest", "Refactor", "Improve", "Generate", "Harden",
    "Analyze", "Analyse", "Investigate", "Why", "Run",
}


def _extract_entities(prompt: str) -> Dict[str, Any]:
    """Extract structured entities from a prompt string."""
    entities: Dict[str, Any] = {}

    # Route: "GET /api/users"
    m = _ROUTE_RE.search(prompt)
    if m:
        entities["method"] = m.group(1).upper()
        entities["route"] = m.group(2)
    else:
        # Bare path: "/api/users"
        m = _PATH_RE.search(prompt)
        if m:
            entities["route"] = m.group(1)

    # Model name: "User model"
    m = _MODEL_NAME_RE.search(prompt)
    if m and m.group(1) not in _SKIP_WORDS:
        entities["model"] = m.group(1)

    return entities


# ─── Public API ──────────────────────────────────────────────────────────────

def classify_intent(prompt: str) -> IntentMatch:
    """Classify a natural-language prompt into an ``IntentMatch``.

    Parameters
    ----------
    prompt : str
        User input, e.g. ``"why is /api/users slow?"``.

    Returns
    -------
    IntentMatch
        Best matching intent, or ``unknown`` with ``confidence=0.0``.
    """
    if not prompt or not prompt.strip():
        return IntentMatch(raw_prompt=prompt or "")

    text = prompt.strip()
    best: Optional[IntentMatch] = None

    for pattern, intent, base_confidence in _RULES:
        m = pattern.search(text)
        if m:
            confidence = base_confidence
            # Boost when a large fraction of the message matches
            match_ratio = len(m.group(0)) / max(len(text), 1)
            confidence = min(confidence + match_ratio * 0.08, 1.0)

            if best is None or confidence > best.confidence:
                best = IntentMatch(
                    intent=intent,
                    confidence=round(confidence, 3),
                    entities=_extract_entities(text),
                    raw_prompt=text,
                )

    return best or IntentMatch(raw_prompt=text)


def list_supported_intents() -> List[str]:
    """Return all supported intent identifiers."""
    return list(SUPPORTED_INTENTS)
