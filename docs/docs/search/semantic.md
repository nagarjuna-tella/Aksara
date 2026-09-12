# Local search engine

**Experimental developer tooling.** The local index is suitable for trying
project-artifact retrieval; validate relevance on your own data before depending
on it. It does not contact an embedding provider.

## Complete example

This module creates a private in-memory collection and searches it:

```python title="local_search.py"
from aksara.search import SearchDocument, SearchIndex

index = SearchIndex()
index.add_many([
    SearchDocument(
        id="auth", kind="model", title="Account authentication",
        summary="Account login and credentials", content="Authenticate an account",
        tags=["identity"],
    ),
    SearchDocument(
        id="billing", kind="route", title="Invoice payment",
        summary="Pay an invoice", content="Record a billing payment",
        tags=["billing"],
    ),
])
results = index.search("authentication", mode="hybrid", kind="model", top_k=5)
matched_ids = [result.document.id for result in results]
```

`matched_ids` is `["auth"]`. Each result contains its document, score, highlights,
and `match_type`. Scores are ranking values, not probabilities or confidence
that the result is correct.

## Documents and updates

`SearchDocument` requires `kind`, `title`, `summary`, and `content`. Optional fields
include `id`, `metadata`, `tags`, `source`, and `created_at`. Without an ID it uses
a 16-character UUID-derived hexadecimal string; without a timestamp it records
creation time. Supply IDs when reproducible identity matters.

`index.add(document)` replaces a document with the same ID. `add_many(documents)`
returns the number supplied, not the number of new unique IDs. `get(id)` returns
a document or `None`; `remove(id)` returns whether it existed. `clear()` empties
the index. These are memory operations, not durable storage.

The index caches tokenized text. After changing a document's searchable content,
call `add(document)` again; mutating the returned object does not refresh those
cached tokens. `stats()` reports counts, vocabulary size and `is_dirty`; vocabulary
is rebuilt lazily for semantic/hybrid queries and can lag additions before then.

## Query options

`search(query, *, top_k=10, kind=None, kinds=None, tags=None, min_score=0.0,
mode="hybrid")` returns results in descending score order.

- `kind` takes precedence over `kinds` when supplied.
- `tags` matches any supplied tag, not all tags.
- `keyword` uses token overlap; `semantic` uses local TF-IDF cosine similarity.
- `hybrid` weights matching keyword and semantic results 40%/60% when merged.
- Empty queries and collections produce no results.

Use valid mode names and positive result limits. The direct Python interface is
not an input-validation or access-control layer. Populate only documents the
caller may read, and recheck permissions before using a retrieved artifact.
