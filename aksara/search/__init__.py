"""
Aksara Semantic Search & AI Index

v0.5.22: Cross-referenced code intelligence with semantic search.

Provides:
- SearchDocument: Structured document for indexing
- SearchResult: Ranked search result with score
- SearchIndex: In-memory search index with embedding support
- LocalEmbedder: Built-in TF-IDF embedding (no external deps)
- Index builders for models, routes, migrations, queries, tests, settings
"""

from aksara.search.engine import (
    SearchDocument,
    SearchResult,
    SearchIndex,
    SearchDocumentKind,
)
from aksara.search.embeddings import (
    BaseEmbeddingProvider,
    LocalTfIdfEmbedder,
    get_embedding_provider,
)
from aksara.search.indexers import (
    build_model_documents,
    build_route_documents,
    build_migration_documents,
    build_query_documents,
    build_settings_documents,
    build_playbook_documents,
    build_full_index,
)

__all__ = [
    # Engine
    "SearchDocument",
    "SearchResult",
    "SearchIndex",
    "SearchDocumentKind",
    # Embeddings
    "BaseEmbeddingProvider",
    "LocalTfIdfEmbedder",
    "get_embedding_provider",
    # Indexers
    "build_model_documents",
    "build_route_documents",
    "build_migration_documents",
    "build_query_documents",
    "build_settings_documents",
    "build_playbook_documents",
    "build_full_index",
]
