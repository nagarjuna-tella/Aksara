"""
Tests for Aksara AI Profiles & Provider Contracts

v0.5.11: Tests for the vendor-agnostic AI profile system.
"""

import pytest
from unittest.mock import MagicMock, patch

from aksara.ai.providers import (
    AiModelProfile,
    AiProviderProfile,
    AiProfileSet,
    AiProviderSecretHint,
    AiProviderConfigInfo,
    AiProviderRegistry,
    get_ai_provider_registry,
    build_default_ai_profile_set,
    build_secret_hints_from_settings,
    build_example_profile_set,
)


class TestAiModelProfile:
    """Tests for AiModelProfile model."""
    
    def test_create_minimal_model(self):
        """Test creating a model with minimal required fields."""
        model = AiModelProfile(
            name="test-model",
            display_name="Test Model",
            model_id="test-model-v1",
        )
        assert model.name == "test-model"
        assert model.display_name == "Test Model"
        assert model.model_id == "test-model-v1"
        assert model.kind == "chat"  # default
        assert model.supports_tools is False  # default
        assert model.supports_streaming is True  # default
        assert model.tags == []  # default
    
    def test_create_full_model(self):
        """Test creating a model with all fields."""
        model = AiModelProfile(
            name="gpt-4o",
            display_name="GPT-4 Omni",
            model_id="gpt-4o-2024-05-13",
            kind="chat",
            max_input_tokens=128000,
            max_output_tokens=4096,
            supports_tools=True,
            supports_streaming=True,
            supports_vision=True,
            tags=["fast", "multimodal"],
        )
        assert model.name == "gpt-4o"
        assert model.max_input_tokens == 128000
        assert model.max_output_tokens == 4096
        assert model.supports_tools is True
        assert model.supports_vision is True
        assert "fast" in model.tags
    
    def test_model_kind_validation(self):
        """Test that model kind must be a valid literal."""
        model = AiModelProfile(
            name="test",
            display_name="Test",
            model_id="test",
            kind="embedding",
        )
        assert model.kind == "embedding"
    
    def test_model_extra_fields_forbidden(self):
        """Test that extra fields are rejected."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            AiModelProfile(
                name="test",
                display_name="Test",
                model_id="test",
                unknown_field="value",
            )


class TestAiProviderProfile:
    """Tests for AiProviderProfile model."""
    
    def test_create_minimal_provider(self):
        """Test creating a provider with minimal required fields."""
        provider = AiProviderProfile(
            name="test-provider",
            display_name="Test Provider",
            kind="openai",
        )
        assert provider.name == "test-provider"
        assert provider.kind == "openai"
        assert provider.models == []
        assert provider.base_url is None
        assert provider.metadata == {}
    
    def test_create_provider_with_models(self):
        """Test creating a provider with models."""
        model = AiModelProfile(
            name="test-model",
            display_name="Test Model",
            model_id="test-model-v1",
        )
        provider = AiProviderProfile(
            name="test-provider",
            display_name="Test Provider",
            kind="openai",
            models=[model],
            default_model="test-model",
        )
        assert len(provider.models) == 1
        assert provider.default_model == "test-model"
    
    def test_get_model(self):
        """Test getting a model by name."""
        model = AiModelProfile(
            name="gpt-4o",
            display_name="GPT-4 Omni",
            model_id="gpt-4o-2024-05-13",
        )
        provider = AiProviderProfile(
            name="test",
            display_name="Test",
            kind="openai",
            models=[model],
        )
        
        # Get by name
        result = provider.get_model("gpt-4o")
        assert result is not None
        assert result.name == "gpt-4o"
        
        # Get by model_id
        result = provider.get_model("gpt-4o-2024-05-13")
        assert result is not None
        
        # Not found
        result = provider.get_model("nonexistent")
        assert result is None
    
    def test_get_default_model(self):
        """Test getting the default model."""
        model1 = AiModelProfile(name="m1", display_name="M1", model_id="m1")
        model2 = AiModelProfile(name="m2", display_name="M2", model_id="m2")
        
        # With explicit default
        provider = AiProviderProfile(
            name="test",
            display_name="Test",
            kind="openai",
            models=[model1, model2],
            default_model="m2",
        )
        default = provider.get_default_model()
        assert default.name == "m2"
        
        # Without explicit default (returns first)
        provider2 = AiProviderProfile(
            name="test",
            display_name="Test",
            kind="openai",
            models=[model1, model2],
        )
        default = provider2.get_default_model()
        assert default.name == "m1"
        
        # No models
        provider3 = AiProviderProfile(
            name="test",
            display_name="Test",
            kind="openai",
        )
        default = provider3.get_default_model()
        assert default is None


class TestAiProfileSet:
    """Tests for AiProfileSet model."""
    
    def test_create_empty_set(self):
        """Test creating an empty profile set."""
        profile_set = AiProfileSet()
        assert profile_set.providers == []
        assert profile_set.default_provider is None
        assert profile_set.total_models() == 0
    
    def test_create_set_with_providers(self):
        """Test creating a profile set with providers."""
        model = AiModelProfile(name="m1", display_name="M1", model_id="m1")
        provider = AiProviderProfile(
            name="p1",
            display_name="P1",
            kind="openai",
            models=[model],
        )
        
        profile_set = AiProfileSet(
            providers=[provider],
            default_provider="p1",
            environment="development",
            version="1.0.0",
        )
        
        assert len(profile_set.providers) == 1
        assert profile_set.default_provider == "p1"
        assert profile_set.total_models() == 1
    
    def test_get_provider(self):
        """Test getting a provider by name."""
        provider = AiProviderProfile(name="p1", display_name="P1", kind="openai")
        profile_set = AiProfileSet(providers=[provider])
        
        result = profile_set.get_provider("p1")
        assert result is not None
        assert result.name == "p1"
        
        result = profile_set.get_provider("nonexistent")
        assert result is None
    
    def test_get_default_provider(self):
        """Test getting the default provider."""
        p1 = AiProviderProfile(name="p1", display_name="P1", kind="openai")
        p2 = AiProviderProfile(name="p2", display_name="P2", kind="anthropic")
        
        # With explicit default
        profile_set = AiProfileSet(
            providers=[p1, p2],
            default_provider="p2",
        )
        default = profile_set.get_default_provider()
        assert default.name == "p2"
        
        # Without explicit default (returns first)
        profile_set2 = AiProfileSet(providers=[p1, p2])
        default = profile_set2.get_default_provider()
        assert default.name == "p1"


class TestAiProviderSecretHint:
    """Tests for AiProviderSecretHint model."""
    
    def test_create_secret_hint(self):
        """Test creating a secret hint."""
        hint = AiProviderSecretHint(
            provider_name="openai",
            env_var="OPENAI_API_KEY",
            required=True,
            description="API key from platform.openai.com",
        )
        assert hint.provider_name == "openai"
        assert hint.env_var == "OPENAI_API_KEY"
        assert hint.required is True
        assert hint.description == "API key from platform.openai.com"
    
    def test_create_optional_hint(self):
        """Test creating an optional secret hint."""
        hint = AiProviderSecretHint(
            provider_name="local",
            env_var="LOCAL_API_KEY",
            required=False,
        )
        assert hint.required is False


class TestAiProviderConfigInfo:
    """Tests for AiProviderConfigInfo model."""
    
    def test_create_config_info(self):
        """Test creating a config info object."""
        profile_set = AiProfileSet()
        secret = AiProviderSecretHint(
            provider_name="test",
            env_var="TEST_KEY",
        )
        
        config = AiProviderConfigInfo(
            profile_set=profile_set,
            secrets=[secret],
        )
        assert config.profile_set is not None
        assert len(config.secrets) == 1


class TestAiProviderRegistry:
    """Tests for AiProviderRegistry."""
    
    def test_register_and_get_provider(self):
        """Test registering and retrieving a provider."""
        registry = AiProviderRegistry()
        provider = AiProviderProfile(name="test", display_name="Test", kind="openai")
        
        registry.register_profile(provider)
        
        result = registry.get_provider("test")
        assert result is not None
        assert result.name == "test"
    
    def test_list_providers(self):
        """Test listing all providers."""
        registry = AiProviderRegistry()
        p1 = AiProviderProfile(name="p1", display_name="P1", kind="openai")
        p2 = AiProviderProfile(name="p2", display_name="P2", kind="anthropic")
        
        registry.register_profile(p1)
        registry.register_profile(p2)
        
        providers = registry.list_providers()
        assert len(providers) == 2
    
    def test_list_models(self):
        """Test listing models."""
        registry = AiProviderRegistry()
        
        m1 = AiModelProfile(name="m1", display_name="M1", model_id="m1")
        m2 = AiModelProfile(name="m2", display_name="M2", model_id="m2")
        
        p1 = AiProviderProfile(name="p1", display_name="P1", kind="openai", models=[m1])
        p2 = AiProviderProfile(name="p2", display_name="P2", kind="anthropic", models=[m2])
        
        registry.register_profile(p1)
        registry.register_profile(p2)
        
        # List all models
        all_models = registry.list_models()
        assert len(all_models) == 2
        
        # Filter by provider
        p1_models = registry.list_models(provider_name="p1")
        assert len(p1_models) == 1
        assert p1_models[0].name == "m1"
    
    def test_default_provider(self):
        """Test default provider logic."""
        registry = AiProviderRegistry()
        p1 = AiProviderProfile(name="p1", display_name="P1", kind="openai")
        p2 = AiProviderProfile(name="p2", display_name="P2", kind="anthropic")
        
        registry.register_profile(p1)
        registry.register_profile(p2)
        
        # No default set - returns first
        default = registry.get_default_provider()
        assert default is not None
        
        # Set explicit default
        registry.set_default_provider("p2")
        default = registry.get_default_provider()
        assert default.name == "p2"
    
    def test_set_default_provider_not_found(self):
        """Test setting a non-existent default provider."""
        registry = AiProviderRegistry()
        
        with pytest.raises(ValueError):
            registry.set_default_provider("nonexistent")
    
    def test_get_profile_set(self):
        """Test getting a profile set from the registry."""
        registry = AiProviderRegistry()
        p1 = AiProviderProfile(name="p1", display_name="P1", kind="openai")
        
        registry.register_profile(p1)
        registry.set_default_provider("p1")
        registry.set_metadata(environment="test", version="1.0")
        
        profile_set = registry.get_profile_set()
        assert len(profile_set.providers) == 1
        assert profile_set.default_provider == "p1"
        assert profile_set.environment == "test"
    
    def test_clear(self):
        """Test clearing the registry."""
        registry = AiProviderRegistry()
        p1 = AiProviderProfile(name="p1", display_name="P1", kind="openai")
        
        registry.register_profile(p1)
        assert len(registry) == 1
        
        registry.clear()
        assert len(registry) == 0
    
    def test_contains(self):
        """Test checking if a provider exists."""
        registry = AiProviderRegistry()
        p1 = AiProviderProfile(name="p1", display_name="P1", kind="openai")
        
        registry.register_profile(p1)
        
        assert "p1" in registry
        assert "p2" not in registry


class TestGetAiProviderRegistry:
    """Tests for get_ai_provider_registry helper."""
    
    def test_get_from_app(self):
        """Test getting registry from app."""
        app = MagicMock()
        registry = AiProviderRegistry()
        app.ai_provider_registry = registry
        
        result = get_ai_provider_registry(app)
        assert result is registry
    
    def test_get_from_app_state(self):
        """Test getting registry from app.state."""
        app = MagicMock(spec=[])
        app.state = MagicMock()
        registry = AiProviderRegistry()
        app.state.ai_provider_registry = registry
        
        # Remove direct attribute
        del app.ai_provider_registry
        
        result = get_ai_provider_registry(app)
        assert result is registry
    
    def test_create_new_if_not_found(self):
        """Test creating new registry if none exists."""
        result = get_ai_provider_registry(None)
        assert isinstance(result, AiProviderRegistry)


class TestBuildDefaultAiProfileSet:
    """Tests for build_default_ai_profile_set helper."""
    
    def test_disabled_returns_empty(self):
        """Test that disabled profiles returns empty set."""
        settings = MagicMock()
        settings.ai_profiles_enabled = False
        
        result = build_default_ai_profile_set(settings)
        assert len(result.providers) == 0
        assert result.version == "disabled"
    
    def test_no_config_returns_examples(self):
        """Test that missing config returns example profiles."""
        settings = MagicMock()
        settings.ai_profiles_enabled = True
        settings.ai_providers = None
        settings.ai_default_provider = None
        settings.debug = True
        
        result = build_default_ai_profile_set(settings)
        assert len(result.providers) > 0
        
        # Check that at least one is an example
        has_example = any(p.metadata.get("_example", False) for p in result.providers)
        assert has_example
    
    def test_explicit_config_used(self):
        """Test that explicit config is used when provided."""
        settings = MagicMock()
        settings.ai_profiles_enabled = True
        settings.ai_default_provider = "my_provider"
        settings.ai_providers = [
            {
                "name": "my_provider",
                "display_name": "My Provider",
                "kind": "openai",
                "models": [
                    {
                        "name": "my-model",
                        "display_name": "My Model",
                        "model_id": "my-model-v1",
                    }
                ],
            }
        ]
        settings.debug = False
        
        result = build_default_ai_profile_set(settings)
        assert len(result.providers) == 1
        assert result.providers[0].name == "my_provider"
        assert result.default_provider == "my_provider"


class TestBuildSecretHintsFromSettings:
    """Tests for build_secret_hints_from_settings helper."""
    
    def test_explicit_hints_used(self):
        """Test that explicit hints from settings are used."""
        settings = MagicMock()
        settings.ai_secret_hints = [
            {
                "provider_name": "test",
                "env_var": "TEST_API_KEY",
                "required": True,
            }
        ]
        
        result = build_secret_hints_from_settings(settings)
        assert len(result) == 1
        assert result[0].env_var == "TEST_API_KEY"
    
    def test_default_hints_when_none(self):
        """Test that default hints are returned when none configured."""
        settings = MagicMock()
        settings.ai_secret_hints = None
        
        result = build_secret_hints_from_settings(settings)
        assert len(result) > 0


class TestBuildExampleProfileSet:
    """Tests for build_example_profile_set helper."""
    
    def test_returns_valid_profile_set(self):
        """Test that example profile set is valid."""
        result = build_example_profile_set()
        
        assert isinstance(result, AiProfileSet)
        assert len(result.providers) > 0
        assert result.default_provider is not None
    
    def test_all_providers_marked_as_example(self):
        """Test that all providers are marked as examples."""
        result = build_example_profile_set()
        
        for provider in result.providers:
            assert provider.metadata.get("_example", False) is True
    
    def test_has_openai_like_provider(self):
        """Test that OpenAI-like provider exists."""
        result = build_example_profile_set()
        
        openai_provider = result.get_provider("example_openai_like")
        assert openai_provider is not None
        assert openai_provider.kind == "openai"
        assert len(openai_provider.models) > 0
