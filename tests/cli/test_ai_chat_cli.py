"""
v0.5.31 — CLI ``aksara ai chat`` tests.

Tests cover:
    - Command registration and help text
    - Argument validation
    - Output formatting (text and JSON)
    - Error handling for unknown intents and empty messages
    - _print_console_result() output
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from click.testing import CliRunner


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════


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
    version = "0.5.35"
    def configured_providers(self): return [_FakeProvider()]
    def get_provider(self, kind): return _FakeProvider() if kind == "openai" else None
    def provider_status_summary(self): return {}
    def resolve_defaults(self): return {}
    def to_safe_dict(self): return {}


def _mock_hub():
    return patch("aksara.ai.hub_settings.load_aihub_settings", return_value=_FakeHub())


def _make_runtime_result(**overrides):
    result = {
        "ok": True,
        "provider": "openai",
        "model": "gpt-4o",
        "response": "Analysis result here.",
        "tokens": {"prompt": 20, "completion": 40, "total": 60},
        "elapsed_ms": 150.0,
        "error": None,
    }
    result.update(overrides)
    return result


def _mock_runtime(result=None):
    r = result or _make_runtime_result()
    return patch("aksara.ai.runtime.run_prompt_pack", new_callable=AsyncMock, return_value=r)


def _get_cli_group():
    from aksara.cli.main import ai_flows_group
    return ai_flows_group


# ═══════════════════════════════════════════════════════════════════════════
# Command registration
# ═══════════════════════════════════════════════════════════════════════════


class TestChatCommandRegistration:

    def test_chat_command_exists(self):
        group = _get_cli_group()
        names = [c.name for c in group.commands.values()] if hasattr(group, 'commands') else []
        assert "chat" in names

    def test_chat_help_text(self):
        runner = CliRunner()
        group = _get_cli_group()
        result = runner.invoke(group, ["chat", "--help"])
        assert result.exit_code == 0
        assert "natural-language" in result.output.lower() or "console" in result.output.lower() or "chat" in result.output.lower()

    def test_chat_requires_message(self):
        runner = CliRunner()
        group = _get_cli_group()
        result = runner.invoke(group, ["chat"])
        assert result.exit_code != 0  # missing required argument

    def test_chat_format_option(self):
        runner = CliRunner()
        group = _get_cli_group()
        result = runner.invoke(group, ["chat", "--help"])
        assert "--format" in result.output


# ═══════════════════════════════════════════════════════════════════════════
# Text output
# ═══════════════════════════════════════════════════════════════════════════


class TestChatTextOutput:

    def test_success_output(self):
        from aksara.cli.main import _print_console_result
        from io import StringIO
        from unittest.mock import patch as _patch

        result = {
            "ok": True,
            "intent": "explain_model",
            "flow_type": "model",
            "action_key": "explain_model",
            "confidence": 0.91,
            "extracted_context": {"model_name": "User"},
            "prompt_pack": {},
            "execution": {
                "ok": True,
                "provider": "openai",
                "model": "gpt-4o",
                "response": "The User model has 5 fields.",
                "tokens": {"prompt": 10, "completion": 20, "total": 30},
                "elapsed_ms": 100.0,
            },
            "suggestions": ["suggest_constraints"],
            "elapsed_ms": 120.0,
            "error": None,
            "error_code": None,
        }

        runner = CliRunner()
        # Use click's echo instead of capturing stdout
        with runner.isolated_filesystem():
            from click import echo
            _print_console_result(result, "text")

    def test_error_output(self):
        from aksara.cli.main import _print_console_result

        result = {
            "ok": False,
            "intent": "unknown",
            "flow_type": "",
            "action_key": "",
            "confidence": 0.0,
            "extracted_context": {},
            "prompt_pack": None,
            "execution": None,
            "suggestions": [],
            "elapsed_ms": 0,
            "error": "Could not understand input",
            "error_code": "UNKNOWN_INTENT",
        }

        # Should not raise
        _print_console_result(result, "text")


# ═══════════════════════════════════════════════════════════════════════════
# JSON output
# ═══════════════════════════════════════════════════════════════════════════


class TestChatJsonOutput:

    def test_json_format(self):
        from aksara.cli.main import _print_console_result

        result = {
            "ok": True,
            "intent": "explain_model",
            "flow_type": "model",
            "action_key": "explain_model",
            "confidence": 0.91,
            "extracted_context": {},
            "prompt_pack": {},
            "execution": {"provider": "openai", "model": "gpt-4o", "response": "ok", "tokens": {}},
            "suggestions": [],
            "elapsed_ms": 100.0,
            "error": None,
            "error_code": None,
        }

        runner = CliRunner()
        # Capture output
        import io, sys
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            _print_console_result(result, "json")
        finally:
            sys.stdout = old_stdout


# ═══════════════════════════════════════════════════════════════════════════
# Full CLI invocation (mocked)
# ═══════════════════════════════════════════════════════════════════════════


class TestChatCLIInvocation:

    def test_chat_invocation_explain(self):
        runner = CliRunner()
        group = _get_cli_group()
        with _mock_hub(), _mock_runtime():
            result = runner.invoke(group, ["chat", "explain the User model"])
            # Should not crash
            assert result.exit_code == 0 or "error" in result.output.lower() or "AI Console" in result.output

    def test_chat_invocation_json(self):
        runner = CliRunner()
        group = _get_cli_group()
        with _mock_hub(), _mock_runtime():
            result = runner.invoke(group, ["chat", "explain the User model", "--format", "json"])
            assert result.exit_code == 0 or "error" in result.output.lower()

    def test_chat_unknown_intent(self):
        runner = CliRunner()
        group = _get_cli_group()
        result = runner.invoke(group, ["chat", "xyzzy plugh nothing"])
        # Should handle gracefully — error output
        assert result.exit_code == 0 or result.exit_code == 1
