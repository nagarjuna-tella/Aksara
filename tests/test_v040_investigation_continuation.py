"""
v0.5.40 — Investigation Continuation Tests

Tests for session continuation, get_next_step, run_step, active session
retrieval, and console engine integration.
"""

from __future__ import annotations

import pytest


# =============================================================================
# 1. Import Tests
# =============================================================================


class TestImports:
    """Verify continuation-related imports work."""

    def test_import_get_active_session(self):
        from aksara.ai.session_store import get_active_session
        assert callable(get_active_session)

    def test_import_get_next_step(self):
        from aksara.ai.investigation_runner import get_next_step
        assert callable(get_next_step)

    def test_import_run_step(self):
        from aksara.ai.investigation_runner import run_step
        assert callable(run_step)

    def test_import_execute_next_step(self):
        from aksara.ai.investigation_runner import execute_next_step
        assert callable(execute_next_step)


# =============================================================================
# 2. get_active_session Tests
# =============================================================================


class TestGetActiveSession:
    """Test the get_active_session function."""

    @pytest.fixture(autouse=True)
    def clear_sessions(self):
        from aksara.ai.session_store import clear_sessions
        clear_sessions()
        yield
        clear_sessions()

    def test_no_active_session(self):
        from aksara.ai.session_store import get_active_session

        assert get_active_session() is None

    def test_single_active_session(self):
        from aksara.ai.session_store import create_session, get_active_session

        session = create_session("Test investigation")
        active = get_active_session()
        assert active is not None
        assert active.id == session.id

    def test_completed_session_not_active(self):
        from aksara.ai.session_store import (
            create_session,
            update_session,
            get_active_session,
        )

        session = create_session("Done investigation")
        session.status = "completed"
        update_session(session)

        assert get_active_session() is None

    def test_most_recent_active_session(self):
        from aksara.ai.session_store import (
            create_session,
            update_session,
            get_active_session,
        )
        import time

        s1 = create_session("First investigation")
        time.sleep(0.01)
        s2 = create_session("Second investigation")

        # Both are active, should return the most recently updated
        active = get_active_session()
        assert active is not None
        assert active.id == s2.id

    def test_running_session_is_active(self):
        from aksara.ai.session_store import (
            create_session,
            update_session,
            get_active_session,
        )

        session = create_session("Running investigation")
        session.status = "running"
        update_session(session)

        active = get_active_session()
        assert active is not None
        assert active.status == "running"

    def test_failed_session_not_active(self):
        from aksara.ai.session_store import (
            create_session,
            update_session,
            get_active_session,
        )

        session = create_session("Failed investigation")
        session.status = "failed"
        update_session(session)

        assert get_active_session() is None


# =============================================================================
# 3. get_next_step Tests
# =============================================================================


class TestGetNextStep:
    """Test get_next_step from the investigation runner."""

    @pytest.fixture(autouse=True)
    def clear_sessions(self):
        from aksara.ai.session_store import clear_sessions
        clear_sessions()
        yield
        clear_sessions()

    def test_no_plan(self):
        from aksara.ai.investigation import InvestigationSession
        from aksara.ai.investigation_runner import get_next_step

        session = InvestigationSession(goal="test")
        assert get_next_step(session) is None

    def test_no_steps(self):
        from aksara.ai.investigation import InvestigationSession, InvestigationPlan
        from aksara.ai.investigation_runner import get_next_step

        session = InvestigationSession(goal="test")
        session.plan = InvestigationPlan(goal="test", steps=[])
        assert get_next_step(session) is None

    def test_returns_first_pending_step(self):
        from aksara.ai.investigation import (
            InvestigationSession,
            InvestigationPlan,
            InvestigationStep,
        )
        from aksara.ai.investigation_runner import get_next_step

        steps = [
            InvestigationStep(name="project_graph"),
            InvestigationStep(name="performance_analysis"),
        ]
        session = InvestigationSession(goal="test")
        session.plan = InvestigationPlan(goal="test", steps=steps)

        ns = get_next_step(session)
        assert ns is not None
        assert ns.name == "project_graph"

    def test_skips_done_steps(self):
        from aksara.ai.investigation import (
            InvestigationSession,
            InvestigationPlan,
            InvestigationStep,
        )
        from aksara.ai.investigation_runner import get_next_step

        steps = [
            InvestigationStep(name="project_graph"),
            InvestigationStep(name="performance_analysis"),
        ]
        steps[0].status = "done"
        session = InvestigationSession(goal="test")
        session.plan = InvestigationPlan(goal="test", steps=steps)

        ns = get_next_step(session)
        assert ns is not None
        assert ns.name == "performance_analysis"

    def test_returns_none_when_all_done(self):
        from aksara.ai.investigation import (
            InvestigationSession,
            InvestigationPlan,
            InvestigationStep,
        )
        from aksara.ai.investigation_runner import get_next_step

        steps = [
            InvestigationStep(name="project_graph"),
            InvestigationStep(name="summarise"),
        ]
        steps[0].status = "done"
        steps[1].status = "done"
        session = InvestigationSession(goal="test")
        session.plan = InvestigationPlan(goal="test", steps=steps)

        assert get_next_step(session) is None


# =============================================================================
# 4. run_step Tests
# =============================================================================


class TestRunStep:
    """Test run_step from the investigation runner."""

    @pytest.fixture(autouse=True)
    def clear_sessions(self):
        from aksara.ai.session_store import clear_sessions
        clear_sessions()
        yield
        clear_sessions()

    def test_run_unknown_step_skips(self):
        from aksara.ai.investigation import (
            InvestigationSession,
            InvestigationPlan,
            InvestigationStep,
        )
        from aksara.ai.investigation_runner import run_step
        from aksara.ai.session_store import create_session

        session = create_session("test")
        step = InvestigationStep(name="nonexistent_step")
        session.plan = InvestigationPlan(goal="test", steps=[step])

        result = run_step(session, step)
        assert result.status == "skipped"
        assert result.error is not None

    def test_run_summarise_step(self):
        from aksara.ai.investigation import (
            InvestigationPlan,
            InvestigationStep,
        )
        from aksara.ai.investigation_runner import run_step
        from aksara.ai.session_store import create_session

        session = create_session("test")
        step = InvestigationStep(name="summarise")
        session.plan = InvestigationPlan(goal="test", steps=[step])

        result = run_step(session, step)
        assert result.status == "done"
        assert result.result is not None
        assert result.completed_at is not None

    def test_run_step_updates_timestamps(self):
        from aksara.ai.investigation import (
            InvestigationPlan,
            InvestigationStep,
        )
        from aksara.ai.investigation_runner import run_step
        from aksara.ai.session_store import create_session

        session = create_session("test")
        step = InvestigationStep(name="summarise")
        session.plan = InvestigationPlan(goal="test", steps=[step])

        run_step(session, step)
        assert step.started_at is not None
        assert step.completed_at is not None


# =============================================================================
# 5. execute_next_step Tests
# =============================================================================


class TestExecuteNextStep:
    """Test execute_next_step for step-by-step execution."""

    @pytest.fixture(autouse=True)
    def clear_sessions(self):
        from aksara.ai.session_store import clear_sessions
        clear_sessions()
        yield
        clear_sessions()

    def test_execute_next_step_on_empty_plan(self):
        from aksara.ai.investigation_runner import execute_next_step
        from aksara.ai.session_store import create_session

        session = create_session("test")
        result = execute_next_step(session)
        assert result.id == session.id

    def test_execute_next_step_advances(self):
        from aksara.ai.investigation import (
            InvestigationPlan,
            InvestigationStep,
        )
        from aksara.ai.investigation_runner import execute_next_step
        from aksara.ai.session_store import create_session, update_session

        session = create_session("test")
        steps = [
            InvestigationStep(name="summarise"),
            InvestigationStep(name="summarise"),
        ]
        session.plan = InvestigationPlan(goal="test", steps=steps)
        update_session(session)

        # Execute first step
        session = execute_next_step(session)
        assert steps[0].status == "done"
        assert steps[1].status == "pending"

        # Execute second step
        session = execute_next_step(session)
        assert steps[1].status == "done"
        assert session.status == "completed"


# =============================================================================
# 6. Console Continuation Tests
# =============================================================================


class TestConsoleContinuation:
    """Test the console engine continuation shortcut."""

    @pytest.fixture(autouse=True)
    def clear_sessions(self):
        from aksara.ai.session_store import clear_sessions
        clear_sessions()
        yield
        clear_sessions()

    def test_continue_no_active_session(self):
        from aksara.ai.console_engine import _continue_investigation
        import time

        result = _continue_investigation(time.monotonic())
        assert result is None

    def test_continue_with_active_session(self):
        from aksara.ai.console_engine import _continue_investigation
        from aksara.ai.investigation import (
            InvestigationPlan,
            InvestigationStep,
        )
        from aksara.ai.session_store import create_session, update_session
        import time

        session = create_session("test continue")
        steps = [InvestigationStep(name="summarise")]
        session.plan = InvestigationPlan(goal="test", steps=steps)
        update_session(session)

        result = _continue_investigation(time.monotonic())
        assert result is not None
        assert result["ok"] is True
        assert result["intent"] == "investigation_continue"
        assert result["session_id"] == session.id

    def test_continue_response_has_progress(self):
        from aksara.ai.console_engine import _continue_investigation
        from aksara.ai.investigation import (
            InvestigationPlan,
            InvestigationStep,
        )
        from aksara.ai.session_store import create_session, update_session
        import time

        session = create_session("test progress")
        steps = [
            InvestigationStep(name="summarise"),
            InvestigationStep(name="summarise"),
        ]
        session.plan = InvestigationPlan(goal="test", steps=steps)
        update_session(session)

        result = _continue_investigation(time.monotonic())
        assert "execution" in result
        exec_data = result["execution"]
        assert "steps_done" in exec_data
        assert "steps_pending" in exec_data


# =============================================================================
# 7. Session Store Edge Cases
# =============================================================================


class TestSessionStoreEdgeCases:
    """Edge cases for session store operations."""

    @pytest.fixture(autouse=True)
    def clear_sessions(self):
        from aksara.ai.session_store import clear_sessions
        clear_sessions()
        yield
        clear_sessions()

    def test_clear_sessions_returns_count(self):
        from aksara.ai.session_store import create_session, clear_sessions

        create_session("s1")
        create_session("s2")
        count = clear_sessions()
        assert count == 2

    def test_delete_nonexistent_session(self):
        from aksara.ai.session_store import delete_session

        assert delete_session("nonexistent") is False

    def test_get_nonexistent_session(self):
        from aksara.ai.session_store import get_session

        assert get_session("nonexistent") is None

    def test_list_sessions_ordered_newest_first(self):
        from aksara.ai.session_store import create_session, list_sessions
        import time

        s1 = create_session("first")
        time.sleep(0.01)
        s2 = create_session("second")

        sessions = list_sessions()
        assert len(sessions) == 2
        assert sessions[0].id == s2.id
        assert sessions[1].id == s1.id
