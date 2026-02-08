"""
Tests for Agent Playbooks — Studio Endpoints.

v0.5.20: Tests for GET /studio/agent/playbooks and
POST /studio/agent/playbooks/prompt endpoints.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch, AsyncMock

from aksara.studio.models import (
    AgentContextSection,
    AgentPlaybookSet,
    StudioAgentContext,
    StudioAgentPromptResponse,
    StudioAgentPlaybookPromptRequest,
)


# =============================================================================
# Fixtures
# =============================================================================


def _make_mock_context() -> StudioAgentContext:
    """Build a minimal agent context for test use."""
    return StudioAgentContext(
        total_sections=3,
        total_size_kb=1.5,
        sections=[
            AgentContextSection(
                title="Models", description="All models", key="models",
                data=[{"name": "User"}], size_kb=0.5,
            ),
            AgentContextSection(
                title="Routes", description="All routes", key="routes",
                data=[{"path": "/api/users"}], size_kb=0.5,
            ),
            AgentContextSection(
                title="Migrations", description="Migrations", key="migrations",
                data={"apps": []}, size_kb=0.5,
            ),
        ],
    )


# =============================================================================
# build_agent_prompt_from_playbook Tests
# =============================================================================


class TestBuildAgentPromptFromPlaybook:
    """Tests for the playbook-driven prompt builder."""

    def test_basic_playbook_prompt(self):
        from aksara.ai.playbooks import get_playbook_by_key
        from aksara.studio.utils import build_agent_prompt_from_playbook

        pb = get_playbook_by_key("add_field_to_model")
        assert pb is not None
        ctx = _make_mock_context()
        result = build_agent_prompt_from_playbook(
            playbook=pb,
            user_goal="Add an email field to User",
            selected_sections=["models"],
            custom_system_prompt=None,
            context=ctx,
        )
        assert isinstance(result, StudioAgentPromptResponse)
        assert "Playbook: Add Field to Model" in result.system_prompt
        assert "Add an email field to User" in result.system_prompt
        assert result.tokens_estimate > 0

    def test_uses_default_goal_template(self):
        from aksara.ai.playbooks import get_playbook_by_key
        from aksara.studio.utils import build_agent_prompt_from_playbook

        pb = get_playbook_by_key("debug_slow_queries")
        assert pb is not None
        ctx = _make_mock_context()
        result = build_agent_prompt_from_playbook(
            playbook=pb,
            user_goal=None,
            selected_sections=None,
            custom_system_prompt=None,
            context=ctx,
        )
        # Should use the default goal template
        assert pb.default_goal_template in result.system_prompt

    def test_uses_default_sections(self):
        from aksara.ai.playbooks import get_playbook_by_key
        from aksara.studio.utils import build_agent_prompt_from_playbook

        pb = get_playbook_by_key("add_field_to_model")
        assert pb is not None
        ctx = _make_mock_context()
        result = build_agent_prompt_from_playbook(
            playbook=pb,
            user_goal="Test",
            selected_sections=None,  # Use defaults
            custom_system_prompt=None,
            context=ctx,
        )
        # Should use playbook's default_sections — "models" is one
        assert "Models" in result.system_prompt

    def test_override_sections(self):
        from aksara.ai.playbooks import get_playbook_by_key
        from aksara.studio.utils import build_agent_prompt_from_playbook

        pb = get_playbook_by_key("add_field_to_model")
        assert pb is not None
        ctx = _make_mock_context()
        result = build_agent_prompt_from_playbook(
            playbook=pb,
            user_goal="Test",
            selected_sections=["routes"],  # Override
            custom_system_prompt=None,
            context=ctx,
        )
        assert "Routes" in result.system_prompt

    def test_custom_system_prompt_prefix(self):
        from aksara.ai.playbooks import get_playbook_by_key
        from aksara.studio.utils import build_agent_prompt_from_playbook

        pb = get_playbook_by_key("add_field_to_model")
        assert pb is not None
        ctx = _make_mock_context()
        result = build_agent_prompt_from_playbook(
            playbook=pb,
            user_goal="Test",
            selected_sections=["models"],
            custom_system_prompt="CUSTOM PREFIX HERE",
            context=ctx,
        )
        assert "CUSTOM PREFIX HERE" in result.system_prompt
        # Custom should come before playbook header
        idx_custom = result.system_prompt.index("CUSTOM PREFIX HERE")
        idx_playbook = result.system_prompt.index("Playbook:")
        assert idx_custom < idx_playbook

    def test_playbook_header_includes_steps(self):
        from aksara.ai.playbooks import get_playbook_by_key
        from aksara.studio.utils import build_agent_prompt_from_playbook

        pb = get_playbook_by_key("add_field_to_model")
        assert pb is not None
        ctx = _make_mock_context()
        result = build_agent_prompt_from_playbook(
            playbook=pb,
            user_goal="Test",
            selected_sections=["models"],
            custom_system_prompt=None,
            context=ctx,
        )
        for step in pb.steps:
            assert step.title in result.system_prompt

    def test_playbook_header_includes_risk_and_usage(self):
        from aksara.ai.playbooks import get_playbook_by_key
        from aksara.studio.utils import build_agent_prompt_from_playbook

        pb = get_playbook_by_key("fix_migration_conflicts")
        assert pb is not None
        ctx = _make_mock_context()
        result = build_agent_prompt_from_playbook(
            playbook=pb,
            user_goal="Fix conflicts",
            selected_sections=["migrations"],
            custom_system_prompt=None,
            context=ctx,
        )
        assert "Risk: high" in result.system_prompt
        assert "Usage: admin" in result.system_prompt

    def test_empty_goal_string(self):
        from aksara.ai.playbooks import get_playbook_by_key
        from aksara.studio.utils import build_agent_prompt_from_playbook

        pb = get_playbook_by_key("add_validation_rule")
        assert pb is not None
        ctx = _make_mock_context()
        result = build_agent_prompt_from_playbook(
            playbook=pb,
            user_goal="   ",  # whitespace only
            selected_sections=None,
            custom_system_prompt=None,
            context=ctx,
        )
        # Should fall back to default_goal_template
        assert pb.default_goal_template in result.system_prompt

    def test_playbook_notes_included(self):
        from aksara.ai.playbooks import get_playbook_by_key
        from aksara.studio.utils import build_agent_prompt_from_playbook

        pb = get_playbook_by_key("add_field_to_model")
        assert pb is not None
        assert pb.notes is not None
        ctx = _make_mock_context()
        result = build_agent_prompt_from_playbook(
            playbook=pb,
            user_goal="Test",
            selected_sections=["models"],
            custom_system_prompt=None,
            context=ctx,
        )
        assert pb.notes in result.system_prompt

    def test_returns_recommended_model_and_temp(self):
        from aksara.ai.playbooks import get_playbook_by_key
        from aksara.studio.utils import build_agent_prompt_from_playbook

        pb = get_playbook_by_key("debug_slow_queries")
        assert pb is not None
        ctx = _make_mock_context()
        result = build_agent_prompt_from_playbook(
            playbook=pb,
            user_goal="Debug slow queries in user API",
            selected_sections=None,
            custom_system_prompt=None,
            context=ctx,
        )
        assert result.recommended_model  # non-empty string
        assert isinstance(result.recommended_temperature, float)


# =============================================================================
# Endpoint Tests (without running full app)
# =============================================================================


class TestPlaybookEndpointLogic:
    """Test the endpoint handler logic without HTTP transport."""

    def test_get_playbooks_returns_all(self):
        from aksara.ai.playbooks import get_builtin_playbooks

        result = get_builtin_playbooks()
        assert result.total_count >= 7
        assert len(result.playbooks) == result.total_count

    def test_get_playbooks_filter_by_category(self):
        from aksara.ai.playbooks import get_builtin_playbooks

        result = get_builtin_playbooks(category="api")
        assert result.total_count >= 1
        for pb in result.playbooks:
            assert pb.category == "api"

    def test_get_playbooks_filter_by_risk(self):
        from aksara.ai.playbooks import get_builtin_playbooks

        result = get_builtin_playbooks(risk_level="medium")
        assert result.total_count >= 1
        for pb in result.playbooks:
            assert pb.risk_level == "medium"

    def test_playbook_prompt_missing_key(self):
        """Verify behavior when key doesn't exist."""
        from aksara.ai.playbooks import get_playbook_by_key

        pb = get_playbook_by_key("nonexistent_key")
        assert pb is None

    def test_playbook_prompt_happy_path(self):
        from aksara.ai.playbooks import get_playbook_by_key
        from aksara.studio.utils import build_agent_prompt_from_playbook

        pb = get_playbook_by_key("add_api_action_to_viewset")
        assert pb is not None
        ctx = _make_mock_context()
        result = build_agent_prompt_from_playbook(
            playbook=pb,
            user_goal="Add a bulk_delete action to UserViewSet",
            selected_sections=None,
            custom_system_prompt=None,
            context=ctx,
        )
        assert "Playbook: Add API Action" in result.system_prompt
        assert "bulk_delete" in result.system_prompt


# =============================================================================
# Studio UI Tests (HTML/JS structure checks)
# =============================================================================


class TestStudioPlaybookUI:
    """Tests for Studio UI playbook markup and scripts."""

    def test_html_has_playbook_template(self):
        from pathlib import Path
        html = (Path(__file__).resolve().parent.parent.parent
                / "aksara" / "studio" / "static" / "index.html").read_text()
        assert "agent-playbook-list" in html
        assert "agent-playbook-search" in html
        assert "agent-playbook-filters" in html
        assert "agent-playbook-count" in html

    def test_js_has_playbook_functions(self):
        from pathlib import Path
        js = (Path(__file__).resolve().parent.parent.parent
              / "aksara" / "studio" / "static" / "app.js").read_text()
        assert "loadAgentPlaybooks" in js
        assert "renderAgentPlaybooks" in js
        assert "selectPlaybook" in js
        assert "filterPlaybooks" in js
        assert "renderPlaybookSteps" in js
        assert "initPlaybookFilters" in js
        assert "initPlaybookSearch" in js

    def test_css_has_playbook_styles(self):
        from pathlib import Path
        css = (Path(__file__).resolve().parent.parent.parent
               / "aksara" / "studio" / "static" / "styles.css").read_text()
        assert ".agent-playbook-card" in css
        assert ".agent-playbook-card--selected" in css
        assert ".agent-playbook-badge" in css
        assert ".agent-playbook-search" in css
        assert ".agent-playbook-list" in css
        assert ".agent-filter-pill" in css

    def test_js_has_shift_p_shortcut(self):
        from pathlib import Path
        js = (Path(__file__).resolve().parent.parent.parent
              / "aksara" / "studio" / "static" / "app.js").read_text()
        assert "Shift+P" in js or "e.key === 'P'" in js

    def test_js_state_has_playbook_fields(self):
        from pathlib import Path
        js = (Path(__file__).resolve().parent.parent.parent
              / "aksara" / "studio" / "static" / "app.js").read_text()
        assert "selectedPlaybook" in js
        assert "playbookFilter" in js
        assert "playbookSearch" in js

    def test_js_posts_to_playbook_prompt_endpoint(self):
        from pathlib import Path
        js = (Path(__file__).resolve().parent.parent.parent
              / "aksara" / "studio" / "static" / "app.js").read_text()
        assert "/studio/agent/playbooks/prompt" in js
