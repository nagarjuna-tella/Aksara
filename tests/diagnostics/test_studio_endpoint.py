"""
Tests for the Studio /studio/diagnostics endpoint.

v0.5.17: Tests for the FastAPI diagnostics endpoint.
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aksara.diagnostics import DiagnosticIssue, DiagnosticReport


def _make_report(**kwargs):
    """Create a test DiagnosticReport."""
    report = DiagnosticReport(
        system={"aksara_version": "0.5.17", "python_version": "3.12", "os": "Test", "arch": "x86"},
        duration_ms=10.0,
        **kwargs,
    )
    return report


class TestStudioDiagnosticsEndpoint:
    """Tests for GET /studio/diagnostics."""

    def _get_client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from aksara.studio.fastapi import router

        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_endpoint_returns_200(self):
        report = _make_report()
        with patch("aksara.studio.fastapi.run_all_checks", new_callable=AsyncMock, return_value=report):
            with patch("aksara.studio.fastapi.verify_studio_origin", new_callable=AsyncMock):
                client = self._get_client()
                resp = client.get("/studio/diagnostics")
        assert resp.status_code == 200

    def test_endpoint_returns_report_structure(self):
        report = _make_report()
        report.add(DiagnosticIssue(kind="general", severity="info", title="Test", message="test"))
        with patch("aksara.studio.fastapi.run_all_checks", new_callable=AsyncMock, return_value=report):
            with patch("aksara.studio.fastapi.verify_studio_origin", new_callable=AsyncMock):
                client = self._get_client()
                resp = client.get("/studio/diagnostics")
        data = resp.json()
        assert "issues" in data
        assert "stats" in data
        assert "system" in data
        assert "duration_ms" in data
        assert "timestamp" in data

    def test_endpoint_issues_have_required_fields(self):
        report = _make_report()
        report.add(DiagnosticIssue(
            kind="database_connectivity", severity="error",
            title="DB Error", message="Cannot connect",
            hint="Check DATABASE_URL", meta={"host": "localhost"},
        ))
        with patch("aksara.studio.fastapi.run_all_checks", new_callable=AsyncMock, return_value=report):
            with patch("aksara.studio.fastapi.verify_studio_origin", new_callable=AsyncMock):
                client = self._get_client()
                resp = client.get("/studio/diagnostics")
        data = resp.json()
        issue = data["issues"][0]
        assert issue["kind"] == "database_connectivity"
        assert issue["severity"] == "error"
        assert issue["title"] == "DB Error"
        assert issue["message"] == "Cannot connect"
        assert issue["hint"] == "Check DATABASE_URL"
        assert issue["meta"]["host"] == "localhost"

    def test_endpoint_stats_counts(self):
        report = _make_report()
        report.add(DiagnosticIssue(kind="a", severity="error", title="E", message="e"))
        report.add(DiagnosticIssue(kind="b", severity="warning", title="W", message="w"))
        report.add(DiagnosticIssue(kind="c", severity="info", title="I", message="i"))
        with patch("aksara.studio.fastapi.run_all_checks", new_callable=AsyncMock, return_value=report):
            with patch("aksara.studio.fastapi.verify_studio_origin", new_callable=AsyncMock):
                client = self._get_client()
                resp = client.get("/studio/diagnostics")
        data = resp.json()
        assert data["stats"]["errors"] == 1
        assert data["stats"]["warnings"] == 1
        assert data["stats"]["info"] == 1

    def test_endpoint_system_metadata(self):
        report = _make_report()
        with patch("aksara.studio.fastapi.run_all_checks", new_callable=AsyncMock, return_value=report):
            with patch("aksara.studio.fastapi.verify_studio_origin", new_callable=AsyncMock):
                client = self._get_client()
                resp = client.get("/studio/diagnostics")
        data = resp.json()
        assert data["system"]["aksara_version"] == "0.5.17"

    def test_endpoint_empty_report(self):
        report = _make_report()
        with patch("aksara.studio.fastapi.run_all_checks", new_callable=AsyncMock, return_value=report):
            with patch("aksara.studio.fastapi.verify_studio_origin", new_callable=AsyncMock):
                client = self._get_client()
                resp = client.get("/studio/diagnostics")
        data = resp.json()
        assert data["issues"] == []
        assert data["stats"]["errors"] == 0
