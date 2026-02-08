"""
Tests for v0.5.22 Semantic Search integration features.

Tests for: new playbook, agent context 12th section, settings,
and cross-cutting v0.5.22 invariants.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock


# =============================================================================
# New Playbook Tests
# =============================================================================


class TestIdentifyRootCausePlaybook:
    """Tests for the identify_root_cause_from_search playbook."""

    def test_playbook_exists(self):
        from aksara.ai.playbooks import get_playbook_by_key
        pb = get_playbook_by_key("identify_root_cause_from_search")
        assert pb is not None

    def test_playbook_label(self):
        from aksara.ai.playbooks import get_playbook_by_key
        pb = get_playbook_by_key("identify_root_cause_from_search")
        assert pb.label == "Root Cause from Search"

    def test_playbook_kind(self):
        from aksara.ai.playbooks import get_playbook_by_key
        pb = get_playbook_by_key("identify_root_cause_from_search")
        assert pb.kind == "debug_queries"

    def test_playbook_category(self):
        from aksara.ai.playbooks import get_playbook_by_key
        pb = get_playbook_by_key("identify_root_cause_from_search")
        assert pb.category == "diagnostics"

    def test_playbook_risk_level(self):
        from aksara.ai.playbooks import get_playbook_by_key
        pb = get_playbook_by_key("identify_root_cause_from_search")
        assert pb.risk_level == "low"

    def test_playbook_usage_kind(self):
        from aksara.ai.playbooks import get_playbook_by_key
        pb = get_playbook_by_key("identify_root_cause_from_search")
        assert pb.usage_kind == "read_only"

    def test_playbook_has_steps(self):
        from aksara.ai.playbooks import get_playbook_by_key
        pb = get_playbook_by_key("identify_root_cause_from_search")
        assert len(pb.steps) == 4

    def test_playbook_step_ids(self):
        from aksara.ai.playbooks import get_playbook_by_key
        pb = get_playbook_by_key("identify_root_cause_from_search")
        step_ids = [s.id for s in pb.steps]
        assert "search_codebase" in step_ids
        assert "cross_reference" in step_ids
        assert "check_settings" in step_ids
        assert "propose_fix" in step_ids

    def test_playbook_default_sections(self):
        from aksara.ai.playbooks import get_playbook_by_key
        pb = get_playbook_by_key("identify_root_cause_from_search")
        assert "semantic_index" in pb.default_sections

    def test_playbook_tags(self):
        from aksara.ai.playbooks import get_playbook_by_key
        pb = get_playbook_by_key("identify_root_cause_from_search")
        assert "search" in pb.tags
        assert "semantic" in pb.tags

    def test_playbook_notes(self):
        from aksara.ai.playbooks import get_playbook_by_key
        pb = get_playbook_by_key("identify_root_cause_from_search")
        assert "v0.5.22" in pb.notes

    def test_total_builtin_playbooks_is_8(self):
        from aksara.ai.playbooks import get_builtin_playbooks
        pset = get_builtin_playbooks()
        assert pset.total_count == 8

    def test_playbook_in_diagnostics_category(self):
        from aksara.ai.playbooks import get_builtin_playbooks
        pset = get_builtin_playbooks(category="diagnostics")
        keys = [p.key for p in pset.playbooks]
        assert "identify_root_cause_from_search" in keys

    def test_playbook_default_goal_template(self):
        from aksara.ai.playbooks import get_playbook_by_key
        pb = get_playbook_by_key("identify_root_cause_from_search")
        assert "{issue_description}" in pb.default_goal_template


# =============================================================================
# Settings Tests
# =============================================================================


class TestSearchSettings:
    """Tests for v0.5.22 search settings."""

    def test_semantic_search_enabled_default(self):
        from aksara.conf import Settings
        s = Settings(_configured=True)
        assert s.semantic_search_enabled is True

    def test_embedding_provider_default(self):
        from aksara.conf import Settings
        s = Settings(_configured=True)
        assert s.embedding_provider == "local"

    def test_embedding_model_default(self):
        from aksara.conf import Settings
        s = Settings(_configured=True)
        assert s.embedding_model == "local_tfidf"

    def test_embedding_dimensions_default(self):
        from aksara.conf import Settings
        s = Settings(_configured=True)
        assert s.embedding_dimensions == 512

    def test_search_index_backend_default(self):
        from aksara.conf import Settings
        s = Settings(_configured=True)
        assert s.search_index_backend == "memory"

    def test_settings_can_override(self):
        from aksara.conf import Settings
        s = Settings(
            semantic_search_enabled=False,
            embedding_provider="openai",
            embedding_dimensions=1536,
            _configured=True,
        )
        assert s.semantic_search_enabled is False
        assert s.embedding_provider == "openai"
        assert s.embedding_dimensions == 1536


# =============================================================================
# Agent Context - 12th Section
# =============================================================================


class TestAgentContextSemanticIndex:
    """Tests for the semantic_index (12th) section in agent context."""

    @pytest.fixture
    def mock_app(self):
        return MagicMock()

    @pytest.mark.asyncio
    async def test_semantic_index_section_present(self, mock_app):
        with patch("aksara.registry.ModelRegistry") as mock_reg, \
             patch("aksara.studio.utils.build_routes_info", return_value=[]), \
             patch("aksara.studio.utils.build_migration_summary", new_callable=AsyncMock, return_value=MagicMock(model_dump=lambda: {})), \
             patch("aksara.studio.utils.build_ai_profile_set_summary", return_value=MagicMock(model_dump=lambda: {})), \
             patch("aksara.studio.utils.build_ai_hints", return_value=MagicMock(model_dump=lambda: {})), \
             patch("aksara.studio.utils.build_query_inspector", return_value=MagicMock(model_dump=lambda: {})), \
             patch("aksara.studio.utils.compute_schema_checksum", return_value="abc123"), \
             patch("aksara.diagnostics.run_all_checks", new_callable=AsyncMock, return_value=MagicMock(model_dump=lambda **kw: {})):
            mock_reg.all.return_value = {}

            from aksara.studio.utils import build_agent_context
            ctx = await build_agent_context(mock_app)
            keys = {s.key for s in ctx.sections}
            assert "semantic_index" in keys

    @pytest.mark.asyncio
    async def test_semantic_index_has_stats(self, mock_app):
        with patch("aksara.registry.ModelRegistry") as mock_reg, \
             patch("aksara.studio.utils.build_routes_info", return_value=[]), \
             patch("aksara.studio.utils.build_migration_summary", new_callable=AsyncMock, return_value=MagicMock(model_dump=lambda: {})), \
             patch("aksara.studio.utils.build_ai_profile_set_summary", return_value=MagicMock(model_dump=lambda: {})), \
             patch("aksara.studio.utils.build_ai_hints", return_value=MagicMock(model_dump=lambda: {})), \
             patch("aksara.studio.utils.build_query_inspector", return_value=MagicMock(model_dump=lambda: {})), \
             patch("aksara.studio.utils.compute_schema_checksum", return_value="abc123"), \
             patch("aksara.diagnostics.run_all_checks", new_callable=AsyncMock, return_value=MagicMock(model_dump=lambda **kw: {})):
            mock_reg.all.return_value = {}

            from aksara.studio.utils import build_agent_context
            ctx = await build_agent_context(mock_app)
            section = next(s for s in ctx.sections if s.key == "semantic_index")
            # Should have dictionary data (even if empty on error)
            assert isinstance(section.data, dict)


# =============================================================================
# Studio Exports Tests
# =============================================================================


class TestStudioExports:
    """Tests for v0.5.22 exports from aksara.studio."""

    def test_search_request_exported(self):
        from aksara.studio import StudioSearchRequest
        assert StudioSearchRequest is not None

    def test_search_result_item_exported(self):
        from aksara.studio import StudioSearchResultItem
        assert StudioSearchResultItem is not None

    def test_search_result_set_exported(self):
        from aksara.studio import StudioSearchResultSet
        assert StudioSearchResultSet is not None

    def test_search_index_info_exported(self):
        from aksara.studio import StudioSearchIndexInfo
        assert StudioSearchIndexInfo is not None

    def test_build_search_index_info_exported(self):
        from aksara.studio import build_search_index_info
        assert callable(build_search_index_info)

    def test_build_search_results_exported(self):
        from aksara.studio import build_search_results
        assert callable(build_search_results)


# =============================================================================
# Search Package Import Tests
# =============================================================================


class TestSearchPackageImports:
    """Tests for aksara.search package imports."""

    def test_import_search_document(self):
        from aksara.search import SearchDocument
        assert SearchDocument is not None

    def test_import_search_result(self):
        from aksara.search import SearchResult
        assert SearchResult is not None

    def test_import_search_index(self):
        from aksara.search import SearchIndex
        assert SearchIndex is not None

    def test_import_embedder(self):
        from aksara.search import LocalTfIdfEmbedder
        assert LocalTfIdfEmbedder is not None

    def test_import_provider(self):
        from aksara.search import get_embedding_provider
        assert callable(get_embedding_provider)

    def test_import_indexers(self):
        from aksara.search import build_model_documents, build_full_index
        assert callable(build_model_documents)
        assert callable(build_full_index)
