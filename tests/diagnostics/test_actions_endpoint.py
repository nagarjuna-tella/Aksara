"""
Tests for the Studio /studio/diagnostics endpoint — actions in response.

v0.5.18: Verifies that autoremediation actions are included in the
JSON response from the diagnostics endpoint.
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, patch

from aksara.diagnostics import (
    DiagnosticAction,
    DiagnosticIssue,
    DiagnosticReport,
    build_action,
)


def _make_report(**kwargs):
    """Create a test DiagnosticReport."""
    return DiagnosticReport(
        system={"aksara_version": "0.5.18", "python_version": "3.12", "os": "Test", "arch": "x86"},
        duration_ms=5.0,
        **kwargs,
    )


class TestDiagnosticsActionsEndpoint:
    """Tests for actions in GET /studio/diagnostics response."""

    def _get_client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from aksara.studio.fastapi import router, verify_studio_auth

        app = FastAPI()
        app.include_router(router)
        # Use dependency_overrides — the proper FastAPI pattern for bypassing
        # router-level Depends() in tests (patch() cannot intercept callables
        # that were already captured by Depends() at module import time).
        app.dependency_overrides[verify_studio_auth] = lambda: None
        return TestClient(app)

    def test_actions_included_in_response(self):
        report = _make_report()
        report.add(DiagnosticIssue(
            kind="settings_invalid", severity="error",
            title="Missing DB", message="No DATABASE_URL",
            actions=[
                build_action(kind="set_env", target="DATABASE_URL", title="Set DB URL"),
            ],
        ))
        with patch("aksara.studio.fastapi.run_all_checks", new_callable=AsyncMock, return_value=report):
            client = self._get_client()
            resp = client.get("/studio/diagnostics")
        assert resp.status_code == 200
        data = resp.json()
        issue = data["issues"][0]
        assert "actions" in issue
        assert len(issue["actions"]) == 1
        assert issue["actions"][0]["kind"] == "set_env"
        assert issue["actions"][0]["target"] == "DATABASE_URL"

    def test_empty_actions_in_response(self):
        report = _make_report()
        report.add(DiagnosticIssue(
            kind="general", severity="info", title="No actions", message="m",
        ))
        with patch("aksara.studio.fastapi.run_all_checks", new_callable=AsyncMock, return_value=report):
            client = self._get_client()
            resp = client.get("/studio/diagnostics")
        data = resp.json()
        assert data["issues"][0]["actions"] == []

    def test_multiple_actions_per_issue(self):
        report = _make_report()
        report.add(DiagnosticIssue(
            kind="database_connectivity", severity="error",
            title="No DB", message="m",
            actions=[
                build_action(kind="set_env", target="DATABASE_URL", title="Set DB"),
                build_action(kind="open_doc", target="https://docs.example.com", title="Docs"),
            ],
        ))
        with patch("aksara.studio.fastapi.run_all_checks", new_callable=AsyncMock, return_value=report):
            client = self._get_client()
            resp = client.get("/studio/diagnostics")
        data = resp.json()
        actions = data["issues"][0]["actions"]
        assert len(actions) == 2
        kinds = {a["kind"] for a in actions}
        assert "set_env" in kinds
        assert "open_doc" in kinds

    def test_action_example_field_in_response(self):
        report = _make_report()
        report.add(DiagnosticIssue(
            kind="general", severity="warning", title="t", message="m",
            actions=[
                build_action(
                    kind="run_command", target="pip install x",
                    title="Install x", example="pip install x",
                ),
            ],
        ))
        with patch("aksara.studio.fastapi.run_all_checks", new_callable=AsyncMock, return_value=report):
            client = self._get_client()
            resp = client.get("/studio/diagnostics")
        data = resp.json()
        action = data["issues"][0]["actions"][0]
        assert action["example"] == "pip install x"

    def test_action_all_kinds_serialize(self):
        report = _make_report()
        kinds = ["set_env", "edit_file", "run_command", "open_doc", "add_setting"]
        for k in kinds:
            report.add(DiagnosticIssue(
                kind="general", severity="info", title=f"test-{k}", message="m",
                actions=[build_action(kind=k, target="x", title=f"action-{k}")],
            ))
        with patch("aksara.studio.fastapi.run_all_checks", new_callable=AsyncMock, return_value=report):
            client = self._get_client()
            resp = client.get("/studio/diagnostics")
        data = resp.json()
        response_kinds = {issue["actions"][0]["kind"] for issue in data["issues"]}
        assert response_kinds == set(kinds)
