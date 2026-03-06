"""
v0.5.31 — AI Console Engine: unit tests.

Tests cover:
    - run_console_query() — happy path with mocked runtime
    - Intent detection routing through the full pipeline
    - Error paths: empty message, unknown intent, runtime failure
    - _console_error() shape validation
    - _get_suggestions() returns recommended_next from AI_FLOW_ACTIONS
    - Response shape invariants
    - Safety: console never auto-modifies code
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aksara.ai.console_engine import (
    run_console_query,
    _console_error,
    _get_suggestions,
)


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures & helpers
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
    version = "0.5.32"
    def configured_providers(self): return [_FakeProvider()]
    def get_provider(self, kind): return _FakeProvider() if kind == "openai" else None
    def provider_status_summary(self): return {}
    def resolve_defaults(self): return {}
    def to_safe_dict(self): return {}


class _FakeHubEmpty:
    providers = []
    defaults = _FakeDefaults()
    active_provider = ""
    version = "0.5.32"
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
        "response": "The User model has 5 fields...",
        "tokens": {"prompt": 20, "completion": 40, "total": 60},
        "elapsed_ms": 150.0,
        "error": None,
    }
    result.update(overrides)
    return result


def _mock_runtime(result=None):
    r = result or _make_runtime_result()
    return patch("aksara.ai.runtime.run_prompt_pack", new_callable=AsyncMock, return_value=r)


# ═══════════════════════════════════════════════════════════════════════════
# _console_error shape
# ═══════════════════════════════════════════════════════════════════════════


class TestConsoleError:

    def test_error_shape_keys(self):
        err = _console_error("bad", "ERR")
        assert err["ok"] is False
        assert err["error"] == "bad"
        assert err["error_code"] == "ERR"
        assert err["intent"] == "unknown"

    def test_error_empty_collections(self):
        err = _console_error("x", "Y")
        assert err["extracted_context"] == {}
        assert err["suggestions"] == []
        assert err["prompt_pack"] is None
        assert err["execution"] is None

    def test_error_custom_intent(self):
        err = _console_error("x", "Y", intent="test_intent", confidence=0.5)
        assert err["intent"] == "test_intent"
        assert err["confidence"] == 0.5


# ═══════════════════════════════════════════════════════════════════════════
# _get_suggestions
# ═══════════════════════════════════════════════════════════════════════════


class TestGetSuggestions:

    def test_explain_model_suggestions(self):
        s = _get_suggestions("explain_model")
        assert "suggest_constraints" in s
        assert "refactor_suggestions" in s

    def test_review_endpoint_suggestions(self):
        s = _get_suggestions("review_endpoint")
        assert "harden_permissions" in s

    def test_unknown_action(self):
        s = _get_suggestions("nonexistent_action_xyz")
        assert s == []


# ═══════════════════════════════════════════════════════════════════════════
# run_console_query — happy paths
# ═══════════════════════════════════════════════════════════════════════════


class TestRunConsoleQueryHappy:

    @pytest.mark.asyncio
    async def test_explain_model_ok(self):
        with _mock_hub(), _mock_runtime():
            result = await run_console_query("explain the User model")
            assert result["ok"] is True
            assert result["intent"] == "explain_model"
            assert result["flow_type"] == "model"
            assert result["confidence"] > 0.5

    @pytest.mark.asyncio
    async def test_review_endpoint_ok(self):
        with _mock_hub(), _mock_runtime():
            result = await run_console_query("review GET /api/users")
            assert result["ok"] is True
            assert result["flow_type"] == "route"

    @pytest.mark.asyncio
    async def test_suggest_indexes_ok(self):
        with _mock_hub(), _mock_runtime():
            result = await run_console_query("suggest indexes for the table")
            assert result["ok"] is True
            assert result["action_key"] == "suggest_indexes"

    @pytest.mark.asyncio
    async def test_explain_migration_ok(self):
        with _mock_hub(), _mock_runtime():
            result = await run_console_query("explain migration impact")
            assert result["ok"] is True
            assert result["flow_type"] == "migration"

    @pytest.mark.asyncio
    async def test_diagnostic_prioritize_ok(self):
        with _mock_hub(), _mock_runtime():
            result = await run_console_query("diagnostic prioritize issues")
            assert result["ok"] is True
            assert result["flow_type"] == "diagnostic"

    @pytest.mark.asyncio
    async def test_response_has_execution(self):
        with _mock_hub(), _mock_runtime():
            result = await run_console_query("explain the User model")
            assert result["execution"] is not None
            assert result["execution"]["provider"] == "openai"

    @pytest.mark.asyncio
    async def test_response_has_prompt_pack(self):
        with _mock_hub(), _mock_runtime():
            result = await run_console_query("explain the User model")
            assert result["prompt_pack"] is not None

    @pytest.mark.asyncio
    async def test_response_has_suggestions(self):
        with _mock_hub(), _mock_runtime():
            result = await run_console_query("explain the User model")
            assert isinstance(result["suggestions"], list)

    @pytest.mark.asyncio
    async def test_response_has_elapsed(self):
        with _mock_hub(), _mock_runtime():
            result = await run_console_query("explain the User model")
            assert result["elapsed_ms"] >= 0


# ═══════════════════════════════════════════════════════════════════════════
# run_console_query — error paths
# ═══════════════════════════════════════════════════════════════════════════


class TestRunConsoleQueryErrors:

    @pytest.mark.asyncio
    async def test_empty_message(self):
        result = await run_console_query("")
        assert result["ok"] is False
        assert result["error_code"] == "EMPTY_MESSAGE"

    @pytest.mark.asyncio
    async def test_whitespace_message(self):
        result = await run_console_query("   ")
        assert result["ok"] is False
        assert result["error_code"] == "EMPTY_MESSAGE"

    @pytest.mark.asyncio
    async def test_unknown_intent(self):
        result = await run_console_query("xyzzy plugh nothing")
        assert result["ok"] is False
        assert result["error_code"] == "UNKNOWN_INTENT"

    @pytest.mark.asyncio
    async def test_runtime_failure(self):
        fail_result = _make_runtime_result(ok=False, error="Provider unreachable")
        with _mock_hub(), _mock_runtime(fail_result):
            result = await run_console_query("explain the User model")
            assert result["ok"] is False

    @pytest.mark.asyncio
    async def test_no_provider(self):
        with _mock_hub_empty():
            result = await run_console_query("explain the User model")
            # Should fail at runtime level with no provider
            assert result["ok"] is False


# ═══════════════════════════════════════════════════════════════════════════
# Response shape invariants
# ═══════════════════════════════════════════════════════════════════════════


REQUIRED_KEYS = {
    "ok", "intent", "flow_type", "action_key", "confidence",
    "extracted_context", "prompt_pack", "execution", "suggestions",
    "error", "error_code",
}


class TestResponseShape:

    @pytest.mark.asyncio
    async def test_success_has_all_keys(self):
        with _mock_hub(), _mock_runtime():
            result = await run_console_query("explain the User model")
            for key in REQUIRED_KEYS:
                assert key in result, f"Missing key: {key}"

    @pytest.mark.asyncio
    async def test_error_has_all_keys(self):
        result = await run_console_query("")
        for key in REQUIRED_KEYS:
            assert key in result, f"Missing key: {key}"

    @pytest.mark.asyncio
    async def test_ok_is_bool(self):
        with _mock_hub(), _mock_runtime():
            result = await run_console_query("explain the User model")
            assert isinstance(result["ok"], bool)

    @pytest.mark.asyncio
    async def test_confidence_is_float(self):
        with _mock_hub(), _mock_runtime():
            result = await run_console_query("explain the User model")
            assert isinstance(result["confidence"], float)

    @pytest.mark.asyncio
    async def test_suggestions_is_list(self):
        with _mock_hub(), _mock_runtime():
            result = await run_console_query("explain the User model")
            assert isinstance(result["suggestions"], list)


# ═══════════════════════════════════════════════════════════════════════════
# Safety invariant
# ═══════════════════════════════════════════════════════════════════════════


class TestSafety:

    @pytest.mark.asyncio
    async def test_no_auto_modify(self):
        """Console must NEVER auto-modify code — just return analysis."""
        with _mock_hub(), _mock_runtime():
            result = await run_console_query("explain the User model")
            # The execution result is read-only analysis, never a code change
            assert result.get("auto_modified") is None
            assert result.get("code_written") is None
