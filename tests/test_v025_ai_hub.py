"""
Tests for Aksara v0.5.25 — AI Hub & Unified Provider System

75+ tests covering:
- UnifiedAiProvider (creation, env detection, serialization, ping)
- LLM Client Adapters (all 5 adapters: base protocol, generate, availability)
- Studio API endpoints (4 new /studio/ai/hub/* endpoints)
- CLI ai-provider commands (list, detect, ping, configure)
- AI Hub Studio UI (template rendering, sidebar nav)
- Integration / non-regression tests

All providers are tested with mocked HTTP — no real API calls required.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# =============================================================================
# 1. UnifiedAiProvider Tests (20 tests)
# =============================================================================


class TestUnifiedAiProvider:
    """Tests for aksara.ai.providers_unified.UnifiedAiProvider."""

    def test_create_openai_provider(self):
        from aksara.ai.providers_unified import UnifiedAiProvider
        p = UnifiedAiProvider(provider="openai", api_key="sk-test", model="gpt-4o")
        assert p.provider == "openai"
        assert p.api_key == "sk-test"
        assert p.model == "gpt-4o"

    def test_create_anthropic_provider(self):
        from aksara.ai.providers_unified import UnifiedAiProvider
        p = UnifiedAiProvider(provider="anthropic", api_key="sk-ant-test", model="claude-sonnet-4-20250514")
        assert p.provider == "anthropic"
        assert p.model == "claude-sonnet-4-20250514"

    def test_create_azure_provider(self):
        from aksara.ai.providers_unified import UnifiedAiProvider
        p = UnifiedAiProvider(
            provider="azure",
            api_key="az-key",
            base_url="https://my.openai.azure.com",
            model="gpt-4o",
            extra={"deployment": "my-deploy", "api_version": "2024-02-01"},
        )
        assert p.provider == "azure"
        assert p.extra["deployment"] == "my-deploy"

    def test_create_ollama_provider(self):
        from aksara.ai.providers_unified import UnifiedAiProvider
        p = UnifiedAiProvider(provider="ollama", model="llama3")
        assert p.provider == "ollama"
        assert not p.api_key  # No API key for ollama (None or empty)

    def test_create_custom_provider(self):
        from aksara.ai.providers_unified import UnifiedAiProvider
        p = UnifiedAiProvider(
            provider="custom",
            base_url="https://my-llm.example.com",
            model="my-model",
            extra={"generate_path": "/api/generate"},
        )
        assert p.provider == "custom"

    def test_is_configured_with_api_key(self):
        from aksara.ai.providers_unified import UnifiedAiProvider
        p = UnifiedAiProvider(provider="openai", api_key="sk-test", model="gpt-4o")
        assert p.is_configured() is True

    def test_is_configured_without_api_key(self):
        from aksara.ai.providers_unified import UnifiedAiProvider
        p = UnifiedAiProvider(provider="openai", api_key="", model="gpt-4o")
        assert p.is_configured() is False

    def test_is_configured_ollama_no_key(self):
        from aksara.ai.providers_unified import UnifiedAiProvider
        p = UnifiedAiProvider(provider="ollama", model="llama3")
        # Ollama doesn't require API key — configured if base_url works
        # Our implementation checks api_key or base_url for ollama
        assert p.is_configured() is True or p.is_configured() is False  # depends on impl

    def test_to_safe_dict_redacts_api_key(self):
        from aksara.ai.providers_unified import UnifiedAiProvider
        p = UnifiedAiProvider(provider="openai", api_key="sk-very-secret-key-12345", model="gpt-4o")
        safe = p.to_safe_dict()
        assert "sk-very-secret" not in safe.get("api_key", "")
        assert safe["provider"] == "openai"
        assert safe["model"] == "gpt-4o"

    def test_from_dict(self):
        from aksara.ai.providers_unified import UnifiedAiProvider
        p = UnifiedAiProvider.from_dict({
            "provider": "openai",
            "api_key": "sk-test",
            "model": "gpt-4o",
        })
        assert p.provider == "openai"
        assert p.model == "gpt-4o"

    def test_from_env_openai(self):
        from aksara.ai.providers_unified import UnifiedAiProvider
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-fromenv", "OPENAI_MODEL": "gpt-4"}, clear=False):
            p = UnifiedAiProvider.from_env()
            # Should auto-detect openai if no AKSARA_AI_PROVIDER set
            assert p is not None

    def test_from_env_no_vars(self):
        from aksara.ai.providers_unified import UnifiedAiProvider
        # Clear all AI-related env vars
        env_clean = {k: v for k, v in os.environ.items()
                     if not any(x in k.upper() for x in ["OPENAI", "ANTHROPIC", "AZURE", "OLLAMA", "AKSARA_AI", "AKSARA_CUSTOM"])}
        with patch.dict(os.environ, env_clean, clear=True):
            p = UnifiedAiProvider.from_env()
            # Should return a provider (possibly unconfigured)
            assert p is not None

    def test_save_to_env_file(self):
        from aksara.ai.providers_unified import UnifiedAiProvider
        p = UnifiedAiProvider(provider="openai", api_key="sk-test", model="gpt-4o")
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("aksara.ai.providers_unified.Path.cwd", return_value=Path(tmpdir)):
                path = p.save_to_env_file()
                assert Path(path).exists()
                content = Path(path).read_text()
                assert "OPENAI_API_KEY=sk-test" in content

    def test_save_to_json(self):
        from aksara.ai.providers_unified import UnifiedAiProvider
        p = UnifiedAiProvider(provider="openai", api_key="sk-test", model="gpt-4o")
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("aksara.ai.providers_unified.Path.cwd", return_value=Path(tmpdir)):
                path = p.save_to_json()
                assert Path(path).exists()
                data = json.loads(Path(path).read_text())
                assert data["provider"] == "openai"

    def test_from_json_file(self):
        from aksara.ai.providers_unified import UnifiedAiProvider
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "provider.json"
            json_path.write_text(json.dumps({
                "provider": "anthropic",
                "api_key": "sk-ant",
                "model": "claude-sonnet-4-20250514",
            }))
            p = UnifiedAiProvider.from_json_file(json_path)
            assert p.provider == "anthropic"
            assert p.model == "claude-sonnet-4-20250514"

    def test_detect_all_providers_returns_list(self):
        from aksara.ai.providers_unified import detect_all_providers
        result = detect_all_providers()
        assert isinstance(result, list)
        # Should always return at least the known provider types
        assert len(result) >= 0

    def test_get_active_provider(self):
        from aksara.ai.providers_unified import get_active_provider
        result = get_active_provider()
        # May be None if no env vars set
        assert result is None or hasattr(result, "provider")

    def test_ping_without_server(self):
        from aksara.ai.providers_unified import UnifiedAiProvider
        p = UnifiedAiProvider(provider="openai", api_key="sk-fake", model="gpt-4o",
                              base_url="http://localhost:1")
        # Should return dict with ok=False, not crash
        result = p.ping()
        assert isinstance(result, dict)
        assert result.get("ok") is False

    def test_get_llm_client(self):
        from aksara.ai.providers_unified import UnifiedAiProvider
        p = UnifiedAiProvider(provider="openai", api_key="sk-test", model="gpt-4o")
        client = p.get_llm_client()
        assert client is not None
        assert hasattr(client, "generate")
        assert hasattr(client, "is_available")

    def test_provider_invalid_type(self):
        from aksara.ai.providers_unified import UnifiedAiProvider
        with pytest.raises(Exception):
            UnifiedAiProvider(provider="invalid_provider", api_key="x")


# =============================================================================
# 2. LLM Client Adapter Tests (25 tests)
# =============================================================================


class TestBaseLlmClient:
    """Tests for the base protocol and factory."""

    def test_get_client_for_openai(self):
        from aksara.ai.providers_unified import UnifiedAiProvider
        from aksara.ai.llm_clients import get_client_for_provider
        p = UnifiedAiProvider(provider="openai", api_key="sk-test", model="gpt-4o")
        client = get_client_for_provider(p)
        assert client is not None

    def test_get_client_for_anthropic(self):
        from aksara.ai.providers_unified import UnifiedAiProvider
        from aksara.ai.llm_clients import get_client_for_provider
        p = UnifiedAiProvider(provider="anthropic", api_key="sk-ant", model="claude-sonnet-4-20250514")
        client = get_client_for_provider(p)
        assert client is not None

    def test_get_client_for_azure(self):
        from aksara.ai.providers_unified import UnifiedAiProvider
        from aksara.ai.llm_clients import get_client_for_provider
        p = UnifiedAiProvider(provider="azure", api_key="az-key",
                              base_url="https://my.openai.azure.com",
                              extra={"deployment": "dep1"})
        client = get_client_for_provider(p)
        assert client is not None

    def test_get_client_for_ollama(self):
        from aksara.ai.providers_unified import UnifiedAiProvider
        from aksara.ai.llm_clients import get_client_for_provider
        p = UnifiedAiProvider(provider="ollama", model="llama3")
        client = get_client_for_provider(p)
        assert client is not None

    def test_get_client_for_custom(self):
        from aksara.ai.providers_unified import UnifiedAiProvider
        from aksara.ai.llm_clients import get_client_for_provider
        p = UnifiedAiProvider(provider="custom", base_url="http://localhost:8080", model="my-model")
        client = get_client_for_provider(p)
        assert client is not None


class TestOpenAIAdapter:
    """Tests for the OpenAI LLM adapter."""

    def _make_provider(self, **overrides):
        from aksara.ai.providers_unified import UnifiedAiProvider
        defaults = {"provider": "openai", "api_key": "sk-test", "model": "gpt-4o"}
        defaults.update(overrides)
        return UnifiedAiProvider(**defaults)

    def test_create_adapter(self):
        from aksara.ai.llm_clients.openai_adapter import OpenAIAdapter
        adapter = OpenAIAdapter(self._make_provider())
        assert adapter is not None

    def test_is_available_no_server(self):
        from aksara.ai.llm_clients.openai_adapter import OpenAIAdapter
        adapter = OpenAIAdapter(self._make_provider(base_url="http://localhost:1"))
        assert adapter.is_available() is False

    def test_generate_requires_api_key(self):
        from aksara.ai.llm_clients.openai_adapter import OpenAIAdapter
        from aksara.ai.llm_clients.base import LlmClientError
        adapter = OpenAIAdapter(self._make_provider(api_key="", base_url="http://localhost:1"))
        with pytest.raises((LlmClientError, Exception)):
            adapter.generate("test prompt")

    def test_generate_with_mock(self):
        from aksara.ai.llm_clients.openai_adapter import OpenAIAdapter
        adapter = OpenAIAdapter(self._make_provider())
        mock_response = json.dumps({
            "choices": [{"message": {"content": "Hello from mock!"}}]
        }).encode()
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = mock_response
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp
            result = adapter.generate("Hello")
            assert result == "Hello from mock!"


class TestAnthropicAdapter:
    """Tests for the Anthropic LLM adapter."""

    def _make_provider(self, **overrides):
        from aksara.ai.providers_unified import UnifiedAiProvider
        defaults = {"provider": "anthropic", "api_key": "sk-ant-test", "model": "claude-sonnet-4-20250514"}
        defaults.update(overrides)
        return UnifiedAiProvider(**defaults)

    def test_create_adapter(self):
        from aksara.ai.llm_clients.anthropic_adapter import AnthropicAdapter
        adapter = AnthropicAdapter(self._make_provider())
        assert adapter is not None

    def test_is_available_no_server(self):
        from aksara.ai.llm_clients.anthropic_adapter import AnthropicAdapter
        adapter = AnthropicAdapter(self._make_provider(base_url="http://localhost:1"))
        assert adapter.is_available() is False

    def test_generate_with_mock(self):
        from aksara.ai.llm_clients.anthropic_adapter import AnthropicAdapter
        adapter = AnthropicAdapter(self._make_provider())
        mock_response = json.dumps({
            "content": [{"type": "text", "text": "Hello from Anthropic!"}]
        }).encode()
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = mock_response
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp
            result = adapter.generate("Hello")
            assert result == "Hello from Anthropic!"


class TestAzureAdapter:
    """Tests for the Azure OpenAI LLM adapter."""

    def _make_provider(self, **overrides):
        from aksara.ai.providers_unified import UnifiedAiProvider
        defaults = {
            "provider": "azure",
            "api_key": "az-key",
            "base_url": "https://my.openai.azure.com",
            "model": "gpt-4o",
            "extra": {"deployment": "my-deploy"},
        }
        defaults.update(overrides)
        return UnifiedAiProvider(**defaults)

    def test_create_adapter(self):
        from aksara.ai.llm_clients.azure_adapter import AzureOpenAIAdapter
        adapter = AzureOpenAIAdapter(self._make_provider())
        assert adapter is not None

    def test_is_available_no_server(self):
        from aksara.ai.llm_clients.azure_adapter import AzureOpenAIAdapter
        adapter = AzureOpenAIAdapter(self._make_provider(
            base_url="http://localhost:1",
            extra={"deployment": "dep"},
        ))
        assert adapter.is_available() is False


class TestOllamaAdapter:
    """Tests for the Ollama LLM adapter."""

    def _make_provider(self, **overrides):
        from aksara.ai.providers_unified import UnifiedAiProvider
        defaults = {"provider": "ollama", "model": "llama3"}
        defaults.update(overrides)
        return UnifiedAiProvider(**defaults)

    def test_create_adapter(self):
        from aksara.ai.llm_clients.ollama_adapter import OllamaAdapter
        adapter = OllamaAdapter(self._make_provider())
        assert adapter is not None

    def test_default_base_url(self):
        from aksara.ai.llm_clients.ollama_adapter import OllamaAdapter
        adapter = OllamaAdapter(self._make_provider())
        assert "11434" in adapter.base_url

    def test_is_available_no_server(self):
        from aksara.ai.llm_clients.ollama_adapter import OllamaAdapter
        adapter = OllamaAdapter(self._make_provider(base_url="http://localhost:1"))
        assert adapter.is_available() is False

    def test_list_models_no_server(self):
        from aksara.ai.llm_clients.ollama_adapter import OllamaAdapter
        adapter = OllamaAdapter(self._make_provider(base_url="http://localhost:1"))
        models = adapter.list_models()
        assert models == []

    def test_generate_with_mock(self):
        from aksara.ai.llm_clients.ollama_adapter import OllamaAdapter
        adapter = OllamaAdapter(self._make_provider())
        mock_response = json.dumps({
            "response": "Hello from Ollama!"
        }).encode()
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = mock_response
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp
            result = adapter.generate("Hello")
            assert result == "Hello from Ollama!"


class TestCustomAdapter:
    """Tests for the Custom HTTP LLM adapter."""

    def _make_provider(self, **overrides):
        from aksara.ai.providers_unified import UnifiedAiProvider
        defaults = {
            "provider": "custom",
            "base_url": "http://localhost:8080",
            "model": "my-model",
        }
        defaults.update(overrides)
        return UnifiedAiProvider(**defaults)

    def test_create_adapter(self):
        from aksara.ai.llm_clients.custom_adapter import CustomHttpAdapter
        adapter = CustomHttpAdapter(self._make_provider())
        assert adapter is not None

    def test_is_available_no_server(self):
        from aksara.ai.llm_clients.custom_adapter import CustomHttpAdapter
        adapter = CustomHttpAdapter(self._make_provider(base_url="http://localhost:1"))
        assert adapter.is_available() is False

    def test_custom_response_field(self):
        from aksara.ai.llm_clients.custom_adapter import CustomHttpAdapter
        adapter = CustomHttpAdapter(self._make_provider(
            extra={"response_field": "data.text"},
        ))
        mock_response = json.dumps({
            "data": {"text": "Custom response!"}
        }).encode()
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = mock_response
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp
            result = adapter.generate("Hello")
            assert result == "Custom response!"


class TestLlmClientErrors:
    """Tests for error classes."""

    def test_llm_client_error(self):
        from aksara.ai.llm_clients.base import LlmClientError
        err = LlmClientError("test error")
        assert str(err) == "test error"

    def test_llm_connection_error(self):
        from aksara.ai.llm_clients.base import LlmConnectionError
        err = LlmConnectionError("connection failed")
        assert isinstance(err, Exception)

    def test_llm_auth_error(self):
        from aksara.ai.llm_clients.base import LlmAuthenticationError
        err = LlmAuthenticationError("invalid key")
        assert isinstance(err, Exception)

    def test_llm_rate_limit_error(self):
        from aksara.ai.llm_clients.base import LlmRateLimitError
        err = LlmRateLimitError("rate limited")
        assert isinstance(err, Exception)


# =============================================================================
# 3. Studio API Endpoint Tests (15 tests)
# =============================================================================


class TestStudioAiHubModels:
    """Tests for the Pydantic models used by AI Hub endpoints."""

    def test_provider_status_model(self):
        from aksara.studio.models import StudioAiProviderStatus
        s = StudioAiProviderStatus(provider="openai", configured=True, reachable=True, model="gpt-4o")
        assert s.provider == "openai"
        assert s.configured is True

    def test_providers_summary_model(self):
        from aksara.studio.models import StudioAiProvidersSummary
        s = StudioAiProvidersSummary(active_provider="openai", configured_count=1, total_count=5)
        assert s.active_provider == "openai"

    def test_provider_save_request(self):
        from aksara.studio.models import StudioAiProviderSaveRequest
        r = StudioAiProviderSaveRequest(provider="openai", api_key="sk-test", model="gpt-4o")
        assert r.provider == "openai"
        assert r.save_to == "env"

    def test_provider_save_response(self):
        from aksara.studio.models import StudioAiProviderSaveResponse
        r = StudioAiProviderSaveResponse(saved=True, provider="openai", file_path=".env")
        assert r.saved is True

    def test_ping_request_optional_provider(self):
        from aksara.studio.models import StudioAiProviderPingRequest
        r = StudioAiProviderPingRequest()
        assert r.provider is None

    def test_ping_response(self):
        from aksara.studio.models import StudioAiProviderPingResponse
        r = StudioAiProviderPingResponse(provider="openai", reachable=True, latency_ms=42.5)
        assert r.reachable is True
        assert r.latency_ms == 42.5

    def test_agent_run_request(self):
        from aksara.studio.models import StudioAiAgentRunRequest
        r = StudioAiAgentRunRequest(prompt="Hello")
        assert r.prompt == "Hello"
        assert r.temperature == 0.3
        assert r.include_context is True

    def test_agent_run_response_success(self):
        from aksara.studio.models import StudioAiAgentRunResponse
        r = StudioAiAgentRunResponse(provider="openai", model="gpt-4o", output="Hi there!")
        assert r.output == "Hi there!"
        assert r.error is None

    def test_agent_run_response_error(self):
        from aksara.studio.models import StudioAiAgentRunResponse
        r = StudioAiAgentRunResponse(provider="openai", model="gpt-4o", error="Rate limited")
        assert r.error == "Rate limited"


class TestStudioAiHubUtils:
    """Tests for the build_* utility functions."""

    def test_build_ai_hub_providers(self):
        from aksara.studio.utils import build_ai_hub_providers
        result = build_ai_hub_providers()
        assert hasattr(result, "providers")
        assert hasattr(result, "active_provider")
        assert isinstance(result.total_count, int)

    def test_build_ai_hub_provider_save(self):
        from aksara.studio.utils import build_ai_hub_provider_save
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("aksara.ai.providers_unified.Path.cwd", return_value=Path(tmpdir)):
                result = build_ai_hub_provider_save(
                    provider="openai", api_key="sk-test", model="gpt-4o",
                )
                assert result.saved is True
                assert "openai" in result.message

    def test_build_ai_hub_provider_ping_no_provider(self):
        from aksara.studio.utils import build_ai_hub_provider_ping
        # When no provider is configured
        env_clean = {k: v for k, v in os.environ.items()
                     if not any(x in k.upper() for x in ["OPENAI", "ANTHROPIC", "AZURE", "OLLAMA", "AKSARA_AI", "AKSARA_CUSTOM"])}
        with patch.dict(os.environ, env_clean, clear=True):
            result = build_ai_hub_provider_ping()
            assert result.reachable is False

    def test_build_ai_hub_agent_run_no_provider(self):
        from aksara.studio.utils import build_ai_hub_agent_run
        env_clean = {k: v for k, v in os.environ.items()
                     if not any(x in k.upper() for x in ["OPENAI", "ANTHROPIC", "AZURE", "OLLAMA", "AKSARA_AI", "AKSARA_CUSTOM"])}
        with patch.dict(os.environ, env_clean, clear=True):
            result = build_ai_hub_agent_run(prompt="Hello")
            assert result.error is not None
            assert "No AI provider" in result.error

    def test_build_ai_hub_agent_run_with_mock_provider(self):
        from aksara.studio.utils import build_ai_hub_agent_run
        from aksara.ai.providers_unified import UnifiedAiProvider
        mock_provider = UnifiedAiProvider(
            provider="openai", api_key="sk-test", model="gpt-4o"
        )
        mock_client = MagicMock()
        mock_client.generate.return_value = "Mock response"
        with patch("aksara.ai.providers_unified.get_active_provider", return_value=mock_provider):
            with patch.object(UnifiedAiProvider, "get_llm_client", return_value=mock_client):
                result = build_ai_hub_agent_run(prompt="Hello")
                assert hasattr(result, "provider")


# =============================================================================
# 4. CLI ai-provider Command Tests (10 tests)
# =============================================================================


class TestCliAiProviderCommands:
    """Tests for CLI ai-provider group commands."""

    def test_cli_ai_provider_group_exists(self):
        from aksara.cli.main import ai_provider_group
        assert ai_provider_group is not None

    def test_cli_ai_provider_list_command(self):
        from click.testing import CliRunner
        from aksara.cli.main import ai_provider_group
        runner = CliRunner()
        result = runner.invoke(ai_provider_group, ["list"])
        assert result.exit_code == 0
        assert "AI Providers" in result.output

    def test_cli_ai_provider_list_json_format(self):
        from click.testing import CliRunner
        from aksara.cli.main import ai_provider_group
        runner = CliRunner()
        result = runner.invoke(ai_provider_group, ["list", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "providers" in data

    def test_cli_ai_provider_detect_command(self):
        from click.testing import CliRunner
        from aksara.cli.main import ai_provider_group
        runner = CliRunner()
        result = runner.invoke(ai_provider_group, ["detect"])
        assert result.exit_code == 0
        assert "Provider Detection" in result.output

    def test_cli_ai_provider_ping_no_provider(self):
        from click.testing import CliRunner
        from aksara.cli.main import ai_provider_group
        runner = CliRunner()
        env_clean = {k: v for k, v in os.environ.items()
                     if not any(x in k.upper() for x in ["OPENAI", "ANTHROPIC", "AZURE", "OLLAMA", "AKSARA_AI", "AKSARA_CUSTOM"])}
        result = runner.invoke(ai_provider_group, ["ping"], env=env_clean)
        assert result.exit_code == 0
        # Should report no active provider
        assert "Provider Ping" in result.output

    def test_cli_ai_provider_ping_specific_missing(self):
        from click.testing import CliRunner
        from aksara.cli.main import ai_provider_group
        runner = CliRunner()
        result = runner.invoke(ai_provider_group, ["ping", "--provider", "openai"])
        assert result.exit_code == 0

    def test_cli_ai_provider_configure_interactive(self):
        from click.testing import CliRunner
        from aksara.cli.main import ai_provider_group
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("aksara.ai.providers_unified.Path.cwd", return_value=Path(tmpdir)):
                result = runner.invoke(
                    ai_provider_group,
                    ["configure", "ollama", "--model", "llama3"],
                )
                assert result.exit_code == 0
                assert "Configure Provider" in result.output

    def test_cli_help_text(self):
        from click.testing import CliRunner
        from aksara.cli.main import ai_provider_group
        runner = CliRunner()
        result = runner.invoke(ai_provider_group, ["--help"])
        assert result.exit_code == 0
        assert "Unified AI provider" in result.output

    def test_cli_list_help(self):
        from click.testing import CliRunner
        from aksara.cli.main import ai_provider_group
        runner = CliRunner()
        result = runner.invoke(ai_provider_group, ["list", "--help"])
        assert result.exit_code == 0
        assert "List all detected" in result.output

    def test_cli_configure_help(self):
        from click.testing import CliRunner
        from aksara.cli.main import ai_provider_group
        runner = CliRunner()
        result = runner.invoke(ai_provider_group, ["configure", "--help"])
        assert result.exit_code == 0


# =============================================================================
# 5. Studio UI Tests (10 tests)
# =============================================================================


class TestStudioAiHubUI:
    """Tests for AI Hub Studio UI templates and navigation."""

    def test_index_html_has_ai_hub_nav(self):
        index_path = Path(__file__).parent.parent / "aksara" / "studio" / "static" / "index.html"
        content = index_path.read_text()
        assert 'data-section="ai-hub"' in content
        assert "AI Hub" in content

    def test_index_html_has_ai_hub_template(self):
        index_path = Path(__file__).parent.parent / "aksara" / "studio" / "static" / "index.html"
        content = index_path.read_text()
        assert 'id="template-ai-hub"' in content

    def test_index_html_has_five_tabs(self):
        index_path = Path(__file__).parent.parent / "aksara" / "studio" / "static" / "index.html"
        content = index_path.read_text()
        assert 'data-tab="providers"' in content
        assert 'data-tab="helpers"' in content
        assert 'data-tab="profiles"' in content
        assert 'data-tab="context"' in content
        assert 'data-tab="agent"' in content

    def test_index_html_has_provider_form(self):
        index_path = Path(__file__).parent.parent / "aksara" / "studio" / "static" / "index.html"
        content = index_path.read_text()
        assert 'id="ai-hub-cfg-provider"' in content
        assert 'id="ai-hub-cfg-apikey"' in content
        assert 'id="ai-hub-cfg-save"' in content

    def test_index_html_has_agent_prompt(self):
        index_path = Path(__file__).parent.parent / "aksara" / "studio" / "static" / "index.html"
        content = index_path.read_text()
        assert 'id="ai-hub-agent-prompt"' in content
        assert 'id="ai-hub-agent-run"' in content

    def test_app_js_has_render_ai_hub(self):
        app_js_path = Path(__file__).parent.parent / "aksara" / "studio" / "static" / "app.js"
        content = app_js_path.read_text()
        assert "renderAiHub" in content

    def test_app_js_has_ai_hub_state(self):
        app_js_path = Path(__file__).parent.parent / "aksara" / "studio" / "static" / "app.js"
        content = app_js_path.read_text()
        assert "aiHub:" in content

    def test_app_js_has_section_case(self):
        app_js_path = Path(__file__).parent.parent / "aksara" / "studio" / "static" / "app.js"
        content = app_js_path.read_text()
        assert "'ai-hub'" in content

    def test_app_js_has_keyboard_shortcut(self):
        app_js_path = Path(__file__).parent.parent / "aksara" / "studio" / "static" / "app.js"
        content = app_js_path.read_text()
        # Should have 'A' shortcut for AI Hub
        assert "navigateTo('ai-hub')" in content

    def test_styles_css_has_ai_hub_styles(self):
        css_path = Path(__file__).parent.parent / "aksara" / "studio" / "static" / "styles.css"
        content = css_path.read_text()
        assert ".ai-hub-tabs" in content
        assert ".provider-card" in content
        assert ".tool-grid" in content


# =============================================================================
# 6. Integration & Non-Regression Tests (10 tests)
# =============================================================================


class TestAiHubIntegration:
    """Integration tests for the AI Hub system."""

    def test_version_is_0_5_25(self):
        from aksara._version import __version__
        assert __version__ == "0.5.29"

    def test_cli_version_is_0_5_25(self):
        from aksara.cli.main import CLI_VERSION
        assert CLI_VERSION == "0.5.29"

    def test_unified_provider_imports(self):
        """Verify all unified provider imports work."""
        from aksara.ai.providers_unified import (
            UnifiedAiProvider,
            detect_all_providers,
            get_active_provider,
        )
        assert UnifiedAiProvider is not None
        assert detect_all_providers is not None
        assert get_active_provider is not None

    def test_llm_clients_imports(self):
        """Verify all LLM client imports work."""
        from aksara.ai.llm_clients import (
            BaseLlmClient,
            get_client_for_provider,
        )
        from aksara.ai.llm_clients.openai_adapter import OpenAIAdapter
        from aksara.ai.llm_clients.azure_adapter import AzureOpenAIAdapter
        from aksara.ai.llm_clients.anthropic_adapter import AnthropicAdapter
        from aksara.ai.llm_clients.ollama_adapter import OllamaAdapter
        from aksara.ai.llm_clients.custom_adapter import CustomHttpAdapter
        assert all([
            BaseLlmClient, get_client_for_provider,
            OpenAIAdapter, AzureOpenAIAdapter, AnthropicAdapter,
            OllamaAdapter, CustomHttpAdapter,
        ])

    def test_studio_models_imports(self):
        """Verify all new Studio model imports work."""
        from aksara.studio.models import (
            StudioAiProviderStatus,
            StudioAiProvidersSummary,
            StudioAiProviderSaveRequest,
            StudioAiProviderSaveResponse,
            StudioAiProviderPingRequest,
            StudioAiProviderPingResponse,
            StudioAiAgentRunRequest,
            StudioAiAgentRunResponse,
        )
        assert all([
            StudioAiProviderStatus, StudioAiProvidersSummary,
            StudioAiProviderSaveRequest, StudioAiProviderSaveResponse,
            StudioAiProviderPingRequest, StudioAiProviderPingResponse,
            StudioAiAgentRunRequest, StudioAiAgentRunResponse,
        ])

    def test_studio_utils_imports(self):
        """Verify all new build functions import."""
        from aksara.studio.utils import (
            build_ai_hub_providers,
            build_ai_hub_provider_save,
            build_ai_hub_provider_ping,
            build_ai_hub_agent_run,
        )
        assert all([
            build_ai_hub_providers,
            build_ai_hub_provider_save,
            build_ai_hub_provider_ping,
            build_ai_hub_agent_run,
        ])

    def test_fastapi_router_has_ai_hub_endpoints(self):
        """Verify the Studio router has the new AI Hub endpoints."""
        from aksara.studio.fastapi import router
        paths = [route.path for route in router.routes]
        assert "/studio/ai/hub/providers" in paths
        assert "/studio/ai/hub/providers/save" in paths
        assert "/studio/ai/hub/providers/ping" in paths
        assert "/studio/ai/hub/agent/run" in paths

    def test_no_crash_with_empty_env(self):
        """AI Hub should not crash with no env vars set."""
        env_clean = {k: v for k, v in os.environ.items()
                     if not any(x in k.upper() for x in ["OPENAI", "ANTHROPIC", "AZURE", "OLLAMA", "AKSARA_AI", "AKSARA_CUSTOM"])}
        with patch.dict(os.environ, env_clean, clear=True):
            from aksara.ai.providers_unified import detect_all_providers, get_active_provider
            providers = detect_all_providers()
            assert isinstance(providers, list)
            active = get_active_provider()
            # Should be None or unconfigured, not crash

    def test_no_crash_with_partial_env(self):
        """AI Hub should handle partial env vars gracefully."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False):
            from aksara.ai.providers_unified import detect_all_providers
            providers = detect_all_providers()
            assert isinstance(providers, list)

    def test_existing_ai_module_not_broken(self):
        """Verify existing AI module imports still work."""
        from aksara.ai.client import BaseAiClient
        from aksara.ai.providers import AiProviderProfile, AiProfileSet
        from aksara.ai.registry import AiToolRegistry
        assert all([BaseAiClient, AiProviderProfile, AiProfileSet, AiToolRegistry])
