"""
v0.5.45 — CLI ``aksara ai investigate`` tests.

Tests cover:
    - Command help text
    - Text rendering for successful investigations
    - JSON summary output stays machine-readable
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

from click.testing import CliRunner

from aksara.cli.main import cli


runner = CliRunner()


class _FakeInvestigationResult:
    """Minimal investigation result object for CLI tests."""

    def __init__(self, *, ok: bool = True):
        self.ok = ok
        self.summary = "System looks mostly healthy"
        self.elapsed_ms = 321.0
        self.step_results = [
            SimpleNamespace(step="build_project_graph", ok=True, elapsed_ms=100.0),
            SimpleNamespace(step="run_architecture_review", ok=True, elapsed_ms=110.0),
            SimpleNamespace(step="run_performance_analysis", ok=True, elapsed_ms=111.0),
        ]
        self.report = {
            "architecture_report": {"grade": "B", "score": 84, "finding_count": 2},
            "performance_report": {
                "grade": "A",
                "score": 91,
                "issue_count": 1,
                "top_issues": [{"title": "Slow query on audit log"}],
            },
            "debug_report": {
                "root_cause_count": 1,
                "top_root_causes": [{"title": "Missing index", "confidence": 0.9}],
            },
            "diagnostic_count": 3,
            "gap_count": 1,
            "graph_summary": {
                "counts": {"models": 5, "routes": 8, "queries": 12, "migrations": 4}
            },
        }

    def to_dict(self):
        return {
            "ok": self.ok,
            "summary": self.summary,
            "elapsed_ms": self.elapsed_ms,
            "report": self.report,
            "step_results": [
                {"step": step.step, "ok": step.ok, "elapsed_ms": step.elapsed_ms}
                for step in self.step_results
            ],
        }

    def to_summary_dict(self):
        return {
            "ok": self.ok,
            "summary": self.summary,
            "elapsed_ms": self.elapsed_ms,
            "step_count": len(self.step_results),
        }


class TestAiInvestigateCommand:
    """Test the investigate CLI command."""

    def test_help(self):
        result = runner.invoke(cli, ["ai", "investigate", "--help"])

        assert result.exit_code == 0
        assert "System Intelligence Report" in result.output or "investigate" in result.output.lower()

    def test_text_output(self):
        fake_result = _FakeInvestigationResult()

        with patch("aksara.ai.intent_engine.run_investigation", return_value=fake_result):
            result = runner.invoke(cli, ["ai", "investigate"])

        assert result.exit_code == 0
        assert "System Intelligence Report" in result.output
        assert "Pipeline:" in result.output
        assert "Architecture Score" in result.output
        assert "Performance Score" in result.output

    def test_json_summary_output(self):
        fake_result = _FakeInvestigationResult()

        with patch("aksara.ai.intent_engine.run_investigation", return_value=fake_result):
            result = runner.invoke(cli, ["ai", "investigate", "--json", "--summary"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["step_count"] == 3