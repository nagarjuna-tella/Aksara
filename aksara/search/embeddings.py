"""
Aksara Search — Embedding Providers.

v0.5.22: Built-in TF-IDF embedder (no external dependencies).
Extensible interface for OpenAI / Azure / Anthropic backends.
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


# =============================================================================
# Embedding Provider Protocol
# =============================================================================

@runtime_checkable
class BaseEmbeddingProvider(Protocol):
    """
    Protocol for embedding providers.

    Implementations must provide:
    - embed(text) -> List[float]: Embed a single text string.
    - embed_batch(texts) -> List[List[float]]: Embed multiple texts.
    - dimensions: int property for vector dimensionality.
    - provider_name: str property for display.
    """

    @property
    def provider_name(self) -> str: ...

    @property
    def dimensions(self) -> int: ...

    def embed(self, text: str) -> List[float]: ...

    def embed_batch(self, texts: List[str]) -> List[List[float]]: ...


# =============================================================================
# Stop Words & Tokenization (shared with engine.py but standalone here)
# =============================================================================

_STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "must", "shall", "can", "need",
    "it", "its", "this", "that", "these", "those", "not", "no", "so",
    "if", "then", "than", "too", "very", "just",
}

_TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")


def _tokenize_for_embed(text: str) -> List[str]:
    """Tokenize text for embedding — split camelCase, snake_case, lowercase."""
    expanded = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    expanded = expanded.replace("_", " ").replace("-", " ")
    tokens = _TOKEN_RE.findall(expanded.lower())
    return [t for t in tokens if t not in _STOP_WORDS and len(t) > 1]


# =============================================================================
# LocalTfIdfEmbedder — no external dependencies
# =============================================================================

class LocalTfIdfEmbedder:
    """
    Built-in TF-IDF based embedding provider.

    Uses a bag-of-words approach with TF-IDF weighting. The vocabulary
    is built from all texts passed to fit() or embed_batch(). Individual
    embed() calls use the existing vocabulary.

    This is a lightweight fallback — not as powerful as neural embeddings
    but requires no external dependencies.
    """

    def __init__(self, max_features: int = 512) -> None:
        self._max_features = max_features
        self._vocabulary: List[str] = []
        self._idf: Dict[str, float] = {}
        self._fitted = False

    @property
    def provider_name(self) -> str:
        return "local_tfidf"

    @property
    def dimensions(self) -> int:
        return len(self._vocabulary) if self._vocabulary else self._max_features

    def fit(self, texts: List[str]) -> None:
        """
        Build vocabulary and IDF from a corpus of texts.

        Call this before embed() to set up the vocabulary.
        embed_batch() calls fit() automatically.
        """
        all_tokens: List[List[str]] = [_tokenize_for_embed(t) for t in texts]
        n = len(all_tokens)

        # Count document frequency for each term
        df: Dict[str, int] = {}
        for tokens in all_tokens:
            seen = set(tokens)
            for term in seen:
                df[term] = df.get(term, 0) + 1

        # Sort by document frequency (descending), take top features
        sorted_terms = sorted(df.keys(), key=lambda t: df[t], reverse=True)
        self._vocabulary = sorted_terms[:self._max_features]

        # Compute smoothed IDF
        self._idf = {}
        for term in self._vocabulary:
            self._idf[term] = math.log((n + 1) / (df.get(term, 0) + 1)) + 1.0

        self._fitted = True

    def embed(self, text: str) -> List[float]:
        """
        Embed a single text into a TF-IDF vector.

        If fit() has not been called, returns a simple term presence vector
        built from the text's own tokens.
        """
        tokens = _tokenize_for_embed(text)

        if not self._fitted or not self._vocabulary:
            # Fallback: build a minimal vocabulary from this text alone
            unique = sorted(set(tokens))[:self._max_features]
            tf: Dict[str, float] = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            total = len(tokens) if tokens else 1
            return [tf.get(term, 0.0) / total for term in unique] if unique else [0.0]

        # Compute TF
        tf = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1
        total = len(tokens) if tokens else 1

        # TF-IDF vector against vocabulary
        vector = []
        for term in self._vocabulary:
            tf_val = tf.get(term, 0.0) / total
            idf_val = self._idf.get(term, 1.0)
            vector.append(tf_val * idf_val)

        # L2 normalize
        magnitude = math.sqrt(sum(v * v for v in vector))
        if magnitude > 0:
            vector = [v / magnitude for v in vector]

        return vector

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Embed multiple texts. Automatically fits the vocabulary first.
        """
        if not self._fitted:
            self.fit(texts)
        return [self.embed(text) for text in texts]


# =============================================================================
# Provider Factory
# =============================================================================

_PROVIDERS: Dict[str, type] = {
    "local": LocalTfIdfEmbedder,
    "local_tfidf": LocalTfIdfEmbedder,
}


def register_embedding_provider(name: str, cls: type) -> None:
    """Register a custom embedding provider class."""
    _PROVIDERS[name] = cls


def get_embedding_provider(
    provider: Optional[str] = None,
    **kwargs: Any,
) -> BaseEmbeddingProvider:
    """
    Get an embedding provider instance.

    Args:
        provider: Provider name. Defaults to AI Hub config, then "local" (built-in TF-IDF).
        **kwargs: Extra arguments passed to the provider constructor.

    Returns:
        An embedding provider instance.

    Raises:
        ValueError: If the provider name is not registered.
    """
    # v0.5.28: Try AI Hub defaults when no explicit provider given
    if provider is None:
        try:
            from aksara.ai.hub_settings import load_aihub_settings
            hub = load_aihub_settings()
            if hub.defaults and hub.defaults.embeddings_provider and hub.defaults.embeddings_model:
                # Only use hub default if the provider is registered
                hub_prov = hub.defaults.embeddings_provider
                if hub_prov in _PROVIDERS:
                    provider = hub_prov
                    kwargs.setdefault("model", hub.defaults.embeddings_model)
        except Exception:
            pass
    name = provider or "local"
    cls = _PROVIDERS.get(name)
    if cls is None:
        available = ", ".join(sorted(_PROVIDERS.keys()))
        raise ValueError(
            f"Unknown embedding provider '{name}'. Available: {available}"
        )
    return cls(**kwargs)
