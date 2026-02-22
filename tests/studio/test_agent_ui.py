"""
Tests for Agent Mode — Studio UI.

v0.5.19: Tests for Agent panel HTML, CSS, and JS integration in Studio UI.
"""

import pytest
from pathlib import Path


STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "aksara" / "studio" / "static"


class TestAgentHtml:
    """Tests for Agent panel HTML template."""

    def test_agent_nav_item_exists(self):
        html = (STATIC_DIR / "index.html").read_text()
        # v0.5.25: Agent is consolidated into AI Hub
        assert 'data-section="ai-hub"' in html
        assert "Agent" in html

    def test_agent_template_exists(self):
        html = (STATIC_DIR / "index.html").read_text()
        # v0.5.25: Agent content is inside the AI Hub template
        assert 'id="template-ai-hub"' in html

    def test_agent_section_container(self):
        html = (STATIC_DIR / "index.html").read_text()
        # v0.5.25: Agent panel is inside AI Hub
        assert 'id="ai-hub-agent-panel"' in html

    def test_agent_goal_textarea(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="agent-goal"' in html

    def test_agent_generate_button(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="agent-generate-btn"' in html

    def test_agent_prompt_output(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="agent-prompt-output"' in html

    def test_agent_context_json_output(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="agent-json-output"' in html

    def test_agent_section_list(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="agent-section-list"' in html

    def test_agent_toggle_all_button(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'id="agent-toggle-all"' in html

    def test_agent_tabs(self):
        html = (STATIC_DIR / "index.html").read_text()
        assert 'data-agent-tab="prompt"' in html
        assert 'data-agent-tab="context"' in html


class TestAgentJs:
    """Tests for Agent panel JavaScript."""

    def test_state_agent_object(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "agent:" in js
        assert "selectedSections" in js

    def test_render_agent_panel_function(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "function renderAgentPanel" in js

    def test_load_agent_context_function(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "function loadAgentContext" in js

    def test_generate_agent_prompt_function(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "function generateAgentPrompt" in js

    def test_keyboard_shortcut_digit8(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "'Digit8': 'ai-hub'" in js

    def test_keyboard_shortcut_ctrl_g(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "e.key === 'g'" in js

    def test_section_switch_agent(self):
        js = (STATIC_DIR / "app.js").read_text()
        # v0.5.25: Agent is now loaded via AI Hub tab
        assert "case 'ai-hub':" in js
        assert "renderAgentPanel()" in js

    def test_local_storage_persistence(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "aksara_agent_sections" in js
        assert "localStorage" in js

    def test_json_post_helper(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "function jsonPost" in js

    def test_agent_endpoint_urls(self):
        js = (STATIC_DIR / "app.js").read_text()
        assert "/studio/agent/context" in js
        assert "/studio/agent/prompt" in js


class TestAgentCss:
    """Tests for Agent panel CSS styles."""

    def test_agent_layout(self):
        css = (STATIC_DIR / "styles.css").read_text()
        assert ".agent-layout" in css

    def test_agent_section_list(self):
        css = (STATIC_DIR / "styles.css").read_text()
        assert ".agent-section-list" in css

    def test_agent_section_item(self):
        css = (STATIC_DIR / "styles.css").read_text()
        assert ".agent-section-item" in css

    def test_agent_tabs_styles(self):
        css = (STATIC_DIR / "styles.css").read_text()
        assert ".agent-tab" in css
        assert ".agent-tab.active" in css
        assert ".agent-tab-pane" in css

    def test_agent_prompt_output_style(self):
        css = (STATIC_DIR / "styles.css").read_text()
        assert ".agent-prompt-output" in css

    def test_agent_json_output_style(self):
        css = (STATIC_DIR / "styles.css").read_text()
        assert ".agent-json-output" in css

    def test_agent_prompt_meta(self):
        css = (STATIC_DIR / "styles.css").read_text()
        assert ".agent-prompt-meta" in css

    def test_agent_goal_input(self):
        css = (STATIC_DIR / "styles.css").read_text()
        assert ".agent-goal-input" in css

    def test_responsive_layout(self):
        css = (STATIC_DIR / "styles.css").read_text()
        assert "@media" in css
        # The agent layout should have a responsive breakpoint
        assert "900px" in css


class TestAgentEndpoints:
    """Tests for Agent FastAPI endpoints."""

    def test_agent_context_endpoint_exists(self):
        from aksara.studio.fastapi import router
        paths = [r.path for r in router.routes]
        assert "/studio/agent/context" in paths

    def test_agent_prompt_endpoint_exists(self):
        from aksara.studio.fastapi import router
        paths = [r.path for r in router.routes]
        assert "/studio/agent/prompt" in paths

    def test_agent_context_method_is_get(self):
        from aksara.studio.fastapi import router
        for route in router.routes:
            if getattr(route, 'path', None) == "/studio/agent/context":
                assert "GET" in route.methods
                break

    def test_agent_prompt_method_is_post(self):
        from aksara.studio.fastapi import router
        for route in router.routes:
            if getattr(route, 'path', None) == "/studio/agent/prompt":
                assert "POST" in route.methods
                break
