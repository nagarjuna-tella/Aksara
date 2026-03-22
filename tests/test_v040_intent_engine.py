"""
v0.5.40 — Intent Engine v2 Tests

Tests for structured intent classification, entity extraction,
confidence scoring, and fallback handling.
"""

from __future__ import annotations

import pytest


# =============================================================================
# 1. Import Tests
# =============================================================================


class TestImports:
    """Verify all new Intent Engine v2 symbols are importable."""

    def test_import_intent_engine_v2(self):
        from aksara.ai.intent_engine_v2 import (
            classify_intent_v2,
            IntentResult,
            INTENTS,
            INTENT_INVESTIGATION,
            INTENT_DEBUG_ANALYSIS,
            INTENT_PERFORMANCE_ANALYSIS,
            INTENT_ARCHITECTURE_REVIEW,
            INTENT_SCHEMA_EXPLANATION,
            INTENT_ROUTE_ANALYSIS,
            INTENT_UNKNOWN,
        )
        assert callable(classify_intent_v2)
        assert IntentResult is not None
        assert len(INTENTS) == 7

    def test_import_internal_helpers(self):
        from aksara.ai.intent_engine_v2 import (
            _extract_entities,
            _score_intents,
            _compute_confidence,
        )
        assert callable(_extract_entities)
        assert callable(_score_intents)
        assert callable(_compute_confidence)


# =============================================================================
# 2. IntentResult Model Tests
# =============================================================================


class TestIntentResult:
    """Test the IntentResult dataclass."""

    def test_construction(self):
        from aksara.ai.intent_engine_v2 import IntentResult

        result = IntentResult(
            intent="debug_analysis",
            confidence=0.85,
            entities={"models": ["User"], "routes": [], "signals": ["error"]},
            raw="debug the User model",
        )
        assert result.intent == "debug_analysis"
        assert result.confidence == 0.85
        assert result.entities["models"] == ["User"]
        assert result.raw == "debug the User model"

    def test_to_dict(self):
        from aksara.ai.intent_engine_v2 import IntentResult

        result = IntentResult(
            intent="investigation",
            confidence=0.9123456,
            entities={"models": [], "routes": [], "signals": []},
            raw="investigate",
        )
        d = result.to_dict()
        assert d["intent"] == "investigation"
        assert d["confidence"] == 0.9123  # rounded to 4 places
        assert d["raw"] == "investigate"
        assert "entities" in d

    def test_default_raw(self):
        from aksara.ai.intent_engine_v2 import IntentResult

        result = IntentResult(
            intent="unknown",
            confidence=0.0,
            entities={},
        )
        assert result.raw == ""


# =============================================================================
# 3. Entity Extraction Tests
# =============================================================================


class TestEntityExtraction:
    """Test _extract_entities detects models, routes, and signals."""

    def test_extract_model_names(self):
        from aksara.ai.intent_engine_v2 import _extract_entities

        entities = _extract_entities("Explain the BlogPost model")
        assert "BlogPost" in entities["models"]

    def test_extract_multiple_models(self):
        from aksara.ai.intent_engine_v2 import _extract_entities

        entities = _extract_entities("Compare UserProfile and BlogPost")
        assert "UserProfile" in entities["models"]
        assert "BlogPost" in entities["models"]

    def test_extract_routes(self):
        from aksara.ai.intent_engine_v2 import _extract_entities

        entities = _extract_entities("Review /api/users endpoint")
        assert "/api/users" in entities["routes"]

    def test_extract_nested_route(self):
        from aksara.ai.intent_engine_v2 import _extract_entities

        entities = _extract_entities("Why is /api/orders/{id}/items slow?")
        routes = entities["routes"]
        assert any("/api/orders" in r for r in routes)

    def test_extract_signals(self):
        from aksara.ai.intent_engine_v2 import _extract_entities

        entities = _extract_entities("debug the slow query performance")
        signals = entities["signals"]
        assert "debug" in signals
        assert "slow" in signals
        assert "performance" in signals
        assert "query" in signals

    def test_no_entities_in_simple_text(self):
        from aksara.ai.intent_engine_v2 import _extract_entities

        entities = _extract_entities("hello world")
        assert entities["models"] == []
        assert entities["routes"] == []
        # "hello" and "world" are not signal keywords
        assert len(entities["signals"]) == 0

    def test_deduplicated_entities(self):
        from aksara.ai.intent_engine_v2 import _extract_entities

        entities = _extract_entities("debug debug error error /api/users /api/users")
        assert entities["signals"].count("debug") == 1
        assert entities["signals"].count("error") == 1
        assert entities["routes"].count("/api/users") == 1


# =============================================================================
# 4. Intent Classification Tests
# =============================================================================


class TestClassifyIntentV2:
    """Test the main classify_intent_v2 function."""

    def test_empty_query(self):
        from aksara.ai.intent_engine_v2 import classify_intent_v2, INTENT_UNKNOWN

        result = classify_intent_v2("")
        assert result.intent == INTENT_UNKNOWN
        assert result.confidence == 0.0

    def test_whitespace_only(self):
        from aksara.ai.intent_engine_v2 import classify_intent_v2, INTENT_UNKNOWN

        result = classify_intent_v2("   \n  ")
        assert result.intent == INTENT_UNKNOWN
        assert result.confidence == 0.0

    def test_none_like_empty(self):
        from aksara.ai.intent_engine_v2 import classify_intent_v2, INTENT_UNKNOWN

        result = classify_intent_v2("")
        assert result.intent == INTENT_UNKNOWN

    def test_investigation_intent(self):
        from aksara.ai.intent_engine_v2 import classify_intent_v2, INTENT_INVESTIGATION

        result = classify_intent_v2("Investigate the system")
        assert result.intent == INTENT_INVESTIGATION
        assert result.confidence > 0

    def test_debug_intent(self):
        from aksara.ai.intent_engine_v2 import classify_intent_v2, INTENT_DEBUG_ANALYSIS

        result = classify_intent_v2("Why is the app crashing with an error?")
        assert result.intent == INTENT_DEBUG_ANALYSIS
        assert result.confidence > 0

    def test_performance_intent(self):
        from aksara.ai.intent_engine_v2 import classify_intent_v2, INTENT_PERFORMANCE_ANALYSIS

        result = classify_intent_v2("The app is slow, optimize performance")
        assert result.intent == INTENT_PERFORMANCE_ANALYSIS
        assert result.confidence > 0

    def test_architecture_intent(self):
        from aksara.ai.intent_engine_v2 import classify_intent_v2, INTENT_ARCHITECTURE_REVIEW

        result = classify_intent_v2("Review the architecture and coupling")
        assert result.intent == INTENT_ARCHITECTURE_REVIEW
        assert result.confidence > 0

    def test_schema_intent(self):
        from aksara.ai.intent_engine_v2 import classify_intent_v2, INTENT_SCHEMA_EXPLANATION

        result = classify_intent_v2("Explain the User model schema")
        assert result.intent == INTENT_SCHEMA_EXPLANATION
        assert result.confidence > 0

    def test_route_intent(self):
        from aksara.ai.intent_engine_v2 import classify_intent_v2, INTENT_ROUTE_ANALYSIS

        result = classify_intent_v2("Review the GET /api/users endpoint")
        assert result.intent == INTENT_ROUTE_ANALYSIS
        assert result.confidence > 0

    def test_unknown_intent(self):
        from aksara.ai.intent_engine_v2 import classify_intent_v2, INTENT_UNKNOWN

        result = classify_intent_v2("hello world today")
        assert result.intent == INTENT_UNKNOWN
        assert result.confidence == 0.0

    def test_raw_field_preserved(self):
        from aksara.ai.intent_engine_v2 import classify_intent_v2

        query = "Investigate slow API on /api/users"
        result = classify_intent_v2(query)
        assert result.raw == query

    def test_entities_populated(self):
        from aksara.ai.intent_engine_v2 import classify_intent_v2

        result = classify_intent_v2("Debug slow /api/orders for UserProfile")
        assert "models" in result.entities
        assert "routes" in result.entities
        assert "signals" in result.entities

    def test_confidence_clamped_to_one(self):
        from aksara.ai.intent_engine_v2 import classify_intent_v2

        # A very keyword-dense query should not exceed 1.0
        result = classify_intent_v2("bug error crash debug exception traceback failing broken")
        assert result.confidence <= 1.0

    def test_confidence_range(self):
        from aksara.ai.intent_engine_v2 import classify_intent_v2

        result = classify_intent_v2("slow performance")
        assert 0.0 <= result.confidence <= 1.0


# =============================================================================
# 5. Scoring Tests
# =============================================================================


class TestScoring:
    """Test internal scoring helpers."""

    def test_score_intents_counts_hits(self):
        from aksara.ai.intent_engine_v2 import _score_intents

        scores = _score_intents("slow performance bottleneck")
        assert scores["performance_analysis"] >= 2
        assert scores["investigation"] == 0

    def test_compute_confidence_zero_for_no_hits(self):
        from aksara.ai.intent_engine_v2 import _compute_confidence

        assert _compute_confidence(0, 5) == 0.0

    def test_compute_confidence_positive_for_hits(self):
        from aksara.ai.intent_engine_v2 import _compute_confidence

        assert _compute_confidence(2, 5) > 0.0

    def test_compute_confidence_capped_at_one(self):
        from aksara.ai.intent_engine_v2 import _compute_confidence

        assert _compute_confidence(100, 1) <= 1.0


# =============================================================================
# 6. Intent Constants Tests
# =============================================================================


class TestIntentConstants:
    """Verify intent constants are consistent."""

    def test_all_intents_listed(self):
        from aksara.ai.intent_engine_v2 import (
            INTENTS,
            INTENT_INVESTIGATION,
            INTENT_DEBUG_ANALYSIS,
            INTENT_PERFORMANCE_ANALYSIS,
            INTENT_ARCHITECTURE_REVIEW,
            INTENT_SCHEMA_EXPLANATION,
            INTENT_ROUTE_ANALYSIS,
            INTENT_UNKNOWN,
        )
        assert INTENT_INVESTIGATION in INTENTS
        assert INTENT_DEBUG_ANALYSIS in INTENTS
        assert INTENT_PERFORMANCE_ANALYSIS in INTENTS
        assert INTENT_ARCHITECTURE_REVIEW in INTENTS
        assert INTENT_SCHEMA_EXPLANATION in INTENTS
        assert INTENT_ROUTE_ANALYSIS in INTENTS
        assert INTENT_UNKNOWN in INTENTS

    def test_intent_values_are_strings(self):
        from aksara.ai.intent_engine_v2 import INTENTS

        for intent in INTENTS:
            assert isinstance(intent, str)

    def test_no_duplicate_intents(self):
        from aksara.ai.intent_engine_v2 import INTENTS

        assert len(INTENTS) == len(set(INTENTS))


# =============================================================================
# 7. Plan Builder Integration with Intent Engine v2
# =============================================================================


class TestPlanBuilderIntegration:
    """Test that build_plan_from_intent works with IntentResult."""

    def test_import_build_plan_from_intent(self):
        from aksara.ai.plan_builder import build_plan_from_intent
        assert callable(build_plan_from_intent)

    def test_performance_intent_to_plan(self):
        from aksara.ai.intent_engine_v2 import classify_intent_v2
        from aksara.ai.plan_builder import build_plan_from_intent

        intent = classify_intent_v2("Why is the app slow?")
        plan = build_plan_from_intent(intent)
        assert plan.strategy == "performance"
        step_names = [s.name for s in plan.steps]
        assert "project_graph" in step_names
        assert "performance_analysis" in step_names

    def test_debug_intent_to_plan(self):
        from aksara.ai.intent_engine_v2 import classify_intent_v2
        from aksara.ai.plan_builder import build_plan_from_intent

        intent = classify_intent_v2("There's a bug crashing the app")
        plan = build_plan_from_intent(intent)
        assert plan.strategy == "debug"

    def test_architecture_intent_to_plan(self):
        from aksara.ai.intent_engine_v2 import classify_intent_v2
        from aksara.ai.plan_builder import build_plan_from_intent

        intent = classify_intent_v2("Review the architecture coupling")
        plan = build_plan_from_intent(intent)
        assert plan.strategy == "architecture"

    def test_unknown_intent_falls_to_generic(self):
        from aksara.ai.intent_engine_v2 import classify_intent_v2
        from aksara.ai.plan_builder import build_plan_from_intent

        intent = classify_intent_v2("hello world nothing here")
        plan = build_plan_from_intent(intent)
        assert plan.strategy == "generic"

    def test_step_dependencies_export(self):
        from aksara.ai.plan_builder import get_step_dependencies

        deps = get_step_dependencies("performance_analysis")
        assert "project_graph" in deps

    def test_step_priority_export(self):
        from aksara.ai.plan_builder import get_step_priority

        assert get_step_priority("project_graph") < get_step_priority("summarise")
