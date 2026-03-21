"""
v0.5.34 — AI Architecture Review: Studio UI tests.

Tests cover:
    - Navigation item in sidebar
    - Template structure
    - JS functions for rendering
    - CSS class definitions
"""

from __future__ import annotations

import pytest
from pathlib import Path

_STATIC = Path(__file__).resolve().parent.parent.parent / "aksara" / "studio" / "static"


# ═══════════════════════════════════════════════════════════════════════════
# Navigation
# ═══════════════════════════════════════════════════════════════════════════


class TestNavigation:
    # v0.5.38: sidebar nav item removed (consolidated into AI Inspector)
    def test_nav_item_removed_from_sidebar(self):
        html = (_STATIC / "index.html").read_text()
        # Nav item removed but template preserved
        sidebar_end = html.find('</nav>')
        sidebar_html = html[:sidebar_end] if sidebar_end != -1 else html
        assert 'data-section="ai-architecture"' not in sidebar_html

    def test_nav_label(self):
        html = (_STATIC / "index.html").read_text()
        assert "Architecture" in html

    def test_redirect_to_inspector(self):
        js = (_STATIC / "app.js").read_text()
        # v0.5.38: ai-architecture redirects to ai-inspector
        assert "'ai-architecture'" in js
        assert "'ai-inspector'" in js


# ═══════════════════════════════════════════════════════════════════════════
# Template Structure
# ═══════════════════════════════════════════════════════════════════════════


class TestTemplate:
    def test_template_exists(self):
        html = (_STATIC / "index.html").read_text()
        assert 'id="template-ai-architecture"' in html

    def test_template_has_header(self):
        html = (_STATIC / "index.html").read_text()
        assert "AI Architecture Review" in html

    def test_template_has_run_button(self):
        html = (_STATIC / "index.html").read_text()
        assert 'id="ai-arch-run"' in html

    def test_template_has_score_card(self):
        html = (_STATIC / "index.html").read_text()
        assert 'id="ai-arch-score-card"' in html

    def test_template_has_metrics(self):
        html = (_STATIC / "index.html").read_text()
        assert 'id="ai-arch-metrics"' in html

    def test_template_has_findings_tab(self):
        html = (_STATIC / "index.html").read_text()
        assert 'data-arch-tab="findings"' in html

    def test_template_has_suggestions_tab(self):
        html = (_STATIC / "index.html").read_text()
        assert 'data-arch-tab="suggestions"' in html

    def test_template_has_panel(self):
        html = (_STATIC / "index.html").read_text()
        assert 'id="ai-arch-panel"' in html

    def test_template_has_status(self):
        html = (_STATIC / "index.html").read_text()
        assert 'id="ai-arch-status"' in html


# ═══════════════════════════════════════════════════════════════════════════
# JavaScript Functions
# ═══════════════════════════════════════════════════════════════════════════


class TestJavaScript:
    def test_render_function_exists(self):
        js = (_STATIC / "app.js").read_text()
        assert "function renderAiArchitecture()" in js

    def test_run_function_exists(self):
        js = (_STATIC / "app.js").read_text()
        assert "function _runArchReview()" in js

    def test_render_tab_function_exists(self):
        js = (_STATIC / "app.js").read_text()
        assert "function _renderArchTab(" in js

    def test_render_findings_function(self):
        js = (_STATIC / "app.js").read_text()
        assert "function _renderArchFindings(" in js

    def test_render_suggestions_function(self):
        js = (_STATIC / "app.js").read_text()
        assert "function _renderArchSuggestions(" in js

    def test_switch_case(self):
        js = (_STATIC / "app.js").read_text()
        assert "case 'ai-architecture':" in js

    def test_arch_data_variable(self):
        js = (_STATIC / "app.js").read_text()
        assert "_archData" in js

    def test_fetch_endpoint(self):
        js = (_STATIC / "app.js").read_text()
        assert "/studio/ai/architecture-review" in js

    def test_grade_class_rendering(self):
        js = (_STATIC / "app.js").read_text()
        assert "ai-arch-grade-" in js

    def test_score_rendering(self):
        js = (_STATIC / "app.js").read_text()
        assert "ai-arch-score-num" in js


# ═══════════════════════════════════════════════════════════════════════════
# CSS Classes
# ═══════════════════════════════════════════════════════════════════════════


class TestCSS:
    def test_toolbar_class(self):
        css = (_STATIC / "styles.css").read_text()
        assert ".ai-arch-toolbar" in css

    def test_score_card_class(self):
        css = (_STATIC / "styles.css").read_text()
        assert ".ai-arch-score-card" in css

    def test_grade_classes(self):
        css = (_STATIC / "styles.css").read_text()
        for grade in ("a", "b", "c", "d", "f"):
            assert f".ai-arch-grade-{grade}" in css

    def test_metrics_grid_class(self):
        css = (_STATIC / "styles.css").read_text()
        assert ".ai-arch-metrics-grid" in css

    def test_tabs_class(self):
        css = (_STATIC / "styles.css").read_text()
        assert ".ai-arch-tabs" in css

    def test_tab_active_class(self):
        css = (_STATIC / "styles.css").read_text()
        assert ".ai-arch-tab.active" in css

    def test_finding_card_class(self):
        css = (_STATIC / "styles.css").read_text()
        assert ".ai-arch-finding-card" in css

    def test_severity_border_classes(self):
        css = (_STATIC / "styles.css").read_text()
        for sev in ("critical", "error", "warning", "info"):
            assert f".ai-arch-sev-{sev}" in css

    def test_suggestion_card_class(self):
        css = (_STATIC / "styles.css").read_text()
        assert ".ai-arch-suggestion-card" in css

    def test_impact_badge_classes(self):
        css = (_STATIC / "styles.css").read_text()
        for imp in ("high", "medium", "low"):
            assert f".ai-arch-impact-{imp}" in css

    def test_panel_class(self):
        css = (_STATIC / "styles.css").read_text()
        assert ".ai-arch-panel" in css

    def test_empty_state_class(self):
        css = (_STATIC / "styles.css").read_text()
        assert ".ai-arch-empty" in css
