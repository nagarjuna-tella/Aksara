"""
Tests for Aksara Search — Embedding Providers.

v0.5.22: Tests for LocalTfIdfEmbedder and provider registry.
"""

import pytest

from aksara.search.embeddings import (
    BaseEmbeddingProvider,
    LocalTfIdfEmbedder,
    get_embedding_provider,
    register_embedding_provider,
    _tokenize_for_embed,
)


# =============================================================================
# LocalTfIdfEmbedder Tests
# =============================================================================


class TestLocalTfIdfEmbedder:
    """Tests for LocalTfIdfEmbedder."""

    def test_provider_name(self):
        emb = LocalTfIdfEmbedder()
        assert emb.provider_name == "local_tfidf"

    def test_default_dimensions(self):
        emb = LocalTfIdfEmbedder()
        assert emb.dimensions == 512  # max_features fallback

    def test_custom_max_features(self):
        emb = LocalTfIdfEmbedder(max_features=100)
        assert emb._max_features == 100

    def test_fit_builds_vocabulary(self):
        emb = LocalTfIdfEmbedder()
        emb.fit(["hello world", "world peace"])
        assert len(emb._vocabulary) > 0
        assert "hello" in emb._vocabulary
        assert "world" in emb._vocabulary
        assert "peace" in emb._vocabulary
        assert emb._fitted is True

    def test_fit_limits_features(self):
        emb = LocalTfIdfEmbedder(max_features=2)
        emb.fit(["hello world peace", "world peace love"])
        assert len(emb._vocabulary) <= 2

    def test_embed_after_fit(self):
        emb = LocalTfIdfEmbedder()
        emb.fit(["user authentication", "product catalog", "admin dashboard"])
        vec = emb.embed("user authentication")
        assert isinstance(vec, list)
        assert len(vec) == len(emb._vocabulary)
        assert all(isinstance(v, float) for v in vec)

    def test_embed_without_fit(self):
        emb = LocalTfIdfEmbedder()
        vec = emb.embed("hello world test")
        assert isinstance(vec, list)
        assert len(vec) > 0

    def test_embed_batch(self):
        emb = LocalTfIdfEmbedder()
        texts = ["hello world", "world peace", "peace love"]
        vecs = emb.embed_batch(texts)
        assert len(vecs) == 3
        assert all(isinstance(v, list) for v in vecs)
        assert all(len(v) == len(emb._vocabulary) for v in vecs)

    def test_embed_batch_auto_fits(self):
        emb = LocalTfIdfEmbedder()
        assert emb._fitted is False
        emb.embed_batch(["test data", "more data"])
        assert emb._fitted is True

    def test_embed_produces_normalized_vectors(self):
        import math
        emb = LocalTfIdfEmbedder()
        emb.fit(["hello world data", "world test data"])
        vec = emb.embed("hello world")
        magnitude = math.sqrt(sum(v * v for v in vec))
        if magnitude > 0:
            assert magnitude == pytest.approx(1.0, abs=0.01)

    def test_similar_texts_produce_similar_vectors(self):
        emb = LocalTfIdfEmbedder()
        texts = ["user login authentication", "user logout session", "product price catalog"]
        emb.fit(texts)
        v1 = emb.embed("user login authentication")
        v2 = emb.embed("user logout session")
        v3 = emb.embed("product price catalog")

        # Cosine similarity
        def cosine(a, b):
            import math
            dot = sum(x * y for x, y in zip(a, b))
            ma = math.sqrt(sum(x * x for x in a))
            mb = math.sqrt(sum(x * x for x in b))
            return dot / (ma * mb) if ma > 0 and mb > 0 else 0

        sim_12 = cosine(v1, v2)
        sim_13 = cosine(v1, v3)
        # v1 and v2 both about "user" should be more similar than v1 and v3
        assert sim_12 > sim_13

    def test_empty_text(self):
        emb = LocalTfIdfEmbedder()
        emb.fit(["hello world"])
        vec = emb.embed("")
        assert isinstance(vec, list)

    def test_dimensions_after_fit(self):
        emb = LocalTfIdfEmbedder()
        emb.fit(["hello world", "test data"])
        assert emb.dimensions == len(emb._vocabulary)

    def test_implements_protocol(self):
        emb = LocalTfIdfEmbedder()
        assert isinstance(emb, BaseEmbeddingProvider)


# =============================================================================
# Tokenize Tests
# =============================================================================


class TestTokenizeForEmbed:
    """Tests for _tokenize_for_embed."""

    def test_basic(self):
        tokens = _tokenize_for_embed("hello world")
        assert "hello" in tokens
        assert "world" in tokens

    def test_camel_case(self):
        tokens = _tokenize_for_embed("UserProfile")
        assert "user" in tokens
        assert "profile" in tokens

    def test_stop_words_removed(self):
        tokens = _tokenize_for_embed("the user is logged in")
        assert "the" not in tokens
        assert "user" in tokens

    def test_empty(self):
        assert _tokenize_for_embed("") == []


# =============================================================================
# Provider Registry Tests
# =============================================================================


class TestGetEmbeddingProvider:
    """Tests for get_embedding_provider factory."""

    def test_default_is_local(self):
        provider = get_embedding_provider()
        assert isinstance(provider, LocalTfIdfEmbedder)

    def test_explicit_local(self):
        provider = get_embedding_provider("local")
        assert isinstance(provider, LocalTfIdfEmbedder)

    def test_local_tfidf(self):
        provider = get_embedding_provider("local_tfidf")
        assert isinstance(provider, LocalTfIdfEmbedder)

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown embedding provider"):
            get_embedding_provider("nonexistent_provider")

    def test_register_custom_provider(self):
        class FakeProvider:
            provider_name = "fake"
            dimensions = 10
            def embed(self, text): return [0.0] * 10
            def embed_batch(self, texts): return [[0.0] * 10] * len(texts)

        register_embedding_provider("fake", FakeProvider)
        provider = get_embedding_provider("fake")
        assert isinstance(provider, FakeProvider)

    def test_kwargs_passed_to_constructor(self):
        provider = get_embedding_provider("local", max_features=64)
        assert provider._max_features == 64
