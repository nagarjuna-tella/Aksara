"""
v0.5.33 — Studio AI Debugger UI: template, navigation, JS, and CSS tests.

v0.5.38 update: The standalone ai-debugger template/functions/CSS were
removed and consolidated into the AI Inspector inline tabs. These tests now
verify the consolidated state.

Tests cover:
    - Navigation item removed from sidebar
    - Standalone template removed (consolidated into AI Inspector)
    - AI Inspector has debug tab
    - Redirect map routes ai-debugger → ai-inspector
    - AI Inspector JS functions present; old standalone JS functions removed
    - Old CSS classes removed; AI Inspector CSS classes present
"""

from __future__ import annotations

from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "aksara" / "studio" / "static"


def _read_static(name: str) -> str:
    return (STATIC_DIR / name).read_text(encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════
# Navigation tests
# ═══════════════════════════════════════════════════════════════════════════


class TestNavigation:
    # v0.5.38: sidebar nav item removed (consolidated into AI Inspector)
    def test_ai_debugger_nav_item_removed_from_sidebar(self):
        html = _read_static("index.html")
        sidebar_end = html.find('</nav>')
        sidebar_html = html[:sidebar_end] if sidebar_end != -1 else html
        assert 'data-section="ai-debugger"' not in sidebar_html

    def test_redirect_to_inspector(self):
        js = _read_static("app.js")
        assert "'ai-debugger'" in js
        assert "'ai-inspector'" in js

    def test_ai_debugger_nav_icon(self):
        html = _read_static("index.html")
        assert 'class="nav-icon"' in html

    def test_standalone_template_removed(self):
        # v0.5.38: standalone template removed; debug is a tab in AI Inspector
        html = _read_static("index.html")
        assert 'id="template-ai-debugger"' not in html


# ═══════════════════════════════════════════════════════════════════════════
# Template tests — standalone removed, consolidated into AI Inspector
# ═══════════════════════════════════════════════════════════════════════════


class TestTemplate:
    def test_ai_inspector_template_exists(self):
        html = _read_static("index.html")
        assert 'id="template-ai-inspector"' in html

    def test_ai_inspector_has_debug_tab(self):
        html = _read_static("index.html")
        assert 'data-inspector-tab="debug"' in html

    def test_ai_inspector_has_architecture_tab(self):
        html = _read_static("index.html")
        assert 'data-inspector-tab="architecture"' in html

    def test_ai_inspector_has_performance_tab(self):
        html = _read_static("index.html")
        assert 'data-inspector-tab="performance"' in html

    def test_ai_inspector_panel_exists(self):
        html = _read_static("index.html")
        assert 'id="ai-inspector-panel"' in html

    def test_standalone_template_ids_removed(self):
        html = _read_static("index.html")
        assert 'id="ai-debugger-panel"' not in html
        assert 'id="ai-debugger-run"' not in html
        assert 'id="ai-debugger-summary"' not in html


# ═══════════════════════════════════════════════════════════════════════════
# JavaScript tests
# ═══════════════════════════════════════════════════════════════════════════


class TestJavaScript:
    def test_inspector_render_function_exists(self):
        js = _read_static("app.js")
        assert "function renderAiInspector()" in js

    def test_inspector_tab_render_function_exists(self):
        js = _read_static("app.js")
        assert "function _renderInspectorTab(" in js

    def test_standalone_render_function_removed(self):
        # v0.5.38: renderAiDebugger consolidated into _renderInspectorTab
        js = _read_static("app.js")
        assert "function renderAiDebugger()" not in js

    def test_standalone_switch_case_removed(self):
        js = _read_static("app.js")
        assert "case 'ai-debugger':" not in js

    def test_standalone_run_function_removed(self):
        js = _read_static("app.js")
        assert "function _runDebugger()" not in js

    def test_standalone_tab_renderer_removed(self):
        js = _read_static("app.js")
        assert "function _renderDebuggerTab(" not in js

    def test_standalone_root_cause_renderer_removed(self):
        js = _read_static("app.js")
        assert "function _renderDebugRootCauses(" not in js

    def test_standalone_clusters_renderer_removed(self):
        js = _read_static("app.js")
        assert "function _renderDebugClusters(" not in js

    def test_standalone_data_variable_removed(self):
        js = _read_static("app.js")
        assert "_debuggerData" not in js

    def test_fetch_endpoint(self):
        # Backend endpoint still served; now called from _renderInspectorTab
        js = _read_static("app.js")
        assert "/studio/ai/debug" in js

    def test_post_method(self):
        js = _read_static("app.js")
        assert "method: 'POST'" in js

    def test_escaping_used(self):
        js = _read_static("app.js")
        # _esc() used throughout for XSS prevention
        assert "_esc(" in js


# ═══════════════════════════════════════════════════════════════════════════
# CSS tests
# ═══════════════════════════════════════════════════════════════════════════


class TestStyles:
    def test_standalone_css_removed(self):
        # v0.5.38: all .ai-debugger-* classes were removed with the dead section
        css = _read_static("styles.css")
        assert ".ai-debugger-toolbar" not in css
        assert ".ai-debugger-panel" not in css
        assert ".ai-debugger-tabs" not in css
        assert ".ai-debugger-summary" not in css

    def test_inspector_tabs_class(self):
        css = _read_static("styles.css")
        assert ".ai-inspector-tabs" in css

    def test_inspector_tab_active_class(self):
        css = _read_static("styles.css")
        assert ".ai-inspector-tab.active" in css

    def test_inspector_panel_class(self):
        css = _read_static("styles.css")
        assert ".ai-inspector-panel" in css

    def test_inspector_empty_class(self):
        css = _read_static("styles.css")
        assert ".ai-inspector-empty" in css

    def test_inspector_findings_class(self):
        css = _read_static("styles.css")
        assert ".ai-inspector-findings" in css
