"""
v0.5.35 — AI Performance Analyzer: Studio UI tests.

Tests cover:
    - Navigation: HTML data-section, label, href, SVG icon
    - Template structure: template ID, header, run button, score card,
      metrics, tabs, panel, status
    - JavaScript: functions, switch case, data variable, fetch endpoint,
      grade/score classes
    - CSS: toolbar, score card, grade colours, metrics grid, tabs,
      issue cards, severity borders, recommendation cards, impact badges
"""

from __future__ import annotations

import pytest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent / "aksara" / "studio" / "static"
_HTML = (_ROOT / "index.html").read_text(encoding="utf-8")
_JS = (_ROOT / "app.js").read_text(encoding="utf-8")
_CSS = (_ROOT / "styles.css").read_text(encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════
# Navigation
# ═══════════════════════════════════════════════════════════════════════════


class TestNavigation:
    def test_nav_data_section(self):
        assert 'data-section="ai-performance"' in _HTML

    def test_nav_label(self):
        assert ">Performance</span>" in _HTML

    def test_nav_href(self):
        assert '#/ai-performance' in _HTML

    def test_nav_svg_icon(self):
        # The performance nav icon uses a polyline (pulse/chart)
        assert 'class="nav-icon"' in _HTML

    def test_nav_order_after_architecture(self):
        arch_pos = _HTML.index('data-section="ai-architecture"')
        perf_pos = _HTML.index('data-section="ai-performance"')
        assert perf_pos > arch_pos


# ═══════════════════════════════════════════════════════════════════════════
# Template Structure
# ═══════════════════════════════════════════════════════════════════════════


class TestTemplateStructure:
    def test_template_id(self):
        assert 'id="template-ai-performance"' in _HTML

    def test_section_header(self):
        assert "AI Performance Analyzer" in _HTML

    def test_section_subtitle(self):
        assert "slow queries" in _HTML.lower()
        assert "n+1" in _HTML.lower() or "n+1" in _HTML

    def test_run_button(self):
        assert 'id="ai-perf-run"' in _HTML
        assert "Run Analysis" in _HTML

    def test_score_card(self):
        assert 'id="ai-perf-score-card"' in _HTML

    def test_metrics_element(self):
        assert 'id="ai-perf-metrics"' in _HTML

    def test_tabs(self):
        assert 'class="ai-perf-tabs"' in _HTML
        assert 'data-perf-tab="issues"' in _HTML
        assert 'data-perf-tab="recommendations"' in _HTML

    def test_panel(self):
        assert 'id="ai-perf-panel"' in _HTML

    def test_status(self):
        assert 'id="ai-perf-status"' in _HTML

    def test_empty_state(self):
        assert "ai-perf-empty" in _HTML


# ═══════════════════════════════════════════════════════════════════════════
# JavaScript Functions
# ═══════════════════════════════════════════════════════════════════════════


class TestJavaScript:
    def test_render_function(self):
        assert "function renderAiPerformance()" in _JS

    def test_run_analysis_function(self):
        assert "function _runPerfAnalysis()" in _JS

    def test_render_tab_function(self):
        assert "function _renderPerfTab(" in _JS

    def test_render_issues_function(self):
        assert "function _renderPerfIssues(" in _JS

    def test_render_recommendations_function(self):
        assert "function _renderPerfRecommendations(" in _JS

    def test_switch_case(self):
        assert "case 'ai-performance':" in _JS

    def test_data_variable(self):
        assert "_perfData" in _JS

    def test_fetch_endpoint(self):
        assert "/studio/ai/performance-analysis" in _JS

    def test_grade_classes(self):
        # Grade classes are dynamically constructed in JS via gradeClass variable
        assert "ai-perf-grade-" in _JS
        # Specific grades are defined in CSS
        for grade in ("a", "b", "c", "d", "f"):
            assert f".ai-perf-grade-{grade}" in _CSS

    def test_score_display(self):
        assert "ai-perf-score-num" in _JS

    def test_severity_badge(self):
        assert "ai-perf-sev-badge" in _JS

    def test_impact_badge(self):
        assert "ai-perf-impact-badge" in _JS

    def test_empty_states(self):
        assert "ai-perf-empty" in _JS


# ═══════════════════════════════════════════════════════════════════════════
# CSS Classes
# ═══════════════════════════════════════════════════════════════════════════


class TestCSS:
    def test_toolbar(self):
        assert ".ai-perf-toolbar" in _CSS

    def test_score_card(self):
        assert ".ai-perf-score-card" in _CSS
        assert ".ai-perf-score-inner" in _CSS

    def test_grade_colours(self):
        for grade in ("a", "b", "c", "d", "f"):
            assert f".ai-perf-grade-{grade}" in _CSS

    def test_score_number(self):
        assert ".ai-perf-score-num" in _CSS

    def test_metrics_grid(self):
        assert ".ai-perf-metrics-grid" in _CSS
        assert ".ai-perf-metric" in _CSS
        assert ".ai-perf-metric-num" in _CSS
        assert ".ai-perf-metric-label" in _CSS

    def test_tabs(self):
        assert ".ai-perf-tabs" in _CSS
        assert ".ai-perf-tab" in _CSS
        assert ".ai-perf-tab.active" in _CSS

    def test_issue_card(self):
        assert ".ai-perf-issue-card" in _CSS
        assert ".ai-perf-issue-header" in _CSS

    def test_severity_borders(self):
        for sev in ("critical", "high", "medium", "low"):
            assert f".ai-perf-sev-{sev}" in _CSS

    def test_severity_badge(self):
        assert ".ai-perf-sev-badge" in _CSS

    def test_recommendation_card(self):
        assert ".ai-perf-rec-card" in _CSS
        assert ".ai-perf-rec-header" in _CSS

    def test_impact_badges(self):
        for impact in ("high", "medium", "low"):
            assert f".ai-perf-impact-{impact}" in _CSS

    def test_panel(self):
        assert ".ai-perf-panel" in _CSS

    def test_empty_state(self):
        assert ".ai-perf-empty" in _CSS

    def test_loading_state(self):
        assert ".ai-perf-loading" in _CSS

    def test_error_state(self):
        assert ".ai-perf-error" in _CSS
