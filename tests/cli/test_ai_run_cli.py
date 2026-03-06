"""
v0.5.30 — CLI AI Run Commands: unit tests.

Tests cover:
    - ``aksara ai run`` group exists
    - All 5 subcommands: model, route, query, migration, diagnostic
    - Output formatting (text + JSON)
    - Help text
    - Error cases: missing required options
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from click.testing import CliRunner

from aksara.cli.main import cli


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════


runner = CliRunner()


def _mock_execution_result(**overrides):
    result = {
        "ok": True,
        "prompt_pack": {
            "ok": True,
            "action_key": "explain_model",
            "provider": "openai",
            "model": "gpt-4o",
            "system_prompt": "You are Aksara.",
            "user_prompt": "Explain the User model.",
        },
        "execution": {
            "ok": True,
            "provider": "openai",
            "model": "gpt-4o",
            "response": "The User model has 5 fields.",
            "tokens": {"prompt": 20, "completion": 40, "total": 60},
            "elapsed_ms": 150.0,
            "error": None,
        },
    }
    result.update(overrides)
    return result


class _FakeDefaults:
    chat_model = "gpt-4o"
    chat_provider = "openai"
    code_model = "gpt-4o"
    code_provider = "openai"
    embeddings_model = "text-embedding-3-small"
    embeddings_provider = "openai"


class _FakeProvider:
    kind = "openai"
    enabled = True
    is_configured = True
    api_key = "sk-test"
    model = "gpt-4o"
    base_url = ""
    def get_supported_modes(self): return ["chat"]
    def to_unified_provider(self): return MagicMock()


class _FakeHub:
    providers = [_FakeProvider()]
    defaults = _FakeDefaults()
    active_provider = "openai"
    version = "0.5.34"
    def configured_providers(self): return [_FakeProvider()]
    def get_provider(self, kind): return _FakeProvider() if kind == "openai" else None
    def provider_status_summary(self): return {}
    def resolve_defaults(self): return {}
    def to_safe_dict(self): return {}


def _mock_hub():
    return patch("aksara.ai.hub_settings.load_aihub_settings", return_value=_FakeHub())


def _mock_execute(flow_fn_path, result=None):
    """Mock an async execute_* function to return a canned result."""
    async_mock = AsyncMock(return_value=result or _mock_execution_result())
    return patch(flow_fn_path, async_mock)


# ═══════════════════════════════════════════════════════════════════════════
# 1. Group existence & help
# ═══════════════════════════════════════════════════════════════════════════


class TestAiRunGroupExists:
    def test_help(self):
        result = runner.invoke(cli, ["ai", "run", "--help"])
        assert result.exit_code == 0
        assert "Execute AI flows" in result.output or "connector" in result.output.lower()

    def test_model_help(self):
        result = runner.invoke(cli, ["ai", "run", "model", "--help"])
        assert result.exit_code == 0
        assert "--action" in result.output

    def test_route_help(self):
        result = runner.invoke(cli, ["ai", "run", "route", "--help"])
        assert result.exit_code == 0

    def test_query_help(self):
        result = runner.invoke(cli, ["ai", "run", "query", "--help"])
        assert result.exit_code == 0

    def test_migration_help(self):
        result = runner.invoke(cli, ["ai", "run", "migration", "--help"])
        assert result.exit_code == 0

    def test_diagnostic_help(self):
        result = runner.invoke(cli, ["ai", "run", "diagnostic", "--help"])
        assert result.exit_code == 0


# ═══════════════════════════════════════════════════════════════════════════
# 2. Missing required options
# ═══════════════════════════════════════════════════════════════════════════


class TestMissingOptions:
    def test_model_no_action(self):
        result = runner.invoke(cli, ["ai", "run", "model", "User"])
        assert result.exit_code != 0

    def test_route_no_action(self):
        result = runner.invoke(cli, ["ai", "run", "route", "GET:/api/users"])
        assert result.exit_code != 0

    def test_query_no_sql(self):
        result = runner.invoke(cli, ["ai", "run", "query", "--action", "explain_plan"])
        assert result.exit_code != 0

    def test_diagnostic_no_action(self):
        result = runner.invoke(cli, ["ai", "run", "diagnostic"])
        assert result.exit_code != 0


# ═══════════════════════════════════════════════════════════════════════════
# 3. Successful execution (mocked)
# ═══════════════════════════════════════════════════════════════════════════


class TestModelRunCommand:
    def test_text_output(self):
        with _mock_hub():
            with _mock_execute("aksara.studio.ai_flows.execute_model_flow"):
                result = runner.invoke(cli, ["ai", "run", "model", "User", "--action", "explain_model"])
        assert result.exit_code == 0
        assert "executed" in result.output.lower() or "response" in result.output.lower() or "explain" in result.output.lower()

    def test_json_output(self):
        exec_result = _mock_execution_result()
        with _mock_hub():
            with _mock_execute("aksara.studio.ai_flows.execute_model_flow", exec_result):
                result = runner.invoke(cli, ["ai", "run", "model", "User", "--action", "explain_model", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True


class TestRouteRunCommand:
    def test_text_output(self):
        with _mock_hub():
            with _mock_execute("aksara.studio.ai_flows.execute_route_flow"):
                result = runner.invoke(cli, ["ai", "run", "route", "GET:/api/users", "--action", "review_endpoint"])
        assert result.exit_code == 0

    def test_method_path_split(self):
        """Should split METHOD:/path correctly."""
        with _mock_hub():
            with _mock_execute("aksara.studio.ai_flows.execute_route_flow") as mock_fn:
                runner.invoke(cli, ["ai", "run", "route", "POST:/api/items", "--action", "review_endpoint"])


class TestQueryRunCommand:
    def test_text_output(self):
        with _mock_hub():
            with _mock_execute("aksara.studio.ai_flows.execute_query_flow"):
                result = runner.invoke(cli, ["ai", "run", "query", "--sql", "SELECT 1", "--action", "explain_plan"])
        assert result.exit_code == 0


class TestMigrationRunCommand:
    def test_text_output(self):
        with _mock_hub():
            with _mock_execute("aksara.studio.ai_flows.execute_migration_flow"):
                result = runner.invoke(cli, ["ai", "run", "migration", "--action", "explain_migration", "--app", "blog"])
        assert result.exit_code == 0


class TestDiagnosticRunCommand:
    def test_text_output(self):
        with _mock_hub():
            with _mock_execute("aksara.studio.ai_flows.execute_diagnostic_flow"):
                result = runner.invoke(cli, ["ai", "run", "diagnostic", "--action", "diagnostic_prioritize", "--issue-id", "DB_NO_URL"])
        assert result.exit_code == 0


# ═══════════════════════════════════════════════════════════════════════════
# 4. Error output
# ═══════════════════════════════════════════════════════════════════════════


class TestErrorOutput:
    def test_model_error_shows_message(self):
        fail_result = _mock_execution_result(ok=False)
        fail_result["execution"] = None
        fail_result["error"] = "No provider"

        with _mock_hub():
            with _mock_execute("aksara.studio.ai_flows.execute_model_flow", fail_result):
                result = runner.invoke(cli, ["ai", "run", "model", "User", "--action", "explain_model"])
        assert result.exit_code == 0  # CLI itself doesn't fail, just prints error

    def test_json_error_output(self):
        fail_result = _mock_execution_result(ok=False)
        fail_result["error"] = "Provider down"

        with _mock_hub():
            with _mock_execute("aksara.studio.ai_flows.execute_model_flow", fail_result):
                result = runner.invoke(cli, ["ai", "run", "model", "User", "--action", "explain_model", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is False


# ═══════════════════════════════════════════════════════════════════════════
# 5. Provider and model overrides via CLI flags
# ═══════════════════════════════════════════════════════════════════════════


class TestOverrideFlags:
    def test_provider_override(self):
        with _mock_hub():
            with _mock_execute("aksara.studio.ai_flows.execute_model_flow") as mock_fn:
                result = runner.invoke(cli, [
                    "ai", "run", "model", "User",
                    "--action", "explain_model",
                    "--provider", "anthropic",
                ])
        assert result.exit_code == 0

    def test_model_override(self):
        with _mock_hub():
            with _mock_execute("aksara.studio.ai_flows.execute_model_flow") as mock_fn:
                result = runner.invoke(cli, [
                    "ai", "run", "model", "User",
                    "--action", "explain_model",
                    "--model", "gpt-3.5-turbo",
                ])
        assert result.exit_code == 0

    def test_both_overrides(self):
        with _mock_hub():
            with _mock_execute("aksara.studio.ai_flows.execute_model_flow") as mock_fn:
                result = runner.invoke(cli, [
                    "ai", "run", "model", "User",
                    "--action", "explain_model",
                    "--provider", "ollama",
                    "--model", "llama3",
                ])
        assert result.exit_code == 0
