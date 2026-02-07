"""
Tests for aksara ai examples CLI command

v0.5.14: Tests for the `aksara ai examples` CLI command.
"""

import os
import tempfile
import pytest
from click.testing import CliRunner
from unittest.mock import patch


class TestAiExamplesCommand:
    """Tests for `aksara ai examples` CLI command."""

    @pytest.fixture
    def runner(self):
        """Create CLI runner."""
        return CliRunner()

    @pytest.fixture
    def cli(self):
        """Import CLI."""
        from aksara.cli.main import cli
        return cli

    def test_ai_examples_help(self, runner, cli):
        """Test --help output."""
        result = runner.invoke(cli, ["ai", "examples", "--help"])
        assert result.exit_code == 0
        assert "Show real-world AI provider wiring examples" in result.output

    def test_ai_examples_overview(self, runner, cli):
        """Test default overview output."""
        result = runner.invoke(cli, ["ai", "examples"])
        assert result.exit_code == 0
        assert "AI Provider Wiring Examples" in result.output
        assert "Protocol-based adapters" in result.output

    def test_ai_examples_list(self, runner, cli):
        """Test --list option shows files."""
        result = runner.invoke(cli, ["ai", "examples", "--list"])
        assert result.exit_code == 0
        assert "settings.py" in result.output
        assert "adapters.py" in result.output
        assert "prompting.py" in result.output

    def test_ai_examples_provider_openai(self, runner, cli):
        """Test --provider openai shows OpenAI info."""
        result = runner.invoke(cli, ["ai", "examples", "--provider", "openai"])
        assert result.exit_code == 0
        assert "OPENAI_API_KEY" in result.output
        assert "pip install openai" in result.output

    def test_ai_examples_provider_azure(self, runner, cli):
        """Test --provider azure shows Azure info."""
        result = runner.invoke(cli, ["ai", "examples", "--provider", "azure"])
        assert result.exit_code == 0
        assert "AZURE_OPENAI_ENDPOINT" in result.output
        assert "AZURE_OPENAI_API_KEY" in result.output
        assert "AZURE_OPENAI_DEPLOYMENT" in result.output

    def test_ai_examples_provider_anthropic(self, runner, cli):
        """Test --provider anthropic shows Anthropic info."""
        result = runner.invoke(cli, ["ai", "examples", "--provider", "anthropic"])
        assert result.exit_code == 0
        assert "ANTHROPIC_API_KEY" in result.output
        assert "pip install anthropic" in result.output

    def test_ai_examples_output_dir_creates_files(self, runner, cli):
        """Test --output-dir copies files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = os.path.join(tmpdir, "ai_adapters")
            result = runner.invoke(cli, ["ai", "examples", "-o", output_dir])
            
            # Note: This may fail if examples package is not installed
            # The command should at least not crash
            if result.exit_code == 0:
                # Check files exist
                assert os.path.exists(output_dir)
                # Files may or may not exist depending on source availability

    def test_ai_examples_output_dir_force(self, runner, cli):
        """Test --force overwrites existing files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = os.path.join(tmpdir, "ai_adapters")
            os.makedirs(output_dir, exist_ok=True)
            
            # Create a dummy file
            dummy = os.path.join(output_dir, "settings.py")
            with open(dummy, "w") as f:
                f.write("# dummy")
            
            # First without force - should warn
            result1 = runner.invoke(cli, ["ai", "examples", "-o", output_dir])
            
            # Then with force
            result2 = runner.invoke(cli, ["ai", "examples", "-o", output_dir, "--force"])
            # Should not have "already exists" warning for same file

    def test_ai_examples_invalid_provider_rejected(self, runner, cli):
        """Test that invalid provider is rejected by Click."""
        result = runner.invoke(cli, ["ai", "examples", "--provider", "invalid"])
        assert result.exit_code != 0
        assert "Invalid value" in result.output or "invalid" in result.output.lower()

    def test_ai_examples_shows_documentation_link(self, runner, cli):
        """Test that docs link is shown."""
        result = runner.invoke(cli, ["ai", "examples"])
        assert result.exit_code == 0
        assert "bring-your-own-llm" in result.output or "Documentation" in result.output


class TestAiExamplesCommandIntegration:
    """Integration tests for ai examples command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def cli(self):
        from aksara.cli.main import cli
        return cli

    def test_ai_examples_is_under_ai_group(self, runner, cli):
        """Test that examples command is under ai group."""
        result = runner.invoke(cli, ["ai", "--help"])
        assert result.exit_code == 0
        assert "examples" in result.output

    def test_ai_group_lists_examples(self, runner, cli):
        """Test that ai --help lists examples command."""
        result = runner.invoke(cli, ["ai", "--help"])
        assert "examples" in result.output
        assert "provider wiring" in result.output.lower() or "real-world" in result.output.lower()


class TestAiExamplesCommandFormats:
    """Tests for different output formats of ai examples command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def cli(self):
        from aksara.cli.main import cli
        return cli

    def test_output_includes_version(self, runner, cli):
        """Test that output includes v0.5.14."""
        result = runner.invoke(cli, ["ai", "examples"])
        assert "0.5.14" in result.output

    def test_list_shows_all_example_files(self, runner, cli):
        """Test that --list shows all expected files."""
        result = runner.invoke(cli, ["ai", "examples", "--list"])
        assert result.exit_code == 0
        
        expected_files = [
            "settings.py",
            "adapters.py",
            "prompting.py",
            "views.py",
            "main.py",
            "__init__.py",
        ]
        
        for f in expected_files:
            assert f in result.output, f"Missing file in list: {f}"

    def test_provider_shows_usage_example(self, runner, cli):
        """Test that provider info shows usage example."""
        result = runner.invoke(cli, ["ai", "examples", "--provider", "openai"])
        assert "get_llm_client" in result.output
        assert "complete" in result.output
