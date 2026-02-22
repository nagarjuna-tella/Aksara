"""
Tests for provider detection — AI Hub 2.0.

v0.5.28: Covers detect_all_providers(), provider_status_summary(),
UnifiedAiProvider.from_provider_config(), is_reachable(), get_supported_modes().
"""

import os
import pytest
from unittest import mock

from aksara.ai.providers_unified import (
    UnifiedAiProvider,
    detect_all_providers,
    get_active_provider,
    provider_status_summary,
)
from aksara.ai.hub_settings import (
    AiHubSettings,
    ProviderConfig,
    OpenAIConfig,
    AnthropicConfig,
    AzureOpenAIConfig,
    OllamaConfig,
    CustomHttpConfig,
)


# ==========================================================================
# 1. detect_all_providers()
# ==========================================================================


class TestDetectAllProviders:
    def test_returns_five_providers(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            providers = detect_all_providers()
            assert len(providers) == 5

    def test_all_provider_types_present(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            providers = detect_all_providers()
            kinds = {p.provider for p in providers}
            assert kinds == {"openai", "azure", "anthropic", "ollama", "custom"}

    def test_openai_configured_when_key_present(self):
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-x"}, clear=True):
            providers = detect_all_providers()
            oai = next(p for p in providers if p.provider == "openai")
            assert oai.is_configured()

    def test_anthropic_configured_when_key_present(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "ant-x"}, clear=True):
            providers = detect_all_providers()
            ant = next(p for p in providers if p.provider == "anthropic")
            assert ant.is_configured()

    def test_azure_configured_when_key_present(self):
        with mock.patch.dict(os.environ, {"AZURE_OPENAI_API_KEY": "az-x"}, clear=True):
            providers = detect_all_providers()
            az = next(p for p in providers if p.provider == "azure")
            assert az.is_configured()

    def test_ollama_configured_with_url(self):
        with mock.patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://localhost:11434"}, clear=True):
            providers = detect_all_providers()
            oll = next(p for p in providers if p.provider == "ollama")
            assert oll.is_configured()

    def test_custom_configured_with_key(self):
        with mock.patch.dict(os.environ, {"CUSTOM_LLM_API_KEY": "c-x"}, clear=True):
            providers = detect_all_providers()
            cust = next(p for p in providers if p.provider == "custom")
            assert cust.is_configured()

    def test_returns_unified_provider_instances(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            providers = detect_all_providers()
            for p in providers:
                assert isinstance(p, UnifiedAiProvider)


# ==========================================================================
# 2. provider_status_summary()
# ==========================================================================


class TestProviderStatusSummary:
    def test_summary_structure(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            summary = provider_status_summary()
            assert "total" in summary
            assert "configured" in summary
            assert "active_provider" in summary
            assert "active_model" in summary
            assert "providers" in summary

    def test_summary_total_count(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            summary = provider_status_summary()
            assert summary["total"] == 5

    def test_summary_configured_count(self):
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-x"}, clear=True):
            summary = provider_status_summary()
            assert summary["configured"] >= 1

    def test_summary_provider_items(self):
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-x"}, clear=True):
            summary = provider_status_summary()
            for item in summary["providers"]:
                assert "provider" in item
                assert "configured" in item
                assert "model" in item
                assert "modes" in item

    def test_summary_active_provider(self):
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-x"}, clear=True):
            summary = provider_status_summary()
            assert summary["active_provider"] == "openai"


# ==========================================================================
# 3. UnifiedAiProvider.from_provider_config()
# ==========================================================================


class TestFromProviderConfig:
    def test_from_openai_config(self):
        cfg = ProviderConfig(
            kind="openai",
            openai=OpenAIConfig(api_key="sk-test", model="gpt-4o"),
        )
        up = UnifiedAiProvider.from_provider_config(cfg)
        assert up.provider == "openai"
        assert up.api_key == "sk-test"
        assert up.model == "gpt-4o"

    def test_from_anthropic_config(self):
        cfg = ProviderConfig(
            kind="anthropic",
            anthropic=AnthropicConfig(api_key="ant-key", model="claude-3-5-sonnet-20241022"),
        )
        up = UnifiedAiProvider.from_provider_config(cfg)
        assert up.provider == "anthropic"
        assert up.api_key == "ant-key"

    def test_from_azure_config_with_extras(self):
        cfg = ProviderConfig(
            kind="azure",
            azure=AzureOpenAIConfig(
                api_key="az-key",
                deployment="my-dep",
                api_version="2024-01",
            ),
        )
        up = UnifiedAiProvider.from_provider_config(cfg)
        assert up.provider == "azure"
        assert up.extra.get("deployment") == "my-dep"
        assert up.extra.get("api_version") == "2024-01"

    def test_from_ollama_config(self):
        cfg = ProviderConfig(
            kind="ollama",
            ollama=OllamaConfig(base_url="http://gpu:11434", model="llama3"),
        )
        up = UnifiedAiProvider.from_provider_config(cfg)
        assert up.provider == "ollama"
        assert up.base_url == "http://gpu:11434"

    def test_from_custom_config_with_headers(self):
        cfg = ProviderConfig(
            kind="custom",
            custom=CustomHttpConfig(
                api_key="c-key",
                headers={"Authorization": "Bearer tok"},
            ),
        )
        up = UnifiedAiProvider.from_provider_config(cfg)
        assert up.provider == "custom"
        assert up.extra.get("headers") == {"Authorization": "Bearer tok"}


# ==========================================================================
# 4. UnifiedAiProvider.is_reachable()
# ==========================================================================


class TestIsReachable:
    def test_unconfigured_not_reachable(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            p = UnifiedAiProvider(provider="openai")
            assert not p.is_reachable()

    def test_reachable_delegates_to_ping(self):
        p = UnifiedAiProvider(provider="openai", api_key="sk-x")
        with mock.patch(
            "aksara.ai.providers_unified.UnifiedAiProvider.ping",
            return_value={"ok": True},
        ):
            assert p.is_reachable()

    def test_reachable_false_on_ping_failure(self):
        p = UnifiedAiProvider(provider="openai", api_key="sk-x")
        with mock.patch(
            "aksara.ai.providers_unified.UnifiedAiProvider.ping",
            return_value={"ok": False},
        ):
            assert not p.is_reachable()

    def test_reachable_false_on_exception(self):
        p = UnifiedAiProvider(provider="openai", api_key="sk-x")
        with mock.patch(
            "aksara.ai.providers_unified.UnifiedAiProvider.ping",
            side_effect=RuntimeError("boom"),
        ):
            assert not p.is_reachable()


# ==========================================================================
# 5. UnifiedAiProvider.get_supported_modes()
# ==========================================================================


class TestGetSupportedModes:
    def test_openai_modes(self):
        p = UnifiedAiProvider(provider="openai", api_key="sk-x")
        modes = p.get_supported_modes()
        assert "chat" in modes
        assert "code" in modes
        assert "embeddings" in modes

    def test_anthropic_modes(self):
        p = UnifiedAiProvider(provider="anthropic", api_key="ant-x")
        modes = p.get_supported_modes()
        assert "chat" in modes
        assert "code" in modes
        assert "embeddings" not in modes

    def test_ollama_modes(self):
        p = UnifiedAiProvider(provider="ollama", base_url="http://localhost:11434")
        modes = p.get_supported_modes()
        assert "chat" in modes
        assert "embeddings" in modes

    def test_custom_no_embeddings(self):
        p = UnifiedAiProvider(provider="custom", api_key="c-x")
        modes = p.get_supported_modes()
        assert "chat" in modes
        assert "embeddings" not in modes


# ==========================================================================
# 6. get_active_provider() backward compat
# ==========================================================================


class TestGetActiveProvider:
    def test_returns_unified_provider(self):
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-x"}, clear=True):
            active = get_active_provider()
            assert isinstance(active, UnifiedAiProvider)
            assert active.provider == "openai"

    def test_unconfigured_returns_default(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            active = get_active_provider()
            assert isinstance(active, UnifiedAiProvider)

    def test_respects_explicit_provider_env(self):
        with mock.patch.dict(
            os.environ,
            {"AKSARA_AI_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "k"},
            clear=True,
        ):
            active = get_active_provider()
            assert active.provider == "anthropic"


# ==========================================================================
# 7. Hub ↔ UnifiedAiProvider round-trip
# ==========================================================================


class TestHubUnifiedRoundTrip:
    def test_hub_to_unified_providers(self):
        hub = AiHubSettings(
            providers=[
                ProviderConfig(kind="openai", openai=OpenAIConfig(api_key="k1")),
                ProviderConfig(kind="anthropic", anthropic=AnthropicConfig(api_key="k2")),
            ]
        )
        unified = [p.to_unified_provider() for p in hub.configured_providers()]
        assert len(unified) == 2
        assert unified[0].provider == "openai"
        assert unified[1].provider == "anthropic"

    def test_hub_defaults_propagate(self):
        hub = AiHubSettings(
            providers=[ProviderConfig(kind="openai", openai=OpenAIConfig(api_key="k"))],
        )
        hub.resolve_defaults()
        assert hub.defaults.chat_model is not None
        assert hub.defaults.embeddings_model is not None
