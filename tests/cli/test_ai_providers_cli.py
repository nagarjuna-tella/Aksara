"""
Tests for Aksara CLI AI Providers Commands

v0.5.11: Tests for `aksara ai providers`, `aksara ai models`, `aksara ai secrets`.
"""

import pytest
import json
from click.testing import CliRunner
from unittest.mock import patch, MagicMock


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def runner():
    """Create CLI runner."""
    return CliRunner()


def create_mock_settings(**overrides):
    """Create mock settings for testing."""
    defaults = {
        "ai_profiles_enabled": True,
        "ai_providers": None,
        "ai_default_provider": None,
        "ai_secret_hints": None,
    }
    defaults.update(overrides)
    
    mock_settings = MagicMock()
    for key, value in defaults.items():
        setattr(mock_settings, key, value)
    
    return mock_settings


# =============================================================================
# aksara ai providers Tests
# =============================================================================

class TestAiProvidersCommand:
    """Tests for `aksara ai providers` command."""
    
    def test_providers_command_exists(self, runner):
        """Test that providers command exists."""
        from aksara.cli.main import cli
        
        result = runner.invoke(cli, ["ai", "providers", "--help"])
        assert result.exit_code == 0
        assert "providers" in result.output.lower() or "provider" in result.output.lower()
    
    def test_providers_table_format(self, runner):
        """Test providers command with table format."""
        from aksara.cli.main import cli
        
        mock_settings = create_mock_settings()
        
        with patch("aksara.conf.settings", mock_settings):
            result = runner.invoke(cli, ["ai", "providers", "--format", "table"])
        
        assert result.exit_code == 0
        # Should show table header or provider info
        assert "provider" in result.output.lower() or "name" in result.output.lower()
    
    def test_providers_json_format(self, runner):
        """Test providers command with JSON format."""
        from aksara.cli.main import cli
        
        mock_settings = create_mock_settings()
        
        with patch("aksara.conf.settings", mock_settings):
            result = runner.invoke(cli, ["ai", "providers", "--format", "json"])
        
        assert result.exit_code == 0
        # Find the JSON part (skip header line)
        output = result.output.strip()
        json_start = output.find('{')
        if json_start >= 0:
            json_str = output[json_start:]
            try:
                data = json.loads(json_str)
                assert "providers" in data
            except json.JSONDecodeError:
                pytest.fail(f"Output contains invalid JSON: {output}")
    
    def test_providers_when_disabled(self, runner):
        """Test providers command when AI profiles are disabled."""
        from aksara.cli.main import cli
        
        mock_settings = create_mock_settings(ai_profiles_enabled=False)
        
        with patch("aksara.conf.settings", mock_settings):
            result = runner.invoke(cli, ["ai", "providers"])
        
        # Should still work but show disabled status or empty list
        assert result.exit_code == 0


# =============================================================================
# aksara ai models Tests
# =============================================================================

class TestAiModelsCommand:
    """Tests for `aksara ai models` command."""
    
    def test_models_command_exists(self, runner):
        """Test that models command exists."""
        from aksara.cli.main import cli
        
        result = runner.invoke(cli, ["ai", "models", "--help"])
        assert result.exit_code == 0
        assert "model" in result.output.lower()
    
    def test_models_all_providers(self, runner):
        """Test models command without provider filter."""
        from aksara.cli.main import cli
        
        mock_settings = create_mock_settings()
        
        with patch("aksara.conf.settings", mock_settings):
            result = runner.invoke(cli, ["ai", "models", "--format", "table"])
        
        assert result.exit_code == 0
    
    def test_models_json_format(self, runner):
        """Test models command with JSON format."""
        from aksara.cli.main import cli
        
        mock_settings = create_mock_settings()
        
        with patch("aksara.conf.settings", mock_settings):
            result = runner.invoke(cli, ["ai", "models", "--format", "json"])
        
        assert result.exit_code == 0
        # Find the JSON part (skip header line)
        output = result.output.strip()
        json_start = output.find('{')
        if json_start >= 0:
            json_str = output[json_start:]
            try:
                data = json.loads(json_str)
                assert "models" in data
            except json.JSONDecodeError:
                pytest.fail(f"Output contains invalid JSON: {output}")
    
    def test_models_filter_by_provider(self, runner):
        """Test models command with provider filter."""
        from aksara.cli.main import cli
        
        mock_settings = create_mock_settings()
        
        with patch("aksara.conf.settings", mock_settings):
            result = runner.invoke(cli, ["ai", "models", "--provider", "example_openai_like"])
        
        # Command should succeed regardless of whether provider exists
        assert result.exit_code == 0
    
    def test_models_unknown_provider(self, runner):
        """Test models command with non-existent provider."""
        from aksara.cli.main import cli
        
        mock_settings = create_mock_settings()
        
        with patch("aksara.conf.settings", mock_settings):
            result = runner.invoke(cli, ["ai", "models", "--provider", "nonexistent_provider_xyz"])
        
        # Should not crash
        assert result.exit_code == 0


# =============================================================================
# aksara ai secrets Tests
# =============================================================================

class TestAiSecretsCommand:
    """Tests for `aksara ai secrets` command."""
    
    def test_secrets_command_exists(self, runner):
        """Test that secrets command exists."""
        from aksara.cli.main import cli
        
        result = runner.invoke(cli, ["ai", "secrets", "--help"])
        assert result.exit_code == 0
        assert "secret" in result.output.lower()
    
    def test_secrets_table_format(self, runner):
        """Test secrets command with table format."""
        from aksara.cli.main import cli
        
        mock_settings = create_mock_settings()
        
        with patch("aksara.conf.settings", mock_settings):
            result = runner.invoke(cli, ["ai", "secrets", "--format", "table"])
        
        assert result.exit_code == 0
    
    def test_secrets_json_format(self, runner):
        """Test secrets command with JSON format."""
        from aksara.cli.main import cli
        
        mock_settings = create_mock_settings()
        
        with patch("aksara.conf.settings", mock_settings):
            result = runner.invoke(cli, ["ai", "secrets", "--format", "json"])
        
        assert result.exit_code == 0
        # Find the JSON part (skip header line)
        output = result.output.strip()
        json_start = output.find('{')
        if json_start >= 0:
            json_str = output[json_start:]
            try:
                data = json.loads(json_str)
                assert "secrets" in data
            except json.JSONDecodeError:
                pytest.fail(f"Output contains invalid JSON: {output}")
    
    def test_secrets_never_expose_values(self, runner):
        """Test that secrets command never exposes actual values."""
        from aksara.cli.main import cli
        
        mock_settings = create_mock_settings()
        
        with patch("aksara.conf.settings", mock_settings):
            result = runner.invoke(cli, ["ai", "secrets", "--format", "json"])
        
        if result.exit_code == 0 and result.output.strip():
            try:
                data = json.loads(result.output)
                for secret in data:
                    # Should not have value field
                    assert "value" not in secret
                    assert "key_value" not in secret
            except json.JSONDecodeError:
                pass  # May not be JSON in all cases
    
    def test_secrets_table_shows_env_vars(self, runner):
        """Test that secrets table shows environment variable names."""
        from aksara.cli.main import cli
        
        mock_settings = create_mock_settings()
        
        with patch("aksara.conf.settings", mock_settings):
            result = runner.invoke(cli, ["ai", "secrets"])
        
        assert result.exit_code == 0


# =============================================================================
# aksara ai group Tests
# =============================================================================

class TestAiCommandGroup:
    """Tests for the `aksara ai` command group itself."""
    
    def test_ai_command_exists(self, runner):
        """Test that ai command group exists."""
        from aksara.cli.main import cli
        
        result = runner.invoke(cli, ["ai", "--help"])
        assert result.exit_code == 0
        assert "ai" in result.output.lower()
    
    def test_ai_subcommands_listed(self, runner):
        """Test that all subcommands are listed in help."""
        from aksara.cli.main import cli
        
        result = runner.invoke(cli, ["ai", "--help"])
        
        assert result.exit_code == 0
        output_lower = result.output.lower()
        
        # All subcommands should be mentioned
        assert "providers" in output_lower
        assert "models" in output_lower
        assert "secrets" in output_lower
