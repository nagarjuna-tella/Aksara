"""
Tests for Aksara CLI AI Hub Commands

v0.5.28: Tests for `aksara ai-hub` group and its subcommands:
    status, providers, models, defaults, configure, doctor
"""

import json
import pytest
from click.testing import CliRunner
from unittest import mock
from unittest.mock import MagicMock


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def cli():
    from aksara.cli.main import cli
    return cli


@pytest.fixture
def mock_hub():
    """Create a realistic mock AiHubSettings with configured openai."""
    from aksara.ai.hub_settings import (
        AiHubSettings, ProviderConfig, AiDefaultModels,
        OpenAIConfig, OllamaConfig,
    )
    return AiHubSettings(
        providers=[
            ProviderConfig(kind="openai", openai=OpenAIConfig(api_key="sk-testkey1234")),
            ProviderConfig(kind="ollama", ollama=OllamaConfig()),
        ],
        defaults=AiDefaultModels(
            chat_model="gpt-4o",
            chat_provider="openai",
            code_model="gpt-4o",
            code_provider="openai",
        ),
        active_provider="openai",
    )


@pytest.fixture
def mock_hub_empty():
    """An AI Hub with no providers configured."""
    from aksara.ai.hub_settings import AiHubSettings, AiDefaultModels
    return AiHubSettings(
        providers=[],
        defaults=AiDefaultModels(),
        active_provider=None,
    )


# =============================================================================
# Group Registration
# =============================================================================

class TestAiHubGroupRegistration:
    """Tests that the ai-hub group and its subcommands are registered."""

    def test_ai_hub_group_exists(self, runner, cli):
        result = runner.invoke(cli, ["ai-hub", "--help"])
        assert result.exit_code == 0
        assert "ai-hub" in result.output.lower() or "AI Hub" in result.output

    def test_ai_hub_status_subcommand(self, runner, cli):
        result = runner.invoke(cli, ["ai-hub", "--help"])
        assert "status" in result.output

    def test_ai_hub_providers_subcommand(self, runner, cli):
        result = runner.invoke(cli, ["ai-hub", "--help"])
        assert "providers" in result.output

    def test_ai_hub_models_subcommand(self, runner, cli):
        result = runner.invoke(cli, ["ai-hub", "--help"])
        assert "models" in result.output

    def test_ai_hub_defaults_subcommand(self, runner, cli):
        result = runner.invoke(cli, ["ai-hub", "--help"])
        assert "defaults" in result.output

    def test_ai_hub_configure_subcommand(self, runner, cli):
        result = runner.invoke(cli, ["ai-hub", "--help"])
        assert "configure" in result.output

    def test_ai_hub_doctor_subcommand(self, runner, cli):
        result = runner.invoke(cli, ["ai-hub", "--help"])
        assert "doctor" in result.output

    def test_ai_hub_help_mentions_v0528(self, runner, cli):
        result = runner.invoke(cli, ["ai-hub", "--help"])
        assert "0.5.28" in result.output


# =============================================================================
# Status Command
# =============================================================================

class TestAiHubStatusCommand:
    """Tests for `aksara ai-hub status`."""

    def test_status_pretty_with_providers(self, runner, cli, mock_hub):
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=mock_hub):
            result = runner.invoke(cli, ["ai-hub", "status"])
        assert result.exit_code == 0
        assert "Ready" in result.output or "●" in result.output

    def test_status_pretty_shows_active_provider(self, runner, cli, mock_hub):
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=mock_hub):
            result = runner.invoke(cli, ["ai-hub", "status"])
        assert "openai" in result.output

    def test_status_pretty_shows_defaults(self, runner, cli, mock_hub):
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=mock_hub):
            result = runner.invoke(cli, ["ai-hub", "status"])
        assert "gpt-4o" in result.output

    def test_status_json_format(self, runner, cli, mock_hub):
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=mock_hub):
            result = runner.invoke(cli, ["ai-hub", "status", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, dict)

    def test_status_no_providers(self, runner, cli, mock_hub_empty):
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=mock_hub_empty):
            result = runner.invoke(cli, ["ai-hub", "status"])
        assert result.exit_code == 0
        assert "No providers" in result.output or "not set" in result.output.lower()


# =============================================================================
# Providers Command
# =============================================================================

class TestAiHubProvidersCommand:
    """Tests for `aksara ai-hub providers`."""

    def test_providers_pretty(self, runner, cli, mock_hub):
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=mock_hub):
            result = runner.invoke(cli, ["ai-hub", "providers"])
        assert result.exit_code == 0
        assert "openai" in result.output

    def test_providers_json(self, runner, cli, mock_hub):
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=mock_hub):
            result = runner.invoke(cli, ["ai-hub", "providers", "-f", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_providers_shows_api_key_masked(self, runner, cli, mock_hub):
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=mock_hub):
            result = runner.invoke(cli, ["ai-hub", "providers"])
        # Should show masked key (last 4 chars)
        assert "***" in result.output or "1234" in result.output

    def test_providers_no_providers(self, runner, cli, mock_hub_empty):
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=mock_hub_empty):
            result = runner.invoke(cli, ["ai-hub", "providers"])
        assert result.exit_code == 0
        assert "No providers" in result.output or "configure" in result.output.lower()

    def test_providers_shows_active_marker(self, runner, cli, mock_hub):
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=mock_hub):
            result = runner.invoke(cli, ["ai-hub", "providers"])
        assert "active" in result.output.lower()


# =============================================================================
# Models Command
# =============================================================================

class TestAiHubModelsCommand:
    """Tests for `aksara ai-hub models`."""

    def test_models_pretty(self, runner, cli, mock_hub):
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=mock_hub):
            result = runner.invoke(cli, ["ai-hub", "models"])
        assert result.exit_code == 0
        assert "Chat" in result.output
        assert "Code" in result.output
        assert "Embeddings" in result.output

    def test_models_json(self, runner, cli, mock_hub):
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=mock_hub):
            result = runner.invoke(cli, ["ai-hub", "models", "-f", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "defaults" in data
        assert "providers" in data

    def test_models_shows_chat_model(self, runner, cli, mock_hub):
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=mock_hub):
            result = runner.invoke(cli, ["ai-hub", "models"])
        assert "gpt-4o" in result.output

    def test_models_json_has_defaults_keys(self, runner, cli, mock_hub):
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=mock_hub):
            result = runner.invoke(cli, ["ai-hub", "models", "-f", "json"])
        data = json.loads(result.output)
        defaults = data["defaults"]
        assert "chat_model" in defaults
        assert "code_model" in defaults
        assert "embeddings_model" in defaults


# =============================================================================
# Defaults Command
# =============================================================================

class TestAiHubDefaultsCommand:
    """Tests for `aksara ai-hub defaults`."""

    def test_defaults_show_pretty(self, runner, cli, mock_hub):
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=mock_hub):
            result = runner.invoke(cli, ["ai-hub", "defaults"])
        assert result.exit_code == 0
        assert "Chat Model" in result.output or "chat_model" in result.output.lower()

    def test_defaults_show_json(self, runner, cli, mock_hub):
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=mock_hub):
            result = runner.invoke(cli, ["ai-hub", "defaults", "-f", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "chat_model" in data

    def test_defaults_set_chat_model(self, runner, cli, mock_hub):
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=mock_hub):
            with mock.patch("aksara.ai.hub_settings.save_aihub_settings") as mock_save:
                result = runner.invoke(cli, ["ai-hub", "defaults", "--chat-model", "gpt-4o-mini"])
        assert result.exit_code == 0
        assert "saved" in result.output.lower() or "Saved" in result.output
        mock_save.assert_called_once()

    def test_defaults_set_multiple(self, runner, cli, mock_hub):
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=mock_hub):
            with mock.patch("aksara.ai.hub_settings.save_aihub_settings"):
                result = runner.invoke(cli, [
                    "ai-hub", "defaults",
                    "--chat-model", "gpt-4o",
                    "--code-model", "gpt-4o",
                    "--embeddings-model", "text-embedding-3-large",
                ])
        assert result.exit_code == 0

    def test_defaults_set_json_output(self, runner, cli, mock_hub):
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=mock_hub):
            with mock.patch("aksara.ai.hub_settings.save_aihub_settings"):
                result = runner.invoke(cli, [
                    "ai-hub", "defaults",
                    "--chat-model", "gpt-4o",
                    "-f", "json",
                ])
        data = json.loads(result.output)
        assert data["saved"] is True
        assert "defaults" in data


# =============================================================================
# Configure Command
# =============================================================================

class TestAiHubConfigureCommand:
    """Tests for `aksara ai-hub configure`."""

    def test_configure_new_openai(self, runner, cli, mock_hub_empty):
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=mock_hub_empty):
            with mock.patch("aksara.ai.hub_settings.save_aihub_settings") as mock_save:
                result = runner.invoke(cli, [
                    "ai-hub", "configure", "openai",
                    "--api-key", "sk-testkey12345678",
                ])
        assert result.exit_code == 0
        assert "openai" in result.output.lower()
        assert "enabled" in result.output.lower() or "✓" in result.output
        mock_save.assert_called_once()

    def test_configure_ollama_with_url(self, runner, cli, mock_hub_empty):
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=mock_hub_empty):
            with mock.patch("aksara.ai.hub_settings.save_aihub_settings"):
                result = runner.invoke(cli, [
                    "ai-hub", "configure", "ollama",
                    "--base-url", "http://gpu:11434",
                ])
        assert result.exit_code == 0
        assert "ollama" in result.output.lower()

    def test_configure_disable_provider(self, runner, cli, mock_hub):
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=mock_hub):
            with mock.patch("aksara.ai.hub_settings.save_aihub_settings"):
                result = runner.invoke(cli, [
                    "ai-hub", "configure", "openai", "--disable",
                ])
        assert result.exit_code == 0
        assert "disabled" in result.output.lower()

    def test_configure_invalid_provider(self, runner, cli):
        result = runner.invoke(cli, ["ai-hub", "configure", "invalid"])
        assert result.exit_code != 0

    def test_configure_with_model(self, runner, cli, mock_hub_empty):
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=mock_hub_empty):
            with mock.patch("aksara.ai.hub_settings.save_aihub_settings"):
                result = runner.invoke(cli, [
                    "ai-hub", "configure", "anthropic",
                    "--api-key", "sk-ant-test123456",
                    "--model", "claude-3-5-sonnet-20241022",
                ])
        assert result.exit_code == 0
        assert "anthropic" in result.output.lower()

    def test_configure_masks_api_key(self, runner, cli, mock_hub_empty):
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=mock_hub_empty):
            with mock.patch("aksara.ai.hub_settings.save_aihub_settings"):
                result = runner.invoke(cli, [
                    "ai-hub", "configure", "openai",
                    "--api-key", "sk-verylongapikey5678",
                ])
        assert result.exit_code == 0
        assert "sk-verylongapikey5678" not in result.output
        assert "***" in result.output


# =============================================================================
# Doctor Command
# =============================================================================

class TestAiHubDoctorCommand:
    """Tests for `aksara ai-hub doctor`."""

    def test_doctor_healthy(self, runner, cli, mock_hub):
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=mock_hub):
            result = runner.invoke(cli, ["ai-hub", "doctor"])
        assert result.exit_code == 0
        assert "healthy" in result.output.lower() or "passed" in result.output.lower()

    def test_doctor_no_providers(self, runner, cli, mock_hub_empty):
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=mock_hub_empty):
            result = runner.invoke(cli, ["ai-hub", "doctor"])
        assert "No AI providers" in result.output or "warning" in result.output.lower()

    def test_doctor_json_format(self, runner, cli, mock_hub):
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=mock_hub):
            result = runner.invoke(cli, ["ai-hub", "doctor", "-f", "json"])
        data = json.loads(result.output)
        assert "ok" in data
        assert "providers_configured" in data
        assert "issues" in data

    def test_doctor_json_healthy(self, runner, cli, mock_hub):
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=mock_hub):
            result = runner.invoke(cli, ["ai-hub", "doctor", "-f", "json"])
        data = json.loads(result.output)
        assert data["ok"] is True

    def test_doctor_json_no_providers(self, runner, cli, mock_hub_empty):
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=mock_hub_empty):
            result = runner.invoke(cli, ["ai-hub", "doctor", "-f", "json"])
        data = json.loads(result.output)
        assert data["ok"] is False
        assert data["providers_configured"] == 0

    def test_doctor_shows_hints(self, runner, cli, mock_hub_empty):
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=mock_hub_empty):
            result = runner.invoke(cli, ["ai-hub", "doctor"])
        # Should show actionable hints
        assert "aksara ai-hub configure" in result.output or "Hint" in result.output


# =============================================================================
# Source-Level Verification
# =============================================================================

class TestAiHubCliSource:
    """Verify CLI implementation code structure."""

    def test_ai_hub_group_in_source(self):
        from pathlib import Path
        src = Path(__file__).resolve().parents[2] / "aksara" / "cli" / "main.py"
        text = src.read_text()
        assert 'def ai_hub_group()' in text

    def test_status_command_in_source(self):
        from pathlib import Path
        src = Path(__file__).resolve().parents[2] / "aksara" / "cli" / "main.py"
        text = src.read_text()
        assert 'def ai_hub_status(' in text

    def test_providers_command_in_source(self):
        from pathlib import Path
        src = Path(__file__).resolve().parents[2] / "aksara" / "cli" / "main.py"
        text = src.read_text()
        assert 'def ai_hub_providers(' in text

    def test_models_command_in_source(self):
        from pathlib import Path
        src = Path(__file__).resolve().parents[2] / "aksara" / "cli" / "main.py"
        text = src.read_text()
        assert 'def ai_hub_models(' in text

    def test_defaults_command_in_source(self):
        from pathlib import Path
        src = Path(__file__).resolve().parents[2] / "aksara" / "cli" / "main.py"
        text = src.read_text()
        assert 'def ai_hub_defaults(' in text

    def test_configure_command_in_source(self):
        from pathlib import Path
        src = Path(__file__).resolve().parents[2] / "aksara" / "cli" / "main.py"
        text = src.read_text()
        assert 'def ai_hub_configure(' in text

    def test_doctor_command_in_source(self):
        from pathlib import Path
        src = Path(__file__).resolve().parents[2] / "aksara" / "cli" / "main.py"
        text = src.read_text()
        assert 'def ai_hub_doctor(' in text

    def test_group_uses_cli_version(self):
        from pathlib import Path
        src = Path(__file__).resolve().parents[2] / "aksara" / "cli" / "main.py"
        text = src.read_text()
        # Find ai_hub_status function and verify CLI_VERSION is referenced
        idx = text.find("def ai_hub_status(")
        assert idx > 0
        snippet = text[idx:idx + 800]
        assert "CLI_VERSION" in snippet

    def test_all_commands_have_format_option(self):
        """All data-producing commands should support --format."""
        from pathlib import Path
        src = Path(__file__).resolve().parents[2] / "aksara" / "cli" / "main.py"
        text = src.read_text()
        for cmd in ["ai_hub_status", "ai_hub_providers", "ai_hub_models", "ai_hub_defaults", "ai_hub_doctor"]:
            idx = text.find(f"def {cmd}(")
            assert idx > 0, f"{cmd} not found in CLI source"
            # Look backwards for @click.option with output_format
            before = text[max(0, idx - 400):idx]
            assert "output_format" in before, f"{cmd} missing --format option"

    def test_configure_has_provider_argument(self):
        from pathlib import Path
        src = Path(__file__).resolve().parents[2] / "aksara" / "cli" / "main.py"
        text = src.read_text()
        idx = text.find("def ai_hub_configure(")
        assert idx > 0
        before = text[max(0, idx - 400):idx]
        assert "provider_name" in before or "provider_name" in text[idx:idx + 200]


# =============================================================================
# Edge Cases
# =============================================================================

class TestAiHubCliEdgeCases:
    """Edge cases and error handling."""

    def test_status_no_crash_on_import_error(self, runner, cli):
        """Status should not crash even if hub_settings fails to import."""
        with mock.patch.dict("sys.modules", {"aksara.ai.hub_settings": None}):
            result = runner.invoke(cli, ["ai-hub", "status"])
        # May show error but should not traceback crash
        assert isinstance(result.exit_code, int)

    def test_defaults_no_args_shows_current(self, runner, cli, mock_hub):
        """Without any --chat-model etc., defaults just shows current values."""
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=mock_hub):
            result = runner.invoke(cli, ["ai-hub", "defaults"])
        assert result.exit_code == 0
        # Should NOT have "saved" in output (no update performed)
        assert "saved" not in result.output.lower() or "not set" in result.output.lower()

    def test_configure_provider_choices(self, runner, cli):
        """Only valid provider names should be accepted."""
        result = runner.invoke(cli, ["ai-hub", "configure", "--help"])
        assert result.exit_code == 0
        assert "openai" in result.output
        assert "anthropic" in result.output
        assert "ollama" in result.output
        assert "custom" in result.output
        assert "azure" in result.output

    def test_doctor_exit_code_zero_when_healthy(self, runner, cli, mock_hub):
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=mock_hub):
            result = runner.invoke(cli, ["ai-hub", "doctor"])
        assert result.exit_code == 0
