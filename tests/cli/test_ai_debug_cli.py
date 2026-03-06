"""
v0.5.33 — CLI AI Debug: command registration and output tests.

Tests cover:
    - Command registration under 'aksara ai debug'
    - --json flag
    - --summary flag
    - --query option
    - --model and --route filter options
    - Text output format
    - Error handling
    - Help text
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock, patch
from click.testing import CliRunner

from aksara.cli.main import cli, ai_flows_group, ai_debug


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

runner = CliRunner()


def _make_empty_report():
    from aksara.ai.debugger import DebugReport
    return DebugReport(
        ok=True, query=None,
        summary="Full project debug analysis. Found 0 issues in 0 clusters. No specific root causes detected.",
        elapsed_ms=5.0,
        generated_at="2025-01-01T00:00:00Z",
    )


def _make_report_with_issues():
    from aksara.ai.debugger import DebugReport, DebugIssue, IssueCluster, RootCause

    issues = [
        DebugIssue(id="diag-1", source="diagnostic", severity="error",
                   title="DB_NO_URL", message="No database URL set"),
        DebugIssue(id="gap-2", source="gap", severity="warning",
                   title="GAP_001", message="Missing index on users table"),
    ]
    clusters = [
        IssueCluster(cluster_id="cluster-1", label="General: uncategorised",
                     component_type="general", component_name="uncategorised",
                     issue_ids=["diag-1", "gap-2"], severity="error", size=2),
    ]
    root_causes = [
        RootCause(cause_id="rc-1", title="Database connectivity problem",
                  description="Multiple issues related to database connectivity.",
                  confidence=0.85, severity="error",
                  evidence=["[error] DB_NO_URL: No database URL set"],
                  related_issues=["diag-1"],
                  fix_suggestions=["Check DATABASE_URL environment variable."]),
    ]
    return DebugReport(
        ok=True, query=None,
        issues=issues, clusters=clusters, root_causes=root_causes,
        summary="Found 2 issues in 1 clusters. Detected 1 potential root causes.",
        issue_count=2, cluster_count=1, root_cause_count=1,
        elapsed_ms=12.3,
        generated_at="2025-01-01T00:00:00Z",
    )


def _make_failed_report():
    from aksara.ai.debugger import DebugReport
    return DebugReport(
        ok=False, query=None,
        summary="Could not load project graph: boom",
        elapsed_ms=1.0,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Command registration
# ═══════════════════════════════════════════════════════════════════════════


class TestCommandRegistration:
    def test_debug_command_exists(self):
        assert "debug" in [c.name for c in ai_flows_group.commands.values()]

    def test_help_text(self):
        result = runner.invoke(ai_flows_group, ["debug", "--help"])
        assert result.exit_code == 0
        assert "AI Debugger" in result.output

    def test_options_in_help(self):
        result = runner.invoke(ai_flows_group, ["debug", "--help"])
        assert "--json" in result.output
        assert "--summary" in result.output
        assert "--query" in result.output
        assert "--model" in result.output
        assert "--route" in result.output


# ═══════════════════════════════════════════════════════════════════════════
# Text output
# ═══════════════════════════════════════════════════════════════════════════


class TestTextOutput:
    @patch("aksara.ai.project_graph.build_project_graph")
    def test_empty_report_text(self, mock_build):
        from aksara.ai.project_graph import ProjectGraph
        mock_build.return_value = ProjectGraph()

        result = runner.invoke(ai_flows_group, ["debug"])
        assert result.exit_code == 0
        assert "AI Debugger" in result.output
        assert "Issues:" in result.output

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_report_with_issues_text(self, mock_build):
        g = MagicMock()
        g.diagnostics = [MagicMock(code="DB_NO_URL", severity="error",
                                   message="No database URL set",
                                   related_models=[], related_routes=[], related_queries=[])]
        g.gaps = []
        g.events = []
        g.models = []
        g.routes = []
        g.queries = []
        g.migrations = []
        g.ai_hub = None
        m = MagicMock()
        m.model_count = 0
        m.route_count = 0
        m.query_count = 0
        m.migration_count = 0
        m.diagnostic_count = 1
        m.gap_count = 0
        m.event_count = 0
        g.metadata = m
        mock_build.return_value = g

        result = runner.invoke(ai_flows_group, ["debug"])
        assert result.exit_code == 0
        assert "Root Causes" in result.output or "Issues:" in result.output

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_failed_report_text(self, mock_build):
        mock_build.side_effect = RuntimeError("boom")

        result = runner.invoke(ai_flows_group, ["debug"])
        assert result.exit_code == 0
        assert "failed" in result.output.lower() or "graph" in result.output.lower()


# ═══════════════════════════════════════════════════════════════════════════
# JSON output
# ═══════════════════════════════════════════════════════════════════════════


class TestJsonOutput:
    @patch("aksara.ai.project_graph.build_project_graph")
    def test_json_flag(self, mock_build):
        from aksara.ai.project_graph import ProjectGraph
        mock_build.return_value = ProjectGraph()

        result = runner.invoke(ai_flows_group, ["debug", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "ok" in data
        assert "issues" in data

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_json_summary_flag(self, mock_build):
        from aksara.ai.project_graph import ProjectGraph
        mock_build.return_value = ProjectGraph()

        result = runner.invoke(ai_flows_group, ["debug", "--json", "--summary"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "ok" in data
        assert "top_root_causes" in data
        assert "issues" not in data  # summary dict has no full issues


# ═══════════════════════════════════════════════════════════════════════════
# Summary flag
# ═══════════════════════════════════════════════════════════════════════════


class TestSummaryOutput:
    @patch("aksara.ai.project_graph.build_project_graph")
    def test_summary_text(self, mock_build):
        from aksara.ai.project_graph import ProjectGraph
        mock_build.return_value = ProjectGraph()

        result = runner.invoke(ai_flows_group, ["debug", "--summary"])
        assert result.exit_code == 0
        # Summary output should NOT include detailed clusters
        assert "cluster-" not in result.output


# ═══════════════════════════════════════════════════════════════════════════
# Query option
# ═══════════════════════════════════════════════════════════════════════════


class TestQueryOption:
    @patch("aksara.ai.project_graph.build_project_graph")
    def test_query_param(self, mock_build):
        from aksara.ai.project_graph import ProjectGraph
        mock_build.return_value = ProjectGraph()

        result = runner.invoke(ai_flows_group, ["debug", "--query", "database issues"])
        assert result.exit_code == 0

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_model_filter(self, mock_build):
        from aksara.ai.project_graph import ProjectGraph
        mock_build.return_value = ProjectGraph()

        result = runner.invoke(ai_flows_group, ["debug", "--model", "User"])
        assert result.exit_code == 0

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_route_filter(self, mock_build):
        from aksara.ai.project_graph import ProjectGraph
        mock_build.return_value = ProjectGraph()

        result = runner.invoke(ai_flows_group, ["debug", "--route", "/api/users"])
        assert result.exit_code == 0

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_combined_filters(self, mock_build):
        from aksara.ai.project_graph import ProjectGraph
        mock_build.return_value = ProjectGraph()

        result = runner.invoke(ai_flows_group, ["debug", "--model", "User", "--route", "/api/users"])
        assert result.exit_code == 0


# ═══════════════════════════════════════════════════════════════════════════
# Output structure
# ═══════════════════════════════════════════════════════════════════════════


class TestOutputStructure:
    @patch("aksara.ai.project_graph.build_project_graph")
    def test_json_has_required_keys(self, mock_build):
        from aksara.ai.project_graph import ProjectGraph
        mock_build.return_value = ProjectGraph()

        result = runner.invoke(ai_flows_group, ["debug", "--json"])
        data = json.loads(result.output)
        for key in ("ok", "issues", "clusters", "root_causes",
                     "summary", "issue_count", "cluster_count",
                     "root_cause_count", "elapsed_ms", "generated_at"):
            assert key in data, f"Missing key: {key}"

    @patch("aksara.ai.project_graph.build_project_graph")
    def test_root_cause_shape(self, mock_build):
        g = MagicMock()
        g.diagnostics = [MagicMock(code="DB_NO_URL", severity="error",
                                   message="No database URL",
                                   related_models=[], related_routes=[], related_queries=[])]
        g.gaps = []
        g.events = []
        g.models = []
        g.routes = []
        g.queries = []
        g.migrations = []
        g.ai_hub = None
        m = MagicMock()
        m.model_count = m.route_count = m.query_count = 0
        m.migration_count = m.diagnostic_count = m.gap_count = m.event_count = 0
        m.diagnostic_count = 1
        g.metadata = m
        mock_build.return_value = g

        result = runner.invoke(ai_flows_group, ["debug", "--json"])
        data = json.loads(result.output)
        if data["root_causes"]:
            rc = data["root_causes"][0]
            assert "cause_id" in rc
            assert "title" in rc
            assert "confidence" in rc
            assert "fix_suggestions" in rc
