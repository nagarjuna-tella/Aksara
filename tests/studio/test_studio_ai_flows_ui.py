"""
v0.5.29 — Studio AI Flows: UI wiring & endpoint tests.

Tests cover:
    - FastAPI endpoints exist and respond
    - HTML has AI flow panel + buttons in all 5 sections
    - JS has all required functions (openAiFlowPanel, showToast, etc.)
    - No alert() usage in AI flow code
    - Copy buttons present
    - Tabs: result / prompt / json
    - Provider/model fields in panel
    - showToast used for errors
    - CSS classes exist
    - Keyboard shortcuts wired
"""

from __future__ import annotations

import pytest
from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "aksara" / "studio" / "static"


@pytest.fixture(scope="module")
def js_source():
    return (STATIC_DIR / "app.js").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def html_source():
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def css_source():
    return (STATIC_DIR / "styles.css").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def router():
    from aksara.studio.fastapi import router
    return router


# ─── 1. Endpoint Existence ──────────────────────────────────────────────────

class TestAiFlowEndpoints:
    def test_get_actions_endpoint(self, router):
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/studio/ai/flows/actions" in paths

    def test_post_model_endpoint(self, router):
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/studio/ai/flows/model" in paths

    def test_post_route_endpoint(self, router):
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/studio/ai/flows/route" in paths

    def test_post_query_endpoint(self, router):
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/studio/ai/flows/query" in paths

    def test_post_migration_endpoint(self, router):
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/studio/ai/flows/migration" in paths

    def test_post_diagnostic_endpoint(self, router):
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/studio/ai/flows/diagnostic" in paths

    def test_total_flow_endpoints(self, router):
        flow_paths = [r.path for r in router.routes if hasattr(r, "path") and "/studio/ai/flows/" in r.path]
        assert len(flow_paths) == 7  # actions + 5 POST builders + 1 POST run (v0.5.30)


# ─── 2. HTML Structure ──────────────────────────────────────────────────────

class TestHtmlAiFlowPanel:
    def test_ai_flow_panel_exists(self, html_source):
        assert 'id="ai-flow-panel"' in html_source

    def test_ai_flow_panel_has_close_button(self, html_source):
        assert 'id="ai-flow-panel-close"' in html_source

    def test_ai_flow_panel_has_title(self, html_source):
        assert 'id="ai-flow-panel-title"' in html_source

    def test_ai_flow_panel_has_badge(self, html_source):
        assert 'id="ai-flow-badge"' in html_source

    def test_ai_flow_panel_has_provider(self, html_source):
        assert 'id="ai-flow-provider"' in html_source

    def test_ai_flow_panel_has_model(self, html_source):
        assert 'id="ai-flow-model"' in html_source

    def test_ai_flow_panel_has_result_tab(self, html_source):
        assert 'data-ai-flow-tab="result"' in html_source

    def test_ai_flow_panel_has_prompt_tab(self, html_source):
        assert 'data-ai-flow-tab="prompt"' in html_source

    def test_ai_flow_panel_has_json_tab(self, html_source):
        assert 'data-ai-flow-tab="json"' in html_source

    def test_ai_flow_panel_has_copy_result(self, html_source):
        assert 'id="ai-flow-copy-result"' in html_source

    def test_ai_flow_panel_has_copy_cli(self, html_source):
        assert 'id="ai-flow-copy-cli"' in html_source

    def test_ai_flow_panel_has_copy_prompts(self, html_source):
        assert 'id="ai-flow-copy-prompts"' in html_source

    def test_ai_flow_panel_has_copy_json(self, html_source):
        assert 'id="ai-flow-copy-json"' in html_source

    def test_ai_flow_panel_has_system_prompt(self, html_source):
        assert 'id="ai-flow-system-prompt"' in html_source

    def test_ai_flow_panel_has_user_prompt(self, html_source):
        assert 'id="ai-flow-user-prompt"' in html_source

    def test_ai_flow_panel_has_raw_json(self, html_source):
        assert 'id="ai-flow-raw-json"' in html_source

    def test_ai_flow_panel_has_suggested_next(self, html_source):
        assert 'id="ai-flow-suggested-next"' in html_source

    def test_ai_flow_panel_has_error_div(self, html_source):
        assert 'id="ai-flow-error"' in html_source

    def test_what_it_does_element(self, html_source):
        assert 'id="ai-flow-what-it-does"' in html_source

    def test_what_it_cannot_element(self, html_source):
        assert 'id="ai-flow-what-it-cannot"' in html_source


class TestHtmlAiButtons:
    """Ensure each section header has AI dropdown buttons."""

    def test_models_ai_dropdown(self, html_source):
        assert 'id="models-ai-dropdown"' in html_source

    def test_models_ai_btn(self, html_source):
        assert 'id="models-ai-btn"' in html_source

    def test_routes_ai_dropdown(self, html_source):
        assert 'id="routes-ai-dropdown"' in html_source

    def test_routes_ai_btn(self, html_source):
        assert 'id="routes-ai-btn"' in html_source

    def test_migrations_ai_dropdown(self, html_source):
        assert 'id="migrations-ai-dropdown"' in html_source

    def test_diagnostics_ai_dropdown(self, html_source):
        assert 'id="diagnostics-ai-dropdown"' in html_source

    def test_queries_ai_dropdown(self, html_source):
        assert 'id="queries-ai-dropdown"' in html_source

    def test_models_has_explain_model(self, html_source):
        assert 'data-action="explain_model"' in html_source

    def test_models_has_suggest_constraints(self, html_source):
        assert 'data-action="suggest_constraints"' in html_source

    def test_models_has_refactor_suggestions(self, html_source):
        assert 'data-action="refactor_suggestions"' in html_source

    def test_routes_has_review_endpoint(self, html_source):
        assert 'data-action="review_endpoint"' in html_source

    def test_routes_has_harden_permissions(self, html_source):
        assert 'data-action="harden_permissions"' in html_source

    def test_routes_has_generate_examples(self, html_source):
        assert 'data-action="generate_examples"' in html_source

    def test_queries_has_explain_plan(self, html_source):
        assert 'data-action="explain_plan"' in html_source

    def test_queries_has_suggest_indexes(self, html_source):
        assert 'data-action="suggest_indexes"' in html_source

    def test_queries_has_rewrite_suggestions(self, html_source):
        assert 'data-action="rewrite_suggestions"' in html_source

    def test_migrations_has_explain_migration(self, html_source):
        assert 'data-action="explain_migration"' in html_source

    def test_migrations_has_safe_rollout_plan(self, html_source):
        assert 'data-action="safe_rollout_plan"' in html_source

    def test_diagnostics_has_diagnostic_prioritize(self, html_source):
        assert 'data-action="diagnostic_prioritize"' in html_source

    def test_ai_buttons_initially_disabled(self, html_source):
        """All AI buttons should start disabled (hub not yet checked)."""
        import re
        ai_btns = re.findall(r'class="btn btn-sm btn-ai-flow"[^>]*disabled', html_source)
        assert len(ai_btns) >= 5

    def test_ai_buttons_have_title_tooltip(self, html_source):
        """Disabled buttons should have a tooltip describing the purpose."""
        import re
        # At least one button has a title attribute
        ai_titles = re.findall(r'btn-ai-flow"[^>]*title="([^"]+)"', html_source)
        assert len(ai_titles) >= 5


# ─── 3. JavaScript Functions ────────────────────────────────────────────────

class TestJsAiFlowFunctions:
    def test_open_ai_flow_panel_exists(self, js_source):
        assert "function openAiFlowPanel" in js_source or "async function openAiFlowPanel" in js_source

    def test_init_ai_flow_buttons_exists(self, js_source):
        assert "function initAiFlowButtons" in js_source or "async function initAiFlowButtons" in js_source

    def test_init_ai_flow_dropdowns_exists(self, js_source):
        assert "function initAiFlowDropdowns" in js_source

    def test_dispatch_ai_flow_exists(self, js_source):
        assert "_dispatchAiFlow" in js_source

    def test_build_cli_command_exists(self, js_source):
        assert "_buildCliCommand" in js_source

    def test_set_ai_flow_tab_exists(self, js_source):
        assert "_setAiFlowTab" in js_source

    def test_wire_ai_flow_copy_exists(self, js_source):
        assert "_wireAiFlowCopy" in js_source

    def test_hook_row_selection_exists(self, js_source):
        assert "_hookAiFlowRowSelection" in js_source

    def test_sync_flow_button_states_exists(self, js_source):
        assert "_syncFlowButtonStates" in js_source

    def test_close_all_ai_menus_exists(self, js_source):
        assert "_closeAllAiMenus" in js_source

    def test_keyboard_shortcuts_init(self, js_source):
        assert "_initAiFlowKeyboardShortcuts" in js_source

    def test_shift_a_shortcut(self, js_source):
        """Shift+A should navigate to AI Hub."""
        assert "e.key === 'A'" in js_source or "key === 'A'" in js_source

    def test_escape_closes_panel(self, js_source):
        assert "'Escape'" in js_source

    def test_no_alert_in_flows(self, js_source):
        """AI flow code must use showToast, not alert()."""
        # Check that the AI flows section doesn't use alert()
        flow_section = js_source[js_source.index("v0.5.29: Studio AI Flows"):]
        assert "alert(" not in flow_section

    def test_show_toast_used_for_errors(self, js_source):
        """showToast should be used for error display in flows."""
        flow_section = js_source[js_source.index("v0.5.29: Studio AI Flows"):]
        assert "showToast(" in flow_section

    def test_clipboard_copy_support(self, js_source):
        """Clipboard API should be used for copy buttons."""
        assert "navigator.clipboard.writeText" in js_source

    def test_json_post_used_for_flows(self, js_source):
        """jsonPost should be used to call flow endpoints."""
        assert "jsonPost(`/studio/ai/flows/" in js_source or "jsonPost('/studio/ai/flows/" in js_source

    def test_render_section_hooks_flows(self, js_source):
        """renderSection should call initAiFlowDropdowns."""
        assert "initAiFlowDropdowns()" in js_source

    def test_domcontentloaded_inits_flows(self, js_source):
        """DOMContentLoaded should init flow panel controls."""
        assert "_initAiFlowPanelControls()" in js_source
        assert "initAiFlowButtons()" in js_source


# ─── 4. CSS Classes ─────────────────────────────────────────────────────────

class TestCssAiFlowStyles:
    def test_ai_flow_panel_class(self, css_source):
        assert ".ai-flow-panel" in css_source

    def test_ai_flow_badge_class(self, css_source):
        assert ".ai-flow-badge" in css_source

    def test_ai_flow_badge_medium(self, css_source):
        assert ".ai-flow-badge-medium" in css_source

    def test_ai_flow_badge_high(self, css_source):
        assert ".ai-flow-badge-high" in css_source

    def test_ai_flow_tabs_class(self, css_source):
        assert ".ai-flow-tabs" in css_source

    def test_ai_flow_tab_class(self, css_source):
        assert ".ai-flow-tab" in css_source

    def test_ai_flow_copy_btn_class(self, css_source):
        assert ".ai-flow-copy-btn" in css_source

    def test_btn_ai_flow_class(self, css_source):
        assert ".btn-ai-flow" in css_source

    def test_ai_flow_dropdown_menu(self, css_source):
        assert ".ai-flow-dropdown-menu" in css_source

    def test_ai_flow_dropdown_item(self, css_source):
        assert ".ai-flow-dropdown-item" in css_source

    def test_ai_flow_prompt_box(self, css_source):
        assert ".ai-flow-prompt-box" in css_source

    def test_ai_flow_error_class(self, css_source):
        assert ".ai-flow-error" in css_source

    def test_ai_flow_meta_tag(self, css_source):
        assert ".ai-flow-meta-tag" in css_source

    def test_ai_flow_result_class(self, css_source):
        assert ".ai-flow-result" in css_source

    def test_ai_flow_suggested_next(self, css_source):
        assert ".ai-flow-suggested-next" in css_source


# ─── 5. Pydantic Model Import Checks ────────────────────────────────────────

class TestModelImports:
    def test_request_models_importable(self):
        from aksara.studio.models import (
            StudioAiFlowModelRequest,
            StudioAiFlowRouteRequest,
            StudioAiFlowQueryRequest,
            StudioAiFlowMigrationRequest,
            StudioAiFlowDiagnosticRequest,
        )
        assert StudioAiFlowModelRequest is not None

    def test_response_model_importable(self):
        from aksara.studio.models import StudioAiFlowResponse
        assert StudioAiFlowResponse is not None

    def test_actions_response_importable(self):
        from aksara.studio.models import StudioAiFlowActionsResponse
        assert StudioAiFlowActionsResponse is not None

    def test_action_descriptor_importable(self):
        from aksara.studio.models import StudioAiFlowActionDescriptor
        assert StudioAiFlowActionDescriptor is not None

    def test_flow_request_has_action_key(self):
        from aksara.studio.models import StudioAiFlowRequest
        f = StudioAiFlowRequest(action_key="test")
        assert f.action_key == "test"

    def test_model_request_has_model_name(self):
        from aksara.studio.models import StudioAiFlowModelRequest
        f = StudioAiFlowModelRequest(action_key="test", model_name="User")
        assert f.model_name == "User"

    def test_route_request_has_path(self):
        from aksara.studio.models import StudioAiFlowRouteRequest
        f = StudioAiFlowRouteRequest(action_key="test", path="/api")
        assert f.path == "/api"

    def test_query_request_has_sql(self):
        from aksara.studio.models import StudioAiFlowQueryRequest
        f = StudioAiFlowQueryRequest(action_key="test", sql="SELECT 1")
        assert f.sql == "SELECT 1"
