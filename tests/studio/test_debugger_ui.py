"""
v0.5.33 — Studio AI Debugger UI: template, navigation, JS, and CSS tests.

Tests cover:
    - Navigation item present in index.html
    - Template structure for ai-debugger
    - app.js rendering functions
    - styles.css AI Debugger styles
    - Correct section wiring
"""

from __future__ import annotations

import pytest
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

    def test_ai_debugger_nav_label(self):
        html = _read_static("index.html")
        assert "AI Debugger" in html

    def test_redirect_to_inspector(self):
        js = _read_static("app.js")
        assert "'ai-debugger'" in js
        assert "'ai-inspector'" in js

    def test_ai_debugger_nav_icon(self):
        html = _read_static("index.html")
        # Bug icon SVG path
        assert 'class="nav-icon"' in html

    def test_template_preserved(self):
        html = _read_static("index.html")
        assert 'id="template-ai-debugger"' in html


# ═══════════════════════════════════════════════════════════════════════════
# Template tests
# ═══════════════════════════════════════════════════════════════════════════


class TestTemplate:
    def test_template_id(self):
        html = _read_static("index.html")
        assert 'id="template-ai-debugger"' in html

    def test_section_header(self):
        html = _read_static("index.html")
        assert "AI Debugger" in html
        assert "root-cause analysis" in html.lower()

    def test_toolbar_elements(self):
        html = _read_static("index.html")
        assert 'id="ai-debugger-query"' in html
        assert 'id="ai-debugger-run"' in html
        assert 'id="ai-debugger-status"' in html

    def test_summary_container(self):
        html = _read_static("index.html")
        assert 'id="ai-debugger-summary"' in html

    def test_tabs(self):
        html = _read_static("index.html")
        assert 'data-debug-tab="root-causes"' in html
        assert 'data-debug-tab="clusters"' in html
        assert 'data-debug-tab="issues"' in html
        assert 'data-debug-tab="fix-plan"' in html

    def test_panel(self):
        html = _read_static("index.html")
        assert 'id="ai-debugger-panel"' in html

    def test_query_input_placeholder(self):
        html = _read_static("index.html")
        assert "why is" in html.lower()

    def test_run_button_label(self):
        html = _read_static("index.html")
        assert "Run Debugger" in html


# ═══════════════════════════════════════════════════════════════════════════
# JavaScript tests
# ═══════════════════════════════════════════════════════════════════════════


class TestJavaScript:
    def test_render_function_exists(self):
        js = _read_static("app.js")
        assert "renderAiDebugger" in js

    def test_render_section_case(self):
        js = _read_static("app.js")
        assert "case 'ai-debugger'" in js

    def test_run_debugger_function(self):
        js = _read_static("app.js")
        assert "_runDebugger" in js

    def test_render_tab_function(self):
        js = _read_static("app.js")
        assert "_renderDebuggerTab" in js

    def test_root_causes_renderer(self):
        js = _read_static("app.js")
        assert "_renderDebugRootCauses" in js

    def test_clusters_renderer(self):
        js = _read_static("app.js")
        assert "_renderDebugClusters" in js

    def test_issues_renderer(self):
        js = _read_static("app.js")
        assert "_renderDebugIssues" in js

    def test_fix_plan_renderer(self):
        js = _read_static("app.js")
        assert "_renderDebugFixPlan" in js

    def test_fetch_endpoint(self):
        js = _read_static("app.js")
        assert "/studio/ai/debug" in js

    def test_post_method(self):
        js = _read_static("app.js")
        assert "method: 'POST'" in js

    def test_debugger_data_variable(self):
        js = _read_static("app.js")
        assert "_debuggerData" in js

    def test_escaping_used(self):
        js = _read_static("app.js")
        # _esc() should be used for XSS prevention
        assert "_esc(" in js


# ═══════════════════════════════════════════════════════════════════════════
# CSS tests
# ═══════════════════════════════════════════════════════════════════════════


class TestStyles:
    def test_toolbar_style(self):
        css = _read_static("styles.css")
        assert ".ai-debugger-toolbar" in css

    def test_query_input_style(self):
        css = _read_static("styles.css")
        assert ".ai-debugger-query-input" in css

    def test_summary_style(self):
        css = _read_static("styles.css")
        assert ".ai-debugger-summary" in css

    def test_summary_grid(self):
        css = _read_static("styles.css")
        assert ".ai-debugger-summary-grid" in css

    def test_stat_styles(self):
        css = _read_static("styles.css")
        assert ".ai-debugger-stat" in css
        assert ".ai-debugger-stat-num" in css
        assert ".ai-debugger-stat-label" in css

    def test_tabs_style(self):
        css = _read_static("styles.css")
        assert ".ai-debugger-tabs" in css
        assert ".ai-debugger-tab" in css
        assert ".ai-debugger-tab.active" in css

    def test_panel_style(self):
        css = _read_static("styles.css")
        assert ".ai-debugger-panel" in css

    def test_table_style(self):
        css = _read_static("styles.css")
        assert ".ai-debugger-table" in css

    def test_root_cause_card_style(self):
        css = _read_static("styles.css")
        assert ".ai-debugger-rc-card" in css

    def test_confidence_style(self):
        css = _read_static("styles.css")
        assert ".ai-debugger-confidence" in css

    def test_severity_styles(self):
        css = _read_static("styles.css")
        assert ".ai-debugger-rc-card.severity-error" in css
        assert ".ai-debugger-rc-card.severity-warning" in css

    def test_fix_plan_styles(self):
        css = _read_static("styles.css")
        assert ".ai-debugger-fix-plan" in css
        assert ".ai-debugger-fix-group" in css

    def test_loading_style(self):
        css = _read_static("styles.css")
        assert ".ai-debugger-loading" in css

    def test_error_style(self):
        css = _read_static("styles.css")
        assert ".ai-debugger-error" in css

    def test_empty_style(self):
        css = _read_static("styles.css")
        assert ".ai-debugger-empty" in css
