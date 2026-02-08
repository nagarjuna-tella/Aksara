"""
Tests for Studio Semantic Search integration.

v0.5.22: Tests for search models, util functions, and FastAPI endpoints.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from aksara.studio.models import (
    StudioSearchRequest,
    StudioSearchResultItem,
    StudioSearchResultSet,
    StudioSearchIndexInfo,
)


# =============================================================================
# Model Tests
# =============================================================================


class TestStudioSearchRequest:
    """Tests for StudioSearchRequest model."""

    def test_minimal(self):
        req = StudioSearchRequest(query="user")
        assert req.query == "user"
        assert req.top_k == 10
        assert req.kind is None
        assert req.kinds is None
        assert req.tags is None
        assert req.min_score == 0.0
        assert req.mode == "hybrid"

    def test_full(self):
        req = StudioSearchRequest(
            query="test",
            top_k=5,
            kind="model",
            kinds=["model", "route"],
            tags=["auth"],
            min_score=0.3,
            mode="semantic",
        )
        assert req.top_k == 5
        assert req.kind == "model"
        assert req.mode == "semantic"

    def test_model_dump(self):
        req = StudioSearchRequest(query="hello")
        d = req.model_dump()
        assert d["query"] == "hello"
        assert d["top_k"] == 10


class TestStudioSearchResultItem:
    """Tests for StudioSearchResultItem model."""

    def test_create(self):
        item = StudioSearchResultItem(
            id="abc",
            kind="model",
            title="User",
            summary="User model",
            score=0.95,
        )
        assert item.id == "abc"
        assert item.kind == "model"
        assert item.score == 0.95
        assert item.highlights == []
        assert item.tags == []

    def test_with_metadata(self):
        item = StudioSearchResultItem(
            id="x", kind="route", title="T", summary="S", score=0.5,
            metadata={"path": "/api"},
            highlights=["...match..."],
            match_type="semantic",
        )
        assert item.metadata["path"] == "/api"
        assert len(item.highlights) == 1

    def test_model_dump(self):
        item = StudioSearchResultItem(
            id="x", kind="model", title="T", summary="S", score=0.8
        )
        d = item.model_dump()
        assert d["id"] == "x"
        assert d["score"] == 0.8


class TestStudioSearchResultSet:
    """Tests for StudioSearchResultSet model."""

    def test_empty(self):
        rs = StudioSearchResultSet(query="test")
        assert rs.query == "test"
        assert rs.total_results == 0
        assert rs.results == []
        assert rs.mode == "hybrid"
        assert rs.index_size == 0

    def test_with_results(self):
        items = [
            StudioSearchResultItem(id="a", kind="model", title="A", summary="S", score=0.9),
            StudioSearchResultItem(id="b", kind="route", title="B", summary="S", score=0.7),
        ]
        rs = StudioSearchResultSet(
            query="test", total_results=2, results=items,
            mode="semantic", index_size=50,
        )
        assert rs.total_results == 2
        assert len(rs.results) == 2
        assert rs.index_size == 50


class TestStudioSearchIndexInfo:
    """Tests for StudioSearchIndexInfo model."""

    def test_defaults(self):
        info = StudioSearchIndexInfo()
        assert info.total_documents == 0
        assert info.by_kind == {}
        assert info.vocabulary_size == 0
        assert info.kinds_available == []
        assert info.embedding_provider == "local_tfidf"

    def test_populated(self):
        info = StudioSearchIndexInfo(
            total_documents=42,
            by_kind={"model": 10, "route": 32},
            vocabulary_size=256,
            kinds_available=["model", "route"],
        )
        assert info.total_documents == 42
        assert info.by_kind["model"] == 10


# =============================================================================
# Utils Tests
# =============================================================================


class TestBuildSearchIndexInfo:
    """Tests for build_search_index_info."""

    def test_returns_model(self):
        from aksara.studio.utils import build_search_index_info

        with patch("aksara.search.indexers.build_full_index") as mock_build:
            mock_idx = MagicMock()
            mock_idx.stats.return_value = {
                "total_documents": 10,
                "by_kind": {"model": 5, "setting": 5},
                "vocabulary_size": 100,
                "is_dirty": False,
            }
            mock_idx.kinds.return_value = ["model", "setting"]
            mock_build.return_value = mock_idx

            # Clear cached index
            import aksara.studio.utils as u
            u._search_index_cache = None

            info = build_search_index_info()
            assert isinstance(info, StudioSearchIndexInfo)
            assert info.total_documents == 10

    def test_caches_index(self):
        from aksara.studio.utils import build_search_index_info, _get_search_index
        import aksara.studio.utils as u

        mock_idx = MagicMock()
        mock_idx.stats.return_value = {"total_documents": 1, "by_kind": {}, "vocabulary_size": 0, "is_dirty": False}
        mock_idx.kinds.return_value = []

        u._search_index_cache = mock_idx
        info = build_search_index_info()
        assert info.total_documents == 1

        # Cleanup
        u._search_index_cache = None


class TestBuildSearchResults:
    """Tests for build_search_results."""

    def test_returns_result_set(self):
        from aksara.studio.utils import build_search_results
        from aksara.search.engine import SearchDocument, SearchResult
        import aksara.studio.utils as u

        mock_idx = MagicMock()
        doc = SearchDocument(id="x", kind="model", title="T", summary="S", content="C")
        mock_idx.search.return_value = [
            SearchResult(document=doc, score=0.9, match_type="hybrid")
        ]
        mock_idx.size = 10
        u._search_index_cache = mock_idx

        result = build_search_results("test query")
        assert isinstance(result, StudioSearchResultSet)
        assert result.query == "test query"
        assert result.total_results == 1
        assert result.results[0].score == 0.9

        u._search_index_cache = None

    def test_empty_results(self):
        from aksara.studio.utils import build_search_results
        import aksara.studio.utils as u

        mock_idx = MagicMock()
        mock_idx.search.return_value = []
        mock_idx.size = 0
        u._search_index_cache = mock_idx

        result = build_search_results("nonexistent")
        assert result.total_results == 0
        assert result.results == []

        u._search_index_cache = None


# =============================================================================
# CLI Search Tests
# =============================================================================


class TestSearchCLI:
    """Tests for aksara search CLI commands."""

    def test_search_query_json(self):
        from click.testing import CliRunner
        from aksara.cli.main import cli
        from aksara.search.engine import SearchDocument, SearchResult

        runner = CliRunner()

        mock_idx = MagicMock()
        doc = SearchDocument(id="abc", kind="model", title="User", summary="User model", content="user data")
        mock_idx.search.return_value = [SearchResult(document=doc, score=0.9)]
        mock_idx.size = 1

        with patch("aksara.search.indexers.build_full_index", return_value=mock_idx):
            result = runner.invoke(cli, ["search", "query", "user", "--json"])
            assert result.exit_code == 0
            import json
            data = json.loads(result.output)
            assert data["query"] == "user"
            assert len(data["results"]) == 1

    def test_search_query_text(self):
        from click.testing import CliRunner
        from aksara.cli.main import cli
        from aksara.search.engine import SearchDocument, SearchResult

        runner = CliRunner()

        mock_idx = MagicMock()
        doc = SearchDocument(id="abc", kind="model", title="User", summary="User model", content="user data")
        mock_idx.search.return_value = [SearchResult(document=doc, score=0.85)]
        mock_idx.size = 1

        with patch("aksara.search.indexers.build_full_index", return_value=mock_idx):
            result = runner.invoke(cli, ["search", "query", "user"])
            assert result.exit_code == 0
            assert "User" in result.output

    def test_search_query_no_results(self):
        from click.testing import CliRunner
        from aksara.cli.main import cli

        runner = CliRunner()

        mock_idx = MagicMock()
        mock_idx.search.return_value = []
        mock_idx.size = 0

        with patch("aksara.search.indexers.build_full_index", return_value=mock_idx):
            result = runner.invoke(cli, ["search", "query", "nonexistent"])
            assert result.exit_code == 0
            assert "No results" in result.output

    def test_search_index_json(self):
        from click.testing import CliRunner
        from aksara.cli.main import cli

        runner = CliRunner()

        mock_idx = MagicMock()
        mock_idx.stats.return_value = {
            "total_documents": 42,
            "by_kind": {"model": 10},
            "vocabulary_size": 100,
            "is_dirty": False,
        }

        with patch("aksara.search.indexers.build_full_index", return_value=mock_idx):
            result = runner.invoke(cli, ["search", "index", "--json"])
            assert result.exit_code == 0
            import json
            data = json.loads(result.output)
            assert data["total_documents"] == 42

    def test_search_index_text(self):
        from click.testing import CliRunner
        from aksara.cli.main import cli

        runner = CliRunner()

        mock_idx = MagicMock()
        mock_idx.stats.return_value = {
            "total_documents": 10,
            "by_kind": {"model": 5, "setting": 5},
            "vocabulary_size": 50,
            "is_dirty": False,
        }

        with patch("aksara.search.indexers.build_full_index", return_value=mock_idx):
            result = runner.invoke(cli, ["search", "index"])
            assert result.exit_code == 0
            assert "Total Documents" in result.output

    def test_search_query_semantic_flag(self):
        from click.testing import CliRunner
        from aksara.cli.main import cli

        runner = CliRunner()

        mock_idx = MagicMock()
        mock_idx.search.return_value = []
        mock_idx.size = 0

        with patch("aksara.search.indexers.build_full_index", return_value=mock_idx):
            result = runner.invoke(cli, ["search", "query", "test", "--semantic"])
            assert result.exit_code == 0
            mock_idx.search.assert_called_once()
            call_kwargs = mock_idx.search.call_args
            assert call_kwargs[1]["mode"] == "semantic" or call_kwargs.kwargs.get("mode") == "semantic"

    def test_search_query_kind_filter(self):
        from click.testing import CliRunner
        from aksara.cli.main import cli

        runner = CliRunner()

        mock_idx = MagicMock()
        mock_idx.search.return_value = []
        mock_idx.size = 0

        with patch("aksara.search.indexers.build_full_index", return_value=mock_idx):
            result = runner.invoke(cli, ["search", "query", "test", "--kind", "model"])
            assert result.exit_code == 0
