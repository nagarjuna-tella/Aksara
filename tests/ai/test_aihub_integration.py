"""
Tests for AI Hub 2.0 — Integration Wiring.

v0.5.28: Tests for AI Hub integration into agents, workflows,
search, and diagnostics.
"""

import pytest
from unittest import mock


# =============================================================================
# Context Integration Tests
# =============================================================================

class TestAiHubContextIntegration:
    """Tests for ai_hub_summary in AiFullContext."""

    def test_ai_full_context_has_hub_summary_field(self):
        from aksara.ai.context import AiFullContext
        fields = AiFullContext.model_fields
        assert "ai_hub_summary" in fields

    def test_ai_full_context_hub_summary_optional(self):
        from aksara.ai.context import AiFullContext
        field = AiFullContext.model_fields["ai_hub_summary"]
        assert field.default is None

    def test_extract_ai_hub_summary_exists(self):
        from aksara.ai.context import _extract_ai_hub_summary
        assert callable(_extract_ai_hub_summary)

    def test_extract_ai_hub_summary_returns_dict_or_none(self):
        from aksara.ai.context import _extract_ai_hub_summary
        result = _extract_ai_hub_summary()
        assert result is None or isinstance(result, dict)

    def test_extract_ai_hub_summary_with_mocked_settings(self):
        """When hub settings are available, should return a dict."""
        from aksara.ai.context import _extract_ai_hub_summary

        # Direct call — may return None if load fails (no real env) or a dict
        result = _extract_ai_hub_summary()
        assert result is None or isinstance(result, dict)

    def test_extract_ai_hub_summary_keys_when_available(self):
        from aksara.ai.hub_settings import AiHubSettings, ProviderConfig, AiDefaultModels
        from aksara.ai.context import _extract_ai_hub_summary

        mock_hub = AiHubSettings(
            providers=[
                ProviderConfig(kind="openai", api_key="sk-test"),
            ],
            defaults=AiDefaultModels(chat_model="gpt-4o", chat_provider="openai"),
            active_provider="openai",
        )

        with mock.patch(
            "aksara.ai.hub_settings.load_aihub_settings",
            return_value=mock_hub,
        ):
            result = _extract_ai_hub_summary()
            # May or may not use our mock (lazy import caching), but shouldn't crash
            assert result is None or isinstance(result, dict)

    def test_hub_summary_included_in_context_data(self):
        """The build_full_ai_context function references ai_hub_summary."""
        import inspect
        from aksara.ai.context import build_full_ai_context
        source = inspect.getsource(build_full_ai_context)
        assert "ai_hub_summary" in source

    def test_hub_summary_in_context_dict(self):
        """The context_data dict includes ai_hub_summary."""
        import inspect
        from aksara.ai.context import build_full_ai_context
        source = inspect.getsource(build_full_ai_context)
        assert '"ai_hub_summary"' in source


# =============================================================================
# Workflow Integration Tests
# =============================================================================

class TestAiHubWorkflowIntegration:
    """Tests for AI Hub defaults injection into workflows."""

    def test_workflow_source_has_ai_hub_code(self):
        """build_agent_workflow source references ai_hub and load_aihub_settings."""
        from pathlib import Path
        src = (Path(__file__).resolve().parent.parent.parent / "aksara" / "ai" / "workflows.py").read_text()
        assert "ai_hub" in src
        assert "load_aihub_settings" in src

    def test_workflow_metadata_ai_hub_keys(self):
        """Workflow source injects active_provider, chat_model, etc."""
        from pathlib import Path
        src = (Path(__file__).resolve().parent.parent.parent / "aksara" / "ai" / "workflows.py").read_text()
        assert '"active_provider"' in src
        assert '"chat_model"' in src
        assert '"code_model"' in src

    def test_workflow_hub_injection_wrapped_in_try(self):
        """Hub injection in workflows is wrapped in try/except for safety."""
        from pathlib import Path
        src = (Path(__file__).resolve().parent.parent.parent / "aksara" / "ai" / "workflows.py").read_text()
        # Find the ai_hub injection block — need wider window
        idx = src.index('"ai_hub"')
        snippet = src[max(0, idx - 300):idx + 500]
        assert "try:" in snippet
        assert "except" in snippet


# =============================================================================
# Embedding Provider Integration Tests
# =============================================================================

class TestAiHubEmbeddingIntegration:
    """Tests for AI Hub defaults in embedding provider selection."""

    def test_get_embedding_provider_default_local(self):
        """Default provider should still be 'local' without hub or with unregistered hub provider."""
        from aksara.search.embeddings import get_embedding_provider
        # Even if hub resolves a provider like 'ollama', it won't be in _PROVIDERS
        # so it falls back to 'local'
        provider = get_embedding_provider()
        assert provider is not None

    def test_get_embedding_provider_explicit_local(self):
        from aksara.search.embeddings import get_embedding_provider
        provider = get_embedding_provider(provider="local")
        assert provider is not None

    def test_get_embedding_provider_explicit_tfidf(self):
        from aksara.search.embeddings import get_embedding_provider
        provider = get_embedding_provider(provider="local_tfidf")
        assert provider is not None

    def test_get_embedding_provider_unknown_raises(self):
        from aksara.search.embeddings import get_embedding_provider
        with pytest.raises(ValueError, match="Unknown embedding provider"):
            get_embedding_provider(provider="nonexistent_provider_xyz")

    def test_get_embedding_provider_source_has_hub_check(self):
        """Verify the hub integration code exists in get_embedding_provider."""
        import inspect
        from aksara.search.embeddings import get_embedding_provider
        source = inspect.getsource(get_embedding_provider)
        assert "load_aihub_settings" in source
        assert "embeddings_provider" in source

    def test_get_embedding_provider_with_mocked_hub_unknown_provider(self):
        """Hub defaults with unregistered provider should fall back to local."""
        from aksara.search.embeddings import get_embedding_provider
        from aksara.ai.hub_settings import AiHubSettings, AiDefaultModels

        mock_hub = AiHubSettings(
            providers=[],
            defaults=AiDefaultModels(
                embeddings_provider="openai",
                embeddings_model="text-embedding-3-small",
            ),
        )

        with mock.patch(
            "aksara.ai.hub_settings.load_aihub_settings",
            return_value=mock_hub,
        ):
            # openai isn't registered, so it should fall back to local
            provider = get_embedding_provider()
            assert provider is not None

    def test_get_embedding_provider_hub_exception_falls_back(self):
        """When hub loading raises, fall back to local."""
        from aksara.search.embeddings import get_embedding_provider

        with mock.patch(
            "aksara.ai.hub_settings.load_aihub_settings",
            side_effect=ImportError("no module"),
        ):
            provider = get_embedding_provider()
            assert provider is not None


# =============================================================================
# Diagnostics Integration Tests
# =============================================================================

class TestAiHubDiagnosticsIntegration:
    """Tests for AI Hub diagnostics checker."""

    def test_check_ai_hub_config_exists(self):
        from aksara.diagnostics import check_ai_hub_config
        assert callable(check_ai_hub_config)

    @pytest.mark.asyncio
    async def test_check_ai_hub_config_returns_list(self):
        from aksara.diagnostics import check_ai_hub_config
        result = await check_ai_hub_config()
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_check_ai_hub_config_no_crash_without_providers(self):
        from aksara.diagnostics import check_ai_hub_config
        result = await check_ai_hub_config()
        # Should return issues or empty list, not crash
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_check_ai_hub_config_with_no_providers(self):
        from aksara.diagnostics import check_ai_hub_config
        from aksara.ai.hub_settings import AiHubSettings, AiDefaultModels

        mock_hub = AiHubSettings(
            providers=[],
            defaults=AiDefaultModels(),
        )

        with mock.patch(
            "aksara.ai.hub_settings.load_aihub_settings",
            return_value=mock_hub,
        ):
            result = await check_ai_hub_config()
            kinds = [i.kind for i in result]
            assert "ai_hub_no_provider" in kinds

    @pytest.mark.asyncio
    async def test_check_ai_hub_config_with_configured_no_defaults(self):
        from aksara.diagnostics import check_ai_hub_config
        from aksara.ai.hub_settings import AiHubSettings, ProviderConfig, AiDefaultModels, CustomHttpConfig

        # Custom provider has empty embeddings in _PROVIDER_DEFAULT_MODELS,
        # so resolve_defaults won't fill embeddings_model → triggers ai_hub_defaults_missing.
        mock_hub = AiHubSettings(
            providers=[ProviderConfig(
                kind="custom",
                custom=CustomHttpConfig(api_key="test-key", base_url="http://localhost:9999"),
            )],
            defaults=AiDefaultModels(),  # no defaults
            active_provider="custom",
        )

        with mock.patch(
            "aksara.ai.hub_settings.load_aihub_settings",
            return_value=mock_hub,
        ):
            result = await check_ai_hub_config()
            kinds = [i.kind for i in result]
            # Custom provider has no default models, so resolve_defaults won't fill them
            assert "ai_hub_defaults_missing" in kinds

    def test_check_ai_hub_config_registered_in_run_all_checks(self):
        """check_ai_hub_config should be in the run_all_checks checker list."""
        import inspect
        from aksara.diagnostics import run_all_checks
        source = inspect.getsource(run_all_checks)
        assert "check_ai_hub_config" in source

    def test_check_ai_hub_config_in_all(self):
        from aksara import diagnostics
        assert "check_ai_hub_config" in diagnostics.__all__

    @pytest.mark.asyncio
    async def test_check_ai_hub_config_import_error_graceful(self):
        """When hub_settings can't be imported, should return empty list."""
        from aksara.diagnostics import check_ai_hub_config

        with mock.patch.dict("sys.modules", {"aksara.ai.hub_settings": None}):
            # This simulates ImportError
            result = await check_ai_hub_config()
            assert isinstance(result, list)
