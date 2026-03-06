"""
v0.5.32 — Studio Graph Explorer UI: template and integration tests.

Tests cover:
    - Nav item presence in index.html
    - Template presence in index.html
    - Template structure (toolbar, counts, tabs, panel)
    - AI Graph tab labels
    - app.js renderAiGraph function presence
    - CSS class definitions for graph components
    - Empty state handling classes
"""

from __future__ import annotations

import os
import pytest

# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_STATIC = os.path.join(_BASE, "aksara", "studio", "static")


def _read_static(filename: str) -> str:
    with open(os.path.join(_STATIC, filename), "r") as f:
        return f.read()


# ═══════════════════════════════════════════════════════════════════════════
# Tests: index.html — Nav Item
# ═══════════════════════════════════════════════════════════════════════════


class TestGraphNavItem:
    def test_nav_link_present(self):
        html = _read_static("index.html")
        assert 'data-section="ai-graph"' in html

    def test_nav_link_href(self):
        html = _read_static("index.html")
        assert 'href="#/ai-graph"' in html

    def test_nav_label(self):
        html = _read_static("index.html")
        # Should contain the label text
        assert "AI Graph" in html


# ═══════════════════════════════════════════════════════════════════════════
# Tests: index.html — Template
# ═══════════════════════════════════════════════════════════════════════════


class TestGraphTemplate:
    def test_template_present(self):
        html = _read_static("index.html")
        assert 'id="template-ai-graph"' in html

    def test_has_toolbar(self):
        html = _read_static("index.html")
        assert "ai-graph-toolbar" in html

    def test_has_rebuild_button(self):
        html = _read_static("index.html")
        assert "ai-graph-rebuild-btn" in html or "Rebuild" in html

    def test_has_counts_container(self):
        html = _read_static("index.html")
        assert "ai-graph-counts" in html

    def test_has_tabs(self):
        html = _read_static("index.html")
        assert "ai-graph-tabs" in html

    def test_has_panel(self):
        html = _read_static("index.html")
        assert "ai-graph-panel" in html

    def test_tab_labels_present(self):
        html = _read_static("index.html")
        for label in ("Models", "Routes", "Queries", "Diagnostics",
                       "Migrations", "Events", "Relationships"):
            assert label in html, f"Missing tab: {label}"


# ═══════════════════════════════════════════════════════════════════════════
# Tests: app.js — Functions
# ═══════════════════════════════════════════════════════════════════════════


class TestGraphJsFunctions:
    def test_render_function_present(self):
        js = _read_static("app.js")
        assert "renderAiGraph" in js

    def test_fetch_function_present(self):
        js = _read_static("app.js")
        assert "_fetchAiGraph" in js

    def test_render_counts_function(self):
        js = _read_static("app.js")
        assert "_renderAiGraphCounts" in js

    def test_render_tab_function(self):
        js = _read_static("app.js")
        assert "_renderAiGraphTab" in js

    def test_render_models_function(self):
        js = _read_static("app.js")
        assert "_renderGraphModels" in js

    def test_render_routes_function(self):
        js = _read_static("app.js")
        assert "_renderGraphRoutes" in js

    def test_render_events_function(self):
        js = _read_static("app.js")
        assert "_renderGraphEvents" in js

    def test_render_relationships_function(self):
        js = _read_static("app.js")
        assert "_renderGraphRelationships" in js

    def test_section_switch_case(self):
        js = _read_static("app.js")
        assert "case 'ai-graph'" in js


# ═══════════════════════════════════════════════════════════════════════════
# Tests: styles.css — Graph Styles
# ═══════════════════════════════════════════════════════════════════════════


class TestGraphCss:
    def test_toolbar_class(self):
        css = _read_static("styles.css")
        assert ".ai-graph-toolbar" in css

    def test_counts_class(self):
        css = _read_static("styles.css")
        assert ".ai-graph-counts" in css

    def test_tabs_class(self):
        css = _read_static("styles.css")
        assert ".ai-graph-tabs" in css

    def test_panel_class(self):
        css = _read_static("styles.css")
        assert ".ai-graph-panel" in css

    def test_table_class(self):
        css = _read_static("styles.css")
        assert ".ai-graph-table" in css

    def test_severity_classes(self):
        css = _read_static("styles.css")
        assert ".severity-error" in css
        assert ".severity-warning" in css

    def test_loading_class(self):
        css = _read_static("styles.css")
        assert ".ai-graph-loading" in css
