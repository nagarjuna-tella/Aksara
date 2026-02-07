"""
Tests for Aksara CLI AI Hints Command

v0.5.13: Tests for `aksara ai hints` command.
"""

import pytest
import json
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from aksara.ai.models import AiRouteHint, AiHintSet


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
        "debug": True,
        "app_module": None,
    }
    defaults.update(overrides)
    
    mock_settings = MagicMock()
    for key, value in defaults.items():
        setattr(mock_settings, key, value)
    
    return mock_settings


def create_sample_hint_set() -> AiHintSet:
    """Create sample hint set for testing."""
    routes = [
        AiRouteHint(
            title="List Users",
            description="Returns a paginated list of users.",
            view_name="UserViewSet",
            route_name="list",
            path="/api/users",
            methods=["GET"],
            risk_level="low",
            usage_kind="read_only",
            example_prompt="Show me all users",
        ),
        AiRouteHint(
            title="Create User",
            description="Creates a new user account.",
            view_name="UserViewSet",
            route_name="create",
            path="/api/users",
            methods=["POST"],
            risk_level="medium",
            usage_kind="write",
        ),
        AiRouteHint(
            title="Delete User",
            description="Permanently removes a user account.",
            view_name="UserViewSet",
            route_name="destroy",
            path="/api/users/{id}",
            methods=["DELETE"],
            risk_level="high",
            usage_kind="admin",
        ),
    ]
    return AiHintSet(routes=routes, total_count=3, low_risk_count=1, medium_risk_count=1, high_risk_count=1)


# =============================================================================
# aksara ai hints Tests
# =============================================================================

class TestAiHintsCommand:
    """Tests for `aksara ai hints` command."""
    
    def test_hints_command_exists(self, runner):
        """Test that hints command exists."""
        from aksara.cli.main import cli
        
        result = runner.invoke(cli, ["ai", "hints", "--help"])
        assert result.exit_code == 0
        assert "hints" in result.output.lower() or "route" in result.output.lower()
    
    def test_hints_text_format(self, runner):
        """Test hints command with text format (default)."""
        from aksara.cli.main import cli
        
        mock_settings = create_mock_settings()
        sample_hints = create_sample_hint_set()
        
        with patch("aksara.conf.settings", mock_settings):
            with patch("aksara.ai.hints.build_ai_hint_set", return_value=sample_hints):
                with patch("aksara.cli.main.discover_models"):
                    result = runner.invoke(cli, ["ai", "hints"])
        
        assert result.exit_code == 0
        # Check output contains hint info
        assert "Total" in result.output or "hints" in result.output.lower()
    
    def test_hints_json_format(self, runner):
        """Test hints command with JSON format."""
        from aksara.cli.main import cli
        
        mock_settings = create_mock_settings()
        sample_hints = create_sample_hint_set()
        
        with patch("aksara.conf.settings", mock_settings):
            with patch("aksara.ai.hints.build_ai_hint_set", return_value=sample_hints):
                with patch("aksara.cli.main.discover_models"):
                    result = runner.invoke(cli, ["ai", "hints", "--format", "json"])
        
        assert result.exit_code == 0
        # Find JSON in output
        output = result.output.strip()
        json_start = output.find('{')
        if json_start >= 0:
            json_str = output[json_start:]
            try:
                data = json.loads(json_str)
                assert "hints" in data
                assert "total_count" in data
                assert "hints_by_risk" in data
            except json.JSONDecodeError:
                pytest.fail(f"Output contains invalid JSON: {output}")
    
    def test_hints_filter_by_view(self, runner):
        """Test hints command with --view filter."""
        from aksara.cli.main import cli
        
        mock_settings = create_mock_settings()
        sample_hints = create_sample_hint_set()
        
        with patch("aksara.conf.settings", mock_settings):
            with patch("aksara.ai.hints.build_ai_hint_set", return_value=sample_hints):
                with patch("aksara.cli.main.discover_models"):
                    result = runner.invoke(cli, ["ai", "hints", "--view", "UserViewSet"])
        
        assert result.exit_code == 0
    
    def test_hints_filter_by_route(self, runner):
        """Test hints command with --route filter."""
        from aksara.cli.main import cli
        
        mock_settings = create_mock_settings()
        sample_hints = create_sample_hint_set()
        
        with patch("aksara.conf.settings", mock_settings):
            with patch("aksara.ai.hints.build_ai_hint_set", return_value=sample_hints):
                with patch("aksara.cli.main.discover_models"):
                    result = runner.invoke(cli, ["ai", "hints", "--route", "list"])
        
        assert result.exit_code == 0
    
    def test_hints_filter_by_risk(self, runner):
        """Test hints command with --risk filter."""
        from aksara.cli.main import cli
        
        mock_settings = create_mock_settings()
        sample_hints = create_sample_hint_set()
        
        with patch("aksara.conf.settings", mock_settings):
            with patch("aksara.ai.hints.build_ai_hint_set", return_value=sample_hints):
                with patch("aksara.cli.main.discover_models"):
                    result = runner.invoke(cli, ["ai", "hints", "--risk", "high"])
        
        assert result.exit_code == 0
        # With high filter, should show only high-risk hints
        assert "Delete" in result.output or "high" in result.output.lower()
    
    def test_hints_empty_result(self, runner):
        """Test hints command with no hints found."""
        from aksara.cli.main import cli
        
        mock_settings = create_mock_settings()
        empty_hints = AiHintSet(routes=[])
        
        with patch("aksara.conf.settings", mock_settings):
            with patch("aksara.ai.hints.build_ai_hint_set", return_value=empty_hints):
                with patch("aksara.cli.main.discover_models"):
                    result = runner.invoke(cli, ["ai", "hints"])
        
        assert result.exit_code == 0
        # Should indicate no hints
        assert "0 hints" in result.output or "No hints" in result.output
    
    def test_hints_risk_badges_in_output(self, runner):
        """Test that risk levels are shown in output."""
        from aksara.cli.main import cli
        
        mock_settings = create_mock_settings()
        sample_hints = create_sample_hint_set()
        
        with patch("aksara.conf.settings", mock_settings):
            with patch("aksara.ai.hints.build_ai_hint_set", return_value=sample_hints):
                with patch("aksara.cli.main.discover_models"):
                    result = runner.invoke(cli, ["ai", "hints"])
        
        assert result.exit_code == 0
        # Should show risk breakdown
        assert "high" in result.output.lower()
        assert "medium" in result.output.lower()
        assert "low" in result.output.lower()


class TestAiHintsCommandOptions:
    """Tests for hints command options."""
    
    def test_format_option_choices(self, runner):
        """Test that --format option accepts valid choices."""
        from aksara.cli.main import cli
        
        result = runner.invoke(cli, ["ai", "hints", "--format", "invalid"])
        # Should fail with invalid choice
        assert result.exit_code != 0
    
    def test_risk_option_choices(self, runner):
        """Test that --risk option accepts valid choices."""
        from aksara.cli.main import cli
        
        result = runner.invoke(cli, ["ai", "hints", "--risk", "invalid"])
        # Should fail with invalid choice
        assert result.exit_code != 0
    
    def test_combined_filters(self, runner):
        """Test hints command with multiple filters combined."""
        from aksara.cli.main import cli
        
        mock_settings = create_mock_settings()
        sample_hints = create_sample_hint_set()
        
        with patch("aksara.conf.settings", mock_settings):
            with patch("aksara.ai.hints.build_ai_hint_set", return_value=sample_hints):
                with patch("aksara.cli.main.discover_models"):
                    result = runner.invoke(cli, [
                        "ai", "hints",
                        "--view", "User",
                        "--route", "destroy",
                        "--risk", "high",
                    ])
        
        assert result.exit_code == 0
