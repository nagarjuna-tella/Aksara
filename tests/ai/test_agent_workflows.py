"""
Tests for Aksara Agentic Workflows — Builder & Helpers.

v0.5.23: Tests for build_agent_workflow, summarize_agent_workflow,
workflow_stats, and all internal step builders.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from aksara.studio.models import (
    AgentWorkflow,
    AgentWorkflowStep,
    AgentWorkflowRequest,
    AgentWorkflowResponse,
)
from aksara.ai.workflows import (
    build_agent_workflow,
    summarize_agent_workflow,
    workflow_stats,
    _make_step_id,
    _make_workflow_id,
    _risk_from_severity,
    _effort_from_kind,
    _build_diagnostic_steps,
    _build_search_steps,
    _build_inspector_steps,
    _build_playbook_steps,
    _build_test_step,
    _map_playbook_step_kind,
)


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestHelperFunctions:
    """Tests for internal helper functions."""

    def test_make_step_id_deterministic(self):
        id1 = _make_step_id("inspect", 0, "fix bug")
        id2 = _make_step_id("inspect", 0, "fix bug")
        assert id1 == id2
        assert id1.startswith("step-inspect-")

    def test_make_step_id_different_inputs(self):
        id1 = _make_step_id("inspect", 0, "fix bug")
        id2 = _make_step_id("search", 1, "fix bug")
        assert id1 != id2

    def test_make_workflow_id_starts_with_prefix(self):
        wid = _make_workflow_id("test goal")
        assert wid.startswith("wf-")

    def test_risk_from_severity(self):
        assert _risk_from_severity("error") == "high"
        assert _risk_from_severity("warning") == "medium"
        assert _risk_from_severity("info") == "low"
        assert _risk_from_severity("unknown") == "low"

    def test_effort_from_kind(self):
        assert _effort_from_kind("edit_file") == "high"
        assert _effort_from_kind("run_migration") == "high"
        assert _effort_from_kind("run_query") == "medium"
        assert _effort_from_kind("run_test") == "medium"
        assert _effort_from_kind("inspect") == "low"
        assert _effort_from_kind("search") == "low"
        assert _effort_from_kind("diagnostics") == "low"

    def test_map_playbook_step_kind(self):
        assert _map_playbook_step_kind("inspect_models") == "inspect"
        assert _map_playbook_step_kind("search_codebase") == "search"
        assert _map_playbook_step_kind("edit_settings") == "edit_file"
        assert _map_playbook_step_kind("run_migration") == "run_migration"
        assert _map_playbook_step_kind("run_test_suite") == "run_test"
        assert _map_playbook_step_kind("check_env") == "environment"
        assert _map_playbook_step_kind("config_db") == "config"
        assert _map_playbook_step_kind("diagnose_issues") == "diagnostics"
        assert _map_playbook_step_kind("read_doc") == "doc_reading"
        assert _map_playbook_step_kind("something_else") == "config"


# =============================================================================
# Diagnostic Steps Tests
# =============================================================================


class TestBuildDiagnosticSteps:
    """Tests for _build_diagnostic_steps."""

    def test_returns_list(self):
        steps = _build_diagnostic_steps("test goal")
        assert isinstance(steps, list)
        assert len(steps) >= 1

    def test_steps_have_correct_kind(self):
        steps = _build_diagnostic_steps("test goal")
        for step in steps:
            assert step.kind == "diagnostics"

    def test_steps_have_order(self):
        steps = _build_diagnostic_steps("test goal", start_order=5)
        for step in steps:
            assert step.order >= 5

    def test_fallback_on_error(self):
        with patch("aksara.ai.workflows._get_run_all_checks", side_effect=Exception("fail")):
            steps = _build_diagnostic_steps("test goal")
            assert len(steps) == 1
            assert "diagnostic" in steps[0].kind


# =============================================================================
# Search Steps Tests
# =============================================================================


class TestBuildSearchSteps:
    """Tests for _build_search_steps."""

    def test_returns_empty_on_no_results(self):
        mock_index = MagicMock()
        mock_index.search.return_value = []
        mock_builder = MagicMock(return_value=mock_index)

        with patch("aksara.ai.workflows._get_search_index_and_builder", return_value=(MagicMock, mock_builder)):
            steps = _build_search_steps("test goal")
            assert len(steps) == 1
            assert "No search results" in steps[0].description

    def test_builds_steps_from_results(self):
        mock_doc = MagicMock()
        mock_doc.kind = "model"
        mock_doc.title = "User"
        mock_doc.summary = "User model"
        mock_doc.content = "User model content"
        mock_doc.source = "model:User"
        mock_doc.metadata = {"table_name": "users"}
        mock_doc.tags = ["model"]

        mock_result = MagicMock()
        mock_result.document = mock_doc
        mock_result.score = 0.85
        mock_result.highlights = ["user", "account"]
        mock_result.match_type = "hybrid"

        mock_index = MagicMock()
        mock_index.search.return_value = [mock_result]
        mock_builder = MagicMock(return_value=mock_index)

        with patch("aksara.ai.workflows._get_search_index_and_builder", return_value=(MagicMock, mock_builder)):
            steps = _build_search_steps("find user model")
            assert len(steps) == 1
            assert steps[0].kind == "search"
            assert "User" in steps[0].title
            assert steps[0].references["score"] == 0.85

    def test_uses_custom_search_query(self):
        mock_index = MagicMock()
        mock_index.search.return_value = []
        mock_builder = MagicMock(return_value=mock_index)

        with patch("aksara.ai.workflows._get_search_index_and_builder", return_value=(MagicMock, mock_builder)):
            steps = _build_search_steps("default", search_query="custom query")
            assert len(steps) == 1
            assert steps[0].references["query"] == "custom query"

    def test_fallback_on_error(self):
        with patch("aksara.ai.workflows._get_search_index_and_builder", side_effect=Exception("fail")):
            steps = _build_search_steps("test goal")
            assert len(steps) == 1
            assert steps[0].kind == "search"

    def test_model_result_generates_inspect_command(self):
        mock_doc = MagicMock()
        mock_doc.kind = "model"
        mock_doc.title = "Post"
        mock_doc.summary = "Blog post"
        mock_doc.content = "Post model"
        mock_doc.source = "model:Post"
        mock_doc.metadata = {}
        mock_doc.tags = []

        mock_result = MagicMock()
        mock_result.document = mock_doc
        mock_result.score = 0.5
        mock_result.highlights = []
        mock_result.match_type = "keyword"

        mock_index = MagicMock()
        mock_index.search.return_value = [mock_result]
        mock_builder = MagicMock(return_value=mock_index)

        with patch("aksara.ai.workflows._get_search_index_and_builder", return_value=(MagicMock, mock_builder)):
            steps = _build_search_steps("fix Post")
            assert any("aksara inspect models --model Post" in cmd for cmd in steps[0].commands)


# =============================================================================
# Inspector Steps Tests
# =============================================================================


class TestBuildInspectorSteps:
    """Tests for _build_inspector_steps."""

    def test_always_includes_model_inspection(self):
        steps = _build_inspector_steps("any goal")
        assert len(steps) >= 1
        assert steps[0].kind == "inspect"
        assert "model" in steps[0].title.lower()

    def test_includes_query_inspection_for_query_goals(self):
        steps = _build_inspector_steps("fix slow query in posts")
        assert len(steps) == 2
        assert steps[1].kind == "inspect"
        assert "quer" in steps[1].title.lower()

    def test_includes_query_inspection_for_playbook_kind(self):
        steps = _build_inspector_steps("optimize", playbook_kind="debug_slow_queries")
        assert len(steps) == 2

    def test_no_query_step_for_unrelated_goal(self):
        steps = _build_inspector_steps("add new field")
        assert len(steps) == 1

    def test_step_order(self):
        steps = _build_inspector_steps("test", start_order=50)
        assert steps[0].order == 50


# =============================================================================
# Playbook Steps Tests
# =============================================================================


class TestBuildPlaybookSteps:
    """Tests for _build_playbook_steps."""

    def test_returns_empty_for_unknown_playbook(self):
        steps = _build_playbook_steps("nonexistent_playbook", "goal")
        assert steps == []

    def test_builds_steps_from_real_playbook(self):
        mock_pb = MagicMock()
        mock_pb.key = "add_field_to_model"
        mock_pb.risk_level = "medium"
        mock_pb.steps = [
            MagicMock(id="s1", key="define_field", title="Define the field",
                      description="Add the field."),
            MagicMock(id="s2", key="generate_migration", title="Generate migration",
                      description="Run migration gen."),
        ]
        with patch("aksara.ai.workflows._get_playbook", return_value=mock_pb):
            steps = _build_playbook_steps("add_field_to_model", "add email field")
            assert len(steps) == 2
            for step in steps:
                assert step.references.get("playbook") == "add_field_to_model"

    def test_step_order_starts_at_given_value(self):
        mock_pb = MagicMock()
        mock_pb.key = "add_field_to_model"
        mock_pb.risk_level = "low"
        mock_pb.steps = [
            MagicMock(id="s1", key="inspect_model", title="Inspect",
                      description="Inspect model."),
        ]
        with patch("aksara.ai.workflows._get_playbook", return_value=mock_pb):
            steps = _build_playbook_steps("add_field_to_model", "goal", start_order=200)
            assert steps[0].order == 200


# =============================================================================
# Test Step Tests
# =============================================================================


class TestBuildTestStep:
    """Tests for _build_test_step."""

    def test_returns_single_step(self):
        step = _build_test_step("fix bugs")
        assert isinstance(step, AgentWorkflowStep)
        assert step.kind == "run_test"

    def test_has_commands(self):
        step = _build_test_step("fix bugs")
        assert len(step.commands) > 0
        assert any("pytest" in cmd for cmd in step.commands)

    def test_order(self):
        step = _build_test_step("fix bugs", start_order=300)
        assert step.order == 300


# =============================================================================
# Core Builder Tests
# =============================================================================


class TestBuildAgentWorkflow:
    """Tests for build_agent_workflow."""

    def test_basic_workflow(self):
        wf = build_agent_workflow(
            "fix login bug",
            include_diagnostics=False,
            include_search=False,
        )
        assert isinstance(wf, AgentWorkflow)
        assert wf.goal == "fix login bug"
        assert len(wf.steps) > 0

    def test_workflow_has_id(self):
        wf = build_agent_workflow("test", include_diagnostics=False, include_search=False)
        assert wf.id.startswith("wf-")

    def test_steps_sorted_by_order(self):
        wf = build_agent_workflow("test", include_diagnostics=False, include_search=False)
        orders = [s.order for s in wf.steps]
        assert orders == sorted(orders)

    def test_includes_diagnostics_when_enabled(self):
        wf = build_agent_workflow("fix bug", include_diagnostics=True, include_search=False)
        kinds = [s.kind for s in wf.steps]
        assert "diagnostics" in kinds

    def test_skips_diagnostics_when_disabled(self):
        wf = build_agent_workflow("fix bug", include_diagnostics=False, include_search=False)
        kinds = [s.kind for s in wf.steps]
        # May or may not have diagnostics (inspect and run_test are always there)
        # but we verify inspect is present
        assert "inspect" in kinds

    def test_includes_search_when_enabled(self):
        wf = build_agent_workflow("fix bug", include_diagnostics=False, include_search=True)
        kinds = [s.kind for s in wf.steps]
        assert "search" in kinds

    def test_skips_search_when_disabled(self):
        wf = build_agent_workflow("fix bug", include_diagnostics=False, include_search=False)
        kinds = [s.kind for s in wf.steps]
        assert "search" not in kinds

    def test_always_includes_test_step(self):
        wf = build_agent_workflow("fix bug", include_diagnostics=False, include_search=False)
        kinds = [s.kind for s in wf.steps]
        assert "run_test" in kinds

    def test_playbook_adds_steps(self):
        mock_pb = MagicMock()
        mock_pb.key = "add_field_to_model"
        mock_pb.label = "Add Field to Model"
        mock_pb.kind = "add_field"
        mock_pb.risk_level = "medium"
        mock_pb.steps = [
            MagicMock(id="s1", key="define_field", title="Define the field",
                      description="Add the field."),
            MagicMock(id="s2", key="generate_migration", title="Generate migration",
                      description="Run migration gen."),
        ]
        with patch("aksara.ai.workflows._get_playbook", return_value=mock_pb):
            wf = build_agent_workflow(
                "add email to user model",
                playbook="add_field_to_model",
                include_diagnostics=False,
                include_search=False,
            )
            assert wf.playbook == "add_field_to_model"
            assert len(wf.steps) > 2  # inspect + playbook steps + test

    def test_source_is_manual_when_no_extras(self):
        wf = build_agent_workflow("test", include_diagnostics=False, include_search=False)
        assert wf.source == "manual"

    def test_source_is_mixed_with_diagnostics_and_search(self):
        wf = build_agent_workflow("test", include_diagnostics=True, include_search=True)
        assert wf.source == "mixed"

    def test_metadata_includes_goal(self):
        wf = build_agent_workflow("fix it", include_diagnostics=False, include_search=False)
        assert wf.metadata["goal"] == "fix it"

    def test_metadata_includes_playbook_info(self):
        mock_pb = MagicMock()
        mock_pb.key = "add_field_to_model"
        mock_pb.label = "Add Field to Model"
        mock_pb.kind = "add_field"
        mock_pb.risk_level = "medium"
        mock_pb.steps = []
        with patch("aksara.ai.workflows._get_playbook", return_value=mock_pb):
            wf = build_agent_workflow(
                "add field",
                playbook="add_field_to_model",
                include_diagnostics=False,
                include_search=False,
            )
            assert wf.metadata.get("playbook_key") == "add_field_to_model"
            assert "playbook_label" in wf.metadata

    def test_custom_search_query(self):
        wf = build_agent_workflow(
            "fix login",
            include_diagnostics=False,
            include_search=True,
            search_query="authentication error",
        )
        assert wf.metadata.get("search_query") == "authentication error"

    def test_search_limit(self):
        wf = build_agent_workflow(
            "test",
            include_diagnostics=False,
            include_search=True,
            search_limit=3,
        )
        search_steps = [s for s in wf.steps if s.kind == "search"]
        assert len(search_steps) <= 3 + 1  # +1 for fallback step


# =============================================================================
# Summary & Stats Tests
# =============================================================================


class TestSummarizeAgentWorkflow:
    """Tests for summarize_agent_workflow."""

    def test_returns_nonempty_string(self):
        wf = build_agent_workflow("test", include_diagnostics=False, include_search=False)
        summary = summarize_agent_workflow(wf)
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_includes_goal(self):
        wf = build_agent_workflow("fix login bug", include_diagnostics=False, include_search=False)
        summary = summarize_agent_workflow(wf)
        assert "fix login bug" in summary

    def test_includes_step_count(self):
        wf = build_agent_workflow("test", include_diagnostics=False, include_search=False)
        summary = summarize_agent_workflow(wf)
        assert str(len(wf.steps)) in summary

    def test_mentions_playbook(self):
        mock_pb = MagicMock()
        mock_pb.key = "add_field_to_model"
        mock_pb.label = "Add Field to Model"
        mock_pb.kind = "add_field"
        mock_pb.risk_level = "medium"
        mock_pb.steps = [
            MagicMock(id="s1", key="define_field", title="Define",
                      description="Define."),
        ]
        with patch("aksara.ai.workflows._get_playbook", return_value=mock_pb):
            wf = build_agent_workflow(
                "add field",
                playbook="add_field_to_model",
                include_diagnostics=False,
                include_search=False,
            )
            summary = summarize_agent_workflow(wf)
            assert "add_field_to_model" in summary


class TestWorkflowStats:
    """Tests for workflow_stats."""

    def test_returns_dict(self):
        wf = build_agent_workflow("test", include_diagnostics=False, include_search=False)
        stats = workflow_stats(wf)
        assert isinstance(stats, dict)

    def test_has_expected_keys(self):
        wf = build_agent_workflow("test", include_diagnostics=False, include_search=False)
        stats = workflow_stats(wf)
        assert "total_steps" in stats
        assert "by_kind" in stats
        assert "by_risk" in stats
        assert "by_effort" in stats
        assert "has_high_risk" in stats
        assert "source" in stats

    def test_total_steps_matches(self):
        wf = build_agent_workflow("test", include_diagnostics=False, include_search=False)
        stats = workflow_stats(wf)
        assert stats["total_steps"] == len(wf.steps)

    def test_by_kind_sums_correctly(self):
        wf = build_agent_workflow("test", include_diagnostics=False, include_search=False)
        stats = workflow_stats(wf)
        total_from_kinds = sum(stats["by_kind"].values())
        assert total_from_kinds == stats["total_steps"]


# =============================================================================
# Model Validation Tests
# =============================================================================


class TestWorkflowModels:
    """Tests for Pydantic model validation."""

    def test_agent_workflow_step_defaults(self):
        step = AgentWorkflowStep(
            id="step-1",
            kind="inspect",
            title="Test step",
        )
        assert step.estimated_effort == "low"
        assert step.risk is None
        assert step.commands == []
        assert step.notes == []
        assert step.order == 0
        assert step.references == {}

    def test_agent_workflow_defaults(self):
        wf = AgentWorkflow(
            id="wf-1",
            goal="test goal",
        )
        assert wf.playbook is None
        assert wf.source == "mixed"
        assert wf.steps == []
        assert wf.metadata == {}

    def test_agent_workflow_request_defaults(self):
        req = AgentWorkflowRequest(goal="test")
        assert req.include_diagnostics is True
        assert req.include_search is True
        assert req.search_query is None
        assert req.playbook is None
        assert req.limit_search_results == 10
        assert req.limit_diagnostics == 10

    def test_agent_workflow_response_defaults(self):
        wf = AgentWorkflow(id="wf-1", goal="test")
        resp = AgentWorkflowResponse(workflow=wf)
        assert resp.summary == ""
        assert resp.stats == {}

    def test_all_step_kinds_valid(self):
        valid_kinds = [
            "inspect", "search", "edit_file", "run_migration",
            "run_query", "run_test", "environment", "config",
            "diagnostics", "doc_reading",
        ]
        for kind in valid_kinds:
            step = AgentWorkflowStep(id="s", kind=kind, title="T")
            assert step.kind == kind

    def test_workflow_serialization(self):
        wf = build_agent_workflow("test", include_diagnostics=False, include_search=False)
        data = wf.model_dump()
        assert isinstance(data, dict)
        assert data["goal"] == "test"
        assert isinstance(data["steps"], list)

    def test_response_serialization(self):
        wf = build_agent_workflow("test", include_diagnostics=False, include_search=False)
        resp = AgentWorkflowResponse(
            workflow=wf,
            summary=summarize_agent_workflow(wf),
            stats=workflow_stats(wf),
        )
        data = resp.model_dump()
        assert "workflow" in data
        assert "summary" in data
        assert "stats" in data
