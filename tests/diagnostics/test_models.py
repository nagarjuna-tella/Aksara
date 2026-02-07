"""
Tests for Diagnostic Models (DiagnosticIssue, DiagnosticReport).

v0.5.17: 25+ tests covering model creation, validation, serialization,
stats tracking, and edge cases.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from aksara.diagnostics import (
    DiagnosticIssue,
    DiagnosticReport,
)


# =============================================================================
# DiagnosticIssue Model Tests
# =============================================================================


class TestDiagnosticIssue:
    """Tests for the DiagnosticIssue Pydantic model."""

    def test_create_minimal(self):
        issue = DiagnosticIssue(
            kind="general",
            severity="info",
            title="Test",
            message="A test message",
        )
        assert issue.kind == "general"
        assert issue.severity == "info"
        assert issue.title == "Test"
        assert issue.message == "A test message"
        assert issue.hint is None
        assert issue.meta is None

    def test_create_full(self):
        issue = DiagnosticIssue(
            kind="database_connectivity",
            severity="error",
            title="DB down",
            message="Cannot connect",
            hint="Check your DATABASE_URL",
            meta={"host": "localhost", "port": 5432},
        )
        assert issue.kind == "database_connectivity"
        assert issue.severity == "error"
        assert issue.hint == "Check your DATABASE_URL"
        assert issue.meta["host"] == "localhost"
        assert issue.meta["port"] == 5432

    def test_severity_info(self):
        issue = DiagnosticIssue(kind="general", severity="info", title="t", message="m")
        assert issue.severity == "info"

    def test_severity_warning(self):
        issue = DiagnosticIssue(kind="general", severity="warning", title="t", message="m")
        assert issue.severity == "warning"

    def test_severity_error(self):
        issue = DiagnosticIssue(kind="general", severity="error", title="t", message="m")
        assert issue.severity == "error"

    def test_all_valid_kinds(self):
        kinds = [
            "database_connectivity", "database_schema", "migrations_pending",
            "migrations_conflict", "ai_provider_missing", "ai_provider_invalid",
            "ai_secret_missing", "ai_profile_issue", "env_missing",
            "settings_invalid", "cache_unavailable", "file_system_unwritable",
            "security_warning", "general",
        ]
        for kind in kinds:
            issue = DiagnosticIssue(kind=kind, severity="info", title="t", message="m")
            assert issue.kind == kind

    def test_serialization_roundtrip(self):
        issue = DiagnosticIssue(
            kind="security_warning",
            severity="warning",
            title="Debug on",
            message="Debug is enabled",
            hint="Disable in production",
            meta={"debug": True},
        )
        data = issue.model_dump()
        restored = DiagnosticIssue(**data)
        assert restored == issue

    def test_json_serialization(self):
        issue = DiagnosticIssue(
            kind="general", severity="info", title="t", message="m"
        )
        json_str = issue.model_dump_json()
        assert '"kind":"general"' in json_str or '"kind": "general"' in json_str

    def test_meta_none_by_default(self):
        issue = DiagnosticIssue(kind="general", severity="info", title="t", message="m")
        assert issue.meta is None

    def test_meta_complex_dict(self):
        issue = DiagnosticIssue(
            kind="general", severity="info", title="t", message="m",
            meta={"list": [1, 2, 3], "nested": {"a": "b"}, "count": 42},
        )
        assert issue.meta["list"] == [1, 2, 3]
        assert issue.meta["nested"]["a"] == "b"

    def test_empty_string_fields(self):
        issue = DiagnosticIssue(kind="", severity="info", title="", message="")
        assert issue.kind == ""
        assert issue.title == ""
        assert issue.message == ""


# =============================================================================
# DiagnosticReport Model Tests
# =============================================================================


class TestDiagnosticReport:
    """Tests for the DiagnosticReport Pydantic model."""

    def test_create_empty(self):
        report = DiagnosticReport()
        assert report.issues == []
        assert report.stats == {"errors": 0, "warnings": 0, "info": 0}
        assert report.duration_ms == 0.0
        assert isinstance(report.timestamp, datetime)
        assert report.system == {}

    def test_add_error(self):
        report = DiagnosticReport()
        report.add(DiagnosticIssue(kind="general", severity="error", title="E", message="err"))
        assert len(report.issues) == 1
        assert report.stats["errors"] == 1
        assert report.stats["warnings"] == 0
        assert report.stats["info"] == 0

    def test_add_warning(self):
        report = DiagnosticReport()
        report.add(DiagnosticIssue(kind="general", severity="warning", title="W", message="warn"))
        assert report.stats["warnings"] == 1

    def test_add_info(self):
        report = DiagnosticReport()
        report.add(DiagnosticIssue(kind="general", severity="info", title="I", message="info"))
        assert report.stats["info"] == 1

    def test_add_multiple(self):
        report = DiagnosticReport()
        report.add(DiagnosticIssue(kind="a", severity="error", title="E1", message="e1"))
        report.add(DiagnosticIssue(kind="b", severity="error", title="E2", message="e2"))
        report.add(DiagnosticIssue(kind="c", severity="warning", title="W1", message="w1"))
        report.add(DiagnosticIssue(kind="d", severity="info", title="I1", message="i1"))
        assert len(report.issues) == 4
        assert report.stats["errors"] == 2
        assert report.stats["warnings"] == 1
        assert report.stats["info"] == 1

    def test_has_errors_true(self):
        report = DiagnosticReport()
        report.add(DiagnosticIssue(kind="a", severity="error", title="E", message="e"))
        assert report.has_errors is True

    def test_has_errors_false_empty(self):
        report = DiagnosticReport()
        assert report.has_errors is False

    def test_has_errors_false_warnings_only(self):
        report = DiagnosticReport()
        report.add(DiagnosticIssue(kind="a", severity="warning", title="W", message="w"))
        assert report.has_errors is False

    def test_overall_status_ok(self):
        report = DiagnosticReport()
        assert report.overall_status == "ok"

    def test_overall_status_warning(self):
        report = DiagnosticReport()
        report.add(DiagnosticIssue(kind="a", severity="warning", title="W", message="w"))
        assert report.overall_status == "warning"

    def test_overall_status_error(self):
        report = DiagnosticReport()
        report.add(DiagnosticIssue(kind="a", severity="error", title="E", message="e"))
        assert report.overall_status == "error"

    def test_overall_status_error_overrides_warning(self):
        report = DiagnosticReport()
        report.add(DiagnosticIssue(kind="a", severity="warning", title="W", message="w"))
        report.add(DiagnosticIssue(kind="b", severity="error", title="E", message="e"))
        assert report.overall_status == "error"

    def test_system_metadata(self):
        report = DiagnosticReport(system={"aksara_version": "0.5.17", "python_version": "3.12"})
        assert report.system["aksara_version"] == "0.5.17"

    def test_duration_ms(self):
        report = DiagnosticReport(duration_ms=42.5)
        assert report.duration_ms == 42.5

    def test_timestamp_utc(self):
        report = DiagnosticReport()
        assert report.timestamp.tzinfo is not None

    def test_serialization_roundtrip(self):
        report = DiagnosticReport(
            system={"aksara_version": "0.5.17"},
            duration_ms=10.0,
        )
        report.add(DiagnosticIssue(kind="a", severity="error", title="E", message="e"))
        report.add(DiagnosticIssue(kind="b", severity="info", title="I", message="i"))
        data = report.model_dump()
        restored = DiagnosticReport(**data)
        assert len(restored.issues) == 2
        assert restored.stats["errors"] == 1
        assert restored.system["aksara_version"] == "0.5.17"

    def test_json_output(self):
        report = DiagnosticReport()
        json_str = report.model_dump_json()
        assert "issues" in json_str
        assert "stats" in json_str
