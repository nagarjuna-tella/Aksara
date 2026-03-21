"""
v0.5.35 — AI Performance Analyzer: Studio UI tests.

v0.5.38 update: The standalone ai-performance template/functions/CSS were
removed and consolidated into the AI Inspector inline tabs. These tests now
verify the consolidated state.

Tests cover:
    - Navigation: sidebar nav item removed, redirect map intact
    - Standalone template removed (consolidated into AI Inspector)
    - AI Inspector has performance tab
    - JavaScript: inspector functions present, old standalone functions removed
    - CSS: old .ai-perf-* classes removed, .ai-perf-sev-badge preserved in AI Inspector section
"""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent / "aksara" / "studio" / "static"
_HTML = (_ROOT / "index.html").read_text(encoding="utf-8")
_JS = (_ROOT / "app.js").read_text(encoding="utf-8")
_CSS = (_ROOT / "styles.css").read_text(encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════
# Navigation
# ═══════════════════════════════════════════════════════════════════════════


class TestNavigation:
    # v0.5.38: sidebar nav item removed (consolidated into AI Inspector)
    def test_nav_item_removed_from_sidebar(self):
        sidebar_end = _HTML.find('</nav>')
        sidebar_html = _HTML[:sidebar_end] if sidebar_end != -1 else _HTML
        assert 'data-section="ai-performance"' not in sidebar_html

    def test_nav_label_in_template(self):
        # "Performance" still appears as a tab in the AI Inspector
        assert "Performance" in _HTML

    def test_redirect_to_inspector(self):
        assert "'ai-performance'" in _JS
        assert "'ai-inspector'" in _JS

    def test_nav_svg_icon(self):
        assert 'class="nav-icon"' in _HTML

    def test_standalone_template_removed(self):
        # v0.5.38: standalone template removed; performance is a tab in AI Inspector
        assert 'id="template-ai-performance"' not in _HTML


# ═══════════════════════════════════════════════════════════════════════════
# Template Structure — consolidated into AI Inspector
# ═══════════════════════════════════════════════════════════════════════════


class TestTemplateStructure:
    def test_ai_inspector_template_exists(self):
        assert 'id="template-ai-inspector"' in _HTML

    def test_ai_inspector_has_performance_tab(self):
        assert 'data-inspector-tab="performance"' in _HTML

    def test_ai_inspector_has_debug_tab(self):
        assert 'data-inspector-tab="debug"' in _HTML

    def test_ai_inspector_has_architecture_tab(self):
        assert 'data-inspector-tab="architecture"' in _HTML

    def test_ai_inspector_has_overview_tab(self):
        assert 'data-inspector-tab="overview"' in _HTML

    def test_ai_inspector_panel_exists(self):
        assert 'id="ai-inspector-panel"' in _HTML

    def test_standalone_template_ids_removed(self):
        assert 'id="ai-perf-run"' not in _HTML
        assert 'id="ai-perf-panel"' not in _HTML
        assert 'id="ai-perf-score-card"' not in _HTML


# ═══════════════════════════════════════════════════════════════════════════
# JavaScript Functions
# ═══════════════════════════════════════════════════════════════════════════


class TestJavaScript:
    def test_inspector_render_function_exists(self):
        assert "function renderAiInspector()" in _JS

    def test_inspector_tab_render_function_exists(self):
        assert "function _renderInspectorTab(" in _JS

    def test_standalone_render_function_removed(self):
        # v0.5.38: renderAiPerformance consolidated into _renderInspectorTab
        assert "function renderAiPerformance()" not in _JS

    def test_standalone_run_function_removed(self):
        assert "function _runPerfAnalysis()" not in _JS

    def test_standalone_tab_function_removed(self):
        assert "function _renderPerfTab(" not in _JS

    def test_standalone_issues_function_removed(self):
        assert "function _renderPerfIssues(" not in _JS

    def test_standalone_recommendations_function_removed(self):
        assert "function _renderPerfRecommendations(" not in _JS

    def test_standalone_switch_case_removed(self):
        assert "case 'ai-performance':" not in _JS

    def test_standalone_data_variable_removed(self):
        assert "_perfData" not in _JS

    def test_fetch_endpoint(self):
        # Backend endpoint still served; now called from _renderInspectorTab
        assert "/studio/ai/performance-analysis" in _JS

    def test_severity_badge(self):
        # ai-perf-sev-badge is still used in _renderInspectorTab performance tab
        assert "ai-perf-sev-badge" in _JS


# ═══════════════════════════════════════════════════════════════════════════
# CSS Classes
# ═══════════════════════════════════════════════════════════════════════════


class TestCSS:
    def test_standalone_css_removed(self):
        # v0.5.38: all .ai-perf-* classes were removed (except ai-perf-sev-badge)
        assert ".ai-perf-toolbar" not in _CSS
        assert ".ai-perf-score-card" not in _CSS
        assert ".ai-perf-tabs" not in _CSS
        assert ".ai-perf-panel" not in _CSS
        assert ".ai-perf-grade-a" not in _CSS

    def test_severity_badge_preserved(self):
        # .ai-perf-sev-badge was preserved; moved to AI Inspector CSS section
        assert ".ai-perf-sev-badge" in _CSS

    def test_inspector_tabs_class(self):
        assert ".ai-inspector-tabs" in _CSS

    def test_inspector_tab_active_class(self):
        assert ".ai-inspector-tab.active" in _CSS

    def test_inspector_panel_class(self):
        assert ".ai-inspector-panel" in _CSS

    def test_inspector_empty_class(self):
        assert ".ai-inspector-empty" in _CSS
