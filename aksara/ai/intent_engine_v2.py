"""
Intent Engine v2  — backward-compatibility shim  (v0.5.41)

All content has been merged into ``aksara.ai.intent_engine``.
Import from there instead.  This module re-exports everything for
existing code and tests that already import from this path.

.. deprecated::
    Import from ``aksara.ai.intent_engine`` directly.
"""

from __future__ import annotations

from aksara.ai.intent_engine import (
    classify_intent_v2,
    IntentResult,
    INTENTS,
    INTENT_UNKNOWN,
    INTENT_INVESTIGATION,
    INTENT_DEBUG_ANALYSIS,
    INTENT_PERFORMANCE_ANALYSIS,
    INTENT_ARCHITECTURE_REVIEW,
    INTENT_SCHEMA_EXPLANATION,
    INTENT_ROUTE_ANALYSIS,
    _extract_entities,
    _score_intents,
    _compute_confidence,
    get_supported_intents,
)

__all__ = [
    "classify_intent_v2",
    "IntentResult",
    "INTENTS",
    "INTENT_UNKNOWN",
    "INTENT_INVESTIGATION",
    "INTENT_DEBUG_ANALYSIS",
    "INTENT_PERFORMANCE_ANALYSIS",
    "INTENT_ARCHITECTURE_REVIEW",
    "INTENT_SCHEMA_EXPLANATION",
    "INTENT_ROUTE_ANALYSIS",
    "_extract_entities",
    "_score_intents",
    "_compute_confidence",
    "get_supported_intents",
]
