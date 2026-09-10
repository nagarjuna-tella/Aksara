# Runtime compatibility

The v0.6 release line supports Python 3.11–3.14. The release matrix runs
Python 3.11 and 3.14 with PostgreSQL 16 plus pgvector at both supported web
dependency boundaries. The packaged reference gate also runs against local
PostgreSQL 18.4. This is the tested matrix, not certification of every operating
system, intermediate dependency combination, or PostgreSQL extension.

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

The v0.6 production profile also requires migrations as a separate deployment
step, a non-superuser/non-BYPASSRLS application role, forced RLS for tenant
tables, and a clean `aksara doctor production-check --release`. Studio,
process-local investigation state, and autonomous AI durability remain outside
the production stability guarantee. Investigation state does not survive
restart or provide multi-worker continuity.

See the [v0.6 stability and production contract](../roadmap/v0-6-stability-contract.md)
for the complete boundary.
