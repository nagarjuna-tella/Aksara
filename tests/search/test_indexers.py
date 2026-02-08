"""
Tests for Aksara Search — Index Builders.

v0.5.22: Tests for model, route, migration, query, settings,
and playbook indexers plus build_full_index.
"""

import sys
import pytest
from unittest.mock import patch, MagicMock

from aksara.search.engine import SearchDocument, SearchIndex
from aksara.search.indexers import (
    build_model_documents,
    build_route_documents,
    build_migration_documents,
    build_query_documents,
    build_settings_documents,
    build_playbook_documents,
    build_full_index,
)


# =============================================================================
# Model Indexer Tests
# =============================================================================


class TestBuildModelDocuments:
    """Tests for build_model_documents."""

    def test_returns_list(self):
        with patch("aksara.registry.ModelRegistry") as mock_reg:
            mock_reg.all.return_value = {}
            docs = build_model_documents()
            assert isinstance(docs, list)

    def test_indexes_registered_models(self):
        mock_field = MagicMock()
        mock_field.field_type = "CharField"
        mock_field.is_relation = False

        mock_model = MagicMock()
        mock_model._fields = {"name": mock_field}
        mock_model._table_name = "users"
        mock_model._ai_description = "User accounts"

        with patch("aksara.registry.ModelRegistry") as mock_reg:
            mock_reg.all.return_value = {"User": mock_model}
            docs = build_model_documents()
            assert len(docs) == 1
            assert docs[0].kind == "model"
            assert docs[0].title == "User"
            assert "users" in docs[0].content
            assert docs[0].metadata["table_name"] == "users"

    def test_handles_registry_error(self):
        with patch.dict("sys.modules", {"aksara.registry": None}):
            # Should return empty list on import error
            docs = build_model_documents()
            assert docs == []

    def test_includes_relations(self):
        fk_field = MagicMock()
        fk_field.field_type = "ForeignKey"
        fk_field.is_relation = True
        fk_field.related_model_name = "Group"

        name_field = MagicMock()
        name_field.field_type = "CharField"
        name_field.is_relation = False

        mock_model = MagicMock()
        mock_model._fields = {"name": name_field, "group": fk_field}
        mock_model._table_name = "users"
        mock_model._ai_description = ""

        with patch("aksara.registry.ModelRegistry") as mock_reg:
            mock_reg.all.return_value = {"User": mock_model}
            docs = build_model_documents()
            assert docs[0].metadata["relation_count"] == 1

    def test_document_tags(self):
        mock_field = MagicMock()
        mock_field.field_type = "CharField"
        mock_field.is_relation = False

        mock_model = MagicMock()
        mock_model._fields = {"email": mock_field}
        mock_model._table_name = "users"
        mock_model._ai_description = ""

        with patch("aksara.registry.ModelRegistry") as mock_reg:
            mock_reg.all.return_value = {"User": mock_model}
            docs = build_model_documents()
            assert "model" in docs[0].tags
            assert "users" in docs[0].tags

    def test_source_format(self):
        mock_model = MagicMock()
        mock_model._fields = {}
        mock_model._table_name = "users"
        mock_model._ai_description = ""

        with patch("aksara.registry.ModelRegistry") as mock_reg:
            mock_reg.all.return_value = {"User": mock_model}
            docs = build_model_documents()
            assert docs[0].source == "model:User"


# =============================================================================
# Route Indexer Tests
# =============================================================================


class TestBuildRouteDocuments:
    """Tests for build_route_documents."""

    def test_no_app_returns_empty(self):
        docs = build_route_documents(None)
        assert docs == []

    def test_indexes_routes(self):
        mock_route = MagicMock()
        mock_route.model_dump.return_value = {
            "path": "/api/users",
            "methods": ["GET", "POST"],
            "name": "users",
            "tags": ["users"],
        }

        with patch("aksara.studio.utils.build_routes_info", return_value=[mock_route]):
            docs = build_route_documents(MagicMock())
            assert len(docs) == 1
            assert docs[0].kind == "route"
            assert "/api/users" in docs[0].title

    def test_handles_dict_routes(self):
        route_dict = {
            "path": "/api/items",
            "methods": ["GET"],
            "name": "items",
            "tags": [],
        }

        with patch("aksara.studio.utils.build_routes_info", return_value=[route_dict]):
            docs = build_route_documents(MagicMock())
            assert len(docs) == 1

    def test_handles_error(self):
        with patch("aksara.studio.utils.build_routes_info", side_effect=Exception("fail")):
            docs = build_route_documents(MagicMock())
            assert docs == []


# =============================================================================
# Settings Indexer Tests
# =============================================================================


class TestBuildSettingsDocuments:
    """Tests for build_settings_documents."""

    def test_returns_documents(self):
        docs = build_settings_documents()
        assert isinstance(docs, list)
        # Should index at least some settings from the Settings dataclass
        assert len(docs) > 0

    def test_document_kind(self):
        docs = build_settings_documents()
        for doc in docs:
            assert doc.kind == "setting"

    def test_includes_debug_setting(self):
        docs = build_settings_documents()
        titles = [d.title for d in docs]
        assert "debug" in titles

    def test_setting_metadata(self):
        docs = build_settings_documents()
        debug_doc = next((d for d in docs if d.title == "debug"), None)
        assert debug_doc is not None
        assert "name" in debug_doc.metadata
        assert "type" in debug_doc.metadata
        assert "env_key" in debug_doc.metadata

    def test_skips_private_fields(self):
        docs = build_settings_documents()
        titles = [d.title for d in docs]
        assert not any(t.startswith("_") for t in titles)


# =============================================================================
# Playbook Indexer Tests
# =============================================================================


class TestBuildPlaybookDocuments:
    """Tests for build_playbook_documents."""

    def test_returns_documents(self):
        docs = build_playbook_documents()
        assert isinstance(docs, list)
        assert len(docs) >= 8  # 8 built-in playbooks

    def test_document_kind(self):
        docs = build_playbook_documents()
        for doc in docs:
            assert doc.kind == "playbook"

    def test_includes_playbook_metadata(self):
        docs = build_playbook_documents()
        for doc in docs:
            assert "key" in doc.metadata
            assert "kind" in doc.metadata
            assert "category" in doc.metadata

    def test_includes_root_cause_playbook(self):
        docs = build_playbook_documents()
        keys = [d.metadata["key"] for d in docs]
        assert "identify_root_cause_from_search" in keys

    def test_source_format(self):
        docs = build_playbook_documents()
        for doc in docs:
            assert doc.source.startswith("playbook:")


# =============================================================================
# Full Index Builder Tests
# =============================================================================


class TestBuildFullIndex:
    """Tests for build_full_index."""

    def test_returns_search_index(self):
        with patch("aksara.search.indexers.build_model_documents", return_value=[]), \
             patch("aksara.search.indexers.build_route_documents", return_value=[]), \
             patch("aksara.search.indexers.build_migration_documents", return_value=[]), \
             patch("aksara.search.indexers.build_query_documents", return_value=[]):
            index = build_full_index()
            assert isinstance(index, SearchIndex)

    def test_includes_settings_and_playbooks(self):
        with patch("aksara.search.indexers.build_model_documents", return_value=[]), \
             patch("aksara.search.indexers.build_route_documents", return_value=[]), \
             patch("aksara.search.indexers.build_migration_documents", return_value=[]), \
             patch("aksara.search.indexers.build_query_documents", return_value=[]):
            index = build_full_index()
            # Should have settings + playbooks at minimum
            assert index.size > 0
            kinds = index.kinds()
            assert "setting" in kinds
            assert "playbook" in kinds

    def test_include_flags(self):
        with patch("aksara.search.indexers.build_model_documents", return_value=[]) as mock_models, \
             patch("aksara.search.indexers.build_route_documents", return_value=[]) as mock_routes, \
             patch("aksara.search.indexers.build_migration_documents", return_value=[]), \
             patch("aksara.search.indexers.build_query_documents", return_value=[]), \
             patch("aksara.search.indexers.build_settings_documents", return_value=[]) as mock_settings, \
             patch("aksara.search.indexers.build_playbook_documents", return_value=[]) as mock_playbooks:
            build_full_index(include_models=False, include_routes=False)
            mock_models.assert_not_called()
            mock_routes.assert_not_called()

    def test_searchable_after_build(self):
        doc = SearchDocument(kind="model", title="Test", summary="S", content="searchable content")
        with patch("aksara.search.indexers.build_model_documents", return_value=[doc]), \
             patch("aksara.search.indexers.build_route_documents", return_value=[]), \
             patch("aksara.search.indexers.build_migration_documents", return_value=[]), \
             patch("aksara.search.indexers.build_query_documents", return_value=[]):
            index = build_full_index()
            results = index.search("searchable")
            assert len(results) >= 1
