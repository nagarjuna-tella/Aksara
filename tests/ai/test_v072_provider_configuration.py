"""Regression contracts for explicit AI-provider configuration detection."""

from __future__ import annotations

import os
from unittest import mock

import pytest

from aksara.ai.hub_settings import CustomHttpConfig, ProviderConfig, _provider_from_env
from aksara.ai.providers_unified import UnifiedAiProvider, detect_all_providers


def _detected(kind: str) -> UnifiedAiProvider:
    return next(provider for provider in detect_all_providers() if provider.provider == kind)


def test_clean_environment_does_not_promote_adapter_defaults_to_configuration():
    with mock.patch.dict(os.environ, {}, clear=True):
        assert not _detected("ollama").is_configured()
        assert not _detected("custom").is_configured()
        assert not _provider_from_env("ollama").is_configured
        assert not _provider_from_env("custom").is_configured


def test_active_provider_selection_alone_does_not_configure_default_ollama():
    with mock.patch.dict(os.environ, {"AKSARA_AI_PROVIDER": "ollama"}, clear=True):
        provider = UnifiedAiProvider.from_env()

    assert provider.provider == "ollama"
    assert not provider.is_configured()


@pytest.mark.parametrize(
    ("environment", "kind", "expected_url"),
    [
        ({"OLLAMA_BASE_URL": "http://localhost:11434"}, "ollama", "http://localhost:11434"),
        ({"OLLAMA_MODEL": "llama3"}, "ollama", "http://localhost:11434"),
        ({"OPENAI_API_KEY": "test-key"}, "openai", "https://api.openai.com/v1"),
        ({"CUSTOM_LLM_BASE_URL": "https://llm.example.test"}, "custom", "https://llm.example.test"),
        (
            {"CUSTOM_LLM_BASE_URL": "https://llm.example.test", "CUSTOM_LLM_API_KEY": "test-key"},
            "custom",
            "https://llm.example.test",
        ),
        ({"CUSTOM_LLM_API_KEY": "test-key"}, "custom", "http://localhost:8080"),
    ],
)
def test_explicit_provider_signals_are_configured(environment, kind, expected_url):
    with mock.patch.dict(os.environ, environment, clear=True):
        provider = _detected(kind)
        hub_provider = _provider_from_env(kind)

    assert provider.is_configured()
    assert provider.base_url == expected_url
    assert hub_provider.is_configured


@pytest.mark.parametrize(
    "provider",
    [
        UnifiedAiProvider(provider="ollama", base_url="localhost:11434"),
        UnifiedAiProvider(provider="custom", base_url="not a URL"),
        UnifiedAiProvider(provider="openai", api_key="test-key", base_url="file:///tmp/socket"),
    ],
)
def test_malformed_endpoint_is_not_configured(provider):
    assert not provider.is_configured()


def test_hub_rejects_malformed_custom_endpoint():
    provider = ProviderConfig(
        kind="custom",
        custom=CustomHttpConfig(base_url="not a URL"),
    )

    assert not provider.is_configured


def test_configuration_detection_never_pings_and_reachability_is_separate():
    provider = UnifiedAiProvider(provider="custom", base_url="https://llm.example.test")

    with mock.patch.object(
        UnifiedAiProvider,
        "ping",
        return_value={"ok": True},
    ) as ping:
        assert provider.is_configured()
        ping.assert_not_called()
        assert provider.is_reachable()
        ping.assert_called_once_with()
