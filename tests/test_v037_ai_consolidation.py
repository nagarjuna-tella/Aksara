"""
Tests for v0.5.37 — AI Consolidation & Orchestration

Tests for:
- Intent classification (intent_classifier.py)
- Execution planning (execution_planner.py)
- Orchestration pipeline (orchestrator.py)
- Intent engine (intent_engine.py)
- Console engine integration (console_engine.py)
- Investigation workflow
- CLI investigate command
"""

from __future__ import annotations

import pytest


# =============================================================================
# Intent Classifier Tests
# =============================================================================


class TestIntentClassifier:
    """Tests for aksara.ai.intent_classifier."""

    def test_import(self):
        from aksara.ai.intent_classifier import classify_intent, IntentMatch
        assert callable(classify_intent)

    def test_empty_prompt(self):
        from aksara.ai.intent_classifier import classify_intent
        match = classify_intent("")
        assert match.intent == "unknown"
        assert match.confidence == 0.0

    def test_none_prompt(self):
        from aksara.ai.intent_classifier import classify_intent
        match = classify_intent(None)
        assert match.intent == "unknown"

    def test_architecture_review_intent(self):
        from aksara.ai.intent_classifier import classify_intent, ARCHITECTURE_REVIEW
        match = classify_intent("review my architecture")
        assert match.intent == ARCHITECTURE_REVIEW
        assert match.confidence > 0.80

    def test_performance_investigation_intent(self):
        from aksara.ai.intent_classifier import classify_intent, PERFORMANCE_INVESTIGATION
        match = classify_intent("why is /api/users slow?")
        assert match.intent == PERFORMANCE_INVESTIGATION
        assert match.confidence > 0.80

    def test_performance_entity_extraction(self):
        from aksara.ai.intent_classifier import classify_intent
        match = classify_intent("why is GET /api/users slow?")
        assert match.entities.get("route") == "/api/users"
        assert match.entities.get("method") == "GET"

    def test_debug_analysis_intent(self):
        from aksara.ai.intent_classifier import classify_intent, DEBUG_ANALYSIS
        match = classify_intent("debug the User model issue")
        assert match.intent == DEBUG_ANALYSIS
        assert match.confidence > 0.80

    def test_project_analysis_intent(self):
        from aksara.ai.intent_classifier import classify_intent, PROJECT_ANALYSIS
        match = classify_intent("analyze my project")
        assert match.intent == PROJECT_ANALYSIS
        assert match.confidence > 0.80

    def test_schema_explanation_intent(self):
        from aksara.ai.intent_classifier import classify_intent, SCHEMA_EXPLANATION
        match = classify_intent("explain the database schema")
        assert match.intent == SCHEMA_EXPLANATION
        assert match.confidence > 0.80

    def test_route_analysis_intent(self):
        from aksara.ai.intent_classifier import classify_intent, ROUTE_ANALYSIS
        match = classify_intent("review endpoint GET /api/posts")
        assert match.intent == ROUTE_ANALYSIS
        assert match.confidence > 0.80

    def test_unknown_intent(self):
        from aksara.ai.intent_classifier import classify_intent
        match = classify_intent("xyzzy foobar baz")
        assert match.intent == "unknown"
        assert match.confidence == 0.0

    def test_raw_prompt_preserved(self):
        from aksara.ai.intent_classifier import classify_intent
        prompt = "explain my architecture"
        match = classify_intent(prompt)
        assert match.raw_prompt == prompt

    def test_supported_intents_list(self):
        from aksara.ai.intent_classifier import list_supported_intents, SUPPORTED_INTENTS
        result = list_supported_intents()
        assert len(result) == 6
        assert result == SUPPORTED_INTENTS

    def test_confidence_range(self):
        from aksara.ai.intent_classifier import classify_intent
        for prompt in [
            "architecture review",
            "why is it slow",
            "debug this",
            "analyze project",
            "explain schema",
            "review endpoint",
        ]:
            match = classify_intent(prompt)
            assert 0.0 <= match.confidence <= 1.0

    def test_investigate_maps_to_project_analysis(self):
        from aksara.ai.intent_classifier import classify_intent, PROJECT_ANALYSIS
        match = classify_intent("investigate my system")
        assert match.intent == PROJECT_ANALYSIS

    def test_model_entity_extraction(self):
        from aksara.ai.intent_classifier import classify_intent
        match = classify_intent("explain the User model")
        assert match.entities.get("model") == "User"

    def test_root_cause_maps_to_debug(self):
        from aksara.ai.intent_classifier import classify_intent, DEBUG_ANALYSIS
        match = classify_intent("find root cause of errors")
        assert match.intent == DEBUG_ANALYSIS

    def test_bottleneck_maps_to_performance(self):
        from aksara.ai.intent_classifier import classify_intent, PERFORMANCE_INVESTIGATION
        match = classify_intent("find bottleneck in performance")
        assert match.intent == PERFORMANCE_INVESTIGATION


# =============================================================================
# Execution Planner Tests
# =============================================================================


class TestExecutionPlanner:
    """Tests for aksara.ai.execution_planner."""

    def test_import(self):
        from aksara.ai.execution_planner import build_execution_plan, ExecutionPlan
        assert callable(build_execution_plan)

    def test_architecture_plan(self):
        from aksara.ai.intent_classifier import IntentMatch, ARCHITECTURE_REVIEW
        from aksara.ai.execution_planner import build_execution_plan
        match = IntentMatch(intent=ARCHITECTURE_REVIEW, confidence=0.9)
        plan = build_execution_plan(match)
        assert plan.intent == ARCHITECTURE_REVIEW
        assert "build_project_graph" in plan.steps
        assert "run_architecture_review" in plan.steps
        assert len(plan.steps) == 2

    def test_performance_plan(self):
        from aksara.ai.intent_classifier import IntentMatch, PERFORMANCE_INVESTIGATION
        from aksara.ai.execution_planner import build_execution_plan
        match = IntentMatch(intent=PERFORMANCE_INVESTIGATION, confidence=0.9)
        plan = build_execution_plan(match)
        assert "build_project_graph" in plan.steps
        assert "run_performance_analysis" in plan.steps
        assert len(plan.steps) == 2

    def test_debug_plan(self):
        from aksara.ai.intent_classifier import IntentMatch, DEBUG_ANALYSIS
        from aksara.ai.execution_planner import build_execution_plan
        match = IntentMatch(intent=DEBUG_ANALYSIS, confidence=0.9)
        plan = build_execution_plan(match)
        assert "build_project_graph" in plan.steps
        assert "run_debugger" in plan.steps
        assert len(plan.steps) == 2

    def test_project_analysis_full_pipeline(self):
        from aksara.ai.intent_classifier import IntentMatch, PROJECT_ANALYSIS
        from aksara.ai.execution_planner import build_execution_plan
        match = IntentMatch(intent=PROJECT_ANALYSIS, confidence=0.9)
        plan = build_execution_plan(match)
        assert len(plan.steps) == 5
        assert "build_project_graph" in plan.steps
        assert "run_architecture_review" in plan.steps
        assert "run_performance_analysis" in plan.steps
        assert "run_debugger" in plan.steps
        assert "run_diagnostics" in plan.steps

    def test_schema_explanation_plan(self):
        from aksara.ai.intent_classifier import IntentMatch, SCHEMA_EXPLANATION
        from aksara.ai.execution_planner import build_execution_plan
        match = IntentMatch(intent=SCHEMA_EXPLANATION, confidence=0.9)
        plan = build_execution_plan(match)
        assert "build_project_graph" in plan.steps
        assert "explain_schema" in plan.steps

    def test_route_analysis_plan(self):
        from aksara.ai.intent_classifier import IntentMatch, ROUTE_ANALYSIS
        from aksara.ai.execution_planner import build_execution_plan
        match = IntentMatch(intent=ROUTE_ANALYSIS, confidence=0.9)
        plan = build_execution_plan(match)
        assert "build_project_graph" in plan.steps
        assert "analyze_route" in plan.steps

    def test_unknown_intent_empty_plan(self):
        from aksara.ai.intent_classifier import IntentMatch
        from aksara.ai.execution_planner import build_execution_plan
        match = IntentMatch(intent="unknown", confidence=0.0)
        plan = build_execution_plan(match)
        assert plan.steps == []

    def test_investigation_plan(self):
        from aksara.ai.execution_planner import build_investigation_plan
        plan = build_investigation_plan()
        assert len(plan.steps) == 5
        assert plan.intent == "project_analysis"

    def test_context_forwarded(self):
        from aksara.ai.intent_classifier import IntentMatch, ROUTE_ANALYSIS
        from aksara.ai.execution_planner import build_execution_plan
        match = IntentMatch(
            intent=ROUTE_ANALYSIS,
            confidence=0.9,
            entities={"route": "/api/users", "method": "GET"},
        )
        plan = build_execution_plan(match)
        assert plan.context.get("route") == "/api/users"
        assert plan.context.get("method") == "GET"

    def test_plan_steps_are_copied(self):
        from aksara.ai.intent_classifier import IntentMatch, ARCHITECTURE_REVIEW
        from aksara.ai.execution_planner import build_execution_plan
        match = IntentMatch(intent=ARCHITECTURE_REVIEW, confidence=0.9)
        plan1 = build_execution_plan(match)
        plan2 = build_execution_plan(match)
        plan1.steps.append("extra_step")
        assert "extra_step" not in plan2.steps


# =============================================================================
# Orchestrator Tests
# =============================================================================


class TestOrchestrator:
    """Tests for aksara.ai.orchestrator."""

    def test_import(self):
        from aksara.ai.orchestrator import execute_plan, OrchestrationResult, StepResult
        assert callable(execute_plan)

    def test_empty_plan(self):
        from aksara.ai.execution_planner import ExecutionPlan
        from aksara.ai.orchestrator import execute_plan
        plan = ExecutionPlan(intent="unknown", steps=[])
        result = execute_plan(plan)
        assert result.ok is False
        assert result.step_results == []

    def test_unknown_step(self):
        from aksara.ai.execution_planner import ExecutionPlan
        from aksara.ai.orchestrator import execute_plan
        plan = ExecutionPlan(intent="test", steps=["nonexistent_step"])
        result = execute_plan(plan)
        assert len(result.step_results) == 1
        assert result.step_results[0].ok is False
        assert "Unknown step" in result.step_results[0].error

    def test_build_project_graph_step(self):
        from aksara.ai.execution_planner import ExecutionPlan
        from aksara.ai.orchestrator import execute_plan
        plan = ExecutionPlan(intent="test", steps=["build_project_graph"])
        result = execute_plan(plan)
        assert len(result.step_results) == 1
        assert result.step_results[0].step == "build_project_graph"
        # Graph build should succeed (it reads from registry which may be empty)
        assert result.step_results[0].ok is True

    def test_result_to_dict(self):
        from aksara.ai.orchestrator import OrchestrationResult
        result = OrchestrationResult(ok=True, intent="test", summary="ok")
        d = result.to_dict()
        assert d["ok"] is True
        assert d["intent"] == "test"
        assert "summary" in d
        assert "step_results" in d

    def test_result_to_summary_dict(self):
        from aksara.ai.orchestrator import OrchestrationResult
        result = OrchestrationResult(ok=True, intent="test")
        d = result.to_summary_dict()
        assert "ok" in d
        assert "intent" in d
        assert "steps_ok" in d
        assert "steps_total" in d

    def test_architecture_review_step(self):
        from aksara.ai.execution_planner import ExecutionPlan
        from aksara.ai.orchestrator import execute_plan
        plan = ExecutionPlan(
            intent="architecture_review",
            steps=["build_project_graph", "run_architecture_review"],
        )
        result = execute_plan(plan)
        assert len(result.step_results) == 2
        assert result.ok is True

    def test_performance_analysis_step(self):
        from aksara.ai.execution_planner import ExecutionPlan
        from aksara.ai.orchestrator import execute_plan
        plan = ExecutionPlan(
            intent="performance_investigation",
            steps=["build_project_graph", "run_performance_analysis"],
        )
        result = execute_plan(plan)
        assert len(result.step_results) == 2
        assert result.ok is True

    def test_debugger_step(self):
        from aksara.ai.execution_planner import ExecutionPlan
        from aksara.ai.orchestrator import execute_plan
        plan = ExecutionPlan(
            intent="debug_analysis",
            steps=["build_project_graph", "run_debugger"],
        )
        result = execute_plan(plan)
        assert len(result.step_results) == 2
        assert result.ok is True

    def test_diagnostics_step(self):
        from aksara.ai.execution_planner import ExecutionPlan
        from aksara.ai.orchestrator import execute_plan
        plan = ExecutionPlan(
            intent="test",
            steps=["build_project_graph", "run_diagnostics"],
        )
        result = execute_plan(plan)
        assert len(result.step_results) == 2

    def test_explain_schema_step(self):
        from aksara.ai.execution_planner import ExecutionPlan
        from aksara.ai.orchestrator import execute_plan
        plan = ExecutionPlan(
            intent="schema_explanation",
            steps=["build_project_graph", "explain_schema"],
        )
        result = execute_plan(plan)
        assert len(result.step_results) == 2

    def test_analyze_route_step(self):
        from aksara.ai.execution_planner import ExecutionPlan
        from aksara.ai.orchestrator import execute_plan
        plan = ExecutionPlan(
            intent="route_analysis",
            steps=["build_project_graph", "analyze_route"],
            context={"route": "/api/users"},
        )
        result = execute_plan(plan)
        assert len(result.step_results) == 2

    def test_full_investigation_pipeline(self):
        from aksara.ai.execution_planner import build_investigation_plan
        from aksara.ai.orchestrator import execute_plan
        plan = build_investigation_plan()
        result = execute_plan(plan)
        assert len(result.step_results) == 5
        assert result.ok is True
        assert result.elapsed_ms >= 0

    def test_elapsed_ms_tracking(self):
        from aksara.ai.execution_planner import ExecutionPlan
        from aksara.ai.orchestrator import execute_plan
        plan = ExecutionPlan(intent="test", steps=["build_project_graph"])
        result = execute_plan(plan)
        assert result.elapsed_ms >= 0
        for sr in result.step_results:
            assert sr.elapsed_ms >= 0


# =============================================================================
# Intent Engine Tests
# =============================================================================


class TestIntentEngine:
    """Tests for aksara.ai.intent_engine."""

    def test_import(self):
        from aksara.ai.intent_engine import handle_prompt, run_investigation
        assert callable(handle_prompt)
        assert callable(run_investigation)

    def test_handle_empty_prompt(self):
        from aksara.ai.intent_engine import handle_prompt
        result = handle_prompt("")
        assert result.ok is False
        assert "Empty prompt" in result.summary

    def test_handle_unknown_prompt(self):
        from aksara.ai.intent_engine import handle_prompt
        result = handle_prompt("xyzzy foobar baz")
        assert result.ok is False
        assert "Could not understand" in result.summary

    def test_handle_architecture_prompt(self):
        from aksara.ai.intent_engine import handle_prompt
        result = handle_prompt("review my architecture")
        assert result.ok is True
        assert result.intent == "architecture_review"

    def test_handle_performance_prompt(self):
        from aksara.ai.intent_engine import handle_prompt
        result = handle_prompt("why is /api/users slow?")
        assert result.ok is True
        assert result.intent == "performance_investigation"

    def test_handle_debug_prompt(self):
        from aksara.ai.intent_engine import handle_prompt
        result = handle_prompt("debug the failing endpoint")
        assert result.ok is True
        assert result.intent == "debug_analysis"

    def test_handle_project_analysis(self):
        from aksara.ai.intent_engine import handle_prompt
        result = handle_prompt("analyze my project")
        assert result.ok is True
        assert result.intent == "project_analysis"

    def test_run_investigation(self):
        from aksara.ai.intent_engine import run_investigation
        result = run_investigation()
        assert result.ok is True
        assert result.intent == "project_analysis"
        assert len(result.step_results) == 5

    def test_classify_and_plan(self):
        from aksara.ai.intent_engine import classify_and_plan
        match, plan = classify_and_plan("explain my architecture")
        assert match.intent == "architecture_review"
        assert "build_project_graph" in plan.steps
        assert "run_architecture_review" in plan.steps

    def test_investigation_report_structure(self):
        from aksara.ai.intent_engine import run_investigation
        result = run_investigation()
        d = result.to_dict()
        assert "ok" in d
        assert "intent" in d
        assert "report" in d
        assert "summary" in d
        assert "step_results" in d

    def test_handle_schema_prompt(self):
        from aksara.ai.intent_engine import handle_prompt
        result = handle_prompt("explain the database schema")
        assert result.ok is True
        assert result.intent == "schema_explanation"

    def test_handle_route_prompt(self):
        from aksara.ai.intent_engine import handle_prompt
        result = handle_prompt("review endpoint GET /api/posts")
        assert result.ok is True
        assert result.intent == "route_analysis"


# =============================================================================
# Console Engine Integration Tests
# =============================================================================


class TestConsoleEngineIntegration:
    """Tests for console engine v0.5.37 Intent Engine integration."""

    @pytest.mark.asyncio
    async def test_console_routes_through_intent_engine(self):
        from aksara.ai.console_engine import run_console_query
        result = await run_console_query("review my architecture")
        assert result["ok"] is True
        assert result.get("orchestrated") is True

    @pytest.mark.asyncio
    async def test_console_performance_through_intent_engine(self):
        from aksara.ai.console_engine import run_console_query
        result = await run_console_query("why is my app slow?")
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_console_debug_through_intent_engine(self):
        from aksara.ai.console_engine import run_console_query
        result = await run_console_query("debug the failing code")
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_console_empty_message(self):
        from aksara.ai.console_engine import run_console_query
        result = await run_console_query("")
        assert result["ok"] is False
        assert result["error_code"] == "EMPTY_MESSAGE"

    @pytest.mark.asyncio
    async def test_console_investigation_prompt(self):
        from aksara.ai.console_engine import run_console_query
        result = await run_console_query("investigate my project")
        assert result["ok"] is True


# =============================================================================
# Investigation Workflow Tests
# =============================================================================


class TestInvestigationWorkflow:
    """End-to-end tests for the AI Investigation feature."""

    def test_investigation_produces_all_sections(self):
        from aksara.ai.intent_engine import run_investigation
        result = run_investigation()
        assert result.ok is True
        # Should have all 5 steps
        step_names = [s.step for s in result.step_results]
        assert "build_project_graph" in step_names
        assert "run_architecture_review" in step_names
        assert "run_performance_analysis" in step_names
        assert "run_debugger" in step_names
        assert "run_diagnostics" in step_names

    def test_investigation_report_has_architecture(self):
        from aksara.ai.intent_engine import run_investigation
        result = run_investigation()
        assert "architecture_report" in result.report

    def test_investigation_report_has_performance(self):
        from aksara.ai.intent_engine import run_investigation
        result = run_investigation()
        assert "performance_report" in result.report

    def test_investigation_report_has_debug(self):
        from aksara.ai.intent_engine import run_investigation
        result = run_investigation()
        assert "debug_report" in result.report

    def test_investigation_report_has_graph_summary(self):
        from aksara.ai.intent_engine import run_investigation
        result = run_investigation()
        assert "graph_summary" in result.report

    def test_investigation_summary_not_empty(self):
        from aksara.ai.intent_engine import run_investigation
        result = run_investigation()
        assert len(result.summary) > 0

    def test_investigation_generated_at(self):
        from aksara.ai.intent_engine import run_investigation
        result = run_investigation()
        assert result.generated_at != ""

    def test_investigation_all_steps_succeed(self):
        from aksara.ai.intent_engine import run_investigation
        result = run_investigation()
        for sr in result.step_results:
            assert sr.ok is True, f"Step {sr.step} failed: {sr.error}"


# =============================================================================
# Module __all__ exports test
# =============================================================================


class TestModuleExports:
    """Tests that v0.5.37 modules are properly exported from aksara.ai."""

    def test_intent_classifier_exports(self):
        from aksara.ai import (
            classify_intent,
            SUPPORTED_INTENTS,
            ARCHITECTURE_REVIEW,
            PERFORMANCE_INVESTIGATION,
            DEBUG_ANALYSIS,
            PROJECT_ANALYSIS,
            SCHEMA_EXPLANATION,
            ROUTE_ANALYSIS,
        )
        assert len(SUPPORTED_INTENTS) == 6

    def test_execution_planner_exports(self):
        from aksara.ai import (
            ExecutionPlan,
            build_execution_plan,
            build_investigation_plan,
            INVESTIGATION_PIPELINE,
        )
        assert len(INVESTIGATION_PIPELINE) == 5

    def test_orchestrator_exports(self):
        from aksara.ai import (
            OrchestrationResult,
            StepResult,
            execute_plan,
        )
        assert callable(execute_plan)

    def test_intent_engine_exports(self):
        from aksara.ai import (
            handle_prompt,
            run_investigation,
            classify_and_plan,
        )
        assert callable(handle_prompt)
        assert callable(run_investigation)

    def test_version_is_0537(self):
        from aksara._version import __version__
        assert __version__ == "0.7.0rc1"
