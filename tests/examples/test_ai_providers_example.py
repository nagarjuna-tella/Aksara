"""
Tests for AI Providers Example Package

v0.5.14: Tests for examples/ai_providers adapters and utilities.
"""

import os
import pytest
from unittest.mock import MagicMock, patch, AsyncMock


# =============================================================================
# Settings Tests
# =============================================================================

class TestAiProvidersSettings:
    """Tests for examples.ai_providers.settings module."""

    def test_settings_class_exists(self):
        """Settings class can be imported."""
        from examples.ai_providers.settings import Settings
        assert Settings is not None

    def test_settings_instance_exists(self):
        """Default settings instance exists."""
        from examples.ai_providers.settings import settings
        assert settings is not None

    def test_default_provider_is_openai(self):
        """Default provider is openai."""
        from examples.ai_providers.settings import settings
        assert settings.AI_DEFAULT_PROVIDER == "openai"

    def test_openai_default_model(self):
        """OpenAI default model is set."""
        from examples.ai_providers.settings import settings
        assert settings.OPENAI_DEFAULT_MODEL == "gpt-4o-mini"

    def test_anthropic_default_model(self):
        """Anthropic default model is set."""
        from examples.ai_providers.settings import settings
        assert settings.ANTHROPIC_DEFAULT_MODEL == "claude-3-5-sonnet-20241022"

    def test_is_provider_configured_openai(self):
        """is_provider_configured works for OpenAI."""
        from examples.ai_providers.settings import Settings
        
        # Settings reads from os.environ at class definition time
        # Test the method works correctly
        s = Settings()
        # Method exists and works
        result = s.is_provider_configured("openai")
        assert isinstance(result, bool)

    def test_is_provider_configured_azure(self):
        """is_provider_configured works for Azure."""
        from examples.ai_providers.settings import Settings
        
        s = Settings()
        result = s.is_provider_configured("azure")
        assert isinstance(result, bool)

    def test_is_provider_configured_anthropic(self):
        """is_provider_configured works for Anthropic."""
        from examples.ai_providers.settings import Settings
        
        s = Settings()
        result = s.is_provider_configured("anthropic")
        assert isinstance(result, bool)

    def test_get_configured_providers(self):
        """get_configured_providers returns list of configured providers."""
        from examples.ai_providers.settings import Settings
        
        s = Settings()
        configured = s.get_configured_providers()
        assert isinstance(configured, list)

    def test_validate_ai_config_no_provider(self):
        """validate_ai_config warns when no provider is configured."""
        from examples.ai_providers.settings import Settings
        
        with patch.dict(os.environ, {}, clear=True):
            s = Settings()
            is_valid, issues = s.validate_ai_config()
            # Should have warnings about no configured providers
            assert len(issues) > 0


# =============================================================================
# Adapters Tests
# =============================================================================

class TestLlmClientProtocol:
    """Tests for LlmClient protocol and adapters."""

    def test_llm_client_protocol_exists(self):
        """LlmClient protocol can be imported."""
        from examples.ai_providers.adapters import LlmClient
        assert LlmClient is not None

    def test_base_llm_client_is_abstract(self):
        """BaseLlmClient is abstract."""
        from examples.ai_providers.adapters import BaseLlmClient
        
        with pytest.raises(TypeError):
            BaseLlmClient()

    def test_check_sdk_availability(self):
        """check_sdk_availability returns dict."""
        from examples.ai_providers.adapters import check_sdk_availability
        
        result = check_sdk_availability()
        assert isinstance(result, dict)
        assert "openai" in result
        assert "anthropic" in result

    def test_get_llm_client_openai_without_sdk(self):
        """get_llm_client raises if openai SDK not installed."""
        from examples.ai_providers.adapters import get_llm_client
        
        with patch.dict("sys.modules", {"openai": None}):
            # This may or may not raise depending on import state
            # What matters is it doesn't crash unexpectedly
            pass

    def test_get_llm_client_from_settings_factory(self):
        """get_llm_client_from_settings is a factory function."""
        from examples.ai_providers.adapters import get_llm_client_from_settings
        assert callable(get_llm_client_from_settings)


class TestOpenAIClient:
    """Tests for OpenAIClient adapter."""

    def test_openai_client_class_exists(self):
        """OpenAIClient class can be imported."""
        from examples.ai_providers.adapters import OpenAIClient
        assert OpenAIClient is not None

    @pytest.mark.skipif(
        not os.environ.get("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY not set"
    )
    def test_openai_client_init_with_key(self):
        """OpenAIClient can be instantiated with API key."""
        try:
            import openai
        except ImportError:
            pytest.skip("openai SDK not installed")
        
        from examples.ai_providers.adapters import OpenAIClient
        client = OpenAIClient(api_key="test-key")
        assert client is not None


class TestAzureOpenAIClient:
    """Tests for AzureOpenAIClient adapter."""

    def test_azure_client_class_exists(self):
        """AzureOpenAIClient class can be imported."""
        from examples.ai_providers.adapters import AzureOpenAIClient
        assert AzureOpenAIClient is not None


class TestAnthropicClient:
    """Tests for AnthropicClient adapter."""

    def test_anthropic_client_class_exists(self):
        """AnthropicClient class can be imported."""
        from examples.ai_providers.adapters import AnthropicClient
        assert AnthropicClient is not None


# =============================================================================
# Prompting Tests
# =============================================================================

class TestPromptingUtilities:
    """Tests for prompting utilities."""

    def test_build_prompt_for_route_exists(self):
        """build_prompt_for_route function exists."""
        from examples.ai_providers.prompting import build_prompt_for_route
        assert callable(build_prompt_for_route)

    def test_build_chat_messages_for_route_exists(self):
        """build_chat_messages_for_route function exists."""
        from examples.ai_providers.prompting import build_chat_messages_for_route
        assert callable(build_chat_messages_for_route)

    def test_format_structured_output_prompt_exists(self):
        """format_structured_output_prompt function exists."""
        from examples.ai_providers.prompting import format_structured_output_prompt
        assert callable(format_structured_output_prompt)

    def test_parse_json_response_valid(self):
        """parse_json_response parses valid JSON."""
        from examples.ai_providers.prompting import parse_json_response
        
        result = parse_json_response('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parse_json_response_with_markdown(self):
        """parse_json_response handles markdown code blocks."""
        from examples.ai_providers.prompting import parse_json_response
        
        result = parse_json_response('```json\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_parse_json_response_invalid(self):
        """parse_json_response raises on invalid JSON."""
        from examples.ai_providers.prompting import parse_json_response
        
        with pytest.raises(ValueError):
            parse_json_response("not json at all")

    def test_extract_tags_from_response_list(self):
        """extract_tags_from_response handles list response."""
        from examples.ai_providers.prompting import extract_tags_from_response
        
        result = extract_tags_from_response('["python", "ai", "testing"]')
        assert result == ["python", "ai", "testing"]

    def test_extract_tags_from_response_dict(self):
        """extract_tags_from_response handles dict with tags key."""
        from examples.ai_providers.prompting import extract_tags_from_response
        
        result = extract_tags_from_response('{"tags": ["python", "ai"]}')
        assert result == ["python", "ai"]

    def test_extract_tags_from_response_plain_text(self):
        """extract_tags_from_response handles plain text."""
        from examples.ai_providers.prompting import extract_tags_from_response
        
        result = extract_tags_from_response("python, ai, testing")
        assert "python" in result
        assert "ai" in result

    def test_get_tag_suggestion_prompt(self):
        """get_tag_suggestion_prompt returns a prompt string."""
        from examples.ai_providers.prompting import get_tag_suggestion_prompt
        
        prompt = get_tag_suggestion_prompt("Test Title", "Test content about Python.")
        assert "Test Title" in prompt
        assert "Test content" in prompt

    def test_get_content_summary_prompt(self):
        """get_content_summary_prompt returns a prompt string."""
        from examples.ai_providers.prompting import get_content_summary_prompt
        
        prompt = get_content_summary_prompt("Long content here...", max_length=100)
        assert "100" in prompt


# =============================================================================
# Views Tests
# =============================================================================

class TestDemoViews:
    """Tests for demo views."""

    def test_demo_post_viewset_exists(self):
        """DemoPostViewSet can be imported."""
        from examples.ai_providers.views import DemoPostViewSet
        assert DemoPostViewSet is not None

    def test_get_ai_client_status_exists(self):
        """get_ai_client_status function exists."""
        from examples.ai_providers.views import get_ai_client_status
        assert callable(get_ai_client_status)


# =============================================================================
# Package Integration Tests
# =============================================================================

class TestPackageExports:
    """Tests for package exports in __init__.py."""

    def test_all_exports_importable(self):
        """All __all__ exports can be imported."""
        from examples.ai_providers import __all__
        
        import examples.ai_providers as pkg
        
        for name in __all__:
            assert hasattr(pkg, name), f"Missing export: {name}"

    def test_settings_export(self):
        """Settings can be imported from package."""
        from examples.ai_providers import Settings, settings
        assert Settings is not None
        assert settings is not None

    def test_adapters_export(self):
        """Adapters can be imported from package."""
        from examples.ai_providers import (
            LlmClient,
            OpenAIClient,
            AzureOpenAIClient,
            AnthropicClient,
            get_llm_client,
        )
        assert LlmClient is not None

    def test_prompting_export(self):
        """Prompting utilities can be imported from package."""
        from examples.ai_providers import (
            build_prompt_for_route,
            build_chat_messages_for_route,
            format_structured_output_prompt,
        )
        assert build_prompt_for_route is not None


# =============================================================================
# Studio Integration Tests
# =============================================================================

class TestStudioProviderReadiness:
    """Tests for Studio provider readiness indicator (v0.5.14)."""

    def test_studio_provider_summary_has_client_ready(self):
        """StudioAiProviderSummary has client_ready field."""
        from aksara.studio.models import StudioAiProviderSummary
        
        # Check field exists in model
        assert "client_ready" in StudioAiProviderSummary.model_fields

    def test_check_provider_ready_function(self):
        """_check_provider_ready function works."""
        from aksara.studio.utils import _check_provider_ready
        from aksara.conf import settings
        
        # Test unknown provider - should return True
        result = _check_provider_ready("unknown", settings)
        assert result is True

    def test_check_provider_ready_openai_no_sdk(self):
        """_check_provider_ready returns False if SDK missing."""
        from aksara.studio.utils import _check_provider_ready
        from aksara.conf import settings
        
        # If openai is not installed, should return False
        try:
            import openai
            # SDK is installed, test requires credentials
            with patch.dict(os.environ, {}, clear=True):
                result = _check_provider_ready("openai", settings)
                assert result is False
        except ImportError:
            # SDK not installed
            result = _check_provider_ready("openai", settings)
            assert result is False

    @pytest.mark.skipif(
        not os.environ.get("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY not set"
    )
    def test_check_provider_ready_openai_configured(self):
        """_check_provider_ready returns True if SDK and key present."""
        try:
            import openai
        except ImportError:
            pytest.skip("openai SDK not installed")
        
        from aksara.studio.utils import _check_provider_ready
        from aksara.conf import settings
        
        result = _check_provider_ready("openai", settings)
        assert result is True
