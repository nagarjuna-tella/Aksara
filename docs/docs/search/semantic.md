# Semantic Search Engine

Deep dive into the TF-IDF search engine powering Aksara's code intelligence.

## SearchDocument

Every indexed artifact becomes a `SearchDocument`:

```python
from aksara.search import SearchDocument

doc = SearchDocument(
    kind="model",              # Category (model, route, setting, etc.)
    title="User",              # Display title
    summary="User model with auth fields",
    content="Model: User\nTable: users\nFields: id, email, password_hash",
    metadata={"table_name": "users", "field_count": 3},
    tags=["model", "users", "auth"],
    source="model:User",
)
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Auto-generated UUID (16 hex chars) |
| `kind` | `Literal` | Document category |
| `title` | `str` | Human-readable title |
| `summary` | `str` | Short description |
| `content` | `str` | Full text for indexing |
| `metadata` | `dict` | Arbitrary key-value pairs |
| `tags` | `list[str]` | Filterable tags |
| `source` | `str` | Source identifier |
| `created_at` | `datetime` | Creation timestamp |

## SearchIndex

The in-memory search index:

```python
from aksara.search import SearchIndex, SearchDocument

index = SearchIndex()

# Add documents
index.add(doc)
index.add_many([doc1, doc2, doc3])

# Search
results = index.search(
    "user authentication",
    top_k=10,
    kind="model",        # Filter by kind
    tags=["auth"],       # Filter by tags
    min_score=0.1,       # Score threshold
    mode="hybrid",       # keyword, semantic, or hybrid
)

# Manage
index.remove(doc_id)
index.clear()
print(index.size)
print(index.stats())
```

## TF-IDF Engine

The built-in search uses **Term Frequency–Inverse Document Frequency** (TF-IDF):

1. **Tokenization**: Text is split into tokens, splitting camelCase and snake_case
2. **Stop word removal**: Common English words are filtered out
3. **TF computation**: Term frequency per document
4. **IDF computation**: Inverse document frequency across the corpus
5. **Cosine similarity**: Query vector compared against document vectors

### Scoring

- **Keyword mode**: Token overlap ratio (query tokens ∩ document tokens)
- **Semantic mode**: TF-IDF cosine similarity
- **Hybrid mode**: 40% keyword + 60% semantic (default, best overall)

## SearchResult

```python
@dataclass
class SearchResult:
    document: SearchDocument   # The matched document
    score: float              # 0.0 to 1.0
    highlights: list[str]     # Matched text snippets
    match_type: str           # "keyword", "semantic", or "hybrid"
```

## Embedding Providers

The `BaseEmbeddingProvider` protocol allows pluggable embedding backends:

```python
from aksara.search.embeddings import get_embedding_provider

# Built-in TF-IDF (default, no dependencies)
provider = get_embedding_provider("local")

# Custom provider
from aksara.search.embeddings import register_embedding_provider

class MyEmbedder:
    provider_name = "custom"
    dimensions = 384
    def embed(self, text): ...
    def embed_batch(self, texts): ...

register_embedding_provider("custom", MyEmbedder)
```
