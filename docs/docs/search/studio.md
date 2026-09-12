# Studio project search

**Experimental Studio surface.** Spotlight searches indexed project descriptions.
It does not enforce application-record tenancy or replace a protected search API.
Use the [Studio setup guide](../getting-started/studio.md) for access configuration;
do not expose developer diagnostics as an ordinary application feature.

## HTTP surface

When Studio's router is enabled, its declared routes include:

| Route | Operation |
| --- | --- |
| `GET /studio/search/index` | Index counts, kinds and vocabulary information |
| `POST /studio/search/query` | Search with query, limit, kind(s), tags, score and mode |
| `POST /studio/search/rebuild` | Rebuild the cached index from current sources |

Responses vary with imported models, application routes and retained process
state. Search results contain artifact descriptions and identifiers rather than
queried business records. The reported provider label `local_tfidf` describes
local scoring, not an external model call.

## Cache and scope

Studio uses a lazily built module-level index cache. Rebuild refreshes that cache
in the handling process; it is not a cross-worker refresh operation. The cache is
not partitioned by tenant or application instance. Avoid treating results as an
authorization-filtered view, especially when multiple applications share a process.

The Spotlight UI can display these results, but keyboard interactions and Studio
internals remain experimental. For a small reproducible Python example, use the
[local search engine](semantic.md). For ordinary application queries, start with
[ORM querying](../orm/querying.md).
