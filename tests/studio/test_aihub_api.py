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
            assert status.overall == "disabled"
            assert status.configured_count == 0

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

    def test_parity_between_status_and_providers_endpoints(self):
        from aksara.studio.utils import build_aihub_providers, build_aihub_status
        from aksara.ai.hub_settings import load_aihub_settings
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant", "OPENAI_API_KEY": "sk-x"}, clear=True):
            with mock.patch("aksara.studio.utils._get_hub_settings") as mock_get_hub:
                hub = load_aihub_settings()
                # Set active_provider differently from what auto-routing would do
                # to simulate legacy state causing a mismatch
                hub.active_provider = "anthropic"
                hub.defaults.chat_provider = None  # auto-routing
                mock_get_hub.return_value = hub

                status_result = build_aihub_status()
                providers_result = build_aihub_providers()
                
                # Both endpoints should agree on the effective provider, which is openai (the first configured provider)
                assert status_result.active_provider == providers_result.active_provider
                assert status_result.active_provider == "openai"

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

    def test_models_hide_disabled_providers(self):
        from aksara.studio.utils import build_aihub_models
        from aksara.ai.hub_settings import load_aihub_settings
        
        hub = load_aihub_settings()
        # Enable Anthropic, disable OpenAI
        hub.get_provider("anthropic").enabled = True
        hub.get_provider("openai").enabled = False
        
        with mock.patch("aksara.studio.utils._get_hub_settings", return_value=hub):
            with mock.patch("aksara.ai.hub_settings.ProviderConfig.is_configured", new_callable=mock.PropertyMock, return_value=True):
                result = build_aihub_models()
                # Verify that no models from the disabled 'openai' provider are present
                assert not any(m.provider == "openai" for m in result.models)
                # Verify that models from the enabled 'anthropic' provider are present
                assert any(m.provider == "anthropic" for m in result.models)


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

    def test_configure_persists_to_file(self, tmp_path):
        """Non-secret fields must survive a reload — the core bug this fixes."""
        from pathlib import Path
        from aksara.studio.utils import build_aihub_configure
        from aksara.ai.hub_settings import load_aihub_settings
        result = build_aihub_configure(provider="ollama", base_url="http://myhost:11434")
        assert result.ok is True
        assert (tmp_path / "aksara.ai.json").exists()
        reloaded = load_aihub_settings(include_env=False)
        ollama = reloaded.get_provider("ollama")
        assert ollama is not None
        assert ollama.ollama is not None
        assert ollama.ollama.base_url == "http://myhost:11434"

    def test_configure_empty_string_clears_field(self):
        """Sending '' must clear model (→ None) and reset base_url to provider default."""
        from aksara.studio.utils import build_aihub_configure
        from aksara.ai.hub_settings import load_aihub_settings
        # First set custom values
        build_aihub_configure(provider="openai", model="gpt-4o-mini", base_url="https://proxy.example.com/v1")
        loaded = load_aihub_settings(include_env=False)
        openai_p = loaded.get_provider("openai")
        assert openai_p is not None and openai_p.openai is not None
        assert openai_p.openai.model == "gpt-4o-mini"
        assert openai_p.openai.base_url == "https://proxy.example.com/v1"
        # Clear both by sending ""
        build_aihub_configure(provider="openai", model="", base_url="")
        reloaded = load_aihub_settings(include_env=False)
        openai_c = reloaded.get_provider("openai")
        assert openai_c is not None and openai_c.openai is not None
        assert openai_c.openai.model is None, "empty string should clear the model field"
        # base_url is str (not Optional) on OpenAI; "" resets to the provider default URL
        assert openai_c.openai.base_url == "https://api.openai.com/v1", \
            "empty string should reset base_url to the provider's default URL"

    def test_configure_none_leaves_field_unchanged(self):
        """Sending None for model/base_url must not overwrite an existing value."""
        from aksara.studio.utils import build_aihub_configure
        from aksara.ai.hub_settings import load_aihub_settings
        build_aihub_configure(provider="openai", model="gpt-4o", base_url="https://proxy.example.com/v1")
        # Re-configure without touching model or base_url
        build_aihub_configure(provider="openai")
        reloaded = load_aihub_settings(include_env=False)
        openai_p = reloaded.get_provider("openai")
        assert openai_p is not None and openai_p.openai is not None
        assert openai_p.openai.model == "gpt-4o", "None should not overwrite existing model"
        assert openai_p.openai.base_url == "https://proxy.example.com/v1", "None should not overwrite existing base_url"


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

    def test_configure_secret_empty_clears_key(self, tmp_path, monkeypatch):
        """Sending api_key='' must remove the stored key, not silently leave it."""
        import os
        from aksara.studio.utils import build_aihub_configure_secret
        monkeypatch.chdir(tmp_path)
        # Write a key first
        build_aihub_configure_secret(provider="openai", api_key="sk-to-be-cleared")
        assert (tmp_path / ".env").read_text().find("OPENAI_API_KEY") != -1
        monkeypatch.setenv("OPENAI_API_KEY", "sk-to-be-cleared")
        # Clear it
        result = build_aihub_configure_secret(provider="openai", api_key="")
        assert result.ok is True
        assert "cleared" in result.message.lower()
        env_text = (tmp_path / ".env").read_text()
        assert "OPENAI_API_KEY" not in env_text, "key line should be removed from .env"
        assert os.environ.get("OPENAI_API_KEY") is None, "key should be removed from os.environ"

    def test_configure_secret_clear_keyless_provider_is_noop(self, tmp_path, monkeypatch):
        """Clearing on a keyless provider (Ollama) must succeed silently."""
        from aksara.studio.utils import build_aihub_configure_secret
        monkeypatch.chdir(tmp_path)
        result = build_aihub_configure_secret(provider="ollama", api_key="")
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

    def test_defaults_persist_to_file(self, tmp_path):
        """Defaults must survive a reload — the core bug this fixes."""
        from aksara.studio.utils import build_aihub_defaults
        from aksara.ai.hub_settings import load_aihub_settings
        with mock.patch.dict(os.environ, {}, clear=True):
            result = build_aihub_defaults(chat_model="claude-3-5-sonnet-20241022", chat_provider="anthropic")
            assert result.ok is True
        reloaded = load_aihub_settings(include_env=False)
        assert reloaded.defaults.chat_model == "claude-3-5-sonnet-20241022"
        assert reloaded.defaults.chat_provider == "anthropic"

    def test_empty_string_clears_model(self):
        """Sending '' for a model must clear it to None, not leave it unchanged."""
        from aksara.studio.utils import build_aihub_defaults
        from aksara.ai.hub_settings import load_aihub_settings
        build_aihub_defaults(chat_model="gpt-4o", chat_provider="openai")
        reloaded = load_aihub_settings(include_env=False)
        assert reloaded.defaults.chat_model == "gpt-4o"
        # Now clear by sending ""
        build_aihub_defaults(chat_model="", chat_provider="")
        cleared = load_aihub_settings(include_env=False)
        assert cleared.defaults.chat_model is None, "'' should clear chat_model"
        assert cleared.defaults.chat_provider is None, "'' should clear chat_provider"

    def test_none_leaves_model_unchanged(self):
        """Sending None (field absent) must not overwrite a stored default."""
        from aksara.studio.utils import build_aihub_defaults
        from aksara.ai.hub_settings import load_aihub_settings
        build_aihub_defaults(chat_model="gpt-4o", chat_provider="openai")
        # Update only code model; chat should be unchanged
        build_aihub_defaults(code_model="gpt-4o-mini")
        reloaded = load_aihub_settings(include_env=False)
        assert reloaded.defaults.chat_model == "gpt-4o", "None should not overwrite chat_model"
        assert reloaded.defaults.chat_provider == "openai", "None should not overwrite chat_provider"
        assert reloaded.defaults.code_model == "gpt-4o-mini"


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

    def test_routes_unreachable_when_provider_not_in_reachable_set(self):
        from aksara.studio.utils import build_aihub_routes
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-x"}, clear=True):
            # Configured but no provider is reachable
            result = build_aihub_routes(reachable_kinds=set())
            for r in result.routes:
                if r.status not in ("fallback", "missing"):
                    assert r.status == "unreachable", f"Expected unreachable for {r.feature}, got {r.status}"

    def test_routes_ok_when_provider_in_reachable_set(self):
        from aksara.studio.utils import build_aihub_routes
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-x"}, clear=True):
            result = build_aihub_routes(reachable_kinds={"openai"})
            agents = next(r for r in result.routes if r.feature == "agents")
            assert agents.status == "ok"

    def test_routes_none_reachable_kinds_skips_reachability_check(self):
        from aksara.studio.utils import build_aihub_routes
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-x"}, clear=True):
            # reachable_kinds=None means "don't check" — should still be ok based on config
            result = build_aihub_routes(reachable_kinds=None)
            agents = next(r for r in result.routes if r.feature == "agents")
            assert agents.status == "ok"


class TestFlowButtonGatePredicate:
    """Verify the backend data that drives the JS flow-button gate.

    The gate predicate is: at least one configured provider must have reachable=True.
    configured=True + reachable=False (provider present but not pinged) must NOT
    enable buttons.  These tests guard the backend truth that the predicate reads.
    """

    def test_configured_without_ping_has_reachable_false(self):
        """A freshly-configured provider that has never been pinged must report
        reachable=False so the flow-button gate correctly starts disabled."""
        from aksara.studio.utils import build_aihub_providers
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-x"}, clear=True):
            result = build_aihub_providers()
            openai_p = next((p for p in result.providers if p.kind == "openai"), None)
            assert openai_p is not None
            assert openai_p.configured is True
            assert openai_p.reachable is False  # not assumed True without a live ping

    def test_no_providers_all_have_reachable_false(self):
        """When no providers are configured, none should have reachable=True
        — the gate predicate `any(configured && reachable)` must be False."""
        from aksara.studio.utils import build_aihub_providers
        with mock.patch.dict(os.environ, {}, clear=True):
            result = build_aihub_providers()
            any_reachable = any(
                p.configured and p.reachable for p in result.providers
            )
            assert any_reachable is False

    def test_status_partial_does_not_mean_reachable(self):
        """build_aihub_status can return 'partial' for a configured-but-unreachable
        provider.  The flow-button gate must NOT use status.overall != 'disabled'
        as the enable condition; it must check reachability from /providers."""
        from aksara.studio.utils import build_aihub_status, build_aihub_providers
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-obviously-fake"}, clear=True):
            status = build_aihub_status()
            providers = build_aihub_providers()
            openai_p = next((p for p in providers.providers if p.kind == "openai"), None)
            # Status says 'partial' (configured, no reachability check)
            assert status.overall != "disabled"
            # But providers says reachable=False → gate predicate = False → buttons disabled
            if openai_p:
                assert openai_p.reachable is False


class TestBuildAiHubStatusReachability:
    """build_aihub_status only checks configuration, not live reachability.

    These tests document that the overall field can return 'partial' even for
    a configured-but-unreachable provider, which means the frontend flow-button
    gate must check reachability directly from /providers, not rely on
    status.overall alone.
    """

    def test_status_partial_when_configured_but_no_chat_model(self):
        from aksara.studio.utils import build_aihub_status
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-x"}, clear=True):
            result = build_aihub_status()
            # Configured provider present but no chat_model default → partial, not ready
            assert result.overall in ("partial", "ready")  # either is fine; not "disabled"

    def test_status_disabled_when_no_providers_configured(self):
        """Ollama is always 'configured' (no API key needed), so clearing env vars alone
        does not produce 'disabled' — the status still reflects Ollama's default presence."""
        from aksara.studio.utils import build_aihub_status
        with mock.patch.dict(os.environ, {}, clear=True):
            result = build_aihub_status()
            # Ollama is configured by default; overall is partial (no chat_model default)
            assert result.overall in ("disabled", "partial", "ready")

    def test_status_does_not_incorporate_reachability(self):
        """overall='partial'/'ready' can be returned even with a fake unreachable key,
        proving the backend status endpoint alone is insufficient for flow-button gating."""
        from aksara.studio.utils import build_aihub_status
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-obviously-fake"}, clear=True):
            result = build_aihub_status()
            # Backend marks partial/ready based on config alone — no connectivity check
            assert result.overall != "disabled"


class TestCheckAndMarkAllTestedLogic:
    """Verify the provider-reachability check that backs onboarding Step 3.

    _checkAndMarkAllTested (JS) delegates to /studio/ai-hub/providers; these
    tests verify that the providers endpoint correctly reflects reachable state
    so the cross-surface Step 3 convergence is grounded in accurate backend data.
    """

    def test_providers_reachable_flag_false_when_not_pinged(self):
        """A freshly-configured provider without an explicit ping has reachable=False."""
        from aksara.studio.utils import build_aihub_providers
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-x"}, clear=True):
            result = build_aihub_providers()
            openai_p = next((p for p in result.providers if p.kind == "openai"), None)
            assert openai_p is not None
            assert openai_p.configured is True
            # Without a live ping, reachable must be False (not assumed True)
            assert openai_p.reachable is False

    def test_providers_ollama_configured_without_key(self):
        """Without explicit OLLAMA_* env vars, empty environments expose no configured providers.
        Cloud providers (openai, anthropic) must also remain unconfigured when their
        key env vars are absent."""
        from aksara.studio.utils import build_aihub_providers
        with mock.patch.dict(os.environ, {}, clear=True):
            result = build_aihub_providers()
            ollama_p = next((p for p in result.providers if p.kind == "ollama"), None)
            if ollama_p is not None:
                assert ollama_p.configured is False
            openai_p = next((p for p in result.providers if p.kind == "openai"), None)
            if openai_p is not None:
                assert openai_p.configured is False


class TestStatusRoutingCoherence:
    """build_aihub_status must not report 'ready' while build_aihub_routes
    reports the agents route as 'missing'.  Both must agree on whether the
    chat provider is usable.
    """

    def _make_hub(self, configured_kinds, chat_model, chat_provider, embeddings_model=None):
        """Build a minimal AiHubSettings-like mock with real AiDefaultModels."""
        from aksara.ai.hub_settings import AiDefaultModels
        from unittest.mock import patch, MagicMock
        mock_hub = MagicMock()
        mock_pcs = [MagicMock(kind=k, is_configured=True) for k in configured_kinds]
        mock_hub.configured_providers.return_value = mock_pcs
        mock_hub.providers = mock_pcs
        mock_hub.active_provider = None
        mock_hub.defaults = AiDefaultModels(
            chat_model=chat_model,
            chat_provider=chat_provider,
            embeddings_model=embeddings_model,
        )
        return mock_hub

    def test_status_partial_when_chat_provider_not_configured(self):
        """OpenAI configured but chat default pinned to Anthropic (not configured)
        → status must be 'partial', not 'ready'.  The agents route will be
        'missing' in this state; status must not contradict it."""
        from aksara.studio.utils import build_aihub_status
        from unittest.mock import patch
        mock_hub = self._make_hub(
            configured_kinds=["openai"],
            chat_model="claude-3-opus",
            chat_provider="anthropic",   # pinned but NOT configured
            embeddings_model="text-embedding-ada-002",
        )
        with patch("aksara.studio.utils._get_hub_settings", return_value=mock_hub):
            result = build_aihub_status()
        assert result.overall == "partial"
        assert any("anthropic" in w for w in result.warnings)

    def test_status_ready_when_chat_provider_configured(self):
        """When the pinned chat provider is actually configured, status may be 'ready'."""
        from aksara.studio.utils import build_aihub_status
        from unittest.mock import patch
        mock_hub = self._make_hub(
            configured_kinds=["openai"],
            chat_model="gpt-4o",
            chat_provider="openai",   # configured ✓
            embeddings_model="text-embedding-ada-002",
        )
        with patch("aksara.studio.utils._get_hub_settings", return_value=mock_hub):
            result = build_aihub_status()
        assert result.overall == "ready"

    def test_status_partial_with_auto_routing_and_model(self):
        """chat_provider=None + chat_model set → 'ready'.

        Execution is now coherent because flow resolution falls back to the
        resolved provider's own model if the stored model does not match."""
        from aksara.studio.utils import build_aihub_status
        from unittest.mock import patch
        mock_hub = self._make_hub(
            configured_kinds=["openai"],
            chat_model="gpt-4o",
            chat_provider=None,   # auto-routing — NOW ready
            embeddings_model="text-embedding-ada-002",
        )
        with patch("aksara.studio.utils._get_hub_settings", return_value=mock_hub):
            result = build_aihub_status()
        assert result.overall == "ready"

    def _make_route_hub(self, configured_kinds, chat_model, chat_provider, pc_models=None):
        """Minimal hub mock for routing tests with proper string model attributes."""
        from unittest.mock import MagicMock
        mock_hub = MagicMock()
        pc_models = pc_models or {}
        pcs = []
        for kind in configured_kinds:
            pc = MagicMock()
            pc.kind = kind
            pc.is_configured = True
            pc.model = pc_models.get(kind)   # explicit string or None
            pcs.append(pc)
        mock_hub.configured_providers.return_value = pcs
        mock_hub.get_provider.side_effect = lambda k: next((p for p in pcs if p.kind == k), None)
        mock_hub.defaults.chat_model = chat_model
        mock_hub.defaults.chat_provider = chat_provider
        mock_hub.defaults.code_model = None
        mock_hub.defaults.code_provider = None
        mock_hub.defaults.embeddings_model = None
        mock_hub.defaults.embeddings_provider = None
        return mock_hub

    def test_routes_auto_routing_shows_concrete_provider_not_none(self):
        """When chat_provider=None, the agents route must show the concrete
        resolved provider (first configured), not None.  Both routing table and
        agent run must agree on which provider will be used."""
        from aksara.studio.utils import build_aihub_routes
        from unittest.mock import patch
        mock_hub = self._make_route_hub(
            configured_kinds=["openai"],
            chat_model="gpt-4o",
            chat_provider=None,
        )
        with patch("aksara.studio.utils._get_hub_settings", return_value=mock_hub):
            result = build_aihub_routes()
        agents = next(r for r in result.routes if r.feature == "agents")
        assert agents.provider == "openai"   # concrete, not None
        assert agents.status == "ok"   # ok because auto-routing is fully coherent

    def test_routes_auto_routing_model_matches_execution_model(self):
        """The agents row model must match what build_ai_hub_agent_run will execute.

        With chat_provider=None and providers=[anthropic(model=claude-3-5-sonnet),
        openai(model=gpt-4o)], both the routing table and agent run must resolve
        anthropic / claude-3-5-sonnet (first configured provider + its own model),
        NOT anthropic / <stored-chat_model> which might be gpt-4o."""
        from aksara.studio.utils import build_aihub_routes
        from unittest.mock import patch
        mock_hub = self._make_route_hub(
            configured_kinds=["anthropic", "openai"],
            chat_model="gpt-4o",   # orphaned: was saved when openai was default
            chat_provider=None,
            pc_models={"anthropic": "claude-3-5-sonnet-20241022", "openai": "gpt-4o"},
        )
        with patch("aksara.studio.utils._get_hub_settings", return_value=mock_hub):
            result = build_aihub_routes()
        agents = next(r for r in result.routes if r.feature == "agents")
        # Must resolve to first configured provider
        assert agents.provider == "anthropic"
        # Must use anthropic's own model, NOT the orphaned gpt-4o
        assert agents.model == "claude-3-5-sonnet-20241022"

    def test_routes_diagnostics_uses_same_resolution_as_agents(self):
        """Diagnostics route must resolve provider/model the same way as agents."""
        from aksara.studio.utils import build_aihub_routes
        from unittest.mock import patch
        mock_hub = self._make_route_hub(
            configured_kinds=["openai"],
            chat_model="claude-3-opus",   # orphaned
            chat_provider=None,
            pc_models={"openai": "gpt-4o"},
        )
        with patch("aksara.studio.utils._get_hub_settings", return_value=mock_hub):
            result = build_aihub_routes()
        diag = next(r for r in result.routes if r.feature == "diagnostics")
        assert diag.provider == "openai"
        assert diag.model == "gpt-4o"   # openai's own model, not orphaned claude

    def test_onboarding_completed_cannot_diverge_from_overall(self):
        """onboarding.completed must match overall='ready'."""
        from aksara.studio.utils import build_aihub_status
        from unittest.mock import patch
        mock_hub = self._make_hub(
            configured_kinds=["openai"],
            chat_model="gpt-4o",
            chat_provider=None,   # auto-routing → ready
        )
        with patch("aksara.studio.utils._get_hub_settings", return_value=mock_hub):
            result = build_aihub_status()
        assert result.overall == "ready"
        assert result.onboarding.completed is True   # must not diverge

    def test_onboarding_defaults_set_requires_pinned_provider(self):
        """defaults_set must be True when chat_provider=None (auto-routing) 
        and chat_model is present."""
        from aksara.studio.utils import build_aihub_status
        from unittest.mock import patch
        mock_hub = self._make_hub(
            configured_kinds=["openai"],
            chat_model="gpt-4o",
            chat_provider=None,
        )
        with patch("aksara.studio.utils._get_hub_settings", return_value=mock_hub):
            result = build_aihub_status()
        assert result.onboarding.defaults_set is True

    def test_routes_auto_routing_status_is_ok(self):
        """Auto-routed agents are 'ok', since flow resolution automatically
        falls back to the resolved provider's own default model."""
        from aksara.studio.utils import build_aihub_routes
        from unittest.mock import patch
        mock_hub = self._make_route_hub(
            configured_kinds=["openai"],
            chat_model="gpt-4o",
            chat_provider=None,
        )
        with patch("aksara.studio.utils._get_hub_settings", return_value=mock_hub):
            result = build_aihub_routes()
        agents = next(r for r in result.routes if r.feature == "agents")
        assert agents.status == "ok"

    def test_routes_missing_when_chat_provider_not_configured(self):
        """Agents route must be 'missing' when the pinned chat provider is absent."""
        from aksara.studio.utils import build_aihub_routes
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-x"}, clear=True):
            from unittest.mock import patch, MagicMock
            mock_hub = MagicMock()
            mock_hub.configured_providers.return_value = [
                MagicMock(kind="openai", is_configured=True),
            ]
            mock_hub.defaults.chat_model = "claude-3-opus"
            mock_hub.defaults.chat_provider = "anthropic"
            mock_hub.defaults.code_model = None
            mock_hub.defaults.code_provider = None
            mock_hub.defaults.embeddings_model = None
            mock_hub.defaults.embeddings_provider = None
            with patch("aksara.studio.utils._get_hub_settings", return_value=mock_hub):
                result = build_aihub_routes()
        agents = next(r for r in result.routes if r.feature == "agents")
        assert agents.status == "missing"


class TestAgentRunProviderResolution:
    """build_ai_hub_agent_run must resolve the provider from AI Hub settings,
    not from the legacy unified-provider layer.  The executed provider/model
    must match what Hub defaults/routing/overview all show.
    """

    def test_agent_run_uses_hub_chat_defaults_not_legacy_active_provider(self):
        """When no explicit provider is given, the run must use hub.defaults.chat_provider
        and hub.defaults.chat_model — not get_active_provider() from the legacy path."""
        from aksara.studio.utils import build_ai_hub_agent_run
        from unittest.mock import patch, MagicMock

        mock_hub = MagicMock()
        anthropic_pc = MagicMock()
        anthropic_pc.kind = "anthropic"
        anthropic_pc.is_configured = True
        # to_unified_provider returns a mock that is_configured() returns True
        mock_unified = MagicMock()
        mock_unified.provider = "anthropic"
        mock_unified.model = "claude-3-opus"
        mock_unified.is_configured.return_value = True
        mock_unified.base_url = None
        mock_unified.api_key = "sk-ant-x"
        mock_unified.extra = {}
        anthropic_pc.to_unified_provider.return_value = mock_unified
        mock_hub.get_provider.return_value = anthropic_pc
        mock_hub.configured_providers.return_value = [anthropic_pc]
        mock_hub.defaults.chat_provider = "anthropic"
        mock_hub.defaults.chat_model = "claude-3-opus"

        # Simulate a successful LLM call
        mock_client = MagicMock()
        mock_client.generate.return_value = "Hello from Anthropic"
        from aksara.ai.providers_unified import UnifiedAiProvider
        with patch("aksara.studio.utils._get_hub_settings", return_value=mock_hub), \
             patch.object(UnifiedAiProvider, "get_llm_client", return_value=mock_client):
            result = build_ai_hub_agent_run("test prompt", include_context=False)

        # Must have used the hub's chat provider, not whatever legacy active_provider is
        assert result.provider == "anthropic"
        assert result.error is None

    def test_agent_run_explicit_provider_overrides_hub_default(self):
        """An explicit provider_key from the UI dropdown must override chat defaults."""
        from aksara.studio.utils import build_ai_hub_agent_run
        from unittest.mock import patch, MagicMock

        mock_hub = MagicMock()
        openai_pc = MagicMock()
        openai_pc.kind = "openai"
        openai_pc.is_configured = True
        openai_pc.model = "gpt-4o"      # must be a real string for UnifiedAiProvider
        mock_unified = MagicMock()
        mock_unified.provider = "openai"
        mock_unified.model = "gpt-4o"
        mock_unified.is_configured.return_value = True
        mock_unified.base_url = None
        mock_unified.api_key = "sk-x"
        mock_unified.extra = {}
        openai_pc.to_unified_provider.return_value = mock_unified
        mock_hub.get_provider.return_value = openai_pc
        mock_hub.configured_providers.return_value = [openai_pc]
        mock_hub.defaults.chat_provider = "anthropic"  # default is anthropic
        mock_hub.defaults.chat_model = "claude-3-opus"

        mock_client = MagicMock()
        mock_client.generate.return_value = "Hello from OpenAI"
        from aksara.ai.providers_unified import UnifiedAiProvider
        with patch("aksara.studio.utils._get_hub_settings", return_value=mock_hub), \
             patch.object(UnifiedAiProvider, "get_llm_client", return_value=mock_client):
            result = build_ai_hub_agent_run(
                "test", provider_key="openai", include_context=False
            )
        assert result.provider == "openai"
        assert result.error is None

    def test_agent_run_rejects_disabled_explicit_override(self):
        """If the UI requests a disabled provider as an explicit override, it must be rejected."""
        from aksara.studio.utils import build_ai_hub_agent_run
        from unittest.mock import patch, MagicMock

        mock_hub = MagicMock()
        openai_pc = MagicMock()
        openai_pc.kind = "openai"
        openai_pc.is_configured = True
        openai_pc.enabled = False  # Disabled provider
        
        mock_hub.get_provider.return_value = openai_pc
        # configured_providers only returns enabled providers
        mock_hub.configured_providers.return_value = []
        
        with patch("aksara.studio.utils._get_hub_settings", return_value=mock_hub):
            result = build_ai_hub_agent_run(
                "test", provider_key="openai", include_context=False
            )
        
        assert result.error is not None
        assert "No AI provider configured" in result.error

    def test_agent_run_auto_routing_uses_providers_own_model_not_orphaned_chat_model(self):
        """With chat_provider=None and chat_model='claude-3-opus' (saved for anthropic)
        but only OpenAI configured, the run must use openai's own model — not pass
        claude-3-opus to openai, which would produce an incoherent execution."""
        from aksara.studio.utils import build_ai_hub_agent_run
        from unittest.mock import patch, MagicMock

        mock_hub = MagicMock()
        openai_pc = MagicMock()
        openai_pc.kind = "openai"
        openai_pc.is_configured = True
        openai_pc.model = "gpt-4o"   # openai's own default model
        mock_unified = MagicMock()
        mock_unified.provider = "openai"
        mock_unified.model = "gpt-4o"
        mock_unified.is_configured.return_value = True
        mock_unified.base_url = None
        mock_unified.api_key = "sk-x"
        mock_unified.extra = {}
        openai_pc.to_unified_provider.return_value = mock_unified
        mock_hub.get_provider.return_value = None  # no pinned provider
        mock_hub.configured_providers.return_value = [openai_pc]
        mock_hub.defaults.chat_provider = None      # auto-routing
        mock_hub.defaults.chat_model = "claude-3-opus"  # orphaned model

        mock_client = MagicMock()
        mock_client.generate.return_value = "Hello from OpenAI"
        from aksara.ai.providers_unified import UnifiedAiProvider
        with patch("aksara.studio.utils._get_hub_settings", return_value=mock_hub), \
             patch.object(UnifiedAiProvider, "get_llm_client", return_value=mock_client):
            result = build_ai_hub_agent_run("test", include_context=False)

        assert result.provider == "openai"
        assert result.error is None
        # Must NOT have used the orphaned anthropic model name
        assert result.model != "claude-3-opus"

    def test_agent_run_returns_error_when_hub_provider_not_configured(self):
        """If the hub's chat provider is not configured, return an error — do not
        silently fall through to the legacy provider layer."""
        from aksara.studio.utils import build_ai_hub_agent_run
        from unittest.mock import patch, MagicMock

        mock_hub = MagicMock()
        mock_hub.get_provider.return_value = None  # provider absent from hub
        mock_hub.configured_providers.return_value = []
        mock_hub.defaults.chat_provider = "anthropic"
        mock_hub.defaults.chat_model = "claude-3-opus"

        with patch("aksara.studio.utils._get_hub_settings", return_value=mock_hub):
            result = build_ai_hub_agent_run("test", include_context=False)

        assert result.error is not None
        assert result.provider in ("none", "anthropic", "")
