"""
Aksara Search Engine — Core types and in-memory index.

v0.5.22: SearchDocument, SearchResult, SearchIndex with cosine similarity.
"""

from __future__ import annotations

import math
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Sequence, Set, Tuple


# =============================================================================
# Document Kinds
# =============================================================================

SearchDocumentKind = Literal[
    "model",
    "route",
    "migration",
    "query",
    "file",
    "test",
    "setting",
    "playbook",
    "agent_section",
]


# =============================================================================
# SearchDocument
# =============================================================================

@dataclass
class SearchDocument:
    """
    A single indexed document for search.

    Attributes:
        id: Unique document identifier (auto-generated UUID if not provided).
        kind: Category of the document (model, route, migration, etc.).
        title: Human-readable title for display.
        summary: Short description (1-2 sentences).
        content: Full text content for indexing and search.
        metadata: Arbitrary key-value metadata (table name, method, etc.).
        tags: Optional tags for filtering.
        source: Optional source identifier (filename, model name, etc.).
        created_at: Timestamp when document was created.
    """

    kind: SearchDocumentKind
    title: str
    summary: str
    content: str
    id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    source: str = ""
    created_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not self.id:
            self.id = uuid.uuid4().hex[:16]
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for JSON output."""
        return {
            "id": self.id,
            "kind": self.kind,
            "title": self.title,
            "summary": self.summary,
            "content": self.content,
            "metadata": self.metadata,
            "tags": self.tags,
            "source": self.source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# =============================================================================
# SearchResult
# =============================================================================

@dataclass
class SearchResult:
    """
    A ranked search result.

    Attributes:
        document: The matched document.
        score: Relevance score (0.0 to 1.0, higher = more relevant).
        highlights: Extracted text snippets with matches.
        match_type: How the match was found (keyword, semantic, hybrid).
    """

    document: SearchDocument
    score: float
    highlights: List[str] = field(default_factory=list)
    match_type: str = "keyword"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for JSON output."""
        return {
            "document": self.document.to_dict(),
            "score": round(self.score, 4),
            "highlights": self.highlights,
            "match_type": self.match_type,
        }


# =============================================================================
# Text Processing Helpers
# =============================================================================

_STOP_WORDS: Set[str] = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "must", "shall", "can", "need",
    "it", "its", "this", "that", "these", "those", "i", "you", "he",
    "she", "we", "they", "me", "him", "her", "us", "them", "my", "your",
    "his", "our", "their", "not", "no", "nor", "so", "if", "then",
    "than", "too", "very", "just", "about", "above", "after", "before",
    "between", "into", "through", "during", "each", "few", "more",
    "most", "other", "some", "such", "only", "own", "same",
}

_SPLIT_RE = re.compile(r"[a-zA-Z0-9]+")


def _tokenize(text: str) -> List[str]:
    """Tokenize text into lowercase words, splitting camelCase and snake_case."""
    # Split on non-alphanumeric, then split camelCase
    expanded = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    expanded = expanded.replace("_", " ").replace("-", " ")
    tokens = _SPLIT_RE.findall(expanded.lower())
    return [t for t in tokens if t not in _STOP_WORDS and len(t) > 1]


def _extract_highlights(content: str, query_tokens: List[str], max_highlights: int = 3) -> List[str]:
    """Extract text snippets around matched tokens."""
    highlights: List[str] = []
    content_lower = content.lower()
    seen_positions: Set[int] = set()

    for token in query_tokens:
        pos = content_lower.find(token)
        while pos >= 0 and len(highlights) < max_highlights:
            # Avoid overlapping highlights
            window_key = pos // 60
            if window_key not in seen_positions:
                seen_positions.add(window_key)
                start = max(0, pos - 40)
                end = min(len(content), pos + len(token) + 40)
                snippet = content[start:end].strip()
                if start > 0:
                    snippet = "..." + snippet
                if end < len(content):
                    snippet = snippet + "..."
                highlights.append(snippet)
            pos = content_lower.find(token, pos + len(token))

    return highlights[:max_highlights]


# =============================================================================
# TF-IDF Helpers (pure Python, no external deps)
# =============================================================================

def _compute_tf(tokens: List[str]) -> Dict[str, float]:
    """Compute term frequency for a token list."""
    if not tokens:
        return {}
    counts: Dict[str, int] = {}
    for t in tokens:
        counts[t] = counts.get(t, 0) + 1
    total = len(tokens)
    return {t: c / total for t, c in counts.items()}


def _compute_idf(corpus_tokens: List[List[str]], vocabulary: List[str]) -> Dict[str, float]:
    """Compute inverse document frequency for each term in vocabulary."""
    n = len(corpus_tokens)
    if n == 0:
        return {}
    idf: Dict[str, float] = {}
    for term in vocabulary:
        doc_count = sum(1 for doc_tokens in corpus_tokens if term in set(doc_tokens))
        idf[term] = math.log((n + 1) / (doc_count + 1)) + 1.0  # smoothed IDF
    return idf


def _tfidf_vector(tf: Dict[str, float], idf: Dict[str, float], vocabulary: List[str]) -> List[float]:
    """Compute TF-IDF vector for a document against a vocabulary."""
    return [tf.get(term, 0.0) * idf.get(term, 0.0) for term in vocabulary]


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    mag_a = math.sqrt(sum(a * a for a in vec_a))
    mag_b = math.sqrt(sum(b * b for b in vec_b))
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return dot / (mag_a * mag_b)


# =============================================================================
# SearchIndex
# =============================================================================

class SearchIndex:
    """
    In-memory search index with TF-IDF based semantic search.

    Supports:
    - Adding and removing documents
    - Keyword search (token overlap scoring)
    - Semantic search (TF-IDF cosine similarity)
    - Hybrid search (combined keyword + semantic)
    - Filtering by kind and tags
    """

    def __init__(self) -> None:
        self._documents: Dict[str, SearchDocument] = {}
        self._tokens_cache: Dict[str, List[str]] = {}
        # TF-IDF state (rebuilt on index changes)
        self._vocabulary: List[str] = []
        self._idf: Dict[str, float] = {}
        self._tfidf_vectors: Dict[str, List[float]] = {}
        self._dirty: bool = True

    @property
    def size(self) -> int:
        """Number of documents in the index."""
        return len(self._documents)

    def add(self, doc: SearchDocument) -> None:
        """Add a document to the index."""
        self._documents[doc.id] = doc
        content = f"{doc.title} {doc.summary} {doc.content} {' '.join(doc.tags)}"
        self._tokens_cache[doc.id] = _tokenize(content)
        self._dirty = True

    def add_many(self, docs: Sequence[SearchDocument]) -> int:
        """Add multiple documents. Returns count added."""
        for doc in docs:
            self.add(doc)
        return len(docs)

    def remove(self, doc_id: str) -> bool:
        """Remove a document by ID. Returns True if found and removed."""
        if doc_id in self._documents:
            del self._documents[doc_id]
            self._tokens_cache.pop(doc_id, None)
            self._tfidf_vectors.pop(doc_id, None)
            self._dirty = True
            return True
        return False

    def get(self, doc_id: str) -> Optional[SearchDocument]:
        """Get a document by ID."""
        return self._documents.get(doc_id)

    def all_documents(self) -> List[SearchDocument]:
        """Return all documents."""
        return list(self._documents.values())

    def clear(self) -> None:
        """Remove all documents from the index."""
        self._documents.clear()
        self._tokens_cache.clear()
        self._vocabulary.clear()
        self._idf.clear()
        self._tfidf_vectors.clear()
        self._dirty = True

    def kinds(self) -> List[str]:
        """Return unique document kinds in the index."""
        return list(set(doc.kind for doc in self._documents.values()))

    def count_by_kind(self) -> Dict[str, int]:
        """Return document count per kind."""
        counts: Dict[str, int] = {}
        for doc in self._documents.values():
            counts[doc.kind] = counts.get(doc.kind, 0) + 1
        return counts

    def _rebuild_tfidf(self) -> None:
        """Rebuild TF-IDF index from all documents."""
        if not self._dirty:
            return

        all_tokens = list(self._tokens_cache.values())
        doc_ids = list(self._tokens_cache.keys())

        # Build vocabulary from all tokens
        vocab_set: Set[str] = set()
        for tokens in all_tokens:
            vocab_set.update(tokens)
        self._vocabulary = sorted(vocab_set)

        # Compute IDF
        self._idf = _compute_idf(all_tokens, self._vocabulary)

        # Compute TF-IDF vectors for each document
        self._tfidf_vectors.clear()
        for doc_id, tokens in zip(doc_ids, all_tokens):
            tf = _compute_tf(tokens)
            self._tfidf_vectors[doc_id] = _tfidf_vector(tf, self._idf, self._vocabulary)

        self._dirty = False

    def search(
        self,
        query: str,
        *,
        top_k: int = 10,
        kind: Optional[str] = None,
        kinds: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        min_score: float = 0.0,
        mode: str = "hybrid",
    ) -> List[SearchResult]:
        """
        Search the index.

        Args:
            query: Search query string.
            top_k: Maximum number of results to return.
            kind: Filter to a single document kind (shortcut for kinds=[kind]).
            kinds: Filter to specific document kinds.
            tags: Filter to documents with any of these tags.
            min_score: Minimum score threshold (0.0 to 1.0).
            mode: Search mode — "keyword", "semantic", or "hybrid" (default).

        Returns:
            List of SearchResult, sorted by descending score.
        """
        if not query or not self._documents:
            return []

        # Build kind filter
        kind_filter: Optional[Set[str]] = None
        if kind:
            kind_filter = {kind}
        elif kinds:
            kind_filter = set(kinds)

        # Filter documents
        candidates: Dict[str, SearchDocument] = {}
        for doc_id, doc in self._documents.items():
            if kind_filter and doc.kind not in kind_filter:
                continue
            if tags and not set(tags).intersection(set(doc.tags)):
                continue
            candidates[doc_id] = doc

        if not candidates:
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        results: List[SearchResult] = []

        if mode in ("keyword", "hybrid"):
            # Keyword scoring: token overlap ratio
            for doc_id, doc in candidates.items():
                doc_tokens = set(self._tokens_cache.get(doc_id, []))
                if not doc_tokens:
                    continue
                overlap = len(set(query_tokens) & doc_tokens)
                if overlap == 0:
                    continue
                kw_score = overlap / max(len(query_tokens), 1)
                highlights = _extract_highlights(doc.content or doc.summary, query_tokens)
                results.append(SearchResult(
                    document=doc,
                    score=kw_score,
                    highlights=highlights,
                    match_type="keyword",
                ))

        if mode in ("semantic", "hybrid"):
            # Rebuild TF-IDF if dirty
            self._rebuild_tfidf()

            # Compute query vector
            query_tf = _compute_tf(query_tokens)
            query_vec = _tfidf_vector(query_tf, self._idf, self._vocabulary)

            for doc_id, doc in candidates.items():
                doc_vec = self._tfidf_vectors.get(doc_id)
                if not doc_vec:
                    continue
                sem_score = _cosine_similarity(query_vec, doc_vec)
                if sem_score <= 0.0:
                    continue

                # In hybrid mode, merge with existing keyword score
                if mode == "hybrid":
                    existing = next((r for r in results if r.document.id == doc_id), None)
                    if existing:
                        # Weighted combination: 40% keyword + 60% semantic
                        existing.score = 0.4 * existing.score + 0.6 * sem_score
                        existing.match_type = "hybrid"
                        continue

                highlights = _extract_highlights(doc.content or doc.summary, query_tokens)
                results.append(SearchResult(
                    document=doc,
                    score=sem_score,
                    highlights=highlights,
                    match_type="semantic",
                ))

        # Filter by min_score and sort
        results = [r for r in results if r.score >= min_score]
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    def stats(self) -> Dict[str, Any]:
        """Return index statistics."""
        return {
            "total_documents": self.size,
            "by_kind": self.count_by_kind(),
            "vocabulary_size": len(self._vocabulary),
            "is_dirty": self._dirty,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the index state."""
        return {
            "stats": self.stats(),
            "documents": [doc.to_dict() for doc in self._documents.values()],
        }
