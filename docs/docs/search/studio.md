# Studio Spotlight Search

The Studio Spotlight is a command palette for instant project search,
accessible via **⌘K** (macOS) or **Ctrl+K** (Windows/Linux).

## Features

- **Fuzzy + Semantic search** across all indexed artifacts
- **Category filters**: Models, Routes, Settings, Playbooks, Migrations, Queries
- **Keyboard navigation**: Arrow keys, Enter to navigate, Tab to preview, Esc to close
- **Preview pane**: View document details without leaving the spotlight
- **Real-time results**: Debounced search as you type

## API Endpoints

### GET `/studio/search/index`

Returns index statistics:

```json
{
  "total_documents": 42,
  "by_kind": {"model": 10, "route": 15, "setting": 12, "playbook": 5},
  "vocabulary_size": 256,
  "kinds_available": ["model", "route", "setting", "playbook"],
  "embedding_provider": "local_tfidf"
}
```

### POST `/studio/search/query`

Search the index:

```json
{
  "query": "user authentication",
  "top_k": 10,
  "kind": "model",
  "mode": "hybrid",
  "min_score": 0.1
}
```

Response:

```json
{
  "query": "user authentication",
  "total_results": 3,
  "results": [
    {
      "id": "abc123",
      "kind": "model",
      "title": "User",
      "summary": "User model (users) with 5 fields",
      "score": 0.92,
      "highlights": ["...user authentication login..."],
      "match_type": "hybrid",
      "source": "model:User"
    }
  ],
  "mode": "hybrid",
  "index_size": 42
}
```

### POST `/studio/search/rebuild`

Force rebuild the search index:

```json
{
  "status": "rebuilt",
  "total_documents": 42,
  "by_kind": {"model": 10, "route": 15}
}
```
