"""
Tests for Aksara Studio AI Profiles Endpoints

v0.5.11: Tests for /studio/ai/profiles and /studio/ai/secrets endpoints.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from aksara.studio.fastapi import router


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def test_client():
    """Create test client with Studio router."""
    app = FastAPI()
    app.include_router(router)
    app.ai_provider_registry = None
    return TestClient(app)


def create_mock_settings(**overrides):
    """Create mock settings for testing."""
    defaults = {
        "ai_profiles_enabled": True,
        "ai_providers": None,
        "ai_default_provider": None,
        "ai_secret_hints": None,
        "debug": True,
        "studio_allowed_origins": ["*"],
    }
    defaults.update(overrides)
    
    mock_settings = MagicMock()
    for key, value in defaults.items():
        setattr(mock_settings, key, value)
    
    return mock_settings


# =============================================================================
# /studio/ai/profiles Tests
# =============================================================================

class TestStudioAiProfilesEndpoint:
    """Tests for GET /studio/ai/profiles endpoint."""
    
    def test_profiles_endpoint_returns_200(self, test_client):
        """Test that profiles endpoint returns 200."""
        mock_settings = create_mock_settings()
        
        with patch("aksara.conf.settings", mock_settings):
            response = test_client.get("/studio/ai/profiles")
        
        assert response.status_code == 200
    
    def test_profiles_response_structure(self, test_client):
        """Test that profiles response has correct structure."""
        mock_settings = create_mock_settings()
        
        with patch("aksara.conf.settings", mock_settings):
            response = test_client.get("/studio/ai/profiles")
        
        data = response.json()
        
        assert "enabled" in data
        assert "providers" in data
        assert "default_provider" in data
        assert "total_models" in data
        assert "environment" in data
    
    def test_profiles_when_enabled_has_providers(self, test_client):
        """Test profiles when AI profiles are enabled returns example providers."""
        mock_settings = create_mock_settings(ai_profiles_enabled=True)
        
        with patch("aksara.conf.settings", mock_settings):
            response = test_client.get("/studio/ai/profiles")
        
        data = response.json()
        assert data["enabled"] is True
        # Should have example providers when no explicit config
        assert len(data["providers"]) > 0
    
    def test_profiles_when_disabled_is_empty(self, test_client):
        """Test profiles when AI profiles are disabled returns empty."""
        mock_settings = create_mock_settings(ai_profiles_enabled=False)
        
        with patch("aksara.conf.settings", mock_settings):
            response = test_client.get("/studio/ai/profiles")
        
        data = response.json()
        assert data["enabled"] is False
        assert data["providers"] == []
        assert data["total_models"] == 0
    
    def test_provider_summary_has_required_fields(self, test_client):
        """Test that provider summaries have correct structure."""
        mock_settings = create_mock_settings()
        
        with patch("aksara.conf.settings", mock_settings):
            response = test_client.get("/studio/ai/profiles")
        
        data = response.json()
        
        if data["providers"]:
            provider = data["providers"][0]
            assert "name" in provider
            assert "display_name" in provider
            assert "kind" in provider
            assert "model_count" in provider
            assert "models" in provider
    
    def test_model_summary_has_required_fields(self, test_client):
        """Test that model summaries have correct structure."""
        mock_settings = create_mock_settings()
        
        with patch("aksara.conf.settings", mock_settings):
            response = test_client.get("/studio/ai/profiles")
        
        data = response.json()
        
        # Find a provider with models
        for provider in data["providers"]:
            if provider["models"]:
                model = provider["models"][0]
                assert "name" in model
                assert "display_name" in model
                assert "kind" in model
                assert "supports_tools" in model
                assert "supports_streaming" in model
                break


# =============================================================================
# /studio/ai/secrets Tests
# =============================================================================

class TestStudioAiSecretsEndpoint:
    """Tests for GET /studio/ai/secrets endpoint."""
    
    def test_secrets_endpoint_returns_200(self, test_client):
        """Test that secrets endpoint returns 200."""
        mock_settings = create_mock_settings()
        
        with patch("aksara.conf.settings", mock_settings):
            response = test_client.get("/studio/ai/secrets")
        
        assert response.status_code == 200
    
    def test_secrets_response_structure(self, test_client):
        """Test that secrets response has correct structure."""
        mock_settings = create_mock_settings()
        
        with patch("aksara.conf.settings", mock_settings):
            response = test_client.get("/studio/ai/secrets")
        
        data = response.json()
        
        assert "secrets" in data
        assert "configured_count" in data
        assert "total_count" in data
    
    def test_secrets_never_contain_actual_values(self, test_client):
        """Test that secrets response never contains actual API key values."""
        mock_settings = create_mock_settings()
        
        with patch("aksara.conf.settings", mock_settings):
            response = test_client.get("/studio/ai/secrets")
        
        data = response.json()
        
        # Check that no secret contains an actual value field
        for secret in data["secrets"]:
            # Should only have these safe fields
            allowed_fields = {
                "provider_name",
                "env_var",
                "required",
                "description",
                "is_configured",
            }
            assert set(secret.keys()).issubset(allowed_fields)
            
            # Should never have a value field
            assert "value" not in secret
            assert "api_key" not in secret
    
    def test_secrets_count_matches_list_length(self, test_client):
        """Test that total_count matches secrets list length."""
        mock_settings = create_mock_settings()
        
        with patch("aksara.conf.settings", mock_settings):
            response = test_client.get("/studio/ai/secrets")
        
        data = response.json()
        
        # Count should match
        assert data["total_count"] == len(data["secrets"])
        
        # Configured count should be <= total
        assert data["configured_count"] <= data["total_count"]


# =============================================================================
# Unit Tests for Studio Utils
# =============================================================================

class TestBuildAiProfileSetSummary:
    """Unit tests for build_ai_profile_set_summary utility."""
    
    def test_returns_disabled_when_profiles_disabled(self):
        """Test that disabled settings returns disabled summary."""
        from aksara.studio.utils import build_ai_profile_set_summary
        
        mock_settings = create_mock_settings(ai_profiles_enabled=False)
        mock_app = MagicMock()
        mock_app.ai_provider_registry = None
        
        with patch("aksara.conf.settings", mock_settings):
            result = build_ai_profile_set_summary(mock_app)
        
        assert result.enabled is False
        assert result.providers == []
        assert result.total_models == 0
    
    def test_returns_example_providers_when_enabled(self):
        """Test that enabled with no config returns example providers."""
        from aksara.studio.utils import build_ai_profile_set_summary
        
        mock_settings = create_mock_settings(ai_profiles_enabled=True)
        mock_app = MagicMock()
        mock_app.ai_provider_registry = None
        
        with patch("aksara.conf.settings", mock_settings):
            result = build_ai_profile_set_summary(mock_app)
        
        assert result.enabled is True
        assert len(result.providers) > 0


class TestBuildAiSecretsInfo:
    """Unit tests for build_ai_secrets_info utility."""
    
    def test_returns_default_hints(self):
        """Test that default hints are returned."""
        from aksara.studio.utils import build_ai_secrets_info
        
        mock_settings = create_mock_settings()
        
        with patch("aksara.conf.settings", mock_settings):
            result = build_ai_secrets_info()
        
        assert result.secrets is not None
        assert len(result.secrets) >= 0
        assert result.total_count == len(result.secrets)
    
    def test_never_exposes_secret_values(self):
        """Test that actual secret values are never exposed."""
        from aksara.studio.utils import build_ai_secrets_info
        
        mock_settings = create_mock_settings()
        
        with patch("aksara.conf.settings", mock_settings):
            result = build_ai_secrets_info()
        
        for secret in result.secrets:
            # Check the Pydantic model doesn't have a value field
            assert not hasattr(secret, 'value')
            assert not hasattr(secret, 'api_key')
