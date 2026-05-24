from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from click.testing import CliRunner

from aksara.cli.main import cli
from aksara.launch_check import LaunchCheckItem, LaunchCheckReport, run_launch_check


def _project(tmp_path: Path, *, name: str = "sample_project", database_url: str | None = "postgresql://u:p@localhost/db", debug: bool = True, routes: bool = True) -> Path:
    root = tmp_path / name
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    if database_url is None:
        settings_body = f"DEBUG = {debug!r}\n"
    else:
        settings_body = f"DATABASE_URL = {database_url!r}\nDEBUG = {debug!r}\n"
    (root / "settings.py").write_text(settings_body, encoding="utf-8")
    if routes:
        (root / "main.py").write_text(
            "\n".join(
                [
                    "from fastapi import FastAPI",
                    "app = FastAPI()",
                    "@app.get('/studio/ui')",
                    "def studio_ui(): return {'ok': True}",
                    "@app.get('/ai/tools/mcp')",
                    "def mcp(): return {'tools': []}",
                ]
            ),
            encoding="utf-8",
        )
    migrations = root / "migrations"
    migrations.mkdir()
    (migrations / "__init__.py").write_text("", encoding="utf-8")
    (migrations / "0001_initial.py").write_text("# migration\n", encoding="utf-8")
    return root


@pytest.mark.parametrize("status", ["ok", "warning", "error", "skipped"])
def test_launch_check_item_serializes_statuses(status):
    item = LaunchCheckItem("database", "connection", status, "message", "hint", {"x": 1})
    assert item.to_dict()["status"] == status
    assert item.to_dict()["details"] == {"x": 1}


def test_launch_check_item_rejects_unknown_status():
    with pytest.raises(ValueError):
        LaunchCheckItem("x", "y", "bad", "message")


@pytest.mark.parametrize(
    ("status", "exit_code", "ok"),
    [("ready", 0, True), ("partial", 1, False), ("blocked", 2, False)],
)
def test_report_exit_codes(status, exit_code, ok):
    report = LaunchCheckReport(ok=ok, status=status, version="0.5.49", checks=[], next_steps=[])
    assert report.exit_code == exit_code


def test_report_json_is_parseable():
    report = LaunchCheckReport(
        ok=False,
        status="partial",
        version="0.5.49",
        checks=[LaunchCheckItem("ai", "provider_configured", "warning", "No AI provider configured")],
        next_steps=["Configure AI provider optionally"],
    )
    parsed = json.loads(report.to_json())
    assert parsed["status"] == "partial"
    assert parsed["checks"][0]["category"] == "ai"


def test_ready_launch_check_with_mocked_database(monkeypatch, tmp_path):
    root = _project(tmp_path, name="ready_project")
    monkeypatch.setattr("aksara.launch_check._run_database_probe", lambda url, timeout: {"0001_initial"})
    monkeypatch.setattr("aksara.launch_check.find_examples_root", lambda start=None: Path(__file__).resolve().parent.parent / "examples")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    report = run_launch_check(root)
    assert report.status == "ready"
    assert report.ok is True


def test_missing_project_blocks(tmp_path):
    report = run_launch_check(tmp_path, check_database=False)
    assert report.status == "blocked"
    assert any(c.name == "project_detected" and c.status == "error" for c in report.checks)


def test_missing_database_url_blocks(monkeypatch, tmp_path):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("AKSARA_DATABASE_URL", raising=False)
    root = _project(tmp_path, name="missing_db", database_url=None)
    report = run_launch_check(root, check_database=False)
    assert report.status == "blocked"
    assert any(c.name == "database_url" and c.status == "error" for c in report.checks)


def test_database_failure_blocks(monkeypatch, tmp_path):
    root = _project(tmp_path, name="db_failure")

    def fail(url, timeout):
        raise RuntimeError("no db")

    monkeypatch.setattr("aksara.launch_check._run_database_probe", fail)
    report = run_launch_check(root)
    assert report.status == "blocked"
    assert "Verify PostgreSQL" in " ".join(report.next_steps)


def test_pending_migrations_are_warning(monkeypatch, tmp_path):
    root = _project(tmp_path, name="pending_project")
    monkeypatch.setattr("aksara.launch_check._run_database_probe", lambda url, timeout: set())
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    report = run_launch_check(root)
    migration = next(c for c in report.checks if c.name == "migrations")
    assert migration.status == "warning"
    assert report.status == "partial"


def test_missing_ai_provider_is_warning(monkeypatch, tmp_path):
    root = _project(tmp_path, name="no_ai")
    for env_name in [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "OLLAMA_BASE_URL",
        "AKSARA_OLLAMA_BASE_URL",
    ]:
        monkeypatch.delenv(env_name, raising=False)
    report = run_launch_check(root, check_database=False)
    ai = next(c for c in report.checks if c.category == "ai")
    assert ai.status == "warning"
    assert "Configure AI provider optionally" in report.next_steps


def test_missing_routes_are_reported(tmp_path):
    root = _project(tmp_path, name="no_routes", routes=False)
    report = run_launch_check(root, check_database=False)
    assert any(c.category == "studio" and c.status == "skipped" for c in report.checks)


@pytest.mark.parametrize(
    "expected",
    [
        "python_version",
        "aksara_version",
        "project_detected",
        "settings_module",
        "app_registry",
        "database_url",
        "migrations",
        "provider_configured",
    ],
)
def test_report_contains_core_check_names(tmp_path, expected):
    root = _project(tmp_path, name=f"checks_{expected}")
    report = run_launch_check(root, check_database=False)
    assert expected in {check.name for check in report.checks}


@pytest.mark.parametrize(
    ("category", "message"),
    [
        ("environment", "Python"),
        ("project", "project"),
        ("database", "DATABASE_URL"),
        ("studio", "Studio"),
        ("ai", "AI provider"),
        ("examples", "examples"),
        ("security", "Development mode"),
    ],
)
def test_report_has_expected_categories(tmp_path, category, message):
    root = _project(tmp_path, name=f"cat_{category}")
    report = run_launch_check(root, check_database=False)
    matching = [check for check in report.checks if check.category == category]
    assert matching
    assert any(message.lower() in check.message.lower() for check in matching)


@pytest.mark.parametrize("fmt", ["json", "pretty"])
def test_launch_check_cli_uses_report_exit_code(monkeypatch, fmt):
    report = LaunchCheckReport(
        ok=False,
        status="partial",
        version="0.5.49",
        checks=[LaunchCheckItem("ai", "provider_configured", "warning", "No AI provider configured")],
        next_steps=["Configure AI provider optionally"],
    )
    monkeypatch.setattr("aksara.launch_check.run_launch_check", lambda: report)
    result = CliRunner().invoke(cli, ["doctor", "launch-check", "--format", fmt])
    assert result.exit_code == 1
    assert "No AI provider configured" in result.output


def test_launch_check_cli_json_is_pure(monkeypatch):
    report = LaunchCheckReport(
        ok=True,
        status="ready",
        version="0.5.49",
        checks=[LaunchCheckItem("environment", "python_version", "ok", "Python 3.12 detected")],
        next_steps=[],
    )
    monkeypatch.setattr("aksara.launch_check.run_launch_check", lambda: report)
    result = CliRunner().invoke(cli, ["doctor", "launch-check", "--format", "json"])
    assert result.exit_code == 0
    assert result.output.lstrip().startswith("{")
    assert json.loads(result.output)["status"] == "ready"


@pytest.mark.parametrize(
    ("status", "code"),
    [("ready", 0), ("partial", 1), ("blocked", 2)],
)
def test_launch_check_cli_exit_codes(monkeypatch, status, code):
    report = LaunchCheckReport(ok=status == "ready", status=status, version="0.5.49", checks=[], next_steps=[])
    monkeypatch.setattr("aksara.launch_check.run_launch_check", lambda: report)
    result = CliRunner().invoke(cli, ["doctor", "launch-check", "--format", "json"])
    assert result.exit_code == code


def test_redacted_database_url_does_not_expose_password(tmp_path):
    root = _project(tmp_path, name="redacted", database_url="postgresql://user:secretpass@localhost/db")
    report = run_launch_check(root, check_database=False)
    database = next(c for c in report.checks if c.name == "database_url")
    assert "secretpass" not in json.dumps(database.to_dict())
    assert "***" in database.details["redacted_url"]


def test_json_output_contains_no_ansi_sequences(monkeypatch):
    report = LaunchCheckReport(ok=True, status="ready", version="0.5.49", checks=[], next_steps=[])
    monkeypatch.setattr("aksara.launch_check.run_launch_check", lambda: report)
    result = CliRunner().invoke(cli, ["doctor", "launch-check", "--format", "json"])
    assert "\x1b[" not in result.output
