"""
v0.5.38 — AI UX Consolidation (Studio): comprehensive tests.

Tests cover:
    - Version bump to 0.5.38
    - Sidebar navigation restructured (Home, Console, Inspector, Graph, Hub)
    - AI Home template and rendering
    - AI Inspector template with tabs
    - Console plan preview HTML structure
    - Graph summary card HTML structure
    - AI Hub quick action buttons
    - Navigation redirects (debugger → inspector, architecture → inspector, performance → inspector)
    - Keyboard shortcut update (A → ai-home)
    - New endpoints: GET /studio/ai/home, GET /studio/ai/inspector
    - CSS styles for new components
    - JS render functions
"""

from __future__ import annotations

import pytest
from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "aksara" / "studio" / "static"


def _read_static(name: str) -> str:
    return (STATIC_DIR / name).read_text(encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════
# Version tests
# ═══════════════════════════════════════════════════════════════════════════


class TestVersion:
    def test_version_string(self):
        from aksara._version import __version__
        assert __version__ == "0.5.49"

    def test_pyproject_version(self):
        toml = (STATIC_DIR.parent.parent.parent / "pyproject.toml").read_text()
        assert 'version = "0.5.49"' in toml

    def test_cli_version(self):
        cli = (STATIC_DIR.parent.parent / "cli" / "main.py").read_text()
        assert 'CLI_VERSION = "0.5.49"' in cli


# ═══════════════════════════════════════════════════════════════════════════
# Sidebar Navigation tests
# ═══════════════════════════════════════════════════════════════════════════


class TestSidebarNavigation:
    def test_ai_home_nav_removed(self):
        # v0.5.42: ai-home removed from nav; redirect exists in app.js
        html = _read_static("index.html")
        assert 'data-section="ai-home"' not in html
        js = _read_static("app.js")
        assert "'ai-home': 'ai-console'" in js

    def test_ai_console_nav_exists(self):
        html = _read_static("index.html")
        assert 'data-section="ai-console"' in html

    def test_ai_inspector_nav_exists(self):
        html = _read_static("index.html")
        assert 'data-section="ai-inspector"' in html

    def test_ai_graph_nav_exists(self):
        html = _read_static("index.html")
        assert 'data-section="ai-graph"' in html

    def test_ai_hub_nav_exists(self):
        html = _read_static("index.html")
        assert 'data-section="ai-hub"' in html

    def test_nav_order(self):
        # v0.5.42: ai-home removed; new order is console < inspector < graph < hub
        html = _read_static("index.html")
        console_pos = html.find('data-section="ai-console"')
        inspector_pos = html.find('data-section="ai-inspector"')
        graph_pos = html.find('data-section="ai-graph"')
        hub_pos = html.find('data-section="ai-hub"')
        assert console_pos < inspector_pos < graph_pos < hub_pos

    def test_ai_console_nav_label(self):
        # v0.5.42: ai-home removed; verify ai-console has its label
        html = _read_static("index.html")
        idx = html.find('data-section="ai-console"')
        snippet = html[idx:idx + 500]
        assert "AI Console" in snippet or "Console" in snippet

    def test_inspector_nav_label(self):
        html = _read_static("index.html")
        idx = html.find('data-section="ai-inspector"')
        snippet = html[idx:idx + 500]
        assert "Inspector" in snippet


# ═══════════════════════════════════════════════════════════════════════════
# AI Home template tests
# ═══════════════════════════════════════════════════════════════════════════


class TestAiHomeTemplate:
    def test_template_id(self):
        html = _read_static("index.html")
        assert 'id="template-ai-home"' in html

    def test_status_pill(self):
        html = _read_static("index.html")
        assert 'id="ai-home-status"' in html

    def test_provider_meta(self):
        html = _read_static("index.html")
        assert 'id="ai-home-provider-meta"' in html

    def test_prompt_input(self):
        html = _read_static("index.html")
        assert 'id="ai-home-prompt"' in html

    def test_prompt_go_button(self):
        html = _read_static("index.html")
        assert 'id="ai-home-go"' in html

    def test_suggestion_chips(self):
        html = _read_static("index.html")
        assert 'id="ai-home-suggestions"' in html

    def test_quick_action_cards(self):
        html = _read_static("index.html")
        assert "ai-home-action-card" in html

    def test_snapshot_grid(self):
        html = _read_static("index.html")
        assert 'id="ai-home-snapshot"' in html

    def test_scores_section(self):
        html = _read_static("index.html")
        assert 'id="ai-home-scores"' in html

    def test_observations_list(self):
        html = _read_static("index.html")
        assert 'id="ai-home-observations"' in html

    def test_setup_card(self):
        html = _read_static("index.html")
        assert 'id="ai-home-setup"' in html


# ═══════════════════════════════════════════════════════════════════════════
# AI Inspector template tests
# ═══════════════════════════════════════════════════════════════════════════


class TestAiInspectorTemplate:
    def test_template_id(self):
        html = _read_static("index.html")
        assert 'id="template-ai-inspector"' in html

    def test_overview_tab(self):
        html = _read_static("index.html")
        assert 'data-inspector-tab="overview"' in html

    def test_debug_tab(self):
        html = _read_static("index.html")
        assert 'data-inspector-tab="debug"' in html

    def test_architecture_tab(self):
        html = _read_static("index.html")
        assert 'data-inspector-tab="architecture"' in html

    def test_performance_tab(self):
        html = _read_static("index.html")
        assert 'data-inspector-tab="performance"' in html

    def test_inspector_panel(self):
        html = _read_static("index.html")
        assert 'id="ai-inspector-panel"' in html


# ═══════════════════════════════════════════════════════════════════════════
# Console Plan Preview tests
# ═══════════════════════════════════════════════════════════════════════════


class TestConsolePlanPreview:
    def test_plan_preview_container(self):
        html = _read_static("index.html")
        assert 'id="ai-console-plan-preview"' in html

    def test_plan_steps_exist(self):
        html = _read_static("index.html")
        assert "ai-console-plan-step" in html

    def test_plan_progress_indicator(self):
        html = _read_static("index.html")
        assert "ai-console-plan-indicator" in html

    def test_plan_step_labels(self):
        html = _read_static("index.html")
        assert "Build project graph" in html
        assert "Run architecture analysis" in html
        assert "Run performance analysis" in html
        assert "Execute debugger" in html


# ═══════════════════════════════════════════════════════════════════════════
# Graph Summary Card tests
# ═══════════════════════════════════════════════════════════════════════════


class TestGraphSummaryCard:
    def test_summary_card_exists(self):
        html = _read_static("index.html")
        assert 'id="ai-graph-summary-card"' in html

    def test_summary_grid(self):
        html = _read_static("index.html")
        assert 'id="ai-graph-summary-grid"' in html


# ═══════════════════════════════════════════════════════════════════════════
# AI Hub Quick Actions tests
# ═══════════════════════════════════════════════════════════════════════════


class TestAiHubQuickActions:
    def test_test_provider_button(self):
        html = _read_static("index.html")
        assert 'id="ai-hub-qa-test"' in html

    def test_open_console_button(self):
        html = _read_static("index.html")
        assert 'id="ai-hub-qa-console"' in html

    def test_investigate_button(self):
        html = _read_static("index.html")
        assert 'id="ai-hub-qa-investigate"' in html

    def test_quick_actions_class(self):
        html = _read_static("index.html")
        assert "ai-hub-quick-actions" in html


# ═══════════════════════════════════════════════════════════════════════════
# JavaScript — Render functions & navigation
# ═══════════════════════════════════════════════════════════════════════════


class TestJavaScript:
    def test_render_ai_home_function(self):
        js = _read_static("app.js")
        assert "renderAiHome" in js

    def test_render_ai_inspector_function(self):
        js = _read_static("app.js")
        assert "renderAiInspector" in js

    def test_render_inspector_tab_function(self):
        js = _read_static("app.js")
        assert "_renderInspectorTab" in js

    def test_render_section_ai_home(self):
        js = _read_static("app.js")
        assert "case 'ai-home'" in js

    def test_render_section_ai_inspector(self):
        js = _read_static("app.js")
        assert "case 'ai-inspector'" in js

    def test_ai_home_fetch_endpoint(self):
        js = _read_static("app.js")
        assert "/studio/ai/home" in js

    def test_ai_inspector_fetch_endpoint(self):
        js = _read_static("app.js")
        assert "/studio/ai/inspector" in js

    def test_redirect_ai_debugger_to_inspector(self):
        js = _read_static("app.js")
        assert "'ai-debugger'" in js
        assert "'ai-inspector'" in js

    def test_redirect_ai_architecture_to_inspector(self):
        js = _read_static("app.js")
        assert "'ai-architecture'" in js

    def test_redirect_ai_performance_to_inspector(self):
        js = _read_static("app.js")
        assert "'ai-performance'" in js

    def test_keyboard_shortcut_ai_console(self):
        # v0.5.42: 'A' key now navigates to ai-console
        js = _read_static("app.js")
        assert "navigateTo('ai-console')" in js

    def test_prefill_prompt_variable(self):
        js = _read_static("app.js")
        assert "_aiHomePrefillPrompt" in js

    def test_graph_summary_card_render(self):
        js = _read_static("app.js")
        assert "_renderAiGraphSummaryCard" in js

    def test_console_plan_preview_logic(self):
        js = _read_static("app.js")
        assert "ai-console-plan-preview" in js

    def test_investigation_pattern_regex(self):
        js = _read_static("app.js")
        assert "investigate|analyze|architecture|performance|debug|review|diagnose" in js

    def test_hub_quick_action_wiring(self):
        js = _read_static("app.js")
        assert "ai-hub-qa-test" in js
        assert "ai-hub-qa-console" in js
        assert "ai-hub-qa-investigate" in js


# ═══════════════════════════════════════════════════════════════════════════
# CSS tests
# ═══════════════════════════════════════════════════════════════════════════


class TestCSS:
    def test_ai_home_styles(self):
        css = _read_static("styles.css")
        assert ".ai-home-header" in css
        assert ".ai-home-hero" in css
        assert ".ai-home-actions" in css
        assert ".ai-home-action-card" in css
        assert ".ai-home-status-pill" in css

    def test_ai_home_prompt_styles(self):
        css = _read_static("styles.css")
        assert ".ai-home-prompt-input" in css
        assert ".ai-home-prompt-go" in css
        assert ".ai-home-suggestion-chip" in css

    def test_ai_home_snapshot_styles(self):
        css = _read_static("styles.css")
        assert ".ai-home-snapshot-grid" in css
        assert ".ai-home-snapshot-item" in css
        assert ".ai-home-snapshot-value" in css

    def test_ai_home_observations_styles(self):
        css = _read_static("styles.css")
        assert ".ai-home-observations-list" in css
        assert ".ai-home-observations-link" in css

    def test_ai_inspector_styles(self):
        css = _read_static("styles.css")
        assert ".ai-inspector-tabs" in css
        assert ".ai-inspector-tab" in css
        assert ".ai-inspector-panel" in css
        assert ".ai-inspector-score-card" in css

    def test_ai_inspector_grade_styles(self):
        css = _read_static("styles.css")
        assert ".ai-inspector-grade-A" in css
        assert ".ai-inspector-grade-B" in css
        assert ".ai-inspector-grade-C" in css

    def test_console_plan_preview_styles(self):
        css = _read_static("styles.css")
        assert ".ai-console-plan-preview" in css
        assert ".ai-console-plan-step" in css
        assert ".ai-console-plan-indicator" in css

    def test_graph_summary_card_styles(self):
        css = _read_static("styles.css")
        assert ".ai-graph-summary-card" in css
        assert ".ai-graph-summary-grid" in css

    def test_hub_quick_actions_styles(self):
        css = _read_static("styles.css")
        assert ".ai-hub-quick-actions" in css


# ═══════════════════════════════════════════════════════════════════════════
# Backend endpoint tests (route registration)
# ═══════════════════════════════════════════════════════════════════════════


class TestEndpointRegistration:
    """Verify new endpoints are registered on the Studio router."""

    def _get_route_paths(self):
        from aksara.studio.fastapi import router
        return [getattr(r, "path", "") for r in router.routes]

    def test_ai_home_endpoint_registered(self):
        paths = self._get_route_paths()
        assert "/studio/ai/home" in paths

    def test_ai_inspector_endpoint_registered(self):
        paths = self._get_route_paths()
        assert "/studio/ai/inspector" in paths

    def test_ai_home_is_get(self):
        from aksara.studio.fastapi import router
        for route in router.routes:
            if getattr(route, "path", None) == "/studio/ai/home":
                assert "GET" in route.methods
                return
        pytest.fail("GET /studio/ai/home not found")

    def test_ai_inspector_is_get(self):
        from aksara.studio.fastapi import router
        for route in router.routes:
            if getattr(route, "path", None) == "/studio/ai/inspector":
                assert "GET" in route.methods
                return
        pytest.fail("GET /studio/ai/inspector not found")


# ═══════════════════════════════════════════════════════════════════════════
# Backward compatibility
# ═══════════════════════════════════════════════════════════════════════════


class TestBackwardCompatibility:
    """v0.5.38: Old standalone templates/functions removed; routing via redirect map."""

    def test_old_ai_debugger_template_removed(self):
        # v0.5.38: standalone template removed, consolidated into AI Inspector
        html = _read_static("index.html")
        assert 'id="template-ai-debugger"' not in html

    def test_old_ai_architecture_template_removed(self):
        # v0.5.38: standalone template removed, consolidated into AI Inspector
        html = _read_static("index.html")
        assert 'id="template-ai-architecture"' not in html

    def test_old_ai_performance_template_removed(self):
        # v0.5.38: standalone template removed, consolidated into AI Inspector
        html = _read_static("index.html")
        assert 'id="template-ai-performance"' not in html

    def test_old_render_functions_removed(self):
        # v0.5.38: old standalone render functions removed; replaced by _renderInspectorTab
        js = _read_static("app.js")
        assert "function renderAiDebugger()" not in js
        assert "function renderAiArchitecture()" not in js
        assert "function renderAiPerformance()" not in js

    def test_redirect_map_routes_old_sections(self):
        # Redirect map still exists so old URLs navigate to AI Inspector
        js = _read_static("app.js")
        assert "'ai-debugger': 'ai-inspector'" in js
        assert "'ai-architecture': 'ai-inspector'" in js
        assert "'ai-performance': 'ai-inspector'" in js

    def test_ai_inspector_has_consolidated_tabs(self):
        # AI Inspector provides debug, architecture, and performance tabs
        html = _read_static("index.html")
        assert 'data-inspector-tab="debug"' in html
        assert 'data-inspector-tab="architecture"' in html
        assert 'data-inspector-tab="performance"' in html
