"""
Tests for Agent Mode — Prompt Generator.

v0.5.19: Tests for build_agent_prompt() and StudioAgentPromptResponse model.
"""

import pytest
from datetime import datetime, timezone

from aksara.studio.models import (
    AgentContextSection,
    StudioAgentContext,
    StudioAgentPromptRequest,
    StudioAgentPromptResponse,
)
from aksara.studio.utils import build_agent_prompt


# =============================================================================
# Model Tests
# =============================================================================


class TestStudioAgentPromptRequest:
    """Tests for StudioAgentPromptRequest model."""

    def test_minimal(self):
        r = StudioAgentPromptRequest(goal="Fix bugs")
        assert r.goal == "Fix bugs"
        assert r.selected_sections == []
        assert r.custom_system_prompt is None

    def test_with_sections(self):
        r = StudioAgentPromptRequest(
            goal="Migrate DB",
            selected_sections=["models", "migrations"],
        )
        assert r.selected_sections == ["models", "migrations"]

    def test_with_custom_prompt(self):
        r = StudioAgentPromptRequest(
            goal="Build API",
            custom_system_prompt="You are a Django expert.",
        )
        assert r.custom_system_prompt == "You are a Django expert."


class TestStudioAgentPromptResponse:
    """Tests for StudioAgentPromptResponse model."""

    def test_defaults(self):
        r = StudioAgentPromptResponse(system_prompt="Hello")
        assert r.system_prompt == "Hello"
        assert r.recommended_temperature == 0.5
        assert r.recommended_model == "gpt-4o"
        assert r.tokens_estimate == 0

    def test_custom_values(self):
        r = StudioAgentPromptResponse(
            system_prompt="Custom",
            recommended_temperature=0.3,
            recommended_model="claude-3",
            tokens_estimate=500,
        )
        assert r.recommended_temperature == 0.3
        assert r.recommended_model == "claude-3"
        assert r.tokens_estimate == 500


# =============================================================================
# Prompt Generator Tests
# =============================================================================


def _make_context(sections=None):
    """Create a test StudioAgentContext."""
    if sections is None:
        sections = [
            AgentContextSection(
                title="Project Info", description="App info", key="project_info",
                data={"app_title": "TestApp"}, size_kb=0.1,
            ),
            AgentContextSection(
                title="Models", description="DB models", key="models",
                data=[{"name": "User"}], size_kb=0.2,
            ),
            AgentContextSection(
                title="AI Hints", description="Hints", key="ai_hints",
                data={"high_risk_count": 0, "routes": []}, size_kb=0.1,
            ),
            AgentContextSection(
                title="Diagnostics", description="Health", key="diagnostics",
                data={"stats": {"errors": 0, "warnings": 1, "info": 2}}, size_kb=0.1,
            ),
        ]
    return StudioAgentContext(
        total_sections=len(sections),
        total_size_kb=sum(s.size_kb for s in sections),
        sections=sections,
    )


class TestBuildAgentPrompt:
    """Tests for build_agent_prompt()."""

    def test_returns_response(self):
        ctx = _make_context()
        req = StudioAgentPromptRequest(goal="List all users")
        resp = build_agent_prompt(req, ctx)
        assert isinstance(resp, StudioAgentPromptResponse)

    def test_goal_in_prompt(self):
        ctx = _make_context()
        req = StudioAgentPromptRequest(goal="Add a new endpoint")
        resp = build_agent_prompt(req, ctx)
        assert "Add a new endpoint" in resp.system_prompt

    def test_expert_assistant_header(self):
        ctx = _make_context()
        req = StudioAgentPromptRequest(goal="Help me")
        resp = build_agent_prompt(req, ctx)
        assert "expert assistant" in resp.system_prompt.lower()

    def test_all_sections_included_by_default(self):
        ctx = _make_context()
        req = StudioAgentPromptRequest(goal="Review code")
        resp = build_agent_prompt(req, ctx)
        for s in ctx.sections:
            assert s.title in resp.system_prompt

    def test_filter_by_selected_sections(self):
        ctx = _make_context()
        req = StudioAgentPromptRequest(
            goal="Check models",
            selected_sections=["models"],
        )
        resp = build_agent_prompt(req, ctx)
        assert "Models" in resp.system_prompt
        assert "Project Info" not in resp.system_prompt

    def test_custom_system_prompt_prepended(self):
        ctx = _make_context()
        req = StudioAgentPromptRequest(
            goal="Fix it",
            custom_system_prompt="CUSTOM PREFIX",
        )
        resp = build_agent_prompt(req, ctx)
        assert resp.system_prompt.startswith("CUSTOM PREFIX")

    def test_tokens_estimate_positive(self):
        ctx = _make_context()
        req = StudioAgentPromptRequest(goal="Do something")
        resp = build_agent_prompt(req, ctx)
        assert resp.tokens_estimate > 0

    def test_tokens_estimate_word_count(self):
        ctx = _make_context()
        req = StudioAgentPromptRequest(goal="Build REST API")
        resp = build_agent_prompt(req, ctx)
        assert resp.tokens_estimate == len(resp.system_prompt.split())

    def test_default_temperature_no_risk(self):
        ctx = _make_context()
        req = StudioAgentPromptRequest(goal="Read data")
        resp = build_agent_prompt(req, ctx)
        assert resp.recommended_temperature == 0.5

    def test_lower_temperature_high_risk_hints(self):
        sections = [
            AgentContextSection(
                title="AI Hints", description="Hints", key="ai_hints",
                data={"high_risk_count": 3, "routes": []}, size_kb=0.1,
            ),
        ]
        ctx = _make_context(sections=sections)
        req = StudioAgentPromptRequest(goal="Deploy")
        resp = build_agent_prompt(req, ctx)
        assert resp.recommended_temperature == 0.3

    def test_lower_temperature_diagnostic_errors(self):
        sections = [
            AgentContextSection(
                title="Diagnostics", description="Health", key="diagnostics",
                data={"stats": {"errors": 2, "warnings": 0, "info": 0}}, size_kb=0.1,
            ),
        ]
        ctx = _make_context(sections=sections)
        req = StudioAgentPromptRequest(goal="Fix errors")
        resp = build_agent_prompt(req, ctx)
        assert resp.recommended_temperature == 0.3

    def test_default_model_gpt4o(self):
        ctx = _make_context()
        req = StudioAgentPromptRequest(goal="Something")
        resp = build_agent_prompt(req, ctx)
        assert resp.recommended_model == "gpt-4o"

    def test_picks_model_from_ready_provider(self):
        sections = [
            AgentContextSection(
                title="AI Profiles", description="Providers", key="ai_profiles",
                data={
                    "providers": [
                        {
                            "name": "openai",
                            "client_ready": True,
                            "models": [{"name": "gpt-4-turbo"}],
                        },
                    ],
                },
                size_kb=0.2,
            ),
        ]
        ctx = _make_context(sections=sections)
        req = StudioAgentPromptRequest(goal="Query")
        resp = build_agent_prompt(req, ctx)
        assert resp.recommended_model == "gpt-4-turbo"

    def test_skips_non_ready_provider(self):
        sections = [
            AgentContextSection(
                title="AI Profiles", description="Providers", key="ai_profiles",
                data={
                    "providers": [
                        {
                            "name": "openai",
                            "client_ready": False,
                            "models": [{"name": "gpt-4-turbo"}],
                        },
                    ],
                },
                size_kb=0.2,
            ),
        ]
        ctx = _make_context(sections=sections)
        req = StudioAgentPromptRequest(goal="Query")
        resp = build_agent_prompt(req, ctx)
        assert resp.recommended_model == "gpt-4o"  # fallback

    def test_empty_context_still_works(self):
        ctx = _make_context(sections=[])
        req = StudioAgentPromptRequest(goal="Help")
        resp = build_agent_prompt(req, ctx)
        assert "Help" in resp.system_prompt
        assert resp.tokens_estimate > 0

    def test_model_dump_json_serializable(self):
        import json
        ctx = _make_context()
        req = StudioAgentPromptRequest(goal="Test")
        resp = build_agent_prompt(req, ctx)
        d = resp.model_dump()
        serialized = json.dumps(d)
        assert serialized  # no error
