"""
Tests for aksara.ai.hub_settings — AI Hub 2.0 unified settings.

v0.5.28: Covers AiHubSettings, ProviderConfig, default resolution,
file loading, env var detection, and backward compatibility.
"""

import json
import os
import pytest
from pathlib import Path
from unittest import mock

from aksara.ai.hub_settings import (
    AiDefaultModels,
    AiHubSettings,
    AnthropicConfig,
    AzureOpenAIConfig,
    CustomHttpConfig,
    OllamaConfig,
    OpenAIConfig,
    ProviderConfig,
    ProviderKind,
    load_aihub_settings,
    resolve_defaults,
    save_aihub_settings,
    _provider_from_env,
    _detect_active_from_env,
    _load_from_file,
    _PROVIDER_DEFAULT_MODELS,
)


# ==========================================================================
# 1. Provider-specific config models
# ==========================================================================


class TestOpenAIConfig:
    def test_defaults(self):
        c = OpenAIConfig()
        assert c.api_key is None
        assert c.base_url == "https://api.openai.com/v1"
        assert c.model is None
        assert c.organization is None

    def test_with_values(self):
        c = OpenAIConfig(api_key="sk-test", model="gpt-4o")
        assert c.api_key == "sk-test"
        assert c.model == "gpt-4o"

    def test_extra_fields(self):
        c = OpenAIConfig(extra={"timeout": 30})
        assert c.extra["timeout"] == 30


class TestAzureOpenAIConfig:
    def test_defaults(self):
        c = AzureOpenAIConfig()
        assert c.api_version == "2024-02-15-preview"
        assert c.deployment is None
        assert c.base_url is None

    def test_with_values(self):
        c = AzureOpenAIConfig(api_key="az-key", deployment="my-dep")
        assert c.api_key == "az-key"
        assert c.deployment == "my-dep"


class TestAnthropicConfig:
    def test_defaults(self):
        c = AnthropicConfig()
        assert c.base_url == "https://api.anthropic.com"

    def test_with_key(self):
        c = AnthropicConfig(api_key="ant-key", model="claude-3-5-sonnet-20241022")
        assert c.api_key == "ant-key"
        assert c.model == "claude-3-5-sonnet-20241022"


class TestOllamaConfig:
    def test_defaults(self):
        c = OllamaConfig()
        assert c.base_url == "http://localhost:11434"
        assert c.model is None

    def test_custom_url(self):
        c = OllamaConfig(base_url="http://gpu-box:11434", model="mistral")
        assert c.base_url == "http://gpu-box:11434"
        assert c.model == "mistral"


class TestCustomHttpConfig:
    def test_defaults(self):
        c = CustomHttpConfig()
        assert c.base_url == "http://localhost:8080"
        assert c.headers == {}

    def test_with_headers(self):
        c = CustomHttpConfig(headers={"X-Custom": "1"})
        assert c.headers["X-Custom"] == "1"


# ==========================================================================
# 2. ProviderConfig
# ==========================================================================


class TestProviderConfig:
    def test_openai_provider(self):
        cfg = ProviderConfig(kind="openai", openai=OpenAIConfig(api_key="sk-x"))
        assert cfg.is_configured
        assert cfg.api_key == "sk-x"
        assert cfg.kind == "openai"

    def test_unconfigured_openai(self):
        cfg = ProviderConfig(kind="openai", openai=OpenAIConfig())
        assert not cfg.is_configured

    def test_ollama_needs_base_url(self):
        cfg = ProviderConfig(kind="ollama", ollama=OllamaConfig())
        assert cfg.is_configured  # default base_url is set

    def test_ollama_empty_url(self):
        cfg = ProviderConfig(kind="ollama", ollama=OllamaConfig(base_url=""))
        assert not cfg.is_configured

    def test_active_config(self):
        cfg = ProviderConfig(kind="anthropic", anthropic=AnthropicConfig(api_key="k"))
        assert cfg.active_config is not None
        assert isinstance(cfg.active_config, AnthropicConfig)

    def test_active_config_none(self):
        cfg = ProviderConfig(kind="openai")
        assert cfg.active_config is None

    def test_base_url_property(self):
        cfg = ProviderConfig(kind="openai", openai=OpenAIConfig(api_key="k"))
        assert cfg.base_url == "https://api.openai.com/v1"

    def test_model_property(self):
        cfg = ProviderConfig(kind="openai", openai=OpenAIConfig(model="gpt-4o-mini"))
        assert cfg.model == "gpt-4o-mini"

    def test_supported_modes_openai(self):
        cfg = ProviderConfig(kind="openai", openai=OpenAIConfig(api_key="k"))
        modes = cfg.get_supported_modes()
        assert "chat" in modes
        assert "code" in modes
        assert "embeddings" in modes

    def test_supported_modes_anthropic(self):
        cfg = ProviderConfig(kind="anthropic", anthropic=AnthropicConfig(api_key="k"))
        modes = cfg.get_supported_modes()
        assert "chat" in modes
        assert "code" in modes
        # Anthropic has no default embedding model
        assert "embeddings" not in modes

    def test_to_safe_dict_masks_key(self):
        cfg = ProviderConfig(kind="openai", openai=OpenAIConfig(api_key="sk-1234567890abcdef"))
        safe = cfg.to_safe_dict()
        assert safe["openai"]["api_key"] != "sk-1234567890abcdef"
        assert "..." in safe["openai"]["api_key"]

    def test_to_safe_dict_short_key(self):
        cfg = ProviderConfig(kind="openai", openai=OpenAIConfig(api_key="short"))
        safe = cfg.to_safe_dict()
        assert safe["openai"]["api_key"] == "****"

    def test_to_unified_provider(self):
        cfg = ProviderConfig(kind="openai", openai=OpenAIConfig(api_key="k", model="gpt-4o"))
        up = cfg.to_unified_provider()
        assert up.provider == "openai"
        assert up.api_key == "k"
        assert up.model == "gpt-4o"

    def test_to_unified_provider_azure_extra(self):
        cfg = ProviderConfig(
            kind="azure",
            azure=AzureOpenAIConfig(api_key="k", deployment="dep1", api_version="2024-01"),
        )
        up = cfg.to_unified_provider()
        assert up.extra["api_version"] == "2024-01"
        assert up.extra["deployment"] == "dep1"

    def test_enabled_default(self):
        cfg = ProviderConfig(kind="openai", openai=OpenAIConfig(api_key="k"))
        assert cfg.enabled is True

    def test_disabled_provider(self):
        cfg = ProviderConfig(kind="openai", enabled=False, openai=OpenAIConfig(api_key="k"))
        assert cfg.enabled is False


# ==========================================================================
# 3. AiDefaultModels
# ==========================================================================


class TestAiDefaultModels:
    def test_defaults_empty(self):
        d = AiDefaultModels()
        assert d.chat_model is None
        assert d.code_model is None
        assert d.embeddings_model is None

    def test_with_values(self):
        d = AiDefaultModels(
            chat_model="gpt-4o",
            chat_provider="openai",
            embeddings_model="text-embedding-3-large",
            embeddings_provider="openai",
        )
        assert d.chat_model == "gpt-4o"
        assert d.embeddings_provider == "openai"


# ==========================================================================
# 4. AiHubSettings
# ==========================================================================


class TestAiHubSettings:
    def test_empty_settings(self):
        hub = AiHubSettings()
        assert hub.providers == []
        assert hub.active_provider is None
        assert hub.version == "0.5.28"

    def test_get_provider(self):
        hub = AiHubSettings(
            providers=[ProviderConfig(kind="openai", openai=OpenAIConfig(api_key="k"))]
        )
        assert hub.get_provider("openai") is not None
        assert hub.get_provider("anthropic") is None

    def test_configured_providers(self):
        hub = AiHubSettings(
            providers=[
                ProviderConfig(kind="openai", openai=OpenAIConfig(api_key="k")),
                ProviderConfig(kind="anthropic", anthropic=AnthropicConfig()),
            ]
        )
        configured = hub.configured_providers()
        assert len(configured) == 1
        assert configured[0].kind == "openai"

    def test_configured_providers_excludes_disabled(self):
        hub = AiHubSettings(
            providers=[
                ProviderConfig(kind="openai", enabled=False, openai=OpenAIConfig(api_key="k")),
            ]
        )
        assert len(hub.configured_providers()) == 0

    def test_resolve_defaults_chat(self):
        hub = AiHubSettings(
            providers=[ProviderConfig(kind="openai", openai=OpenAIConfig(api_key="k", model="gpt-4o"))]
        )
        hub.resolve_defaults()
        assert hub.defaults.chat_model == "gpt-4o"
        assert hub.defaults.chat_provider == "openai"
        assert hub.active_provider == "openai"

    def test_resolve_defaults_code(self):
        hub = AiHubSettings(
            providers=[ProviderConfig(kind="openai", openai=OpenAIConfig(api_key="k"))]
        )
        hub.resolve_defaults()
        assert hub.defaults.code_provider == "openai"

    def test_resolve_defaults_embeddings(self):
        hub = AiHubSettings(
            providers=[ProviderConfig(kind="openai", openai=OpenAIConfig(api_key="k"))]
        )
        hub.resolve_defaults()
        assert hub.defaults.embeddings_model == "text-embedding-3-large"

    def test_resolve_defaults_no_embedding_fallback(self):
        """Anthropic has no embedding default — should try others."""
        hub = AiHubSettings(
            providers=[
                ProviderConfig(kind="anthropic", anthropic=AnthropicConfig(api_key="k")),
                ProviderConfig(kind="openai", openai=OpenAIConfig(api_key="k2")),
            ]
        )
        hub.resolve_defaults()
        assert hub.defaults.embeddings_model == "text-embedding-3-large"
        assert hub.defaults.embeddings_provider == "openai"

    def test_resolve_defaults_no_providers(self):
        hub = AiHubSettings()
        hub.resolve_defaults()
        assert hub.defaults.chat_model is None

    def test_resolve_defaults_respects_active(self):
        hub = AiHubSettings(
            active_provider="anthropic",
            providers=[
                ProviderConfig(kind="openai", openai=OpenAIConfig(api_key="k")),
                ProviderConfig(kind="anthropic", anthropic=AnthropicConfig(api_key="k2")),
            ],
        )
        hub.resolve_defaults()
        assert hub.defaults.chat_provider == "anthropic"

    def test_resolve_defaults_active_unconfigured_falls_back(self):
        hub = AiHubSettings(
            active_provider="anthropic",
            providers=[
                ProviderConfig(kind="openai", openai=OpenAIConfig(api_key="k")),
                ProviderConfig(kind="anthropic", anthropic=AnthropicConfig()),
            ],
        )
        hub.resolve_defaults()
        assert hub.defaults.chat_provider == "openai"
        assert hub.active_provider == "openai"

    def test_provider_status_summary(self):
        hub = AiHubSettings(
            providers=[
                ProviderConfig(kind="openai", openai=OpenAIConfig(api_key="k")),
                ProviderConfig(kind="ollama", ollama=OllamaConfig()),
            ],
            active_provider="openai",
        )
        summary = hub.provider_status_summary()
        assert summary["total"] == 2
        assert summary["configured"] == 2
        assert summary["active_provider"] == "openai"
        kinds = [p["kind"] for p in summary["providers"]]
        assert "openai" in kinds
        assert "ollama" in kinds

    def test_to_safe_dict(self):
        hub = AiHubSettings(
            providers=[ProviderConfig(kind="openai", openai=OpenAIConfig(api_key="sk-supersecret123"))],
            active_provider="openai",
        )
        safe = hub.to_safe_dict()
        assert "sk-supersecret123" not in json.dumps(safe)
        assert safe["active_provider"] == "openai"
        assert safe["version"] == "0.5.28"


# ==========================================================================
# 5. Env-var loading helpers
# ==========================================================================


class TestEnvVarHelpers:
    def test_detect_active_none(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            assert _detect_active_from_env() is None

    def test_detect_active_explicit(self):
        with mock.patch.dict(os.environ, {"AKSARA_AI_PROVIDER": "anthropic"}, clear=True):
            assert _detect_active_from_env() == "anthropic"

    def test_detect_active_openai(self):
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-x"}, clear=True):
            assert _detect_active_from_env() == "openai"

    def test_detect_active_anthropic(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "ant-x"}, clear=True):
            assert _detect_active_from_env() == "anthropic"

    def test_detect_active_azure(self):
        with mock.patch.dict(os.environ, {"AZURE_OPENAI_API_KEY": "az-x"}, clear=True):
            assert _detect_active_from_env() == "azure"

    def test_detect_active_ollama(self):
        with mock.patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://localhost:11434"}, clear=True):
            assert _detect_active_from_env() == "ollama"

    def test_detect_active_custom(self):
        with mock.patch.dict(os.environ, {"CUSTOM_LLM_API_KEY": "c-x"}, clear=True):
            assert _detect_active_from_env() == "custom"

    def test_provider_from_env_openai(self):
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True):
            cfg = _provider_from_env("openai")
            assert cfg.kind == "openai"
            assert cfg.is_configured
            assert cfg.api_key == "sk-test"

    def test_provider_from_env_ollama(self):
        with mock.patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://gpu:11434", "OLLAMA_MODEL": "mistral"}, clear=True):
            cfg = _provider_from_env("ollama")
            assert cfg.kind == "ollama"
            assert cfg.is_configured
            assert cfg.model == "mistral"

    def test_provider_from_env_unconfigured(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            cfg = _provider_from_env("openai")
            assert not cfg.is_configured


# ==========================================================================
# 6. File loading
# ==========================================================================


class TestFileLoading:
    def test_load_from_nonexistent(self, tmp_path):
        assert _load_from_file(str(tmp_path / "nope.json")) is None

    def test_load_from_valid_json(self, tmp_path):
        cfg = {"providers": [], "defaults": {}}
        p = tmp_path / "aksara.ai.json"
        p.write_text(json.dumps(cfg))
        result = _load_from_file(str(p))
        assert result is not None
        assert "providers" in result

    def test_load_from_invalid_json(self, tmp_path):
        p = tmp_path / "aksara.ai.json"
        p.write_text("{invalid json!")
        assert _load_from_file(str(p)) is None


# ==========================================================================
# 7. load_aihub_settings()
# ==========================================================================


class TestLoadAiHubSettings:
    def test_loads_empty_env(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            hub = load_aihub_settings()
            assert isinstance(hub, AiHubSettings)
            assert len(hub.providers) == 5  # all known types added

    def test_empty_env_keeps_ollama_unconfigured(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            hub = load_aihub_settings()
            assert len(hub.configured_providers()) == 0

    def test_loads_openai_from_env(self):
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"}, clear=True):
            hub = load_aihub_settings()
            oai = hub.get_provider("openai")
            assert oai is not None
            assert oai.is_configured

    def test_active_provider_from_env(self):
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-x"}, clear=True):
            hub = load_aihub_settings()
            assert hub.active_provider == "openai"

    def test_defaults_resolved(self):
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-x"}, clear=True):
            hub = load_aihub_settings()
            assert hub.defaults.chat_model is not None

    def test_loads_from_file(self, tmp_path):
        cfg = {
            "active_provider": "anthropic",
            "providers": [
                {"kind": "anthropic", "anthropic": {"api_key": "ant-file-key"}},
            ],
        }
        p = tmp_path / "aksara.ai.json"
        p.write_text(json.dumps(cfg))
        with mock.patch.dict(os.environ, {}, clear=True):
            hub = load_aihub_settings(config_path=str(p))
            assert hub.active_provider == "anthropic"
            ant = hub.get_provider("anthropic")
            assert ant is not None
            assert ant.api_key == "ant-file-key"

    def test_file_invalid_fallback(self, tmp_path):
        p = tmp_path / "aksara.ai.json"
        p.write_text("not json {{{")
        with mock.patch.dict(os.environ, {}, clear=True):
            hub = load_aihub_settings(config_path=str(p))
            assert isinstance(hub, AiHubSettings)

    def test_no_env_flag(self):
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-x"}, clear=True):
            hub = load_aihub_settings(include_env=False)
            # Without env loading, no providers should be configured
            configured = hub.configured_providers()
            assert len(configured) == 0


# ==========================================================================
# 8. save_aihub_settings()
# ==========================================================================


class TestSaveAiHubSettings:
    def test_save_creates_file(self, tmp_path):
        hub = AiHubSettings(
            providers=[ProviderConfig(kind="openai", openai=OpenAIConfig(api_key="sk-x"))],
            active_provider="openai",
        )
        path = save_aihub_settings(hub, str(tmp_path / "aksara.ai.json"))
        assert Path(path).exists()
        data = json.loads(Path(path).read_text())
        assert data["active_provider"] == "openai"

    def test_save_masks_secrets(self, tmp_path):
        hub = AiHubSettings(
            providers=[ProviderConfig(kind="openai", openai=OpenAIConfig(api_key="sk-secretlongkey123"))],
        )
        path = save_aihub_settings(hub, str(tmp_path / "aksara.ai.json"))
        data = json.loads(Path(path).read_text())
        assert "sk-secretlongkey123" not in json.dumps(data)


# ==========================================================================
# 9. resolve_defaults() convenience
# ==========================================================================


class TestResolveDefaults:
    def test_resolve_with_hub(self):
        hub = AiHubSettings(
            providers=[ProviderConfig(kind="openai", openai=OpenAIConfig(api_key="k"))]
        )
        defaults = resolve_defaults(hub)
        assert defaults.chat_model is not None

    def test_resolve_without_hub(self):
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-x"}, clear=True):
            defaults = resolve_defaults()
            assert defaults.chat_model is not None


# ==========================================================================
# 10. Provider default models table
# ==========================================================================


class TestDefaultModelsTable:
    def test_all_providers_have_defaults(self):
        for kind in ("openai", "azure", "anthropic", "ollama", "custom"):
            assert kind in _PROVIDER_DEFAULT_MODELS

    def test_openai_has_embeddings(self):
        assert _PROVIDER_DEFAULT_MODELS["openai"]["embeddings"]

    def test_anthropic_no_embeddings(self):
        assert not _PROVIDER_DEFAULT_MODELS["anthropic"]["embeddings"]

    def test_ollama_has_embeddings(self):
        assert _PROVIDER_DEFAULT_MODELS["ollama"]["embeddings"]
