"""
Tests for CLI `aksara doctor` commands.

v0.5.17: Tests for doctor run, summary, ai, db subcommands.
"""

from __future__ import annotations

import json
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from click.testing import CliRunner

from aksara.cli.main import cli
from aksara.diagnostics import DiagnosticIssue, DiagnosticReport


def _make_report(errors=0, warnings=0, infos=0):
    """Create a DiagnosticReport with specified counts."""
    report = DiagnosticReport(
        system={"aksara_version": "0.5.17", "python_version": "3.12", "os": "Darwin 23", "arch": "arm64"},
        duration_ms=42.0,
    )
    for i in range(errors):
        report.add(DiagnosticIssue(kind="general", severity="error", title=f"Error {i+1}", message=f"Error message {i+1}"))
    for i in range(warnings):
        report.add(DiagnosticIssue(kind="security_warning", severity="warning", title=f"Warning {i+1}", message=f"Warning message {i+1}", hint=f"Fix warning {i+1}"))
    for i in range(infos):
        report.add(DiagnosticIssue(kind="cache_unavailable", severity="info", title=f"Info {i+1}", message=f"Info message {i+1}"))
    return report


def _make_issues(kinds_severities):
    """Create a list of DiagnosticIssue from (kind, severity) tuples."""
    return [
        DiagnosticIssue(kind=k, severity=s, title=f"Title for {k}", message=f"Message for {k}", hint=f"Hint for {k}")
        for k, s in kinds_severities
    ]


class TestDoctorGroup:
    """Test the doctor command group exists and is accessible."""

    def test_doctor_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["doctor", "--help"])
        assert result.exit_code == 0
        assert "Self-diagnostics" in result.output or "health checks" in result.output

    def test_doctor_run_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["doctor", "run", "--help"])
        assert result.exit_code == 0
        assert "--format" in result.output

    def test_doctor_summary_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["doctor", "summary", "--help"])
        assert result.exit_code == 0

    def test_doctor_ai_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["doctor", "ai", "--help"])
        assert result.exit_code == 0

    def test_doctor_db_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["doctor", "db", "--help"])
        assert result.exit_code == 0


class TestDoctorRun:
    """Tests for `aksara doctor run`."""

    def test_run_pretty_all_clear(self):
        report = _make_report(errors=0, warnings=0, infos=0)
        with patch("aksara.diagnostics.run_all_checks", new_callable=AsyncMock, return_value=report):
            runner = CliRunner()
            result = runner.invoke(cli, ["doctor", "run"])
        assert result.exit_code == 0
        assert "ALL CLEAR" in result.output or "everything looks good" in result.output

    def test_run_pretty_with_errors(self):
        report = _make_report(errors=2, warnings=1, infos=1)
        with patch("aksara.diagnostics.run_all_checks", new_callable=AsyncMock, return_value=report):
            runner = CliRunner()
            result = runner.invoke(cli, ["doctor", "run"])
        assert result.exit_code == 1
        assert "ERRORS FOUND" in result.output
        assert "Error 1" in result.output

    def test_run_pretty_warnings_only(self):
        report = _make_report(errors=0, warnings=2, infos=0)
        with patch("aksara.diagnostics.run_all_checks", new_callable=AsyncMock, return_value=report):
            runner = CliRunner()
            result = runner.invoke(cli, ["doctor", "run"])
        assert result.exit_code == 0
        assert "WARNINGS" in result.output

    def test_run_json_format(self):
        report = _make_report(errors=1, warnings=1, infos=1)
        with patch("aksara.diagnostics.run_all_checks", new_callable=AsyncMock, return_value=report):
            runner = CliRunner()
            result = runner.invoke(cli, ["doctor", "run", "--format", "json"])
        # Exit code 1 due to errors
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert "issues" in data
        assert "stats" in data
        assert data["stats"]["errors"] == 1

    def test_run_json_no_errors_exit_0(self):
        report = _make_report(errors=0, warnings=3, infos=2)
        with patch("aksara.diagnostics.run_all_checks", new_callable=AsyncMock, return_value=report):
            runner = CliRunner()
            result = runner.invoke(cli, ["doctor", "run", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["stats"]["errors"] == 0
        assert data["stats"]["warnings"] == 3

    def test_run_shows_hints(self):
        report = _make_report(errors=0, warnings=1, infos=0)
        with patch("aksara.diagnostics.run_all_checks", new_callable=AsyncMock, return_value=report):
            runner = CliRunner()
            result = runner.invoke(cli, ["doctor", "run"])
        assert "Hint:" in result.output or "Fix warning" in result.output

    def test_run_shows_system_info(self):
        report = _make_report(errors=0, warnings=0, infos=1)
        with patch("aksara.diagnostics.run_all_checks", new_callable=AsyncMock, return_value=report):
            runner = CliRunner()
            result = runner.invoke(cli, ["doctor", "run"])
        assert "0.5.17" in result.output
        assert "3.12" in result.output

    def test_run_shows_duration(self):
        report = _make_report(errors=0, warnings=0, infos=1)
        with patch("aksara.diagnostics.run_all_checks", new_callable=AsyncMock, return_value=report):
            runner = CliRunner()
            result = runner.invoke(cli, ["doctor", "run"])
        assert "42" in result.output or "ms" in result.output


class TestDoctorSummary:
    """Tests for `aksara doctor summary`."""

    def test_summary_all_clear(self):
        report = _make_report(errors=0, warnings=0, infos=0)
        with patch("aksara.diagnostics.run_all_checks", new_callable=AsyncMock, return_value=report):
            runner = CliRunner()
            result = runner.invoke(cli, ["doctor", "summary"])
        assert result.exit_code == 0
        assert "everything looks good" in result.output.lower() or "no issues" in result.output.lower()

    def test_summary_categorized(self):
        report = DiagnosticReport(duration_ms=10.0)
        report.add(DiagnosticIssue(kind="database_connectivity", severity="error", title="DB down", message="m"))
        report.add(DiagnosticIssue(kind="database_connectivity", severity="warning", title="DB slow", message="m"))
        report.add(DiagnosticIssue(kind="security_warning", severity="warning", title="Debug on", message="m"))
        with patch("aksara.diagnostics.run_all_checks", new_callable=AsyncMock, return_value=report):
            runner = CliRunner()
            result = runner.invoke(cli, ["doctor", "summary"])
        assert result.exit_code == 0
        assert "Database Connectivity" in result.output
        assert "Security Warning" in result.output

    def test_summary_shows_total(self):
        report = _make_report(errors=2, warnings=3, infos=1)
        with patch("aksara.diagnostics.run_all_checks", new_callable=AsyncMock, return_value=report):
            runner = CliRunner()
            result = runner.invoke(cli, ["doctor", "summary"])
        assert "2 errors" in result.output
        assert "3 warnings" in result.output


class TestDoctorAi:
    """Tests for `aksara doctor ai`."""

    def test_ai_no_issues(self):
        with patch("aksara.diagnostics.check_ai_profiles", new_callable=AsyncMock, return_value=[]):
            with patch("aksara.diagnostics.check_ai_provider_secrets", new_callable=AsyncMock, return_value=[]):
                with patch("aksara.diagnostics.check_ai_hub_config", new_callable=AsyncMock, return_value=[]):
                    runner = CliRunner()
                    result = runner.invoke(cli, ["doctor", "ai"])
        assert result.exit_code == 0
        assert "No AI issues" in result.output

    def test_ai_with_issues(self):
        issues = _make_issues([("ai_secret_missing", "warning"), ("ai_profile_issue", "info")])
        with patch("aksara.diagnostics.check_ai_profiles", new_callable=AsyncMock, return_value=[issues[1]]):
            with patch("aksara.diagnostics.check_ai_provider_secrets", new_callable=AsyncMock, return_value=[issues[0]]):
                runner = CliRunner()
                result = runner.invoke(cli, ["doctor", "ai"])
        assert result.exit_code == 0
        assert "ai_secret_missing" in result.output or "Title for ai_secret_missing" in result.output

    def test_ai_shows_hints(self):
        issues = _make_issues([("ai_secret_missing", "warning")])
        with patch("aksara.diagnostics.check_ai_profiles", new_callable=AsyncMock, return_value=[]):
            with patch("aksara.diagnostics.check_ai_provider_secrets", new_callable=AsyncMock, return_value=issues):
                runner = CliRunner()
                result = runner.invoke(cli, ["doctor", "ai"])
        assert "Hint:" in result.output


class TestDoctorDb:
    """Tests for `aksara doctor db`."""

    def test_db_no_issues(self):
        with patch("aksara.diagnostics.check_database_connectivity", new_callable=AsyncMock, return_value=[]):
            with patch("aksara.diagnostics.check_migrations_status", new_callable=AsyncMock, return_value=[]):
                runner = CliRunner()
                result = runner.invoke(cli, ["doctor", "db"])
        assert result.exit_code == 0
        assert "No database issues" in result.output

    def test_db_with_issues(self):
        issues = _make_issues([("database_connectivity", "error"), ("migrations_pending", "warning")])
        with patch("aksara.diagnostics.check_database_connectivity", new_callable=AsyncMock, return_value=[issues[0]]):
            with patch("aksara.diagnostics.check_migrations_status", new_callable=AsyncMock, return_value=[issues[1]]):
                runner = CliRunner()
                result = runner.invoke(cli, ["doctor", "db"])
        assert result.exit_code == 0
        assert "database_connectivity" in result.output or "Title for database_connectivity" in result.output

    def test_db_shows_hints(self):
        issues = _make_issues([("database_connectivity", "error")])
        with patch("aksara.diagnostics.check_database_connectivity", new_callable=AsyncMock, return_value=issues):
            with patch("aksara.diagnostics.check_migrations_status", new_callable=AsyncMock, return_value=[]):
                runner = CliRunner()
                result = runner.invoke(cli, ["doctor", "db"])
        assert "Hint:" in result.output
