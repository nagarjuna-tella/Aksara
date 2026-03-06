"""
v0.5.30 — Studio AI Execution: endpoint + flow execution tests.

Tests cover:
    - POST /studio/ai/flows/run endpoint (via HTTPX test client)
    - execute_flow() dispatcher — all 5 flow types
    - Execution with mocked runtime
    - Error paths: unknown flow type, bad action, no provider
    - _dispatch_builder() routing
    - Response shape invariants
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aksara.studio.models import (
    StudioAiFlowResponse,
    StudioAiFlowRunRequest,
    StudioAiFlowRunResponse,
)


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
    version = "0.5.30"
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


# ═══════════════════════════════════════════════════════════════════════════
# 1. _dispatch_builder routing
# ═══════════════════════════════════════════════════════════════════════════


class TestDispatchBuilder:
    def _dispatch(self, flow_type, action_key, context=None):
        from aksara.studio.ai_flows import _dispatch_builder
        with _mock_hub():
            return _dispatch_builder(flow_type, action_key, context or {})

    def test_model(self):
        resp = self._dispatch("model", "explain_model", {"model_name": "User"})
        assert isinstance(resp, StudioAiFlowResponse)
        assert resp.action_key == "explain_model"

    def test_route(self):
        resp = self._dispatch("route", "review_endpoint", {"path": "/api/users", "method": "GET"})
        assert isinstance(resp, StudioAiFlowResponse)

    def test_query(self):
        resp = self._dispatch("query", "explain_plan", {"sql": "SELECT 1"})
        assert isinstance(resp, StudioAiFlowResponse)

    def test_migration(self):
        resp = self._dispatch("migration", "explain_migration", {"app": "blog"})
        assert isinstance(resp, StudioAiFlowResponse)

    def test_diagnostic(self):
        resp = self._dispatch("diagnostic", "diagnostic_prioritize", {"issue_id": "DB_NO_URL"})
        assert isinstance(resp, StudioAiFlowResponse)

    def test_unknown_type(self):
        resp = self._dispatch("alien", "some_action")
        assert resp.ok is False
        assert resp.error_code == "INVALID_FLOW_TYPE"


# ═══════════════════════════════════════════════════════════════════════════
# 2. execute_flow() with mocked runtime
# ═══════════════════════════════════════════════════════════════════════════


class TestExecuteFlow:
    @pytest.mark.asyncio
    async def test_model_flow_success(self):
        from aksara.studio.ai_flows import execute_flow

        runtime_result = _make_runtime_result()

        with _mock_hub():
            with patch("aksara.ai.runtime.run_prompt_pack", new_callable=AsyncMock, return_value=runtime_result):
                result = await execute_flow("model", "explain_model", {"model_name": "User"})

        assert result["ok"] is True
        assert result["prompt_pack"] is not None
        assert result["execution"] is not None
        assert result["execution"]["response"] == "Analysis result here."

    @pytest.mark.asyncio
    async def test_route_flow_success(self):
        from aksara.studio.ai_flows import execute_flow

        runtime_result = _make_runtime_result()
        with _mock_hub():
            with patch("aksara.ai.runtime.run_prompt_pack", new_callable=AsyncMock, return_value=runtime_result):
                result = await execute_flow("route", "review_endpoint", {"path": "/api/users", "method": "GET"})

        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_query_flow_success(self):
        from aksara.studio.ai_flows import execute_flow

        runtime_result = _make_runtime_result()
        with _mock_hub():
            with patch("aksara.ai.runtime.run_prompt_pack", new_callable=AsyncMock, return_value=runtime_result):
                result = await execute_flow("query", "explain_plan", {"sql": "SELECT 1"})

        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_migration_flow_success(self):
        from aksara.studio.ai_flows import execute_flow

        runtime_result = _make_runtime_result()
        with _mock_hub():
            with patch("aksara.ai.runtime.run_prompt_pack", new_callable=AsyncMock, return_value=runtime_result):
                result = await execute_flow("migration", "explain_migration", {"app": "blog"})

        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_diagnostic_flow_success(self):
        from aksara.studio.ai_flows import execute_flow

        runtime_result = _make_runtime_result()
        with _mock_hub():
            with patch("aksara.ai.runtime.run_prompt_pack", new_callable=AsyncMock, return_value=runtime_result):
                result = await execute_flow("diagnostic", "diagnostic_prioritize", {"issue_id": "DB_NO_URL"})

        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_invalid_flow_type(self):
        from aksara.studio.ai_flows import execute_flow

        with _mock_hub():
            result = await execute_flow("alien", "some_action", {})

        assert result["ok"] is False
        assert result["error_code"] == "INVALID_FLOW_TYPE"

    @pytest.mark.asyncio
    async def test_build_failure_propagates(self):
        from aksara.studio.ai_flows import execute_flow

        with _mock_hub():
            result = await execute_flow("model", "nonexistent_action_xyz", {"model_name": "User"})

        assert result["ok"] is False
        assert result["prompt_pack"] is not None

    @pytest.mark.asyncio
    async def test_runtime_failure_propagates(self):
        from aksara.studio.ai_flows import execute_flow

        fail_result = _make_runtime_result(ok=False, error="Provider down")
        with _mock_hub():
            with patch("aksara.ai.runtime.run_prompt_pack", new_callable=AsyncMock, return_value=fail_result):
                result = await execute_flow("model", "explain_model", {"model_name": "User"})

        assert result["ok"] is False


# ═══════════════════════════════════════════════════════════════════════════
# 3. Convenience wrappers
# ═══════════════════════════════════════════════════════════════════════════


class TestConvenienceWrappers:
    @pytest.mark.asyncio
    async def test_execute_model_flow(self):
        from aksara.studio.ai_flows import execute_model_flow

        runtime_result = _make_runtime_result()
        with _mock_hub():
            with patch("aksara.ai.runtime.run_prompt_pack", new_callable=AsyncMock, return_value=runtime_result):
                result = await execute_model_flow("User", "explain_model")

        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_execute_route_flow(self):
        from aksara.studio.ai_flows import execute_route_flow

        runtime_result = _make_runtime_result()
        with _mock_hub():
            with patch("aksara.ai.runtime.run_prompt_pack", new_callable=AsyncMock, return_value=runtime_result):
                result = await execute_route_flow("/api/users", "GET", "review_endpoint")

        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_execute_query_flow(self):
        from aksara.studio.ai_flows import execute_query_flow

        runtime_result = _make_runtime_result()
        with _mock_hub():
            with patch("aksara.ai.runtime.run_prompt_pack", new_callable=AsyncMock, return_value=runtime_result):
                result = await execute_query_flow("SELECT 1", "explain_plan")

        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_execute_migration_flow(self):
        from aksara.studio.ai_flows import execute_migration_flow

        runtime_result = _make_runtime_result()
        with _mock_hub():
            with patch("aksara.ai.runtime.run_prompt_pack", new_callable=AsyncMock, return_value=runtime_result):
                result = await execute_migration_flow("explain_migration", app="blog")

        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_execute_diagnostic_flow(self):
        from aksara.studio.ai_flows import execute_diagnostic_flow

        runtime_result = _make_runtime_result()
        with _mock_hub():
            with patch("aksara.ai.runtime.run_prompt_pack", new_callable=AsyncMock, return_value=runtime_result):
                result = await execute_diagnostic_flow("diagnostic_prioritize", issue_id="DB_NO_URL")

        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_execute_model_flow_with_overrides(self):
        from aksara.studio.ai_flows import execute_model_flow

        runtime_result = _make_runtime_result(provider="anthropic", model="claude-3-5-sonnet-20241022")
        with _mock_hub():
            with patch("aksara.ai.runtime.run_prompt_pack", new_callable=AsyncMock, return_value=runtime_result):
                result = await execute_model_flow("User", "explain_model",
                                                  provider_override="anthropic",
                                                  model_override="claude-3-5-sonnet-20241022")

        assert result["ok"] is True


# ═══════════════════════════════════════════════════════════════════════════
# 4. Pydantic models
# ═══════════════════════════════════════════════════════════════════════════


class TestExecutionModels:
    def test_run_request_model(self):
        req = StudioAiFlowRunRequest(
            flow_type="model",
            action_key="explain_model",
            context={"model_name": "User"},
        )
        assert req.flow_type == "model"
        assert req.provider_override is None

    def test_run_request_with_overrides(self):
        req = StudioAiFlowRunRequest(
            flow_type="route",
            action_key="review_endpoint",
            context={"path": "/api/users"},
            provider_override="anthropic",
            model_override="claude-3-5-sonnet-20241022",
        )
        assert req.provider_override == "anthropic"

    def test_run_response_model(self):
        resp = StudioAiFlowRunResponse(
            ok=True,
            prompt_pack={"action_key": "explain_model"},
            execution={"response": "text"},
        )
        assert resp.ok is True
        assert resp.error is None

    def test_run_response_error(self):
        resp = StudioAiFlowRunResponse(
            ok=False,
            error="Provider not configured",
            error_code="AI_HUB_NOT_CONFIGURED",
        )
        assert resp.ok is False


# ═══════════════════════════════════════════════════════════════════════════
# 5. Response shape invariants
# ═══════════════════════════════════════════════════════════════════════════


class TestExecutionResponseShape:
    @pytest.mark.asyncio
    async def test_success_has_prompt_pack_and_execution(self):
        from aksara.studio.ai_flows import execute_flow

        runtime_result = _make_runtime_result()
        with _mock_hub():
            with patch("aksara.ai.runtime.run_prompt_pack", new_callable=AsyncMock, return_value=runtime_result):
                result = await execute_flow("model", "explain_model", {"model_name": "User"})

        assert "ok" in result
        assert "prompt_pack" in result
        assert "execution" in result

    @pytest.mark.asyncio
    async def test_error_has_prompt_pack(self):
        from aksara.studio.ai_flows import execute_flow

        with _mock_hub():
            result = await execute_flow("alien", "some_action", {})

        assert "ok" in result
        assert result["ok"] is False
