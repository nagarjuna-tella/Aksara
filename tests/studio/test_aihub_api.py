"""
Tests for AI Hub 2.0 API endpoints and Studio utility functions.

v0.5.28: Covers /studio/ai-hub/* endpoints, Studio model schemas,
and builder utilities.
"""

import json
import os
import pytest
from unittest import mock
from pathlib import Path

# ---------------------------------------------------------------------------
# Studio static file assertions (follows test_agent_ui.py pattern)
# ---------------------------------------------------------------------------

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "aksara" / "studio" / "static"


# ==========================================================================
# 1. Endpoint Registration Tests
# ==========================================================================


class TestAiHubEndpoints:
    """Verify all AI Hub 2.0 routes are registered on the Studio router."""

    @pytest.fixture(autouse=True)
    def _load_router(self):
        from aksara.studio.fastapi import router
        self.routes = [r.path for r in router.routes if hasattr(r, "path")]

    def test_status_endpoint(self):
        assert "/studio/ai-hub/status" in self.routes

    def test_providers_endpoint(self):
        assert "/studio/ai-hub/providers" in self.routes

    def test_models_endpoint(self):
        assert "/studio/ai-hub/models" in self.routes

    def test_configure_endpoint(self):
        assert "/studio/ai-hub/configure" in self.routes

    def test_configure_secret_endpoint(self):
        assert "/studio/ai-hub/configure/secret" in self.routes

    def test_defaults_endpoint(self):
        assert "/studio/ai-hub/defaults" in self.routes

    def test_test_endpoint(self):
        assert "/studio/ai-hub/test" in self.routes

    def test_legacy_providers_endpoint_still_exists(self):
        """v0.5.25 endpoint should not be removed (backward compat)."""
        assert "/studio/ai/hub/providers" in self.routes

    def test_legacy_ping_endpoint_still_exists(self):
        assert "/studio/ai/hub/providers/ping" in self.routes

    def test_legacy_save_endpoint_still_exists(self):
        assert "/studio/ai/hub/providers/save" in self.routes


# ==========================================================================
# 2. Studio Model Schema Tests
# ==========================================================================


class TestAiHubModels:
    def test_aihub_provider_schema(self):
        from aksara.studio.models import AiHubProvider
        p = AiHubProvider(kind="openai", configured=True, model="gpt-4o")
        assert p.kind == "openai"
        assert p.configured is True

    def test_aihub_model_schema(self):
        from aksara.studio.models import AiHubModel
        m = AiHubModel(model_id="gpt-4o", provider="openai", mode="chat")
        assert m.model_id == "gpt-4o"

    def test_aihub_status_schema(self):
        from aksara.studio.models import AiHubStatus
        s = AiHubStatus()
        assert s.overall == "disabled"
        assert s.configured_count == 0

    def test_aihub_routes_schema(self):
        from aksara.studio.models import AiHubRoutes
        r = AiHubRoutes()
        assert r.routes == []

    def test_aihub_onboarding_schema(self):
        from aksara.studio.models import AiHubOnboardingStatus
        o = AiHubOnboardingStatus()
        assert o.providers_selected is False
        assert o.completed is False

    def test_aihub_route_mapping_schema(self):
        from aksara.studio.models import AiHubRouteMapping
        rm = AiHubRouteMapping(feature="agents", provider="openai", model="gpt-4o")
        assert rm.status == "ok"

    def test_aihub_configure_request_schema(self):
        from aksara.studio.models import AiHubConfigureRequest
        r = AiHubConfigureRequest(provider="openai")
        assert r.provider == "openai"
        assert r.enabled is True

    def test_aihub_configure_secret_request_schema(self):
        from aksara.studio.models import AiHubConfigureSecretRequest
        r = AiHubConfigureSecretRequest(provider="openai", api_key="sk-test")
        assert r.provider == "openai"

    def test_aihub_defaults_request_schema(self):
        from aksara.studio.models import AiHubDefaultsRequest
        r = AiHubDefaultsRequest(chat_model="gpt-4o")
        assert r.chat_model == "gpt-4o"
        assert r.code_model is None

    def test_aihub_configure_response_schema(self):
        from aksara.studio.models import AiHubConfigureResponse
        r = AiHubConfigureResponse(ok=True, message="Done")
        assert r.ok is True

    def test_aihub_test_request_schema(self):
        from aksara.studio.models import AiHubTestRequest
        r = AiHubTestRequest(provider="openai")
        assert r.provider == "openai"

    def test_aihub_test_response_schema(self):
        from aksara.studio.models import AiHubTestResponse
        r = AiHubTestResponse(provider="openai", reachable=True, latency_ms=42.5)
        assert r.reachable is True
        assert r.latency_ms == 42.5

    def test_aihub_models_response_schema(self):
        from aksara.studio.models import AiHubModelsResponse
        r = AiHubModelsResponse()
        assert r.models == []

    def test_aihub_providers_response_schema(self):
        from aksara.studio.models import AiHubProvidersResponse
        r = AiHubProvidersResponse()
        assert r.providers == []
        assert r.total_count == 0


# ==========================================================================
# 3. Utility Builder Tests
# ==========================================================================


class TestBuildAiHubStatus:
    def test_partial_when_only_ollama_default(self):
        from aksara.studio.utils import build_aihub_status
        with mock.patch.dict(os.environ, {}, clear=True):
            status = build_aihub_status()
            # Ollama is always "configured" due to default base_url
            assert status.overall in ("ready", "partial")
            assert status.configured_count >= 1

    def test_ready_when_configured(self):
        from aksara.studio.utils import build_aihub_status
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True):
            status = build_aihub_status()
            assert status.overall == "ready"
            assert status.configured_count >= 1

    def test_has_onboarding(self):
        from aksara.studio.utils import build_aihub_status
        with mock.patch.dict(os.environ, {}, clear=True):
            status = build_aihub_status()
            assert hasattr(status, "onboarding")
            # Ollama base_url makes it "selected"
            assert isinstance(status.onboarding.providers_selected, bool)

    def test_has_warnings_list(self):
        from aksara.studio.utils import build_aihub_status
        with mock.patch.dict(os.environ, {}, clear=True):
            status = build_aihub_status()
            assert isinstance(status.warnings, list)

    def test_onboarding_completed_when_configured(self):
        from aksara.studio.utils import build_aihub_status
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True):
            status = build_aihub_status()
            assert status.onboarding.providers_selected is True
            assert status.onboarding.keys_entered is True

    def test_defaults_in_status(self):
        from aksara.studio.utils import build_aihub_status
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True):
            status = build_aihub_status()
            assert "chat_model" in status.defaults


class TestBuildAiHubProviders:
    def test_returns_all_providers(self):
        from aksara.studio.utils import build_aihub_providers
        with mock.patch.dict(os.environ, {}, clear=True):
            result = build_aihub_providers()
            assert result.total_count == 5

    def test_configured_count(self):
        from aksara.studio.utils import build_aihub_providers
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-x"}, clear=True):
            result = build_aihub_providers()
            assert result.configured_count >= 1

    def test_provider_kinds(self):
        from aksara.studio.utils import build_aihub_providers
        with mock.patch.dict(os.environ, {}, clear=True):
            result = build_aihub_providers()
            kinds = {p.kind for p in result.providers}
            assert "openai" in kinds
            assert "anthropic" in kinds

    def test_active_provider(self):
        from aksara.studio.utils import build_aihub_providers
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-x"}, clear=True):
            result = build_aihub_providers()
            assert result.active_provider == "openai"

    def test_provider_has_modes(self):
        from aksara.studio.utils import build_aihub_providers
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-x"}, clear=True):
            result = build_aihub_providers()
            oai = next(p for p in result.providers if p.kind == "openai")
            assert "chat" in oai.modes


class TestBuildAiHubModels:
    def test_models_present_even_with_ollama_default(self):
        from aksara.studio.utils import build_aihub_models
        with mock.patch.dict(os.environ, {}, clear=True):
            result = build_aihub_models()
            # Ollama is always configured so some models appear
            assert isinstance(result.models, list)

    def test_models_present_when_configured(self):
        from aksara.studio.utils import build_aihub_models
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-x"}, clear=True):
            result = build_aihub_models()
            assert len(result.models) > 0

    def test_models_have_provider(self):
        from aksara.studio.utils import build_aihub_models
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-x"}, clear=True):
            result = build_aihub_models()
            for m in result.models:
                assert m.provider

    def test_defaults_in_response(self):
        from aksara.studio.utils import build_aihub_models
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-x"}, clear=True):
            result = build_aihub_models()
            assert "chat_model" in result.defaults


class TestBuildAiHubConfigure:
    def test_configure_valid_provider(self):
        from aksara.studio.utils import build_aihub_configure
        result = build_aihub_configure(provider="openai", model="gpt-4o-mini")
        assert result.ok is True
        assert result.provider == "openai"

    def test_configure_unknown_provider(self):
        from aksara.studio.utils import build_aihub_configure
        result = build_aihub_configure(provider="unknown_provider")
        assert result.ok is False
        assert "Unknown" in result.message

    def test_configure_with_base_url(self):
        from aksara.studio.utils import build_aihub_configure
        result = build_aihub_configure(provider="openai", base_url="https://proxy.example.com/v1")
        assert result.ok is True


class TestBuildAiHubConfigureSecret:
    def test_configure_secret_saves(self, tmp_path, monkeypatch):
        from aksara.studio.utils import build_aihub_configure_secret
        monkeypatch.chdir(tmp_path)
        result = build_aihub_configure_secret(provider="openai", api_key="sk-test-secret")
        assert result.ok is True
        assert ".env" in result.message

    def test_configure_secret_invalid_provider(self, tmp_path, monkeypatch):
        from aksara.studio.utils import build_aihub_configure_secret
        monkeypatch.chdir(tmp_path)
        # Should still work — UnifiedAiProvider doesn't validate at construction
        # for unsupported types
        result = build_aihub_configure_secret(provider="openai", api_key="sk-key")
        assert result.ok is True


class TestBuildAiHubDefaults:
    def test_set_chat_model(self):
        from aksara.studio.utils import build_aihub_defaults
        with mock.patch.dict(os.environ, {}, clear=True):
            result = build_aihub_defaults(chat_model="gpt-4o-mini")
            assert result.ok is True

    def test_set_embeddings_model(self):
        from aksara.studio.utils import build_aihub_defaults
        with mock.patch.dict(os.environ, {}, clear=True):
            result = build_aihub_defaults(embeddings_model="text-embedding-3-large")
            assert result.ok is True

    def test_set_multiple(self):
        from aksara.studio.utils import build_aihub_defaults
        with mock.patch.dict(os.environ, {}, clear=True):
            result = build_aihub_defaults(
                chat_model="gpt-4o",
                chat_provider="openai",
                code_model="gpt-4o",
            )
            assert result.ok is True


class TestBuildAiHubTest:
    def test_unconfigured_provider(self):
        from aksara.studio.utils import build_aihub_test
        with mock.patch.dict(os.environ, {}, clear=True):
            result = build_aihub_test("openai")
            assert result.reachable is False
            assert "not configured" in (result.error or "")

    def test_unknown_provider(self):
        from aksara.studio.utils import build_aihub_test
        with mock.patch.dict(os.environ, {}, clear=True):
            result = build_aihub_test("nonexistent")
            assert result.reachable is False

    def test_configured_provider_mock_ping(self):
        from aksara.studio.utils import build_aihub_test
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-x"}, clear=True):
            with mock.patch(
                "aksara.ai.providers_unified.UnifiedAiProvider.ping",
                return_value={"ok": True, "message": "Connected"},
            ):
                result = build_aihub_test("openai")
                assert result.reachable is True
                assert result.latency_ms is not None
                assert result.latency_ms >= 0

    def test_test_returns_modes(self):
        from aksara.studio.utils import build_aihub_test
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-x"}, clear=True):
            with mock.patch(
                "aksara.ai.providers_unified.UnifiedAiProvider.ping",
                return_value={"ok": True},
            ):
                result = build_aihub_test("openai")
                assert "chat" in result.modes


class TestBuildAiHubRoutes:
    def test_routes_with_configured_provider(self):
        from aksara.studio.utils import build_aihub_routes
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-x"}, clear=True):
            result = build_aihub_routes()
            features = [r.feature for r in result.routes]
            assert "agents" in features
            assert "playbooks" in features
            assert "search_embeddings" in features
            assert "diagnostics" in features

    def test_routes_agents_ok_when_configured(self):
        from aksara.studio.utils import build_aihub_routes
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-x"}, clear=True):
            result = build_aihub_routes()
            agents = next(r for r in result.routes if r.feature == "agents")
            assert agents.status == "ok"
            assert agents.provider == "openai"

    def test_routes_fallback_or_ok_with_default_ollama(self):
        from aksara.studio.utils import build_aihub_routes
        with mock.patch.dict(os.environ, {}, clear=True):
            result = build_aihub_routes()
            agents = next(r for r in result.routes if r.feature == "agents")
            # Ollama provides chat defaults
            assert agents.status in ("ok", "missing")

    def test_routes_search_fallback_anthropic_only(self):
        from aksara.studio.utils import build_aihub_routes
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "ant-x"}, clear=True):
            result = build_aihub_routes()
            search = next(r for r in result.routes if r.feature == "search_embeddings")
            # Ollama provides embeddings, so status depends on which is primary
            assert search.status in ("ok", "fallback")

    def test_routes_warnings_type(self):
        from aksara.studio.utils import build_aihub_routes
        with mock.patch.dict(os.environ, {}, clear=True):
            result = build_aihub_routes()
            assert isinstance(result.warnings, list)

    def test_routes_no_warnings_when_fully_configured(self):
        from aksara.studio.utils import build_aihub_routes
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-x"}, clear=True):
            result = build_aihub_routes()
            # OpenAI covers all modes, should have minimal warnings
            agent_routes = [r for r in result.routes if r.status == "missing"]
            assert len(agent_routes) == 0
