"""
Tests for AI Hub Gap Analysis (v0.5.28)

Tests for the ``check_ai_hub`` gap checker and its integration
with the gap analysis orchestrator.
"""

import pytest
from unittest import mock
from unittest.mock import MagicMock


# =============================================================================
# Category Registration
# =============================================================================

class TestAiHubGapRegistration:
    """Tests that ai_hub is properly registered as a gap category."""

    def test_ai_hub_in_category_literal(self):
        """ai_hub should be a valid GapIssueCategory."""
        from aksara.gapanalysis import GapIssueCategory
        # get_args works on Literal types
        from typing import get_args
        categories = get_args(GapIssueCategory)
        assert "ai_hub" in categories

    def test_ai_hub_in_category_checkers(self):
        from aksara.gapanalysis import _CATEGORY_CHECKERS
        assert "ai_hub" in _CATEGORY_CHECKERS

    def test_check_ai_hub_function_exists(self):
        from aksara.gapanalysis import check_ai_hub
        assert callable(check_ai_hub)

    def test_check_ai_hub_in_all(self):
        from aksara import gapanalysis
        assert "check_ai_hub" in gapanalysis.__all__

    def test_nine_categories_total(self):
        from aksara.gapanalysis import _CATEGORY_CHECKERS
        assert len(_CATEGORY_CHECKERS) == 9

    def test_checker_is_async(self):
        import inspect
        from aksara.gapanalysis import check_ai_hub
        assert inspect.iscoroutinefunction(check_ai_hub)


# =============================================================================
# check_ai_hub — No Providers
# =============================================================================

class TestAiHubGapNoProviders:
    """Tests when no AI providers are configured."""

    @pytest.mark.asyncio
    async def test_no_providers_returns_warning(self):
        from aksara.gapanalysis import check_ai_hub
        from aksara.ai.hub_settings import AiHubSettings, AiDefaultModels

        hub = AiHubSettings(providers=[], defaults=AiDefaultModels())
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=hub):
            issues = await check_ai_hub()
        codes = [i.code for i in issues]
        assert "AI_HUB_NO_PROVIDER" in codes

    @pytest.mark.asyncio
    async def test_no_providers_issue_is_warning_severity(self):
        from aksara.gapanalysis import check_ai_hub
        from aksara.ai.hub_settings import AiHubSettings, AiDefaultModels

        hub = AiHubSettings(providers=[], defaults=AiDefaultModels())
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=hub):
            issues = await check_ai_hub()
        no_prov = [i for i in issues if i.code == "AI_HUB_NO_PROVIDER"]
        assert len(no_prov) == 1
        assert no_prov[0].severity == "warning"

    @pytest.mark.asyncio
    async def test_no_providers_issue_has_fix_command(self):
        from aksara.gapanalysis import check_ai_hub
        from aksara.ai.hub_settings import AiHubSettings, AiDefaultModels

        hub = AiHubSettings(providers=[], defaults=AiDefaultModels())
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=hub):
            issues = await check_ai_hub()
        no_prov = [i for i in issues if i.code == "AI_HUB_NO_PROVIDER"]
        assert len(no_prov[0].fix_commands) >= 1

    @pytest.mark.asyncio
    async def test_no_providers_category_is_ai_hub(self):
        from aksara.gapanalysis import check_ai_hub
        from aksara.ai.hub_settings import AiHubSettings, AiDefaultModels

        hub = AiHubSettings(providers=[], defaults=AiDefaultModels())
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=hub):
            issues = await check_ai_hub()
        for iss in issues:
            assert iss.category == "ai_hub"


# =============================================================================
# check_ai_hub — Active Provider Unconfigured
# =============================================================================

class TestAiHubGapActiveProviderUnconfigured:
    """Tests when active_provider points to an unconfigured provider."""

    @pytest.mark.asyncio
    async def test_active_provider_unconfigured(self):
        from aksara.gapanalysis import check_ai_hub
        from aksara.ai.hub_settings import AiHubSettings, AiDefaultModels, ProviderConfig, OpenAIConfig

        # openai is configured, but active_provider points to anthropic (not configured)
        hub = AiHubSettings(
            providers=[
                ProviderConfig(kind="openai", openai=OpenAIConfig(api_key="sk-test")),
                ProviderConfig(kind="anthropic"),  # no config → not configured
            ],
            defaults=AiDefaultModels(),
            active_provider="anthropic",
        )
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=hub):
            issues = await check_ai_hub()
        codes = [i.code for i in issues]
        assert "AI_HUB_ACTIVE_PROVIDER_UNCONFIGURED" in codes


# =============================================================================
# check_ai_hub — Defaults Missing
# =============================================================================

class TestAiHubGapDefaultsMissing:
    """Tests for missing chat/embeddings defaults after resolve."""

    @pytest.mark.asyncio
    async def test_custom_provider_no_embeddings(self):
        """Custom provider has empty embeddings default → should flag."""
        from aksara.gapanalysis import check_ai_hub
        from aksara.ai.hub_settings import AiHubSettings, AiDefaultModels, ProviderConfig, CustomHttpConfig

        hub = AiHubSettings(
            providers=[ProviderConfig(
                kind="custom",
                custom=CustomHttpConfig(api_key="test-key"),
            )],
            defaults=AiDefaultModels(),
            active_provider="custom",
        )
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=hub):
            issues = await check_ai_hub()
        codes = [i.code for i in issues]
        assert "AI_HUB_DEFAULTS_NO_EMBEDDINGS" in codes

    @pytest.mark.asyncio
    async def test_openai_provider_has_defaults_resolved(self):
        """OpenAI provider should resolve all defaults — no default-missing gaps."""
        from aksara.gapanalysis import check_ai_hub
        from aksara.ai.hub_settings import AiHubSettings, AiDefaultModels, ProviderConfig, OpenAIConfig

        hub = AiHubSettings(
            providers=[ProviderConfig(
                kind="openai",
                openai=OpenAIConfig(api_key="sk-test"),
            )],
            defaults=AiDefaultModels(),
            active_provider="openai",
        )
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=hub):
            issues = await check_ai_hub()
        codes = [i.code for i in issues]
        assert "AI_HUB_DEFAULTS_NO_CHAT" not in codes
        assert "AI_HUB_DEFAULTS_NO_EMBEDDINGS" not in codes

    def test_defaults_no_chat_has_fix_command(self):
        """The missing-chat-model gap should have a fix command."""
        from aksara.gapanalysis import check_ai_hub, GapIssue
        # Manually check via source — look for fix_commands in the checker
        import inspect
        src = inspect.getsource(check_ai_hub)
        assert "AI_HUB_DEFAULTS_NO_CHAT" in src
        assert "fix_commands" in src


# =============================================================================
# check_ai_hub — Graceful Handling
# =============================================================================

class TestAiHubGapGraceful:
    """Tests that the checker handles errors gracefully."""

    @pytest.mark.asyncio
    async def test_import_error_returns_empty(self):
        """If hub_settings can't be imported, return empty list."""
        from aksara.gapanalysis import check_ai_hub
        with mock.patch.dict("sys.modules", {"aksara.ai.hub_settings": None}):
            issues = await check_ai_hub()
        assert issues == []

    @pytest.mark.asyncio
    async def test_unexpected_error_returns_empty(self):
        """If load_aihub_settings throws, return empty list."""
        from aksara.gapanalysis import check_ai_hub
        with mock.patch(
            "aksara.ai.hub_settings.load_aihub_settings",
            side_effect=RuntimeError("boom"),
        ):
            issues = await check_ai_hub()
        assert issues == []

    @pytest.mark.asyncio
    async def test_returns_list(self):
        from aksara.gapanalysis import check_ai_hub
        result = await check_ai_hub()
        assert isinstance(result, list)


# =============================================================================
# check_ai_hub — All Issues Are GapIssue
# =============================================================================

class TestAiHubGapIssueShape:
    """Validate the shape of returned GapIssue objects."""

    @pytest.mark.asyncio
    async def test_all_issues_are_gap_issue(self):
        from aksara.gapanalysis import check_ai_hub, GapIssue
        from aksara.ai.hub_settings import AiHubSettings, AiDefaultModels

        hub = AiHubSettings(providers=[], defaults=AiDefaultModels())
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=hub):
            issues = await check_ai_hub()
        for iss in issues:
            assert isinstance(iss, GapIssue)

    @pytest.mark.asyncio
    async def test_issues_have_required_fields(self):
        from aksara.gapanalysis import check_ai_hub
        from aksara.ai.hub_settings import AiHubSettings, AiDefaultModels

        hub = AiHubSettings(providers=[], defaults=AiDefaultModels())
        with mock.patch("aksara.ai.hub_settings.load_aihub_settings", return_value=hub):
            issues = await check_ai_hub()
        for iss in issues:
            assert iss.category
            assert iss.severity
            assert iss.code
            assert iss.title
            assert iss.message


# =============================================================================
# Orchestrator Integration
# =============================================================================

class TestAiHubGapOrchestrator:
    """Tests that check_ai_hub integrates with run_gap_analysis."""

    @pytest.mark.asyncio
    async def test_run_gap_analysis_includes_ai_hub(self):
        from aksara.gapanalysis import run_gap_analysis
        report = await run_gap_analysis(categories=["ai_hub"])
        assert "ai_hub" in report.categories_checked

    @pytest.mark.asyncio
    async def test_run_gap_analysis_ai_hub_only(self):
        from aksara.gapanalysis import run_gap_analysis
        report = await run_gap_analysis(categories=["ai_hub"])
        assert len(report.categories_checked) == 1

    @pytest.mark.asyncio
    async def test_run_gap_analysis_all_includes_ai_hub(self):
        from aksara.gapanalysis import run_gap_analysis
        report = await run_gap_analysis()
        assert "ai_hub" in report.categories_checked

    @pytest.mark.asyncio
    async def test_run_gap_analysis_for_category_ai_hub(self):
        from aksara.gapanalysis import run_gap_analysis_for_category
        issues = await run_gap_analysis_for_category("ai_hub")
        assert isinstance(issues, list)


# =============================================================================
# Source-Level Checks
# =============================================================================

class TestAiHubGapSource:
    """Verify code-level properties of the gap checker."""

    def test_source_has_all_gap_codes(self):
        import inspect
        from aksara.gapanalysis import check_ai_hub
        src = inspect.getsource(check_ai_hub)
        expected_codes = [
            "AI_HUB_NO_PROVIDER",
            "AI_HUB_ACTIVE_PROVIDER_UNCONFIGURED",
            "AI_HUB_DEFAULTS_NO_CHAT",
            "AI_HUB_DEFAULTS_NO_EMBEDDINGS",
            "AI_HUB_SEARCH_EMBEDDING_MISMATCH",
            "AI_HUB_AGENT_NO_MODEL",
        ]
        for code in expected_codes:
            assert code in src, f"Missing gap code: {code}"

    def test_source_uses_make_issue(self):
        import inspect
        from aksara.gapanalysis import check_ai_hub
        src = inspect.getsource(check_ai_hub)
        assert "_make_issue" in src

    def test_source_has_fix_commands(self):
        import inspect
        from aksara.gapanalysis import check_ai_hub
        src = inspect.getsource(check_ai_hub)
        assert "GapFixCommand" in src

    def test_doctor_ai_includes_hub_check(self):
        """Doctor AI command should call check_ai_hub_config."""
        from pathlib import Path
        src = Path(__file__).resolve().parents[1] / "aksara" / "cli" / "main.py"
        text = src.read_text()
        idx = text.find("def doctor_ai()")
        assert idx > 0
        snippet = text[idx:idx + 500]
        assert "check_ai_hub_config" in snippet


# =============================================================================
# CLI gap analysis includes ai_hub
# =============================================================================

class TestAiHubGapCli:
    """Tests that the gaps CLI supports the ai_hub category."""

    def test_gaps_run_help_mentions_categories(self):
        from click.testing import CliRunner
        from aksara.cli.main import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["gaps", "run", "--help"])
        assert result.exit_code == 0
        assert "categories" in result.output.lower()

    def test_gaps_run_ai_hub_category(self):
        """Running gaps with ai_hub category should not crash."""
        from click.testing import CliRunner
        from aksara.cli.main import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["gaps", "run", "-c", "ai_hub"])
        # May exit 0 or 1 depending on config, but should not crash
        assert result.exit_code in (0, 1)
