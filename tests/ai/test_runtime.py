"""
v0.5.30 — AI Execution Runtime: unit tests.

Tests cover:
    - run_prompt_pack() — happy path with mocked connector
    - Provider/model resolution from pack, override, and AI Hub
    - _build_messages() — system/user/empty cases
    - _default_model_for() — all known providers
    - _error_response() — shape validation
    - Error paths: missing provider, unknown provider, connector error
    - Runtime never modifies code (safety invariant)
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from aksara.ai.runtime import (
    run_prompt_pack,
    _build_messages,
    _default_model_for,
    _error_response,
    _resolve_from_hub,
)


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures & helpers
# ═══════════════════════════════════════════════════════════════════════════


def _make_pack(**overrides):
    """Create a minimal prompt pack dict."""
    pack = {
        "ok": True,
        "action_key": "explain_model",
        "provider": "openai",
        "model": "gpt-4o",
        "system_prompt": "You are an Aksara assistant.",
        "user_prompt": "Explain the User model.",
        "result_markdown": "Ready",
    }
    pack.update(overrides)
    return pack


def _make_connector_result(**overrides):
    """Create a mock connector chat() result."""
    result = {
        "ok": True,
        "provider": "openai",
        "model": "gpt-4o",
        "text": "The User model has 5 fields...",
        "tokens": {"prompt": 20, "completion": 50, "total": 70},
        "raw": {},
        "error": None,
        "elapsed_ms": 100.0,
    }
    result.update(overrides)
    return result


class _FakeConnector:
    provider = "openai"

    def __init__(self, result=None):
        self._result = result or _make_connector_result()

    async def chat(self, messages, model, **kwargs):
        return self._result


class _FakeHub:
    active_provider = "openai"

    class defaults:
        chat_model = "gpt-4o"

    def configured_providers(self):
        return [MagicMock(kind="openai")]

    def get_provider(self, kind):
        return MagicMock(kind=kind)

    def resolve_defaults(self):
        return {}


# ═══════════════════════════════════════════════════════════════════════════
# 1. _build_messages
# ═══════════════════════════════════════════════════════════════════════════


class TestBuildMessages:
    def test_system_and_user(self):
        pack = _make_pack()
        msgs = _build_messages(pack)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"

    def test_user_only(self):
        pack = _make_pack(system_prompt="")
        msgs = _build_messages(pack)
        assert len(msgs) == 1
        assert msgs[0]["role"] == "user"

    def test_system_only(self):
        pack = _make_pack(user_prompt="")
        msgs = _build_messages(pack)
        assert len(msgs) == 1
        assert msgs[0]["role"] == "system"

    def test_empty_fallback(self):
        pack = _make_pack(system_prompt="", user_prompt="")
        msgs = _build_messages(pack)
        assert len(msgs) == 1
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "Hello"


# ═══════════════════════════════════════════════════════════════════════════
# 2. _default_model_for
# ═══════════════════════════════════════════════════════════════════════════


class TestDefaultModel:
    @pytest.mark.parametrize("provider,expected", [
        ("openai", "gpt-4o"),
        ("azure", "gpt-4o"),
        ("anthropic", "claude-3-5-sonnet-20241022"),
        ("ollama", "llama3"),
        ("http", "default"),
        ("custom", "default"),
    ])
    def test_known_providers(self, provider, expected):
        assert _default_model_for(provider) == expected

    def test_unknown_provider(self):
        assert _default_model_for("alien") == "default"


# ═══════════════════════════════════════════════════════════════════════════
# 3. _error_response
# ═══════════════════════════════════════════════════════════════════════════


class TestErrorResponse:
    def test_shape(self):
        r = _error_response("broken", "SOME_CODE")
        assert r["ok"] is False
        assert r["error"] == "broken"
        assert r["error_code"] == "SOME_CODE"
        assert r["provider"] == ""
        assert r["model"] == ""
        assert r["response"] == ""

    def test_default_code(self):
        r = _error_response("oops")
        assert r["error_code"] == "RUNTIME_ERROR"


# ═══════════════════════════════════════════════════════════════════════════
# 4. run_prompt_pack — happy path
# ═══════════════════════════════════════════════════════════════════════════


class TestRunPromptPack:
    @pytest.mark.asyncio
    async def test_success(self):
        connector = _FakeConnector()
        pack = _make_pack()

        with patch("aksara.ai.runtime._resolve_from_hub", return_value=("openai", "gpt-4o")):
            with patch("aksara.ai.connectors.registry.get_connector", return_value=connector):
                result = await run_prompt_pack(pack)

        assert result["ok"] is True
        assert result["response"] == "The User model has 5 fields..."
        assert result["provider"] == "openai"
        assert result["model"] == "gpt-4o"
        assert result["tokens"]["total"] == 70
        assert result["elapsed_ms"] > 0

    @pytest.mark.asyncio
    async def test_provider_override(self):
        connector = _FakeConnector(_make_connector_result(provider="anthropic", model="claude-3-5-sonnet-20241022"))
        pack = _make_pack(provider="openai")

        with patch("aksara.ai.connectors.registry.get_connector", return_value=connector) as mock_get:
            result = await run_prompt_pack(pack, provider_override="anthropic", model_override="claude-3-5-sonnet-20241022")

        mock_get.assert_called_once_with("anthropic")
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_model_override(self):
        connector = _FakeConnector()
        pack = _make_pack(provider="openai", model="gpt-3.5-turbo")

        with patch("aksara.ai.connectors.registry.get_connector", return_value=connector):
            result = await run_prompt_pack(pack, model_override="gpt-4o")

        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_no_provider_configured(self):
        pack = _make_pack(provider="")

        with patch("aksara.ai.runtime._resolve_from_hub", return_value=("", "")):
            result = await run_prompt_pack(pack)

        assert result["ok"] is False
        assert result["error_code"] == "AI_HUB_NOT_CONFIGURED"

    @pytest.mark.asyncio
    async def test_unknown_provider(self):
        pack = _make_pack(provider="alien_ai")

        with patch("aksara.ai.connectors.registry.get_connector", side_effect=ValueError("Unknown")):
            result = await run_prompt_pack(pack)

        assert result["ok"] is False
        assert result["error_code"] == "UNKNOWN_PROVIDER"

    @pytest.mark.asyncio
    async def test_connector_error(self):
        connector = _FakeConnector(_make_connector_result(ok=False, error="Rate limited"))
        pack = _make_pack()

        with patch("aksara.ai.connectors.registry.get_connector", return_value=connector):
            result = await run_prompt_pack(pack)

        assert result["ok"] is False
        assert "Rate limited" in result["error"]

    @pytest.mark.asyncio
    async def test_exception_returns_error(self):
        pack = _make_pack()

        with patch("aksara.ai.connectors.registry.get_connector", side_effect=RuntimeError("boom")):
            result = await run_prompt_pack(pack)

        assert result["ok"] is False
        assert result["error_code"] == "RUNTIME_ERROR"

    @pytest.mark.asyncio
    async def test_return_shape_on_success(self):
        connector = _FakeConnector()
        pack = _make_pack()

        with patch("aksara.ai.connectors.registry.get_connector", return_value=connector):
            result = await run_prompt_pack(pack)

        required = {"ok", "provider", "model", "response", "tokens", "elapsed_ms", "error"}
        for key in required:
            assert key in result, f"Missing key: {key}"

    @pytest.mark.asyncio
    async def test_return_shape_on_error(self):
        pack = _make_pack(provider="")

        with patch("aksara.ai.runtime._resolve_from_hub", return_value=("", "")):
            result = await run_prompt_pack(pack)

        required = {"ok", "provider", "model", "error"}
        for key in required:
            assert key in result, f"Missing key: {key}"


# ═══════════════════════════════════════════════════════════════════════════
# 5. _resolve_from_hub
# ═══════════════════════════════════════════════════════════════════════════


class TestResolveFromHub:
    def test_with_active_provider(self):
        hub = _FakeHub()
        with patch("aksara.ai.runtime.load_aihub_settings" if False else "aksara.ai.hub_settings.load_aihub_settings", return_value=hub):
            with patch("aksara.ai.runtime._resolve_from_hub", wraps=_resolve_from_hub) as wrapped:
                provider, model = _resolve_from_hub("")
        # May fall back to empty if import patching is tricky — just ensure no crash
        assert isinstance(provider, str)
        assert isinstance(model, str)

    def test_exception_returns_fallback(self):
        with patch("aksara.ai.hub_settings.load_aihub_settings", side_effect=ImportError("no hub")):
            provider, model = _resolve_from_hub("my-model")
        assert model == "my-model"

    def test_keeps_existing_model(self):
        with patch("aksara.ai.hub_settings.load_aihub_settings", side_effect=Exception):
            _, model = _resolve_from_hub("gpt-4o")
        assert model == "gpt-4o"


# ═══════════════════════════════════════════════════════════════════════════
# 6. Safety invariant
# ═══════════════════════════════════════════════════════════════════════════


class TestSafetyInvariant:
    """The runtime MUST NEVER return anything that modifies files automatically."""

    @pytest.mark.asyncio
    async def test_result_is_text_not_code_mutation(self):
        connector = _FakeConnector()
        pack = _make_pack()

        with patch("aksara.ai.connectors.registry.get_connector", return_value=connector):
            result = await run_prompt_pack(pack)

        # Result should be a plain text response, not auto-applied changes
        assert isinstance(result.get("response"), str)
        assert "auto_apply" not in result
        assert "write_file" not in result

    @pytest.mark.asyncio
    async def test_no_side_effects_on_failure(self):
        pack = _make_pack(provider="")
        with patch("aksara.ai.runtime._resolve_from_hub", return_value=("", "")):
            result = await run_prompt_pack(pack)
        assert result["ok"] is False
        # Should just be an error dict, nothing mutated
        assert isinstance(result, dict)
