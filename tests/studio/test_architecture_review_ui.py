"""
v0.5.34 — AI Architecture Review: Studio UI tests.

v0.5.38 update: The standalone ai-architecture template/functions/CSS were
removed and consolidated into the AI Inspector inline tabs. These tests now
verify the consolidated state.

Tests cover:
    - Navigation item removed from sidebar
    - Standalone template removed (consolidated into AI Inspector)
    - AI Inspector has architecture tab
    - Redirect map routes ai-architecture → ai-inspector
    - AI Inspector JS functions present
    - Old standalone JS functions removed
    - Old CSS classes removed; AI Inspector CSS classes present
"""

from __future__ import annotations

from pathlib import Path

_STATIC = Path(__file__).resolve().parent.parent.parent / "aksara" / "studio" / "static"


# ═══════════════════════════════════════════════════════════════════════════
# Navigation
# ═══════════════════════════════════════════════════════════════════════════


class TestNavigation:
    # v0.5.38: sidebar nav item removed (consolidated into AI Inspector)
    def test_nav_item_removed_from_sidebar(self):
        html = (_STATIC / "index.html").read_text()
        sidebar_end = html.find('</nav>')
        sidebar_html = html[:sidebar_end] if sidebar_end != -1 else html
        assert 'data-section="ai-architecture"' not in sidebar_html

    def test_nav_label(self):
        # "Architecture" still appears as a tab in the AI Inspector
        html = (_STATIC / "index.html").read_text()
        assert "Architecture" in html

    def test_redirect_to_inspector(self):
        js = (_STATIC / "app.js").read_text()
        # v0.5.38: ai-architecture redirects to ai-inspector via redirect map
        assert "'ai-architecture'" in js
        assert "'ai-inspector'" in js


# ═══════════════════════════════════════════════════════════════════════════
# Template — standalone removed, consolidated into AI Inspector
# ═══════════════════════════════════════════════════════════════════════════


class TestTemplate:
    def test_standalone_template_removed(self):
        # v0.5.38: standalone template was removed; functionality is in AI Inspector
        html = (_STATIC / "index.html").read_text()
        assert 'id="template-ai-architecture"' not in html

    def test_ai_inspector_template_exists(self):
        html = (_STATIC / "index.html").read_text()
        assert 'id="template-ai-inspector"' in html

    def test_ai_inspector_has_architecture_tab(self):
        html = (_STATIC / "index.html").read_text()
        assert 'data-inspector-tab="architecture"' in html

    def test_ai_inspector_has_debug_tab(self):
        html = (_STATIC / "index.html").read_text()
        assert 'data-inspector-tab="debug"' in html

    def test_ai_inspector_has_performance_tab(self):
        html = (_STATIC / "index.html").read_text()
        assert 'data-inspector-tab="performance"' in html

    def test_ai_inspector_has_overview_tab(self):
        html = (_STATIC / "index.html").read_text()
        assert 'data-inspector-tab="overview"' in html

    def test_ai_inspector_panel_exists(self):
        html = (_STATIC / "index.html").read_text()
        assert 'id="ai-inspector-panel"' in html


# ═══════════════════════════════════════════════════════════════════════════
# JavaScript Functions
# ═══════════════════════════════════════════════════════════════════════════


class TestJavaScript:
    def test_inspector_render_function_exists(self):
        js = (_STATIC / "app.js").read_text()
        assert "function renderAiInspector()" in js

    def test_inspector_tab_render_function_exists(self):
        js = (_STATIC / "app.js").read_text()
        assert "function _renderInspectorTab(" in js

    def test_standalone_render_function_removed(self):
        # v0.5.38: renderAiArchitecture consolidated into _renderInspectorTab
        js = (_STATIC / "app.js").read_text()
        assert "function renderAiArchitecture()" not in js

    def test_standalone_run_function_removed(self):
        js = (_STATIC / "app.js").read_text()
        assert "function _runArchReview()" not in js

    def test_standalone_tab_function_removed(self):
        js = (_STATIC / "app.js").read_text()
        assert "function _renderArchTab(" not in js

    def test_standalone_findings_function_removed(self):
        js = (_STATIC / "app.js").read_text()
        assert "function _renderArchFindings(" not in js

    def test_standalone_suggestions_function_removed(self):
        js = (_STATIC / "app.js").read_text()
        assert "function _renderArchSuggestions(" not in js

    def test_standalone_switch_case_removed(self):
        js = (_STATIC / "app.js").read_text()
        assert "case 'ai-architecture':" not in js

    def test_inspector_switch_case_exists(self):
        js = (_STATIC / "app.js").read_text()
        assert "case 'ai-inspector':" in js

    def test_fetch_endpoint(self):
        # Backend endpoint still served; now called from _renderInspectorTab
        js = (_STATIC / "app.js").read_text()
        assert "/studio/ai/architecture-review" in js


# ═══════════════════════════════════════════════════════════════════════════
# CSS Classes
# ═══════════════════════════════════════════════════════════════════════════


class TestCSS:
    def test_standalone_css_removed(self):
        # v0.5.38: all .ai-arch-* classes were removed with the dead section
        css = (_STATIC / "styles.css").read_text()
        assert ".ai-arch-toolbar" not in css
        assert ".ai-arch-score-card" not in css
        assert ".ai-arch-tabs" not in css
        assert ".ai-arch-panel" not in css

    def test_inspector_tabs_class(self):
        css = (_STATIC / "styles.css").read_text()
        assert ".ai-inspector-tabs" in css

    def test_inspector_tab_active_class(self):
        css = (_STATIC / "styles.css").read_text()
        assert ".ai-inspector-tab.active" in css

    def test_inspector_panel_class(self):
        css = (_STATIC / "styles.css").read_text()
        assert ".ai-inspector-panel" in css

    def test_inspector_empty_class(self):
        css = (_STATIC / "styles.css").read_text()
        assert ".ai-inspector-empty" in css

    def test_inspector_findings_class(self):
        css = (_STATIC / "styles.css").read_text()
        assert ".ai-inspector-findings" in css

    def test_inspector_grade_classes(self):
        css = (_STATIC / "styles.css").read_text()
        for grade in ("A", "B", "C", "D", "F"):
            assert f".ai-inspector-grade-{grade}" in css
