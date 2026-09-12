# Project search

**Experimental developer tooling.** Aksara's project search indexes descriptions
of models, routes, settings, migrations, retained queries, and playbooks. It is
not an application-record search API, vector database, or authorization boundary.

Start with the [local engine example](semantic.md) to search a small controlled
collection without a database, provider, or network call. For project discovery,
`build_full_index(app=None, *, include_models=True, include_routes=True,
include_migrations=True, include_queries=True, include_settings=True,
include_playbooks=True)` builds a fresh in-memory index from available sources.
Import your model modules first and supply your application for route discovery.
Results depend on what those sources expose in the current process; this is not
a complete repository or database crawl.

The engine's `semantic` mode means TF-IDF cosine similarity over words. It does
not establish understanding of synonyms, intent, or code semantics. Hybrid mode
combines keyword and TF-IDF scores; no benchmark establishes it as universally
better for your corpus.

`SearchIndex` implements its own local scoring and does not select a provider
from `embedding_provider`, `embedding_model`, or `embedding_dimensions` settings.
The separate embedding-provider registry can be used directly by applications;
registering a provider does not make the index use it. Do not infer persistence,
remote embeddings, or service enablement from configuration names alone.

See [Studio search](studio.md) for its process-local cache and access boundary.
Keep indexed SQL, settings, and model details private. Search kind/tag filters
are retrieval filters, not tenant authorization.
