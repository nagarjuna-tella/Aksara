"""
v0.5.40 — AI Investigation Engine Tests

Comprehensive tests for the investigation engine: data models, session store,
plan builder, investigation runner, console integration, and API endpoints.
"""

from __future__ import annotations

import pytest


# =============================================================================
# 1. Import Tests
# =============================================================================


class TestImports:
    """Verify all new modules are importable."""

    def test_import_investigation(self):
        from aksara.ai.investigation import (
            InvestigationStep,
            InvestigationPlan,
            InvestigationSession,
            StepStatus,
            SessionStatus,
        )
        assert InvestigationStep is not None
        assert InvestigationPlan is not None
        assert InvestigationSession is not None

    def test_import_session_store(self):
        from aksara.ai.session_store import (
            create_session,
            get_session,
            update_session,
            list_sessions,
            delete_session,
            clear_sessions,
        )
        assert callable(create_session)
        assert callable(get_session)
        assert callable(update_session)
        assert callable(list_sessions)
        assert callable(delete_session)
        assert callable(clear_sessions)

    def test_import_plan_builder(self):
        from aksara.ai.plan_builder import (
            build_plan,
            STEP_PROJECT_GRAPH,
            STEP_PERFORMANCE,
            STEP_ARCHITECTURE,
            STEP_DEBUG,
            STEP_SUMMARISE,
        )
        assert callable(build_plan)
        assert STEP_PROJECT_GRAPH == "project_graph"

    def test_import_investigation_runner(self):
        from aksara.ai.investigation_runner import (
            execute_investigation,
            execute_next_step,
        )
        assert callable(execute_investigation)
        assert callable(execute_next_step)

    def test_import_from_ai_package(self):
        """Verify re-exports from aksara.ai.__init__."""
        from aksara.ai import (
            InvestigationStep,
            InvestigationPlan,
            InvestigationSession,
            create_session,
            get_session,
            update_session,
            list_sessions,
            delete_session,
            clear_sessions,
            build_plan,
            execute_investigation,
            execute_next_step,
            STEP_PROJECT_GRAPH,
            STEP_PERFORMANCE,
            STEP_ARCHITECTURE,
            STEP_DEBUG,
            STEP_SUMMARISE,
        )
        assert InvestigationStep is not None


# =============================================================================
# 2. InvestigationStep Tests
# =============================================================================


class TestInvestigationStep:
    """Tests for the InvestigationStep dataclass."""

    def test_basic_creation(self):
        from aksara.ai.investigation import InvestigationStep

        step = InvestigationStep(name="project_graph")
        assert step.name == "project_graph"
        assert step.status == "pending"
        assert step.label == "Project Graph"
        assert step.result == {}
        assert step.error is None
        assert step.started_at is None
        assert step.completed_at is None

    def test_custom_label(self):
        from aksara.ai.investigation import InvestigationStep

        step = InvestigationStep(name="my_step", label="Custom Label")
        assert step.label == "Custom Label"

    def test_auto_label_from_name(self):
        from aksara.ai.investigation import InvestigationStep

        step = InvestigationStep(name="performance_analysis")
        assert step.label == "Performance Analysis"

    def test_id_is_auto_generated(self):
        from aksara.ai.investigation import InvestigationStep

        s1 = InvestigationStep(name="a")
        s2 = InvestigationStep(name="b")
        assert len(s1.id) == 12
        assert s1.id != s2.id

    def test_to_dict(self):
        from aksara.ai.investigation import InvestigationStep

        step = InvestigationStep(name="debug_analysis")
        d = step.to_dict()
        assert d["name"] == "debug_analysis"
        assert d["status"] == "pending"
        assert d["label"] == "Debug Analysis"
        assert "id" in d
        assert d["result"] == {}
        assert d["error"] is None

    def test_to_dict_with_result(self):
        from aksara.ai.investigation import InvestigationStep

        step = InvestigationStep(name="test", result={"key": "value"})
        d = step.to_dict()
        assert d["result"] == {"key": "value"}

    def test_to_dict_with_error(self):
        from aksara.ai.investigation import InvestigationStep

        step = InvestigationStep(name="test", status="failed", error="something broke")
        d = step.to_dict()
        assert d["status"] == "failed"
        assert d["error"] == "something broke"


# =============================================================================
# 3. InvestigationPlan Tests
# =============================================================================


class TestInvestigationPlan:
    """Tests for the InvestigationPlan dataclass."""

    def test_basic_creation(self):
        from aksara.ai.investigation import InvestigationPlan

        plan = InvestigationPlan(goal="Why is the app slow?")
        assert plan.goal == "Why is the app slow?"
        assert plan.steps == []
        assert plan.strategy == "generic"

    def test_with_steps(self):
        from aksara.ai.investigation import InvestigationPlan, InvestigationStep

        steps = [
            InvestigationStep(name="project_graph"),
            InvestigationStep(name="performance_analysis"),
        ]
        plan = InvestigationPlan(goal="slow", steps=steps, strategy="performance")
        assert len(plan.steps) == 2
        assert plan.strategy == "performance"

    def test_to_dict(self):
        from aksara.ai.investigation import InvestigationPlan, InvestigationStep

        plan = InvestigationPlan(
            goal="test goal",
            steps=[InvestigationStep(name="step1")],
            strategy="debug",
        )
        d = plan.to_dict()
        assert d["goal"] == "test goal"
        assert d["strategy"] == "debug"
        assert len(d["steps"]) == 1
        assert d["steps"][0]["name"] == "step1"

    def test_to_dict_empty_steps(self):
        from aksara.ai.investigation import InvestigationPlan

        plan = InvestigationPlan(goal="empty")
        d = plan.to_dict()
        assert d["steps"] == []


# =============================================================================
# 4. InvestigationSession Tests
# =============================================================================


class TestInvestigationSession:
    """Tests for the InvestigationSession dataclass."""

    def test_basic_creation(self):
        from aksara.ai.investigation import InvestigationSession

        session = InvestigationSession(goal="test goal")
        assert session.goal == "test goal"
        assert session.status == "created"
        assert session.plan is None
        assert session.findings == []
        assert len(session.id) == 16
        assert session.created_at is not None
        assert session.updated_at is not None

    def test_unique_ids(self):
        from aksara.ai.investigation import InvestigationSession

        s1 = InvestigationSession(goal="a")
        s2 = InvestigationSession(goal="b")
        assert s1.id != s2.id

    def test_touch_updates_timestamp(self):
        from aksara.ai.investigation import InvestigationSession

        session = InvestigationSession(goal="test")
        old_ts = session.updated_at
        import time
        time.sleep(0.01)
        session.touch()
        assert session.updated_at >= old_ts

    def test_add_finding(self):
        from aksara.ai.investigation import InvestigationSession

        session = InvestigationSession(goal="test")
        session.add_finding("Found 5 models")
        assert len(session.findings) == 1
        assert session.findings[0] == "Found 5 models"

    def test_add_multiple_findings(self):
        from aksara.ai.investigation import InvestigationSession

        session = InvestigationSession(goal="test")
        session.add_finding("finding 1")
        session.add_finding("finding 2")
        session.add_finding("finding 3")
        assert len(session.findings) == 3

    def test_to_dict(self):
        from aksara.ai.investigation import InvestigationSession

        session = InvestigationSession(goal="test goal")
        d = session.to_dict()
        assert d["goal"] == "test goal"
        assert d["status"] == "created"
        assert d["plan"] is None
        assert d["findings"] == []
        assert "id" in d
        assert "created_at" in d
        assert "updated_at" in d

    def test_to_dict_with_plan(self):
        from aksara.ai.investigation import (
            InvestigationSession,
            InvestigationPlan,
            InvestigationStep,
        )

        plan = InvestigationPlan(
            goal="g",
            steps=[InvestigationStep(name="s1")],
            strategy="debug",
        )
        session = InvestigationSession(goal="g", plan=plan)
        d = session.to_dict()
        assert d["plan"] is not None
        assert d["plan"]["strategy"] == "debug"

    def test_to_summary_dict(self):
        from aksara.ai.investigation import InvestigationSession

        session = InvestigationSession(goal="summary test")
        sd = session.to_summary_dict()
        assert sd["goal"] == "summary test"
        assert sd["status"] == "created"
        assert sd["steps_total"] == 0
        assert sd["steps_done"] == 0
        assert sd["findings_count"] == 0
        assert sd["strategy"] is None

    def test_to_summary_dict_with_plan(self):
        from aksara.ai.investigation import (
            InvestigationSession,
            InvestigationPlan,
            InvestigationStep,
        )

        steps = [
            InvestigationStep(name="a", status="done"),
            InvestigationStep(name="b", status="pending"),
        ]
        plan = InvestigationPlan(goal="g", steps=steps, strategy="performance")
        session = InvestigationSession(goal="g", plan=plan)
        session.add_finding("one finding")
        sd = session.to_summary_dict()
        assert sd["steps_total"] == 2
        assert sd["steps_done"] == 1
        assert sd["findings_count"] == 1
        assert sd["strategy"] == "performance"


# =============================================================================
# 5. Session Store Tests
# =============================================================================


class TestSessionStore:
    """Tests for the in-memory session store."""

    @pytest.fixture(autouse=True)
    def clear_store(self):
        """Clear session store before and after each test."""
        from aksara.ai.session_store import clear_sessions
        clear_sessions()
        yield
        clear_sessions()

    def test_create_session(self):
        from aksara.ai.session_store import create_session

        session = create_session("test goal")
        assert session.goal == "test goal"
        assert session.status == "created"
        assert len(session.id) == 16

    def test_get_session(self):
        from aksara.ai.session_store import create_session, get_session

        session = create_session("test")
        found = get_session(session.id)
        assert found is not None
        assert found.id == session.id

    def test_get_session_not_found(self):
        from aksara.ai.session_store import get_session

        assert get_session("nonexistent") is None

    def test_update_session(self):
        from aksara.ai.session_store import create_session, get_session, update_session

        session = create_session("test")
        session.status = "running"
        update_session(session)
        found = get_session(session.id)
        assert found.status == "running"

    def test_list_sessions_empty(self):
        from aksara.ai.session_store import list_sessions

        assert list_sessions() == []

    def test_list_sessions_ordered(self):
        from aksara.ai.session_store import create_session, list_sessions

        s1 = create_session("first")
        s2 = create_session("second")
        sessions = list_sessions()
        assert len(sessions) == 2
        # Newest first
        assert sessions[0].id == s2.id
        assert sessions[1].id == s1.id

    def test_delete_session(self):
        from aksara.ai.session_store import create_session, delete_session, get_session

        session = create_session("test")
        assert delete_session(session.id) is True
        assert get_session(session.id) is None

    def test_delete_session_not_found(self):
        from aksara.ai.session_store import delete_session

        assert delete_session("nonexistent") is False

    def test_clear_sessions(self):
        from aksara.ai.session_store import create_session, clear_sessions, list_sessions

        create_session("a")
        create_session("b")
        count = clear_sessions()
        assert count == 2
        assert list_sessions() == []

    def test_clear_sessions_empty(self):
        from aksara.ai.session_store import clear_sessions

        assert clear_sessions() == 0


# =============================================================================
# 6. Plan Builder Tests
# =============================================================================


class TestPlanBuilder:
    """Tests for the rule-based plan builder."""

    def test_performance_strategy(self):
        from aksara.ai.plan_builder import build_plan

        plan = build_plan("Why is the app slow?")
        assert plan.strategy == "performance"
        step_names = [s.name for s in plan.steps]
        assert "project_graph" in step_names
        assert "performance_analysis" in step_names
        assert "summarise" in step_names

    def test_architecture_strategy(self):
        from aksara.ai.plan_builder import build_plan

        plan = build_plan("Review the architecture of my project")
        assert plan.strategy == "architecture"
        step_names = [s.name for s in plan.steps]
        assert "architecture_review" in step_names

    def test_debug_strategy(self):
        from aksara.ai.plan_builder import build_plan

        plan = build_plan("Debug this error in my app")
        assert plan.strategy == "debug"
        step_names = [s.name for s in plan.steps]
        assert "debug_analysis" in step_names

    def test_generic_fallback(self):
        from aksara.ai.plan_builder import build_plan

        plan = build_plan("Tell me about my project")
        assert plan.strategy == "generic"
        step_names = [s.name for s in plan.steps]
        # Generic includes all steps
        assert "project_graph" in step_names
        assert "architecture_review" in step_names
        assert "performance_analysis" in step_names
        assert "debug_analysis" in step_names
        assert "summarise" in step_names

    def test_performance_keywords(self):
        from aksara.ai.plan_builder import build_plan

        for kw in ["slow", "performance", "latency", "n+1", "bottleneck", "optimize"]:
            plan = build_plan(f"The app has {kw} issues")
            assert plan.strategy == "performance", f"Failed for keyword: {kw}"

    def test_architecture_keywords(self):
        from aksara.ai.plan_builder import build_plan

        for kw in ["architecture", "coupling", "structure", "design", "modularity"]:
            plan = build_plan(f"Analyze {kw}")
            assert plan.strategy == "architecture", f"Failed for keyword: {kw}"

    def test_debug_keywords(self):
        from aksara.ai.plan_builder import build_plan

        for kw in ["bug", "error", "debug", "crash", "exception", "traceback"]:
            plan = build_plan(f"Fix this {kw}")
            assert plan.strategy == "debug", f"Failed for keyword: {kw}"

    def test_steps_all_pending(self):
        from aksara.ai.plan_builder import build_plan

        plan = build_plan("investigate everything")
        for step in plan.steps:
            assert step.status == "pending"

    def test_steps_have_unique_ids(self):
        from aksara.ai.plan_builder import build_plan

        plan = build_plan("investigate everything")
        ids = [s.id for s in plan.steps]
        assert len(ids) == len(set(ids))

    def test_goal_preserved(self):
        from aksara.ai.plan_builder import build_plan

        goal = "Why is my app slow and buggy?"
        plan = build_plan(goal)
        assert plan.goal == goal

    def test_empty_goal_returns_generic(self):
        from aksara.ai.plan_builder import build_plan

        plan = build_plan("")
        assert plan.strategy == "generic"

    def test_case_insensitive(self):
        from aksara.ai.plan_builder import build_plan

        plan = build_plan("PERFORMANCE issues in production")
        assert plan.strategy == "performance"


# =============================================================================
# 7. Investigation Runner Tests
# =============================================================================


class TestInvestigationRunner:
    """Tests for the investigation execution engine."""

    @pytest.fixture(autouse=True)
    def clear_store(self):
        from aksara.ai.session_store import clear_sessions
        clear_sessions()
        yield
        clear_sessions()

    def test_execute_no_plan(self):
        from aksara.ai.investigation import InvestigationSession
        from aksara.ai.investigation_runner import execute_investigation
        from aksara.ai.session_store import create_session

        session = create_session("test")
        session = execute_investigation(session)
        assert session.status == "failed"

    def test_execute_empty_plan(self):
        from aksara.ai.investigation import InvestigationPlan, InvestigationSession
        from aksara.ai.investigation_runner import execute_investigation
        from aksara.ai.session_store import create_session

        session = create_session("test")
        session.plan = InvestigationPlan(goal="test", steps=[])
        session = execute_investigation(session)
        assert session.status == "failed"

    def test_execute_with_unknown_step(self):
        from aksara.ai.investigation import (
            InvestigationPlan,
            InvestigationStep,
        )
        from aksara.ai.investigation_runner import execute_investigation
        from aksara.ai.session_store import create_session

        session = create_session("test")
        session.plan = InvestigationPlan(
            goal="test",
            steps=[InvestigationStep(name="unknown_step")],
        )
        session = execute_investigation(session)
        assert session.plan.steps[0].status == "skipped"
        assert "Unknown step" in session.plan.steps[0].error

    def test_execute_project_graph_step(self):
        """Project graph step should succeed (it's local analysis)."""
        from aksara.ai.investigation import (
            InvestigationPlan,
            InvestigationStep,
        )
        from aksara.ai.investigation_runner import execute_investigation
        from aksara.ai.session_store import create_session

        session = create_session("test")
        session.plan = InvestigationPlan(
            goal="test",
            steps=[InvestigationStep(name="project_graph")],
        )
        session = execute_investigation(session)
        step = session.plan.steps[0]
        assert step.status == "done"
        assert step.result is not None
        assert step.completed_at is not None

    def test_execute_summarise_step(self):
        from aksara.ai.investigation import (
            InvestigationPlan,
            InvestigationStep,
        )
        from aksara.ai.investigation_runner import execute_investigation
        from aksara.ai.session_store import create_session

        session = create_session("test")
        session.plan = InvestigationPlan(
            goal="test",
            steps=[InvestigationStep(name="summarise")],
        )
        session = execute_investigation(session)
        step = session.plan.steps[0]
        assert step.status == "done"
        assert "completed_steps" in step.result

    def test_execute_sets_status_running_then_completed(self):
        from aksara.ai.investigation import (
            InvestigationPlan,
            InvestigationStep,
        )
        from aksara.ai.investigation_runner import execute_investigation
        from aksara.ai.session_store import create_session

        session = create_session("test")
        session.plan = InvestigationPlan(
            goal="test",
            steps=[InvestigationStep(name="summarise")],
        )
        session = execute_investigation(session)
        assert session.status == "completed"

    def test_execute_next_step(self):
        from aksara.ai.investigation import (
            InvestigationPlan,
            InvestigationStep,
        )
        from aksara.ai.investigation_runner import execute_next_step
        from aksara.ai.session_store import create_session

        session = create_session("test")
        session.plan = InvestigationPlan(
            goal="test",
            steps=[
                InvestigationStep(name="project_graph"),
                InvestigationStep(name="summarise"),
            ],
        )
        session = execute_next_step(session)
        assert session.plan.steps[0].status == "done"
        assert session.plan.steps[1].status == "pending"
        assert session.status != "completed"

    def test_execute_next_step_completes_when_all_done(self):
        from aksara.ai.investigation import (
            InvestigationPlan,
            InvestigationStep,
        )
        from aksara.ai.investigation_runner import execute_next_step
        from aksara.ai.session_store import create_session

        session = create_session("test")
        session.plan = InvestigationPlan(
            goal="test",
            steps=[InvestigationStep(name="summarise")],
        )
        session = execute_next_step(session)
        assert session.status == "completed"

    def test_execute_next_step_no_plan(self):
        from aksara.ai.investigation_runner import execute_next_step
        from aksara.ai.session_store import create_session

        session = create_session("test")
        result = execute_next_step(session)
        assert result.status == "created"  # unchanged

    def test_findings_appended(self):
        from aksara.ai.investigation import (
            InvestigationPlan,
            InvestigationStep,
        )
        from aksara.ai.investigation_runner import execute_investigation
        from aksara.ai.session_store import create_session

        session = create_session("test")
        session.plan = InvestigationPlan(
            goal="test",
            steps=[
                InvestigationStep(name="project_graph"),
                InvestigationStep(name="summarise"),
            ],
        )
        session = execute_investigation(session)
        # Should have at least 2 findings: one from graph, one from summarise
        assert len(session.findings) >= 2

    def test_step_timestamps_set(self):
        from aksara.ai.investigation import (
            InvestigationPlan,
            InvestigationStep,
        )
        from aksara.ai.investigation_runner import execute_investigation
        from aksara.ai.session_store import create_session

        session = create_session("test")
        session.plan = InvestigationPlan(
            goal="test",
            steps=[InvestigationStep(name="summarise")],
        )
        session = execute_investigation(session)
        step = session.plan.steps[0]
        assert step.started_at is not None
        assert step.completed_at is not None


# =============================================================================
# 8. Console Engine Integration Tests
# =============================================================================


class TestConsoleEngineIntegration:
    """Tests for investigation flow triggered via the console engine."""

    @pytest.fixture(autouse=True)
    def clear_store(self):
        from aksara.ai.session_store import clear_sessions
        clear_sessions()
        yield
        clear_sessions()

    def test_investigate_regex_matches(self):
        from aksara.ai.console_engine import _INVESTIGATE_RE

        assert _INVESTIGATE_RE.search("investigate my project")
        assert _INVESTIGATE_RE.search("Investigate the app")
        assert _INVESTIGATE_RE.search("analyze the system")
        assert _INVESTIGATE_RE.search("review my project")
        assert _INVESTIGATE_RE.search("deep dive into the app")
        assert _INVESTIGATE_RE.search("full analysis of the codebase")

    def test_investigate_regex_no_false_positives(self):
        from aksara.ai.console_engine import _INVESTIGATE_RE

        assert not _INVESTIGATE_RE.search("explain the User model")
        assert not _INVESTIGATE_RE.search("hello world")
        assert not _INVESTIGATE_RE.search("list models")

    @pytest.mark.asyncio
    async def test_investigate_flow_via_console(self):
        from aksara.ai.console_engine import run_console_query

        result = await run_console_query("investigate my project")
        assert result["ok"] is True
        assert result["intent"] == "investigation"
        assert result["flow_type"] == "investigation"
        assert result["investigation"] is True
        assert "session_id" in result
        assert result["execution"]["investigation_session"] is not None

    @pytest.mark.asyncio
    async def test_investigate_creates_session(self):
        from aksara.ai.console_engine import run_console_query
        from aksara.ai.session_store import list_sessions

        result = await run_console_query("investigate my project")
        sessions = list_sessions()
        assert len(sessions) == 1
        assert sessions[0].id == result["session_id"]

    @pytest.mark.asyncio
    async def test_non_investigation_falls_through(self):
        """Non-investigation prompts should not trigger investigation flow."""
        from aksara.ai.console_engine import run_console_query

        result = await run_console_query("explain the User model")
        assert result.get("investigation") is not True

    @pytest.mark.asyncio
    async def test_empty_message_returns_error(self):
        from aksara.ai.console_engine import run_console_query

        result = await run_console_query("")
        assert result["ok"] is False
        assert result["error_code"] == "EMPTY_MESSAGE"


# =============================================================================
# 9. API Endpoint Tests
# =============================================================================


class TestApiEndpoints:
    """Tests for the Studio investigation API endpoints."""

    @pytest.fixture(autouse=True)
    def clear_store(self):
        from aksara.ai.session_store import clear_sessions
        clear_sessions()
        yield
        clear_sessions()

    def test_investigate_endpoint_registered(self):
        """Check the endpoint routes exist on the router."""
        from aksara.studio.fastapi import router

        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/studio/ai/investigate" in paths

    def test_investigate_session_id_endpoint_registered(self):
        from aksara.studio.fastapi import router

        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/studio/ai/investigate/{session_id}" in paths

    def test_investigate_run_endpoint_registered(self):
        from aksara.studio.fastapi import router

        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/studio/ai/investigate/{session_id}/run" in paths


# =============================================================================
# 10. Version Tests
# =============================================================================


class TestVersion:
    """Verify version strings are bumped."""

    def test_version_is_0_5_39(self):
        from aksara._version import __version__

        assert __version__ == "0.5.48"

    def test_cli_version_is_0_5_39(self):
        from aksara.cli.main import CLI_VERSION

        assert CLI_VERSION == "0.5.48"


# =============================================================================
# 11. Finding Extraction Tests
# =============================================================================


class TestFindingExtraction:
    """Tests for the _extract_finding helper."""

    def test_project_graph_finding(self):
        from aksara.ai.investigation_runner import _extract_finding

        result = {"counts": {"models": 5, "routes": 10}}
        finding = _extract_finding("project_graph", result)
        assert "5 models" in finding
        assert "10 routes" in finding

    def test_performance_finding(self):
        from aksara.ai.investigation_runner import _extract_finding

        result = {"score": 85, "grade": "B"}
        finding = _extract_finding("performance_analysis", result)
        assert "85" in finding
        assert "B" in finding

    def test_architecture_finding(self):
        from aksara.ai.investigation_runner import _extract_finding

        result = {"score": 90, "grade": "A"}
        finding = _extract_finding("architecture_review", result)
        assert "90" in finding
        assert "A" in finding

    def test_debug_finding_clean(self):
        from aksara.ai.investigation_runner import _extract_finding

        result = {"ok": True}
        finding = _extract_finding("debug_analysis", result)
        assert "clean" in finding

    def test_debug_finding_issues(self):
        from aksara.ai.investigation_runner import _extract_finding

        result = {"ok": False, "issues_count": 3}
        finding = _extract_finding("debug_analysis", result)
        assert "3" in finding

    def test_summarise_finding(self):
        from aksara.ai.investigation_runner import _extract_finding

        result = {"total_findings": 5}
        finding = _extract_finding("summarise", result)
        assert "5 findings" in finding

    def test_unknown_step_returns_none(self):
        from aksara.ai.investigation_runner import _extract_finding

        assert _extract_finding("nonexistent_step", {}) is None


# =============================================================================
# 12. Strategy Constants Tests
# =============================================================================


class TestStrategyConstants:
    """Verify plan builder strategy constants and blueprints."""

    def test_step_constants(self):
        from aksara.ai.plan_builder import (
            STEP_PROJECT_GRAPH,
            STEP_PERFORMANCE,
            STEP_ARCHITECTURE,
            STEP_DEBUG,
            STEP_SUMMARISE,
        )

        assert STEP_PROJECT_GRAPH == "project_graph"
        assert STEP_PERFORMANCE == "performance_analysis"
        assert STEP_ARCHITECTURE == "architecture_review"
        assert STEP_DEBUG == "debug_analysis"
        assert STEP_SUMMARISE == "summarise"

    def test_all_strategies_end_with_summarise(self):
        from aksara.ai.plan_builder import _STRATEGIES

        for name, steps in _STRATEGIES.items():
            assert steps[-1] == "summarise", f"Strategy '{name}' does not end with summarise"

    def test_all_strategies_start_with_project_graph(self):
        from aksara.ai.plan_builder import _STRATEGIES

        for name, steps in _STRATEGIES.items():
            assert steps[0] == "project_graph", f"Strategy '{name}' does not start with project_graph"


# =============================================================================
# 13. Session Store Edge Cases
# =============================================================================


class TestSessionStoreEdgeCases:
    """Edge case tests for the session store."""

    @pytest.fixture(autouse=True)
    def clear_store(self):
        from aksara.ai.session_store import clear_sessions
        clear_sessions()
        yield
        clear_sessions()

    def test_create_many_sessions(self):
        from aksara.ai.session_store import create_session, list_sessions

        for i in range(20):
            create_session(f"session {i}")
        assert len(list_sessions()) == 20

    def test_delete_then_recreate(self):
        from aksara.ai.session_store import create_session, delete_session, get_session

        s = create_session("test")
        sid = s.id
        delete_session(sid)
        assert get_session(sid) is None
        s2 = create_session("test again")
        assert s2.id != sid

    def test_update_preserves_other_sessions(self):
        from aksara.ai.session_store import create_session, update_session, get_session

        s1 = create_session("one")
        s2 = create_session("two")
        s1.status = "running"
        update_session(s1)
        assert get_session(s2.id).status == "created"


# =============================================================================
# 14. Full Pipeline Integration Tests
# =============================================================================


class TestFullPipeline:
    """End-to-end tests for the complete investigation pipeline."""

    @pytest.fixture(autouse=True)
    def clear_store(self):
        from aksara.ai.session_store import clear_sessions
        clear_sessions()
        yield
        clear_sessions()

    def test_create_plan_execute_pipeline(self):
        """Full pipeline: create session → build plan → execute."""
        from aksara.ai.session_store import create_session
        from aksara.ai.plan_builder import build_plan
        from aksara.ai.investigation_runner import execute_investigation

        session = create_session("Why is my app slow?")
        plan = build_plan(session.goal)
        session.plan = plan
        session = execute_investigation(session)

        assert session.status == "completed"
        assert session.plan.strategy == "performance"
        done = [s for s in session.plan.steps if s.status == "done"]
        assert len(done) >= 1
        assert len(session.findings) >= 1

    def test_step_by_step_execution(self):
        """Execute one step at a time."""
        from aksara.ai.session_store import create_session
        from aksara.ai.plan_builder import build_plan
        from aksara.ai.investigation_runner import execute_next_step

        session = create_session("Investigate me")
        plan = build_plan(session.goal)
        session.plan = plan

        total_steps = len(plan.steps)
        for i in range(total_steps):
            session = execute_next_step(session)
            done = sum(1 for s in session.plan.steps if s.status != "pending")
            assert done >= i + 1

        assert session.status == "completed"

    def test_serialization_round_trip(self):
        """Session serializes and contains expected keys."""
        from aksara.ai.session_store import create_session
        from aksara.ai.plan_builder import build_plan
        from aksara.ai.investigation_runner import execute_investigation

        session = create_session("test")
        session.plan = build_plan("test")
        session = execute_investigation(session)

        d = session.to_dict()
        assert "id" in d
        assert "goal" in d
        assert "plan" in d
        assert "findings" in d
        assert "status" in d
        assert "created_at" in d
        assert "updated_at" in d

        sd = session.to_summary_dict()
        assert "steps_total" in sd
        assert "steps_done" in sd


# =============================================================================
# 15. __all__ Coverage Test
# =============================================================================


class TestAllExports:
    """Verify all new exports are in __all__."""

    def test_investigation_exports_in_all(self):
        from aksara.ai import __all__

        expected = [
            "InvestigationStep",
            "InvestigationPlan",
            "InvestigationSession",
            "StepStatus",
            "SessionStatus",
            "create_session",
            "get_session",
            "update_session",
            "list_sessions",
            "delete_session",
            "clear_sessions",
            "build_plan",
            "execute_investigation",
            "execute_next_step",
            "STEP_PROJECT_GRAPH",
            "STEP_PERFORMANCE",
            "STEP_ARCHITECTURE",
            "STEP_DEBUG",
            "STEP_SUMMARISE",
        ]
        for name in expected:
            assert name in __all__, f"{name} not in __all__"
