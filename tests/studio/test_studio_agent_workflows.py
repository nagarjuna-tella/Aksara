"""
Tests for Agentic Workflows — Studio Endpoints.

v0.5.23: Tests for POST /studio/agent/workflow and
GET /studio/agent/workflow/sample.
"""

import pytest
import json
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
)


# =============================================================================
# POST /studio/agent/workflow
# =============================================================================


class TestPostAgentWorkflow:
    """Tests for the workflow generation endpoint."""

    def test_build_workflow_for_endpoint(self):
        """Simulate what the endpoint does: build + summarize + stats."""
        body = AgentWorkflowRequest(
            goal="Fix slow queries on /api/posts/",
            include_diagnostics=False,
            include_search=False,
        )
        wf = build_agent_workflow(
            goal=body.goal,
            playbook=body.playbook,
            include_diagnostics=body.include_diagnostics,
            include_search=body.include_search,
            search_query=body.search_query,
            search_limit=body.limit_search_results,
            diagnostics_limit=body.limit_diagnostics,
        )
        response = AgentWorkflowResponse(
            workflow=wf,
            summary=summarize_agent_workflow(wf),
            stats=workflow_stats(wf),
        )
        assert response.workflow.goal == "Fix slow queries on /api/posts/"
        assert len(response.workflow.steps) > 0
        assert len(response.summary) > 0
        assert response.stats["total_steps"] > 0

    def test_request_with_playbook(self):
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
        body = AgentWorkflowRequest(
            goal="Add email to User",
            playbook="add_field_to_model",
            include_diagnostics=False,
            include_search=False,
        )
        with patch("aksara.ai.workflows._get_playbook", return_value=mock_pb):
            wf = build_agent_workflow(
                goal=body.goal,
                playbook=body.playbook,
                include_diagnostics=body.include_diagnostics,
                include_search=body.include_search,
            )
            assert wf.playbook == "add_field_to_model"
            assert len(wf.steps) > 2

    def test_request_with_search(self):
        body = AgentWorkflowRequest(
            goal="Fix slow queries",
            include_diagnostics=False,
            include_search=True,
            limit_search_results=3,
        )
        wf = build_agent_workflow(
            goal=body.goal,
            include_diagnostics=body.include_diagnostics,
            include_search=body.include_search,
            search_limit=body.limit_search_results,
        )
        search_steps = [s for s in wf.steps if s.kind == "search"]
        assert len(search_steps) >= 1

    def test_response_fields_present(self):
        wf = build_agent_workflow(
            "test endpoint",
            include_diagnostics=False,
            include_search=False,
        )
        response = AgentWorkflowResponse(
            workflow=wf,
            summary=summarize_agent_workflow(wf),
            stats=workflow_stats(wf),
        )
        data = response.model_dump()
        assert "workflow" in data
        assert "summary" in data
        assert "stats" in data
        assert "steps" in data["workflow"]
        assert data["workflow"]["goal"] == "test endpoint"

    def test_response_json_serializable(self):
        wf = build_agent_workflow(
            "test json",
            include_diagnostics=False,
            include_search=False,
        )
        response = AgentWorkflowResponse(
            workflow=wf,
            summary=summarize_agent_workflow(wf),
            stats=workflow_stats(wf),
        )
        serialized = json.dumps(response.model_dump(), default=str)
        parsed = json.loads(serialized)
        assert parsed["workflow"]["goal"] == "test json"


# =============================================================================
# GET /studio/agent/workflow/sample
# =============================================================================


class TestGetAgentWorkflowSample:
    """Tests for the sample workflow endpoint."""

    def test_sample_workflow_structure(self):
        """Simulate what the sample endpoint does."""
        wf = build_agent_workflow(
            goal="Fix slow queries on /api/posts/",
            include_diagnostics=False,
            include_search=True,
            search_limit=5,
        )
        assert isinstance(wf, AgentWorkflow)
        assert wf.goal == "Fix slow queries on /api/posts/"
        assert len(wf.steps) > 0

    def test_sample_steps_have_valid_kinds(self):
        wf = build_agent_workflow(
            goal="Fix slow queries on /api/posts/",
            include_diagnostics=False,
            include_search=True,
            search_limit=5,
        )
        valid_kinds = {
            "inspect", "search", "edit_file", "run_migration",
            "run_query", "run_test", "environment", "config",
            "diagnostics", "doc_reading",
        }
        for step in wf.steps:
            assert step.kind in valid_kinds

    def test_sample_has_test_step(self):
        wf = build_agent_workflow(
            goal="Fix slow queries on /api/posts/",
            include_diagnostics=False,
            include_search=True,
            search_limit=5,
        )
        assert any(s.kind == "run_test" for s in wf.steps)

    def test_sample_serializable(self):
        wf = build_agent_workflow(
            goal="Fix slow queries on /api/posts/",
            include_diagnostics=False,
            include_search=True,
            search_limit=5,
        )
        data = wf.model_dump()
        serialized = json.dumps(data, default=str)
        assert len(serialized) > 0
