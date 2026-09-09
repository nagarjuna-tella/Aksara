# Runtime compatibility

The unpublished v0.5.55 candidate supports Python 3.11–3.14. Release CI uses
Python 3.11 and 3.14 with PostgreSQL 16 plus pgvector. Local verification also
uses PostgreSQL 18.4. This is the validation matrix, not certification of every
operating system or PostgreSQL extension.

| Web boundary | FastAPI | Starlette |
| --- | --- | --- |
| Minimum | 0.136.1 | 1.0.1 |
| Latest supported | 0.141.1 | 1.6.0 |

The package bounds these dependencies to the reviewed interval. CI explicitly
installs and tests both pairs; intermediate combinations are not individually
certified. Do not upgrade beyond the declared interval without re-running the
release suite. Increasing the upper bound requires the same discovery and HTTP
contract tests. A lower-bound pass does not excuse an upper-bound failure.

## Inspecting routes

FastAPI can retain included routers rather than flattening them into `app.routes`.
Use `aksara.routing.iter_routes(app)` to inspect effective paths, methods, endpoints
and include-time metadata. It applies nested prefixes without changing FastAPI's
routing tree. Returned objects are metadata views, not routes to mutate. Mounts
remain mounts; the helper does not enumerate the contents of a static directory.

```python
from aksara.routing import iter_routes

for route in iter_routes(app):
    print(route.path, route.methods)
```

## Cleanup and deployment scope

Session/transaction contexts own connections they acquire and borrow connections
already held by an enclosing transaction. Setup errors and cancellation restore
session context and return owned pool capacity. Cleanup errors are attached to
an existing error rather than replacing it. Real-pool regressions exercise
repeated failures with a one-connection pool.

This is a correctness release, not a v0.6 Production Mode announcement. Studio,
process-local investigation state and autonomous AI durability are outside a
production stability guarantee. Investigation state does not survive restart or
provide multi-worker continuity.
