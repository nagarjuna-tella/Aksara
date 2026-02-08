# Semantic Search & AI Index

Aksara v0.5.22 introduces **Semantic Search & AI Index** — a cross-referenced
code intelligence layer that indexes your models, routes, settings, migrations,
queries, and playbooks into a unified searchable index.

## Overview

| Feature | Description |
|---------|-------------|
| **SearchDocument** | Structured document with kind, title, summary, content, metadata |
| **SearchIndex** | In-memory TF-IDF index with keyword, semantic, and hybrid search |
| **LocalTfIdfEmbedder** | Built-in embedding provider (no external dependencies) |
| **Index Builders** | Auto-index models, routes, settings, playbooks, migrations, queries |
| **Studio Spotlight** | ⌘K / Ctrl+K command palette for instant project search |
| **CLI Search** | `aksara search query "..."` with JSON output for agent piping |
| **Agent Integration** | 12th context section (`semantic_index`) + new playbook |

## Quick Start

### In Code

```python
from aksara.search import SearchIndex, SearchDocument, build_full_index

# Build a full index from your project
index = build_full_index()

# Search across everything
results = index.search("user authentication", mode="hybrid", top_k=5)

for r in results:
    print(f"[{r.document.kind}] {r.document.title} — score: {r.score:.2f}")
```

### CLI

```bash
# Search your project
aksara search query "user model"

# Semantic search with kind filter
aksara search query "authentication" --kind route --semantic

# JSON output (pipe to agent mode)
aksara search query "database" --json | aksara agent

# Index statistics
aksara search index
```

### Studio Spotlight

Press **⌘K** (macOS) or **Ctrl+K** (Windows/Linux) to open the Spotlight
command palette. Type to search across all indexed project artifacts.

## Architecture

```
aksara/search/
├── __init__.py      # Package exports
├── engine.py        # SearchDocument, SearchResult, SearchIndex
├── embeddings.py    # BaseEmbeddingProvider, LocalTfIdfEmbedder
└── indexers.py      # Index builders for each artifact type
```

## Configuration

```python
from aksara.conf import Settings

settings = Settings(
    semantic_search_enabled=True,    # Enable/disable search (default: True)
    embedding_provider="local",      # Embedding backend (default: "local")
    embedding_model="local_tfidf",   # Model name (default: "local_tfidf")
    embedding_dimensions=512,        # Max dimensions (default: 512)
    search_index_backend="memory",   # Index storage (default: "memory")
)
```

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `AKSARA_SEMANTIC_SEARCH_ENABLED` | `true` | Enable semantic search |
| `AKSARA_EMBEDDING_PROVIDER` | `local` | Embedding provider name |
| `AKSARA_EMBEDDING_MODEL` | `local_tfidf` | Embedding model |
| `AKSARA_EMBEDDING_DIMENSIONS` | `512` | Vector dimensions |

## Document Kinds

Every indexed artifact is categorized by kind:

| Kind | Source | Description |
|------|--------|-------------|
| `model` | ModelRegistry | Registered Aksara models with fields and relations |
| `route` | FastAPI app | API endpoints with methods and paths |
| `migration` | MigrationGraph | Migration files with dependencies |
| `query` | Query Inspector | Recent slow queries with SQL and stats |
| `setting` | Settings dataclass | Configuration settings with env var info |
| `playbook` | Playbook registry | Agent playbooks with steps and categories |

## Search Modes

| Mode | Description |
|------|-------------|
| `keyword` | Token overlap scoring — fast and exact |
| `semantic` | TF-IDF cosine similarity — finds related concepts |
| `hybrid` | 40% keyword + 60% semantic — best overall (default) |
