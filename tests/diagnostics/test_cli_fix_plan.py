"""
Tests for CLI `aksara doctor fix-plan` subcommand.

v0.5.18: Tests for the autoremediation fix-plan CLI output.
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, patch

from click.testing import CliRunner

from aksara.cli.main import cli
from aksara.diagnostics import (
    DiagnosticIssue,
    DiagnosticReport,
    build_action,
)


def _make_report(issues=None):
    """Create a DiagnosticReport with optional issues."""
    report = DiagnosticReport(
        system={"aksara_version": "0.5.18", "python_version": "3.12", "os": "Darwin 23", "arch": "arm64"},
        duration_ms=42.0,
    )
    for issue in (issues or []):
        report.add(issue)
    return report


def _issue_with_actions(severity="error", title="Test Issue", actions=None):
    """Create a DiagnosticIssue with optional actions."""
    return DiagnosticIssue(
        kind="settings_invalid",
        severity=severity,
        title=title,
        message=f"Message for {title}",
        hint=f"Hint for {title}",
        actions=actions or [],
    )


# =============================================================================
# fix-plan subcommand existence and help
# =============================================================================


class TestFixPlanHelp:
    """Basic fix-plan subcommand tests."""

    def test_fix_plan_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["doctor", "fix-plan", "--help"])
        assert result.exit_code == 0
        assert "fix-plan" in result.output or "fix" in result.output
        assert "--format" in result.output
        assert "--only-errors" in result.output
        assert "--only-with-actions" in result.output

    def test_fix_plan_exists_in_doctor_group(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["doctor", "--help"])
        assert result.exit_code == 0
        assert "fix-plan" in result.output


# =============================================================================
# fix-plan text output
# =============================================================================


class TestFixPlanTextOutput:
    """Tests for fix-plan text (default) format."""

    def test_no_issues_shows_clear(self):
        report = _make_report()
        with patch("aksara.diagnostics.run_all_checks", new_callable=AsyncMock, return_value=report):
            runner = CliRunner()
            result = runner.invoke(cli, ["doctor", "fix-plan"])
        assert result.exit_code == 0
        assert "no issues" in result.output.lower() or "No issues" in result.output

    def test_shows_issue_title(self):
        report = _make_report(issues=[
            _issue_with_actions(severity="warning", title="Debug Mode Enabled"),
        ])
        with patch("aksara.diagnostics.run_all_checks", new_callable=AsyncMock, return_value=report):
            runner = CliRunner()
            result = runner.invoke(cli, ["doctor", "fix-plan"])
        assert "Debug Mode Enabled" in result.output

    def test_shows_actions_in_text(self):
        report = _make_report(issues=[
            _issue_with_actions(
                severity="error", title="No DB",
                actions=[
                    build_action(kind="set_env", target="DATABASE_URL", title="Set DB URL",
                                 example='export DATABASE_URL="postgres://..."'),
                ],
            ),
        ])
        with patch("aksara.diagnostics.run_all_checks", new_callable=AsyncMock, return_value=report):
            runner = CliRunner()
            result = runner.invoke(cli, ["doctor", "fix-plan"])
        assert "ENV" in result.output
        assert "Set DB URL" in result.output
        assert "export DATABASE_URL" in result.output

    def test_shows_no_actions_note(self):
        report = _make_report(issues=[
            _issue_with_actions(severity="info", title="Informational"),
        ])
        with patch("aksara.diagnostics.run_all_checks", new_callable=AsyncMock, return_value=report):
            runner = CliRunner()
            result = runner.invoke(cli, ["doctor", "fix-plan"])
        assert "no fix actions" in result.output.lower()

    def test_exit_code_1_for_errors(self):
        report = _make_report(issues=[
            _issue_with_actions(severity="error", title="Bad"),
        ])
        with patch("aksara.diagnostics.run_all_checks", new_callable=AsyncMock, return_value=report):
            runner = CliRunner()
            result = runner.invoke(cli, ["doctor", "fix-plan"])
        assert result.exit_code == 1

    def test_exit_code_0_for_warnings_only(self):
        report = _make_report(issues=[
            _issue_with_actions(severity="warning", title="Meh"),
        ])
        with patch("aksara.diagnostics.run_all_checks", new_callable=AsyncMock, return_value=report):
            runner = CliRunner()
            result = runner.invoke(cli, ["doctor", "fix-plan"])
        assert result.exit_code == 0

    def test_multiple_issues_numbered(self):
        report = _make_report(issues=[
            _issue_with_actions(severity="error", title="Issue A"),
            _issue_with_actions(severity="warning", title="Issue B"),
        ])
        with patch("aksara.diagnostics.run_all_checks", new_callable=AsyncMock, return_value=report):
            runner = CliRunner()
            result = runner.invoke(cli, ["doctor", "fix-plan"])
        assert "1." in result.output
        assert "2." in result.output

    def test_summary_line_shows_counts(self):
        report = _make_report(issues=[
            _issue_with_actions(
                severity="error", title="E",
                actions=[build_action(kind="set_env", target="X", title="Set X")],
            ),
        ])
        with patch("aksara.diagnostics.run_all_checks", new_callable=AsyncMock, return_value=report):
            runner = CliRunner()
            result = runner.invoke(cli, ["doctor", "fix-plan"])
        assert "1 issue" in result.output
        assert "1 fix action" in result.output


# =============================================================================
# fix-plan JSON output
# =============================================================================


class TestFixPlanJsonOutput:
    """Tests for fix-plan --format json."""

    def test_json_output_structure(self):
        report = _make_report(issues=[
            _issue_with_actions(
                severity="error", title="No DB",
                actions=[
                    build_action(kind="set_env", target="DATABASE_URL", title="Set DB"),
                ],
            ),
        ])
        with patch("aksara.diagnostics.run_all_checks", new_callable=AsyncMock, return_value=report):
            runner = CliRunner()
            result = runner.invoke(cli, ["doctor", "fix-plan", "--format", "json"])
        data = json.loads(result.output)
        assert "issues" in data
        assert "stats" in data
        assert "duration_ms" in data
        assert "system" in data

    def test_json_contains_actions(self):
        report = _make_report(issues=[
            _issue_with_actions(
                severity="warning", title="Test",
                actions=[
                    build_action(kind="run_command", target="pip install x", title="Install",
                                 example="pip install x"),
                ],
            ),
        ])
        with patch("aksara.diagnostics.run_all_checks", new_callable=AsyncMock, return_value=report):
            runner = CliRunner()
            result = runner.invoke(cli, ["doctor", "fix-plan", "--format", "json"])
        data = json.loads(result.output)
        actions = data["issues"][0]["actions"]
        assert len(actions) == 1
        assert actions[0]["kind"] == "run_command"
        assert actions[0]["example"] == "pip install x"

    def test_json_empty_actions(self):
        report = _make_report(issues=[
            _issue_with_actions(severity="info", title="No actions"),
        ])
        with patch("aksara.diagnostics.run_all_checks", new_callable=AsyncMock, return_value=report):
            runner = CliRunner()
            result = runner.invoke(cli, ["doctor", "fix-plan", "--format", "json"])
        data = json.loads(result.output)
        assert data["issues"][0]["actions"] == []


# =============================================================================
# fix-plan filters
# =============================================================================


class TestFixPlanFilters:
    """Tests for --only-errors and --only-with-actions flags."""

    def test_only_errors_filters_warnings(self):
        report = _make_report(issues=[
            _issue_with_actions(severity="error", title="Error Issue"),
            _issue_with_actions(severity="warning", title="Warning Issue"),
            _issue_with_actions(severity="info", title="Info Issue"),
        ])
        with patch("aksara.diagnostics.run_all_checks", new_callable=AsyncMock, return_value=report):
            runner = CliRunner()
            result = runner.invoke(cli, ["doctor", "fix-plan", "--only-errors"])
        assert "Error Issue" in result.output
        assert "Warning Issue" not in result.output
        assert "Info Issue" not in result.output

    def test_only_with_actions_filters_no_actions(self):
        report = _make_report(issues=[
            _issue_with_actions(
                severity="error", title="Has Actions",
                actions=[build_action(kind="set_env", target="X", title="A")],
            ),
            _issue_with_actions(severity="warning", title="No Actions"),
        ])
        with patch("aksara.diagnostics.run_all_checks", new_callable=AsyncMock, return_value=report):
            runner = CliRunner()
            result = runner.invoke(cli, ["doctor", "fix-plan", "--only-with-actions"])
        assert "Has Actions" in result.output
        assert "No Actions" not in result.output

    def test_both_filters_combined(self):
        report = _make_report(issues=[
            _issue_with_actions(
                severity="error", title="Error With Action",
                actions=[build_action(kind="set_env", target="X", title="A")],
            ),
            _issue_with_actions(severity="error", title="Error No Action"),
            _issue_with_actions(
                severity="warning", title="Warning With Action",
                actions=[build_action(kind="run_command", target="x", title="B")],
            ),
        ])
        with patch("aksara.diagnostics.run_all_checks", new_callable=AsyncMock, return_value=report):
            runner = CliRunner()
            result = runner.invoke(cli, ["doctor", "fix-plan", "--only-errors", "--only-with-actions"])
        assert "Error With Action" in result.output
        assert "Error No Action" not in result.output
        assert "Warning With Action" not in result.output

    def test_only_errors_json_format(self):
        report = _make_report(issues=[
            _issue_with_actions(severity="error", title="E1"),
            _issue_with_actions(severity="warning", title="W1"),
        ])
        with patch("aksara.diagnostics.run_all_checks", new_callable=AsyncMock, return_value=report):
            runner = CliRunner()
            result = runner.invoke(cli, ["doctor", "fix-plan", "--format", "json", "--only-errors"])
        data = json.loads(result.output)
        assert len(data["issues"]) == 1
        assert data["issues"][0]["title"] == "E1"

    def test_no_matching_issues_shows_filter_note(self):
        report = _make_report(issues=[
            _issue_with_actions(severity="info", title="Info only"),
        ])
        with patch("aksara.diagnostics.run_all_checks", new_callable=AsyncMock, return_value=report):
            runner = CliRunner()
            result = runner.invoke(cli, ["doctor", "fix-plan", "--only-errors"])
        assert result.exit_code == 0
        assert "no issues" in result.output.lower() or "No issues" in result.output


# =============================================================================
# doctor run now shows actions
# =============================================================================


class TestDoctorRunActions:
    """Tests that doctor run shows actions in pretty output."""

    def test_doctor_run_shows_action_kind_labels(self):
        report = _make_report(issues=[
            _issue_with_actions(
                severity="error", title="Missing DB",
                actions=[
                    build_action(kind="set_env", target="DATABASE_URL",
                                 title="Set DB URL", example='export DATABASE_URL="x"'),
                ],
            ),
        ])
        with patch("aksara.diagnostics.run_all_checks", new_callable=AsyncMock, return_value=report):
            runner = CliRunner()
            result = runner.invoke(cli, ["doctor", "run"])
        assert "ENV" in result.output
        assert "Set DB URL" in result.output

    def test_doctor_run_shows_action_example(self):
        report = _make_report(issues=[
            _issue_with_actions(
                severity="warning", title="Cache Missing",
                actions=[
                    build_action(kind="run_command", target="redis-server",
                                 title="Start Redis", example="redis-server --port 6379"),
                ],
            ),
        ])
        with patch("aksara.diagnostics.run_all_checks", new_callable=AsyncMock, return_value=report):
            runner = CliRunner()
            result = runner.invoke(cli, ["doctor", "run"])
        assert "redis-server --port 6379" in result.output
