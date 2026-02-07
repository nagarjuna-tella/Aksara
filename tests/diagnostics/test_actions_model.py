"""
Tests for DiagnosticAction model and build_action helper.

v0.5.18: 20+ tests for the autoremediation action data model.
"""

from __future__ import annotations

import json
import pytest

from aksara.diagnostics import (
    DiagnosticAction,
    DiagnosticIssue,
    DiagnosticReport,
    build_action,
)


# =============================================================================
# DiagnosticAction Model
# =============================================================================


class TestDiagnosticAction:
    """Tests for the DiagnosticAction Pydantic model."""

    def test_create_minimal(self):
        action = DiagnosticAction(kind="set_env", target="FOO", title="Set FOO")
        assert action.kind == "set_env"
        assert action.target == "FOO"
        assert action.title == "Set FOO"
        assert action.example is None
        assert action.description is None

    def test_create_full(self):
        action = DiagnosticAction(
            kind="run_command",
            target="pip install foo",
            title="Install foo",
            example="pip install foo",
            description="Installs the foo package",
        )
        assert action.kind == "run_command"
        assert action.target == "pip install foo"
        assert action.title == "Install foo"
        assert action.example == "pip install foo"
        assert action.description == "Installs the foo package"

    def test_kind_set_env(self):
        a = DiagnosticAction(kind="set_env", target="X", title="t")
        assert a.kind == "set_env"

    def test_kind_edit_file(self):
        a = DiagnosticAction(kind="edit_file", target="f.py", title="t")
        assert a.kind == "edit_file"

    def test_kind_run_command(self):
        a = DiagnosticAction(kind="run_command", target="ls", title="t")
        assert a.kind == "run_command"

    def test_kind_open_doc(self):
        a = DiagnosticAction(kind="open_doc", target="https://docs.example.com", title="t")
        assert a.kind == "open_doc"

    def test_kind_add_setting(self):
        a = DiagnosticAction(kind="add_setting", target="pool_max_size", title="t")
        assert a.kind == "add_setting"

    def test_serialization_json(self):
        a = DiagnosticAction(
            kind="set_env", target="DB", title="Set DB",
            example='export DB="x"',
        )
        data = json.loads(a.model_dump_json())
        assert data["kind"] == "set_env"
        assert data["target"] == "DB"
        assert data["title"] == "Set DB"
        assert "export" in data["example"]
        assert data["description"] is None

    def test_model_dump(self):
        a = DiagnosticAction(kind="run_command", target="ls", title="list")
        d = a.model_dump()
        assert isinstance(d, dict)
        assert d["kind"] == "run_command"
        assert d["target"] == "ls"


# =============================================================================
# build_action helper
# =============================================================================


class TestBuildAction:
    """Tests for the build_action() convenience function."""

    def test_build_minimal(self):
        a = build_action(kind="set_env", target="X", title="Set X")
        assert isinstance(a, DiagnosticAction)
        assert a.kind == "set_env"
        assert a.target == "X"
        assert a.title == "Set X"
        assert a.example is None
        assert a.description is None

    def test_build_with_example(self):
        a = build_action(
            kind="run_command", target="pip install x",
            title="Install x", example="pip install x",
        )
        assert a.example == "pip install x"

    def test_build_with_description(self):
        a = build_action(
            kind="open_doc", target="https://example.com",
            title="Read docs", description="Full documentation",
        )
        assert a.description == "Full documentation"

    def test_build_all_fields(self):
        a = build_action(
            kind="edit_file",
            target="settings.py",
            title="Edit settings",
            example="vi settings.py",
            description="Open and edit",
        )
        assert a.kind == "edit_file"
        assert a.target == "settings.py"
        assert a.title == "Edit settings"
        assert a.example == "vi settings.py"
        assert a.description == "Open and edit"

    def test_returns_diagnostic_action(self):
        a = build_action(kind="add_setting", target="k", title="t")
        assert type(a).__name__ == "DiagnosticAction"


# =============================================================================
# DiagnosticIssue with actions field
# =============================================================================


class TestDiagnosticIssueActions:
    """Tests for the actions field on DiagnosticIssue."""

    def test_default_empty_actions(self):
        issue = DiagnosticIssue(
            kind="general", severity="info", title="t", message="m",
        )
        assert issue.actions == []

    def test_issue_with_single_action(self):
        action = build_action(kind="set_env", target="X", title="Set X")
        issue = DiagnosticIssue(
            kind="settings_invalid", severity="error",
            title="Missing X", message="X is not set",
            actions=[action],
        )
        assert len(issue.actions) == 1
        assert issue.actions[0].kind == "set_env"

    def test_issue_with_multiple_actions(self):
        a1 = build_action(kind="set_env", target="A", title="Set A")
        a2 = build_action(kind="open_doc", target="https://docs", title="Docs")
        a3 = build_action(kind="run_command", target="cmd", title="Run")
        issue = DiagnosticIssue(
            kind="general", severity="warning",
            title="Multi", message="Multiple fixes",
            actions=[a1, a2, a3],
        )
        assert len(issue.actions) == 3
        assert [a.kind for a in issue.actions] == ["set_env", "open_doc", "run_command"]

    def test_issue_actions_serialization(self):
        action = build_action(kind="run_command", target="x", title="Run x", example="x")
        issue = DiagnosticIssue(
            kind="general", severity="info", title="t", message="m",
            actions=[action],
        )
        data = json.loads(issue.model_dump_json())
        assert "actions" in data
        assert len(data["actions"]) == 1
        assert data["actions"][0]["kind"] == "run_command"
        assert data["actions"][0]["example"] == "x"

    def test_issue_empty_actions_serialization(self):
        issue = DiagnosticIssue(kind="general", severity="info", title="t", message="m")
        data = issue.model_dump()
        assert data["actions"] == []


# =============================================================================
# DiagnosticReport with action-bearing issues
# =============================================================================


class TestDiagnosticReportActions:
    """Tests for DiagnosticReport containing issues with actions."""

    def test_report_add_issue_with_actions(self):
        report = DiagnosticReport()
        issue = DiagnosticIssue(
            kind="general", severity="error", title="err", message="msg",
            actions=[build_action(kind="set_env", target="X", title="Set X")],
        )
        report.add(issue)
        assert len(report.issues) == 1
        assert len(report.issues[0].actions) == 1

    def test_report_serialization_includes_actions(self):
        report = DiagnosticReport()
        report.add(DiagnosticIssue(
            kind="general", severity="info", title="t", message="m",
            actions=[
                build_action(kind="open_doc", target="https://docs.example.com", title="Docs"),
            ],
        ))
        data = json.loads(report.model_dump_json())
        assert data["issues"][0]["actions"][0]["kind"] == "open_doc"

    def test_report_mixed_issues(self):
        """Issues with and without actions coexist in a report."""
        report = DiagnosticReport()
        report.add(DiagnosticIssue(kind="general", severity="info", title="no-action", message="m"))
        report.add(DiagnosticIssue(
            kind="general", severity="warning", title="with-action", message="m2",
            actions=[build_action(kind="run_command", target="x", title="Run x")],
        ))
        assert len(report.issues) == 2
        assert report.issues[0].actions == []
        assert len(report.issues[1].actions) == 1
