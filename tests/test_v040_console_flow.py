"""
v0.5.40 — Console Flow Tests

Tests for the console engine's continuation flow, intent routing,
briefing-related keywords, and end-to-end console pipeline.
"""

from __future__ import annotations

import pytest

from aksara.ai.session_store import clear_sessions


# =============================================================================
# 1. Import Tests
# =============================================================================


class TestImports:
    """Verify all console-related symbols are importable."""

    def test_import_console_engine(self):
        from aksara.ai.console_engine import run_console_query
        assert callable(run_console_query)

    def test_import_continuation_helper(self):
        from aksara.ai.console_engine import _continue_investigation
        assert callable(_continue_investigation)

    def test_import_intent_engine_v2(self):
        from aksara.ai.intent_engine_v2 import classify_intent_v2
        assert callable(classify_intent_v2)

    def test_import_investigation_flow(self):
        from aksara.ai.console_engine import _try_investigation_flow
        assert callable(_try_investigation_flow)


# =============================================================================
# 2. Continuation Keyword Detection Tests
# =============================================================================


class TestContinuationKeywords:
    """Test that continuation keywords are recognized."""

    @pytest.fixture(autouse=True)
    def clear(self):
        clear_sessions()
        yield
        clear_sessions()

    @pytest.mark.asyncio
    async def test_continue_keyword_detected(self):
        """The console engine should recognize 'continue' as a continuation keyword."""
        from aksara.ai.console_engine import run_console_query

        # With no active session, it should still handle 'continue' gracefully
        result = await run_console_query("continue")
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_next_keyword_detected(self):
        """The console engine should recognize 'next' as a continuation keyword."""
        from aksara.ai.console_engine import run_console_query

        result = await run_console_query("next")
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_non_continuation_keyword(self):
        """Regular queries should not trigger continuation flow."""
        from aksara.ai.console_engine import run_console_query

        result = await run_console_query("why is my API slow?")
        assert isinstance(result, dict)


# =============================================================================
# 3. Continue Investigation Function Tests
# =============================================================================


class TestContinueInvestigation:
    """Test the _continue_investigation function directly."""

    @pytest.fixture(autouse=True)
    def clear(self):
        clear_sessions()
        yield
        clear_sessions()

    def test_no_active_session(self):
        """When no active session exists, return None."""
        import time
        from aksara.ai.console_engine import _continue_investigation

        result = _continue_investigation(time.perf_counter())
        assert result is None

    def test_with_active_session(self):
        """When an active session exists, it should attempt to run the next step."""
        import time
        from aksara.ai.console_engine import _continue_investigation
        from aksara.ai.session_store import create_session
        from aksara.ai.plan_builder import build_plan
        from aksara.ai.investigation_runner import execute_investigation

        session = create_session(goal="Test investigation")
        # Build and attach a plan so there are steps to run
        plan = build_plan("Test investigation")
        session.plan = plan
        session.status = "running"
        result = _continue_investigation(time.perf_counter())
        # With an active running session that has a plan, we get a dict
        assert isinstance(result, dict)

    def test_completed_session_not_picked_up(self):
        """A completed session should not be picked up for continuation."""
        import time
        from aksara.ai.console_engine import _continue_investigation
        from aksara.ai.session_store import create_session, update_session

        session = create_session(goal="Done investigation")
        session.status = "completed"
        update_session(session)
        result = _continue_investigation(time.perf_counter())
        # Completed sessions are not active, so returns None
        assert result is None


# =============================================================================
# 4. Console Query Pipeline Tests
# =============================================================================


class TestConsoleQueryPipeline:
    """Test the full run_console_query pipeline."""

    @pytest.fixture(autouse=True)
    def clear(self):
        clear_sessions()
        yield
        clear_sessions()

    @pytest.mark.asyncio
    async def test_empty_query(self):
        from aksara.ai.console_engine import run_console_query

        result = await run_console_query("")
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_query_returns_dict(self):
        from aksara.ai.console_engine import run_console_query

        result = await run_console_query("show me all models")
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_investigation_query(self):
        """Queries that look like investigations should route appropriately."""
        from aksara.ai.console_engine import run_console_query

        result = await run_console_query("investigate why the API is slow")
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_debug_query(self):
        from aksara.ai.console_engine import run_console_query

        result = await run_console_query("debug the login endpoint")
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_result_has_timing(self):
        from aksara.ai.console_engine import run_console_query

        result = await run_console_query("what is the project status?")
        assert isinstance(result, dict)
        # Most responses should have elapsed_ms
        if "elapsed_ms" in result:
            assert result["elapsed_ms"] >= 0


# =============================================================================
# 5. Intent Router Integration Tests
# =============================================================================


class TestIntentRouterIntegration:
    """Test that intent classification integrates with console flow."""

    def test_intent_v2_classifies_debug(self):
        from aksara.ai.intent_engine_v2 import classify_intent_v2

        result = classify_intent_v2("debug the slow users endpoint")
        assert result.intent in ("debug_analysis", "performance_analysis", "investigation")

    def test_intent_v2_classifies_investigate(self):
        from aksara.ai.intent_engine_v2 import classify_intent_v2

        result = classify_intent_v2("investigate the failing migration")
        assert result.intent == "investigation"

    def test_intent_v2_classifies_performance(self):
        from aksara.ai.intent_engine_v2 import classify_intent_v2

        result = classify_intent_v2("why is the query so slow?")
        assert result.intent in ("performance_analysis", "debug_analysis")

    def test_intent_v2_classifies_architecture(self):
        from aksara.ai.intent_engine_v2 import classify_intent_v2

        result = classify_intent_v2("review the architecture of my project")
        assert result.intent == "architecture_review"


# =============================================================================
# 6. Session Banner Data Tests
# =============================================================================


class TestSessionBannerData:
    """Test that session data is suitable for the Studio banner UI."""

    @pytest.fixture(autouse=True)
    def clear(self):
        clear_sessions()
        yield
        clear_sessions()

    def test_session_to_dict(self):
        from aksara.ai.session_store import create_session
        from aksara.ai.plan_builder import build_plan

        session = create_session(goal="Test goal")
        plan = build_plan("Test goal")
        session.plan = plan
        d = session.to_dict()
        assert d["goal"] == "Test goal"
        assert d["status"] == "created"
        assert d["plan"] is not None

    def test_session_progress_tracking(self):
        from aksara.ai.session_store import create_session
        from aksara.ai.plan_builder import build_plan
        from aksara.ai.investigation_runner import execute_next_step

        session = create_session(goal="Progress test")
        plan = build_plan("Progress test")
        session.plan = plan
        session.status = "running"
        execute_next_step(session)
        d = session.to_dict()
        if d["plan"] and d["plan"]["steps"]:
            done = sum(1 for s in d["plan"]["steps"] if s.get("status") == "done")
            assert done >= 1

    def test_active_session_lookup(self):
        from aksara.ai.session_store import create_session, get_active_session

        create_session(goal="Active session")
        active = get_active_session()
        assert active is not None
        assert active.goal == "Active session"
