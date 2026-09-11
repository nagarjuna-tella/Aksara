"""Check documented configuration against installed public behavior."""

from __future__ import annotations

import ast
import dataclasses
import inspect
import re
from pathlib import Path

import pytest

import aksara.conf
from aksara.conf import Settings
from aksara.durable import DurableOperationService

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / "docs/docs/reference/settings-reference.md"
ROWS = re.compile(r"^\| `(\w+)` \| (.+?) \| (.+?) \|$", re.MULTILINE)


def _literal(cell: str):
    value = cell.strip("`")
    try:
        return ast.literal_eval(value)
    except (SyntaxError, ValueError):
        return value


def test_documented_settings_defaults_and_environment_names():
    fields = {field.name: field for field in dataclasses.fields(Settings)}
    environment_names = {
        node.value
        for node in ast.walk(ast.parse(inspect.getsource(aksara.conf)))
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value.startswith(("AKSARA_", "DATABASE_URL"))
    }
    checked = set()
    for name, environment, default in ROWS.findall(REFERENCE.read_text()):
        names = re.findall(r"`((?:AKSARA_\w+|DATABASE_URL))`", environment)
        if not names and name not in fields:
            continue  # Other tables describe service arguments, not Settings.
        assert name in fields, f"Unknown documented Settings field: {name}"
        assert set(names) <= environment_names, (name, names)
        field = fields[name]
        actual = (
            field.default_factory()
            if field.default is dataclasses.MISSING
            else field.default
        )
        assert _literal(default) == actual, name
        checked.add(name)
    assert {
        "database_url", "installed_apps", "mcp_allowed_origins",
        "task_poll_interval_seconds", "media_storage", "cookie_secure",
    } <= checked


@pytest.mark.parametrize(
    ("environment", "field", "value"),
    [
        ("AKSARA_TASK_POLL_INTERVAL_SECONDS", "task_poll_interval_seconds", 2.5),
        ("AKSARA_TASK_RETRY_DELAY_SECONDS", "task_retry_delay_seconds", 7.5),
        ("AKSARA_TASK_STALE_LOCK_TIMEOUT_SECONDS", "task_stale_lock_timeout_seconds", 42.0),
        ("AKSARA_TASK_LOCK_RECOVERY_INTERVAL_SECONDS", "task_lock_recovery_interval_seconds", 8.0),
        ("AKSARA_TASK_RETRY_MAX_DELAY_SECONDS", "task_retry_max_delay_seconds", 99.0),
    ],
)
def test_documented_task_variables_configure_the_installed_settings(
    monkeypatch, environment, field, value
):
    monkeypatch.setenv(environment, str(value))
    assert getattr(Settings(), field) == value


def test_documented_durable_defaults_match_service_signature():
    parameters = inspect.signature(DurableOperationService).parameters
    checked = set()
    for name, default, _meaning in ROWS.findall(REFERENCE.read_text()):
        if name not in parameters or parameters[name].default is inspect.Parameter.empty:
            continue
        assert _literal(default) == parameters[name].default, name
        checked.add(name)
    assert checked == {
        "default_max_attempts", "default_lease_seconds", "retention_seconds",
        "idempotency_seconds", "result_retention_seconds", "error_retention_seconds",
    }


def test_explicit_configuration_preserves_mcp_origin_and_host_patterns(monkeypatch):
    # A fresh global object keeps the application's effective configuration intact.
    monkeypatch.setattr(aksara.conf, "settings", Settings())
    monkeypatch.setenv("AKSARA_POOL_SIZE", "37")
    assert Settings(pool_max_size=9).pool_max_size == 37
    configured = aksara.conf.configure(
        pool_max_size=9,
        mcp_allowed_hosts=["api.example.com:443"],
        mcp_allowed_origins=["https://app.example.com"],
    )
    assert configured.pool_max_size == 9
    assert configured.mcp_allowed_hosts == ["api.example.com:443"]
    assert configured.mcp_allowed_origins == ["https://app.example.com"]
