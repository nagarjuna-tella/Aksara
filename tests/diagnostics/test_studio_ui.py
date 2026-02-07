"""
Tests for Studio UI Diagnostics 2.0 (HTML/JS/CSS smoke tests).

v0.5.17: Validates that the Diagnostics 2.0 panel HTML, CSS, and JS
contain the expected elements, classes, and function signatures.
"""

from __future__ import annotations

from pathlib import Path

import pytest


STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "aksara" / "studio" / "static"


class TestDiagnosticsHtml:
    """Smoke tests for index.html diagnostics template."""

    @pytest.fixture
    def html(self):
        return (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    def test_template_exists(self, html):
        assert 'id="template-diagnostics"' in html

    def test_summary_banner(self, html):
        assert 'id="diag-summary-banner"' in html

    def test_status_icon(self, html):
        assert 'id="diag-status-icon"' in html

    def test_status_label(self, html):
        assert 'id="diag-status-label"' in html

    def test_error_count(self, html):
        assert 'id="diag-count-errors"' in html

    def test_warning_count(self, html):
        assert 'id="diag-count-warnings"' in html

    def test_info_count(self, html):
        assert 'id="diag-count-info"' in html

    def test_duration_display(self, html):
        assert 'id="diag-duration"' in html

    def test_system_info_display(self, html):
        assert 'id="diag-system-info"' in html

    def test_filter_buttons(self, html):
        assert 'data-filter="all"' in html
        assert 'data-filter="error"' in html
        assert 'data-filter="warning"' in html
        assert 'data-filter="info"' in html

    def test_search_input(self, html):
        assert 'id="diag-search"' in html

    def test_live_button(self, html):
        assert 'id="diag-live-btn"' in html

    def test_refresh_button(self, html):
        assert 'id="diag-refresh-btn"' in html

    def test_issues_list_container(self, html):
        assert 'id="diag-issues-list"' in html


class TestDiagnosticsJs:
    """Smoke tests for app.js diagnostics functions."""

    @pytest.fixture
    def js(self):
        return (STATIC_DIR / "app.js").read_text(encoding="utf-8")

    def test_render_diagnostics_function(self, js):
        assert "function renderDiagnostics()" in js

    def test_fetch_and_render_function(self, js):
        assert "function fetchAndRenderDiagnostics()" in js or "async function fetchAndRenderDiagnostics()" in js

    def test_update_summary_function(self, js):
        assert "function updateDiagnosticsSummary()" in js

    def test_render_issues_function(self, js):
        assert "function renderDiagnosticsIssues()" in js

    def test_diagnostics_live_state(self, js):
        assert "diagnosticsLive" in js

    def test_diagnostics_filter_state(self, js):
        assert "diagnosticsFilter" in js

    def test_diagnostics_search_state(self, js):
        assert "diagnosticsSearchQuery" in js

    def test_diagnostics_report_state(self, js):
        assert "diagnosticsReport" in js

    def test_fetches_diagnostics_endpoint(self, js):
        assert "/studio/diagnostics" in js

    def test_auto_refresh_interval(self, js):
        assert "10000" in js  # 10 second auto-refresh

    def test_keyboard_d_for_diagnostics(self, js):
        assert "'d'" in js or '"d"' in js

    def test_keyboard_slash_for_search(self, js):
        assert "'/'" in js or '"/"' in js

    def test_escape_key_clears(self, js):
        assert "'Escape'" in js or '"Escape"' in js

    def test_stop_diagnostics_timer(self, js):
        assert "diagnosticsInterval" in js


class TestDiagnosticsCss:
    """Smoke tests for styles.css diagnostics styles."""

    @pytest.fixture
    def css(self):
        return (STATIC_DIR / "styles.css").read_text(encoding="utf-8")

    def test_summary_banner_class(self, css):
        assert ".diag-summary-banner" in css

    def test_banner_status_variants(self, css):
        assert ".diag-banner-ok" in css
        assert ".diag-banner-warning" in css
        assert ".diag-banner-error" in css

    def test_toolbar_class(self, css):
        assert ".diag-toolbar" in css

    def test_filter_button_class(self, css):
        assert ".diag-filter-btn" in css

    def test_search_input_class(self, css):
        assert ".diag-search-input" in css

    def test_issue_card_class(self, css):
        assert ".diag-issue-card" in css

    def test_severity_badge_class(self, css):
        assert ".diag-sev-badge" in css

    def test_severity_variants(self, css):
        assert ".diag-sev-error" in css
        assert ".diag-sev-warning" in css
        assert ".diag-sev-info" in css

    def test_kind_badge_class(self, css):
        assert ".diag-kind-badge" in css

    def test_issue_hint_class(self, css):
        assert ".diag-issue-hint" in css

    def test_all_clear_class(self, css):
        assert ".diag-all-clear" in css
