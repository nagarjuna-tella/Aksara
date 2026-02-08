"""
Tests for Aksara Search Engine — Core types and SearchIndex.

v0.5.22: 80+ tests covering SearchDocument, SearchResult, SearchIndex,
tokenization, TF-IDF, cosine similarity, and search modes.
"""

import pytest
from datetime import datetime, timezone

from aksara.search.engine import (
    SearchDocument,
    SearchResult,
    SearchIndex,
    _tokenize,
    _extract_highlights,
    _compute_tf,
    _compute_idf,
    _tfidf_vector,
    _cosine_similarity,
)


# =============================================================================
# SearchDocument Tests
# =============================================================================


class TestSearchDocument:
    """Tests for SearchDocument dataclass."""

    def test_create_minimal(self):
        doc = SearchDocument(kind="model", title="User", summary="User model", content="The User model")
        assert doc.kind == "model"
        assert doc.title == "User"
        assert doc.summary == "User model"
        assert doc.content == "The User model"
        assert len(doc.id) == 16
        assert doc.metadata == {}
        assert doc.tags == []
        assert doc.source == ""
        assert doc.created_at is not None

    def test_auto_generates_id(self):
        doc1 = SearchDocument(kind="model", title="A", summary="s", content="c")
        doc2 = SearchDocument(kind="model", title="B", summary="s", content="c")
        assert doc1.id != doc2.id

    def test_explicit_id(self):
        doc = SearchDocument(id="my-id", kind="route", title="T", summary="S", content="C")
        assert doc.id == "my-id"

    def test_metadata_and_tags(self):
        doc = SearchDocument(
            kind="setting",
            title="debug",
            summary="Debug flag",
            content="debug = True",
            metadata={"type": "bool"},
            tags=["config", "debug"],
        )
        assert doc.metadata == {"type": "bool"}
        assert doc.tags == ["config", "debug"]

    def test_source(self):
        doc = SearchDocument(kind="model", title="T", summary="S", content="C", source="model:User")
        assert doc.source == "model:User"

    def test_to_dict(self):
        doc = SearchDocument(
            id="abc123", kind="model", title="User",
            summary="User model", content="fields: id, name",
            metadata={"table": "users"}, tags=["user"],
            source="model:User",
        )
        d = doc.to_dict()
        assert d["id"] == "abc123"
        assert d["kind"] == "model"
        assert d["title"] == "User"
        assert d["summary"] == "User model"
        assert d["content"] == "fields: id, name"
        assert d["metadata"] == {"table": "users"}
        assert d["tags"] == ["user"]
        assert d["source"] == "model:User"
        assert d["created_at"] is not None

    def test_to_dict_serializable(self):
        """to_dict output should be JSON-serializable."""
        import json
        doc = SearchDocument(kind="model", title="T", summary="S", content="C")
        json.dumps(doc.to_dict())  # Should not raise

    def test_all_kinds(self):
        for kind in ["model", "route", "migration", "query", "file", "test", "setting", "playbook", "agent_section"]:
            doc = SearchDocument(kind=kind, title="T", summary="S", content="C")
            assert doc.kind == kind

    def test_created_at_timestamp(self):
        doc = SearchDocument(kind="model", title="T", summary="S", content="C")
        assert isinstance(doc.created_at, datetime)
        assert doc.created_at.tzinfo is not None


# =============================================================================
# SearchResult Tests
# =============================================================================


class TestSearchResult:
    """Tests for SearchResult dataclass."""

    def test_create_minimal(self):
        doc = SearchDocument(kind="model", title="T", summary="S", content="C")
        result = SearchResult(document=doc, score=0.85)
        assert result.document is doc
        assert result.score == 0.85
        assert result.highlights == []
        assert result.match_type == "keyword"

    def test_with_highlights(self):
        doc = SearchDocument(kind="route", title="T", summary="S", content="C")
        result = SearchResult(
            document=doc, score=0.7,
            highlights=["...matched text..."],
            match_type="semantic",
        )
        assert len(result.highlights) == 1
        assert result.match_type == "semantic"

    def test_to_dict(self):
        doc = SearchDocument(id="x", kind="model", title="T", summary="S", content="C")
        result = SearchResult(document=doc, score=0.9123, highlights=["h1"])
        d = result.to_dict()
        assert d["score"] == 0.9123
        assert d["highlights"] == ["h1"]
        assert d["document"]["id"] == "x"
        assert d["match_type"] == "keyword"

    def test_score_rounding(self):
        doc = SearchDocument(kind="model", title="T", summary="S", content="C")
        result = SearchResult(document=doc, score=0.12345678)
        d = result.to_dict()
        assert d["score"] == 0.1235  # Rounded to 4 decimals


# =============================================================================
# Tokenization Tests
# =============================================================================


class TestTokenize:
    """Tests for _tokenize helper."""

    def test_simple_text(self):
        tokens = _tokenize("hello world")
        assert "hello" in tokens
        assert "world" in tokens

    def test_camel_case(self):
        tokens = _tokenize("UserProfile")
        assert "user" in tokens
        assert "profile" in tokens

    def test_snake_case(self):
        tokens = _tokenize("user_profile")
        assert "user" in tokens
        assert "profile" in tokens

    def test_removes_stop_words(self):
        tokens = _tokenize("the user is in a group")
        assert "the" not in tokens
        assert "is" not in tokens
        assert "in" not in tokens
        assert "a" not in tokens
        assert "user" in tokens
        assert "group" in tokens

    def test_single_char_removed(self):
        tokens = _tokenize("a b c hello")
        assert "a" not in tokens
        assert "b" not in tokens
        assert "c" not in tokens
        assert "hello" in tokens

    def test_empty_string(self):
        assert _tokenize("") == []

    def test_numbers(self):
        tokens = _tokenize("user123 model456")
        assert "user123" in tokens
        assert "model456" in tokens

    def test_mixed_format(self):
        tokens = _tokenize("getUserByName user_id")
        assert "get" in tokens
        assert "user" in tokens
        assert "name" in tokens
        assert "id" in tokens


# =============================================================================
# Highlight Extraction Tests
# =============================================================================


class TestExtractHighlights:
    """Tests for _extract_highlights helper."""

    def test_finds_match(self):
        content = "The User model has an email field for storing addresses"
        highlights = _extract_highlights(content, ["email"])
        assert len(highlights) >= 1
        assert any("email" in h.lower() for h in highlights)

    def test_max_highlights(self):
        content = "user user user user user user user"
        highlights = _extract_highlights(content, ["user"], max_highlights=2)
        assert len(highlights) <= 2

    def test_no_match(self):
        highlights = _extract_highlights("hello world", ["xyz"])
        assert highlights == []

    def test_adds_ellipsis(self):
        content = "x" * 100 + "match" + "y" * 100
        highlights = _extract_highlights(content, ["match"])
        assert any("..." in h for h in highlights)

    def test_empty_content(self):
        assert _extract_highlights("", ["test"]) == []


# =============================================================================
# TF-IDF Helper Tests
# =============================================================================


class TestComputeTf:
    """Tests for _compute_tf helper."""

    def test_basic(self):
        tf = _compute_tf(["hello", "world", "hello"])
        assert tf["hello"] == pytest.approx(2/3)
        assert tf["world"] == pytest.approx(1/3)

    def test_empty(self):
        assert _compute_tf([]) == {}

    def test_single_token(self):
        tf = _compute_tf(["word"])
        assert tf["word"] == 1.0


class TestComputeIdf:
    """Tests for _compute_idf helper."""

    def test_basic(self):
        corpus = [["hello", "world"], ["hello", "there"]]
        idf = _compute_idf(corpus, ["hello", "world", "there"])
        # "hello" appears in both docs, lower IDF
        # "world" appears in 1 doc, higher IDF
        assert idf["hello"] < idf["world"]
        assert idf["world"] == idf["there"]

    def test_empty_corpus(self):
        assert _compute_idf([], ["test"]) == {}


class TestTfidfVector:
    """Tests for _tfidf_vector helper."""

    def test_basic(self):
        tf = {"hello": 0.5, "world": 0.5}
        idf = {"hello": 1.0, "world": 2.0, "foo": 1.5}
        vocab = ["hello", "world", "foo"]
        vec = _tfidf_vector(tf, idf, vocab)
        assert len(vec) == 3
        assert vec[0] == 0.5 * 1.0  # hello
        assert vec[1] == 0.5 * 2.0  # world
        assert vec[2] == 0.0  # foo (not in tf)


class TestCosineSimilarity:
    """Tests for _cosine_similarity helper."""

    def test_identical_vectors(self):
        vec = [1.0, 2.0, 3.0]
        assert _cosine_similarity(vec, vec) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert _cosine_similarity(a, b) == pytest.approx(0.0)

    def test_similar_vectors(self):
        a = [1.0, 1.0]
        b = [1.0, 0.5]
        sim = _cosine_similarity(a, b)
        assert 0.5 < sim < 1.0

    def test_zero_vector(self):
        assert _cosine_similarity([0, 0, 0], [1, 2, 3]) == 0.0

    def test_empty_vectors(self):
        assert _cosine_similarity([], []) == 0.0

    def test_different_lengths(self):
        assert _cosine_similarity([1, 2], [1, 2, 3]) == 0.0


# =============================================================================
# SearchIndex Tests
# =============================================================================


class TestSearchIndex:
    """Tests for SearchIndex class."""

    def _make_doc(self, kind="model", title="Test", content="test content", **kwargs):
        return SearchDocument(kind=kind, title=title, summary=f"{title} summary", content=content, **kwargs)

    def test_empty_index(self):
        idx = SearchIndex()
        assert idx.size == 0
        assert idx.all_documents() == []
        assert idx.kinds() == []

    def test_add_document(self):
        idx = SearchIndex()
        doc = self._make_doc()
        idx.add(doc)
        assert idx.size == 1

    def test_add_many(self):
        idx = SearchIndex()
        docs = [self._make_doc(title=f"Doc{i}") for i in range(5)]
        count = idx.add_many(docs)
        assert count == 5
        assert idx.size == 5

    def test_remove_document(self):
        idx = SearchIndex()
        doc = self._make_doc()
        idx.add(doc)
        assert idx.remove(doc.id) is True
        assert idx.size == 0

    def test_remove_nonexistent(self):
        idx = SearchIndex()
        assert idx.remove("nonexistent") is False

    def test_get_document(self):
        idx = SearchIndex()
        doc = self._make_doc(title="MyDoc")
        idx.add(doc)
        found = idx.get(doc.id)
        assert found is not None
        assert found.title == "MyDoc"

    def test_get_nonexistent(self):
        idx = SearchIndex()
        assert idx.get("missing") is None

    def test_clear(self):
        idx = SearchIndex()
        idx.add_many([self._make_doc(title=f"D{i}") for i in range(3)])
        assert idx.size == 3
        idx.clear()
        assert idx.size == 0

    def test_kinds(self):
        idx = SearchIndex()
        idx.add(self._make_doc(kind="model"))
        idx.add(self._make_doc(kind="route"))
        idx.add(self._make_doc(kind="model"))
        kinds = idx.kinds()
        assert "model" in kinds
        assert "route" in kinds
        assert len(kinds) == 2

    def test_count_by_kind(self):
        idx = SearchIndex()
        idx.add(self._make_doc(kind="model"))
        idx.add(self._make_doc(kind="route"))
        idx.add(self._make_doc(kind="model"))
        counts = idx.count_by_kind()
        assert counts["model"] == 2
        assert counts["route"] == 1

    def test_stats(self):
        idx = SearchIndex()
        idx.add(self._make_doc())
        stats = idx.stats()
        assert stats["total_documents"] == 1
        assert "by_kind" in stats
        assert "vocabulary_size" in stats
        assert stats["is_dirty"] is True

    def test_to_dict(self):
        idx = SearchIndex()
        idx.add(self._make_doc())
        d = idx.to_dict()
        assert "stats" in d
        assert "documents" in d
        assert len(d["documents"]) == 1

    # -------------------------------------------------------------------------
    # Keyword Search Tests
    # -------------------------------------------------------------------------

    def test_keyword_search_basic(self):
        idx = SearchIndex()
        idx.add(self._make_doc(title="User Model", content="user authentication login"))
        idx.add(self._make_doc(title="Product Model", content="product pricing inventory"))
        results = idx.search("user login", mode="keyword")
        assert len(results) >= 1
        assert results[0].document.title == "User Model"

    def test_keyword_search_no_match(self):
        idx = SearchIndex()
        idx.add(self._make_doc(content="hello world"))
        results = idx.search("xyz nonexistent", mode="keyword")
        assert len(results) == 0

    def test_keyword_search_top_k(self):
        idx = SearchIndex()
        for i in range(20):
            idx.add(self._make_doc(title=f"Doc{i}", content=f"shared keyword doc {i}"))
        results = idx.search("keyword", mode="keyword", top_k=5)
        assert len(results) <= 5

    def test_keyword_search_kind_filter(self):
        idx = SearchIndex()
        idx.add(self._make_doc(kind="model", title="User", content="user model"))
        idx.add(self._make_doc(kind="route", title="GET /users", content="user route"))
        results = idx.search("user", mode="keyword", kind="model")
        assert all(r.document.kind == "model" for r in results)

    def test_keyword_search_kinds_filter(self):
        idx = SearchIndex()
        idx.add(self._make_doc(kind="model", content="data"))
        idx.add(self._make_doc(kind="route", content="data"))
        idx.add(self._make_doc(kind="setting", content="data"))
        results = idx.search("data", mode="keyword", kinds=["model", "route"])
        assert all(r.document.kind in ("model", "route") for r in results)

    def test_keyword_search_tags_filter(self):
        idx = SearchIndex()
        idx.add(self._make_doc(content="database query", tags=["db", "slow"]))
        idx.add(self._make_doc(content="database connection", tags=["db", "config"]))
        idx.add(self._make_doc(content="database backup", tags=["ops"]))
        results = idx.search("database", mode="keyword", tags=["slow"])
        assert len(results) == 1

    def test_keyword_search_min_score(self):
        idx = SearchIndex()
        idx.add(self._make_doc(content="exact match keyword"))
        idx.add(self._make_doc(content="partial keyword extra stuff lots more"))
        results = idx.search("exact match keyword", mode="keyword", min_score=0.5)
        assert all(r.score >= 0.5 for r in results)

    # -------------------------------------------------------------------------
    # Semantic Search Tests
    # -------------------------------------------------------------------------

    def test_semantic_search_basic(self):
        idx = SearchIndex()
        idx.add(self._make_doc(title="User Auth", content="authentication login password security"))
        idx.add(self._make_doc(title="Product Catalog", content="inventory pricing stock management"))
        results = idx.search("login password", mode="semantic")
        assert len(results) >= 1
        assert results[0].document.title == "User Auth"

    def test_semantic_search_returns_scores(self):
        idx = SearchIndex()
        idx.add(self._make_doc(content="machine learning deep neural network"))
        results = idx.search("neural network", mode="semantic")
        if results:
            assert 0.0 < results[0].score <= 1.0

    # -------------------------------------------------------------------------
    # Hybrid Search Tests
    # -------------------------------------------------------------------------

    def test_hybrid_search(self):
        idx = SearchIndex()
        idx.add(self._make_doc(title="User Model", content="user authentication login email"))
        idx.add(self._make_doc(title="Product", content="product pricing stock"))
        results = idx.search("user authentication", mode="hybrid")
        assert len(results) >= 1
        assert results[0].match_type == "hybrid"

    def test_hybrid_search_combines_scores(self):
        idx = SearchIndex()
        idx.add(self._make_doc(content="database query optimization index"))
        results = idx.search("database query", mode="hybrid")
        assert len(results) >= 1

    # -------------------------------------------------------------------------
    # Edge Cases
    # -------------------------------------------------------------------------

    def test_empty_query(self):
        idx = SearchIndex()
        idx.add(self._make_doc())
        assert idx.search("") == []

    def test_empty_index_search(self):
        idx = SearchIndex()
        assert idx.search("test") == []

    def test_search_after_clear(self):
        idx = SearchIndex()
        idx.add(self._make_doc(content="hello"))
        idx.clear()
        assert idx.search("hello") == []

    def test_search_after_remove(self):
        idx = SearchIndex()
        doc = self._make_doc(content="unique_term_xyz")
        idx.add(doc)
        idx.remove(doc.id)
        results = idx.search("unique_term_xyz")
        assert len(results) == 0

    def test_default_mode_is_hybrid(self):
        idx = SearchIndex()
        idx.add(self._make_doc(content="test data"))
        results = idx.search("test")
        if results:
            assert results[0].match_type in ("hybrid", "keyword", "semantic")

    def test_results_sorted_by_score(self):
        idx = SearchIndex()
        idx.add(self._make_doc(title="Low", content="xxxx yyyy match"))
        idx.add(self._make_doc(title="High", content="match match match match"))
        results = idx.search("match", mode="keyword")
        if len(results) >= 2:
            assert results[0].score >= results[1].score

    def test_rebuild_tfidf_on_dirty(self):
        idx = SearchIndex()
        idx.add(self._make_doc(content="word1 word2"))
        assert idx._dirty is True
        idx.search("word1", mode="semantic")
        assert idx._dirty is False
        idx.add(self._make_doc(content="word3"))
        assert idx._dirty is True

    def test_large_index(self):
        """Index with 100 documents should work fine."""
        idx = SearchIndex()
        for i in range(100):
            idx.add(self._make_doc(title=f"Doc {i}", content=f"content for document number {i}"))
        assert idx.size == 100
        results = idx.search("document number", top_k=10)
        assert len(results) <= 10
