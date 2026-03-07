"""
v0.5.31 — Studio AI Console endpoint tests.

Tests cover:
    - POST /studio/ai/console — happy path with mocked runtime
    - GET /studio/ai/console/suggest — suggestion endpoint
    - Error responses: empty message, unknown intent
    - Response shape validation
    - Endpoint presence in router
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


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
    version = "0.5.36"
    def configured_providers(self): return [_FakeProvider()]
    def get_provider(self, kind): return _FakeProvider() if kind == "openai" else None
    def provider_status_summary(self): return {}
    def resolve_defaults(self): return {}
    def to_safe_dict(self): return {}


class _FakeHubEmpty:
    providers = []
    defaults = _FakeDefaults()
    active_provider = ""
    version = "0.5.36"
    def configured_providers(self): return []
    def get_provider(self, kind): return None
    def provider_status_summary(self): return {}
    def resolve_defaults(self): return {}
    def to_safe_dict(self): return {}


def _mock_hub():
    return patch("aksara.ai.hub_settings.load_aihub_settings", return_value=_FakeHub())


def _mock_hub_empty():
    return patch("aksara.ai.hub_settings.load_aihub_settings", return_value=_FakeHubEmpty())


def _make_runtime_result(**overrides):
    result = {
        "ok": True,
        "provider": "openai",
        "model": "gpt-4o",
        "response": "Model analysis here...",
        "tokens": {"prompt": 15, "completion": 35, "total": 50},
        "elapsed_ms": 120.0,
        "error": None,
    }
    result.update(overrides)
    return result


def _mock_runtime(result=None):
    r = result or _make_runtime_result()
    return patch("aksara.ai.runtime.run_prompt_pack", new_callable=AsyncMock, return_value=r)


# ═══════════════════════════════════════════════════════════════════════════
# POST /studio/ai/console
# ═══════════════════════════════════════════════════════════════════════════


class TestConsoleEndpoint:

    @pytest.mark.asyncio
    async def test_console_endpoint_happy(self):
        from aksara.ai.console_engine import run_console_query

        with _mock_hub(), _mock_runtime():
            result = await run_console_query("explain the User model")
            assert result["ok"] is True
            assert result["intent"] == "explain_model"

    @pytest.mark.asyncio
    async def test_console_endpoint_empty_msg(self):
        from aksara.ai.console_engine import run_console_query

        result = await run_console_query("")
        assert result["ok"] is False
        assert result["error_code"] == "EMPTY_MESSAGE"

    @pytest.mark.asyncio
    async def test_console_endpoint_unknown(self):
        from aksara.ai.console_engine import run_console_query

        result = await run_console_query("xyzzy foo bar baz")
        assert result["ok"] is False
        assert result["error_code"] == "UNKNOWN_INTENT"

    @pytest.mark.asyncio
    async def test_console_route_flow(self):
        from aksara.ai.console_engine import run_console_query

        with _mock_hub(), _mock_runtime():
            result = await run_console_query("review GET /api/orders")
            assert result["ok"] is True
            assert result["flow_type"] == "route"

    @pytest.mark.asyncio
    async def test_console_query_flow(self):
        from aksara.ai.console_engine import run_console_query

        with _mock_hub(), _mock_runtime():
            result = await run_console_query("suggest indexes for users")
            assert result["ok"] is True
            assert result["flow_type"] == "query"

    @pytest.mark.asyncio
    async def test_console_migration_flow(self):
        from aksara.ai.console_engine import run_console_query

        with _mock_hub(), _mock_runtime():
            result = await run_console_query("explain migration impact")
            assert result["ok"] is True
            assert result["flow_type"] == "migration"

    @pytest.mark.asyncio
    async def test_console_diagnostic_flow(self):
        from aksara.ai.console_engine import run_console_query

        with _mock_hub(), _mock_runtime():
            result = await run_console_query("diagnostic prioritize all issues")
            assert result["ok"] is True
            assert result["flow_type"] == "diagnostic"


# ═══════════════════════════════════════════════════════════════════════════
# GET /studio/ai/console/suggest
# ═══════════════════════════════════════════════════════════════════════════


class TestSuggestEndpoint:

    def test_suggest_returns_list(self):
        from aksara.ai.intent_router import suggest_commands
        result = suggest_commands("explain")
        assert isinstance(result, list)

    def test_suggest_empty_prefix(self):
        from aksara.ai.intent_router import suggest_commands
        result = suggest_commands("")
        assert len(result) > 0

    def test_list_intents_shape(self):
        from aksara.ai.intent_router import list_intents
        result = list_intents()
        assert isinstance(result, list)
        assert len(result) >= 11
        for item in result:
            assert "action_key" in item
            assert "flow_type" in item


# ═══════════════════════════════════════════════════════════════════════════
# Endpoint presence in router
# ═══════════════════════════════════════════════════════════════════════════


class TestEndpointPresence:

    def test_console_route_registered(self):
        from aksara.studio.fastapi import router
        paths = [r.path for r in router.routes]
        assert "/studio/ai/console" in paths

    def test_suggest_route_registered(self):
        from aksara.studio.fastapi import router
        paths = [r.path for r in router.routes]
        assert "/studio/ai/console/suggest" in paths


# ═══════════════════════════════════════════════════════════════════════════
# Response shape
# ═══════════════════════════════════════════════════════════════════════════


CONSOLE_RESPONSE_KEYS = {
    "ok", "intent", "flow_type", "action_key", "confidence",
    "extracted_context", "prompt_pack", "execution", "suggestions",
    "error", "error_code",
}


class TestConsoleResponseShape:

    @pytest.mark.asyncio
    async def test_all_keys_present_on_success(self):
        from aksara.ai.console_engine import run_console_query

        with _mock_hub(), _mock_runtime():
            result = await run_console_query("explain the User model")
            for k in CONSOLE_RESPONSE_KEYS:
                assert k in result

    @pytest.mark.asyncio
    async def test_all_keys_present_on_error(self):
        from aksara.ai.console_engine import run_console_query

        result = await run_console_query("")
        for k in CONSOLE_RESPONSE_KEYS:
            assert k in result
