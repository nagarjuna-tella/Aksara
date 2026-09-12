# Query profiling

**Evolving — development diagnostics.** Use query capture to check a small test's
query count, or tracing to inspect timed database calls. These tools help find
work to investigate; they are not a production monitoring or audit service.

`Aksara(debug=True)` does not enable trace collection. Tracing requires
`Settings(db_trace_enabled=True)` and a manual session or
`QueryTraceMiddleware`. Query capture works independently of that setting.

## Count and time a small database operation

Save this complete script as `query_examples.py`. It uses the `DATABASE_URL`
already configured for your [local PostgreSQL installation](../getting-started/installation.md).
It issues two parameterized, read-only queries and creates no tables.

```python title="query_examples.py"
import asyncio
import os

from aksara.conf import Settings, configure
from aksara.db import (
    Database,
    capture_queries,
    start_trace_session,
    stop_trace_session,
)


async def inspect_queries(db):
    start_trace_session(request_id="local-example")
    try:
        async with capture_queries() as log:
            value = await db.fetchval("SELECT $1::integer", 7)
            rows = await db.fetch("SELECT $1::text AS label", "example")
    finally:
        batch = stop_trace_session()

    assert value == 7 and rows[0]["label"] == "example"
    assert log.count == 2
    assert batch is not None and batch.total_queries == 2
    return log, batch


async def main():
    configure(Settings(db_trace_enabled=True))
    db = Database(os.environ["DATABASE_URL"])
    await db.connect()
    try:
        log, batch = await inspect_queries(db)
        print(f"Captured calls: {log.count}")
        print(f"Recorded duration: {batch.total_duration_ms:.3f} ms")
    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
```

Run `python query_examples.py` in the environment where Aksara is installed.
The count is two; timing varies. In an existing application, configure tracing
at startup alongside your other settings and pass its connected `Database`
instance to the helper. Do not replace application settings per request.

`capture_queries()` is an **async** context manager exported from `aksara.db`.
Its `QueryLog` has `.count` and `.queries`; events contain SQL and parameters,
but their `duration_ms` is not populated by this capture path. Use the trace
batch for timing. There is no `aksara.testing.QueryCounter` API.

Query capture uses one process-global active log. Use it in isolated tests:
unrelated concurrent tasks can contribute calls, and nested captures temporarily
replace the outer log rather than counting their calls in both. It is not a
per-request collector. See the [testing guide](../advanced/testing.md) for
application test setup.

## Correlate a request with its queries

Use request-ID middleware outside trace middleware, in the order below. Call
this factory with your application's connected database and manage its lifetime
through your application's startup/shutdown flow.

```python title="request_queries.py"
from aksara import Aksara
from aksara.middleware import QueryTraceMiddleware, RequestIDMiddleware


def create_query_example(db):
    app = Aksara(
        database_url=None,
        auto_discover=False,
        enable_admin=False,
        middlewares=[
            (RequestIDMiddleware, {}),
            (QueryTraceMiddleware, {}),
        ],
    )

    @app.get("/query-example")
    async def query_example():
        value = await db.fetchval("SELECT $1::integer", 7)
        return {"value": value}

    return app
```

With tracing enabled, a successful request returns `{"value": 7}` and an
`X-Request-ID` header. After the response, inspect that batch **in the same
server process** with `aksara.db.get_trace_by_request_id(request_id)`.
`get_recent_traces()` returns recent batches and `clear_traces()` clears that
process's stored batches. A separate Python process or CLI invocation does not
share the server's in-memory history.

Request IDs are correlation values, not authenticated identities. An incoming
`X-Request-ID` can be reused by a client; storing the same ID replaces its prior
batch. Without an ID, a manual session still returns a batch, but it is not
retained in recent history. The request middleware stops collection when the
response is produced; do not use its totals to certify streaming or background
work after that point.

## Interpret the measurements

| Setting / result | Meaning |
|---|---|
| `db_trace_enabled` | Defaults to `False`; enables starting and recording trace sessions. |
| `db_trace_slow_threshold_ms` | Defaults to `100.0`; a recorded duration at or above this value is slow. |
| `db_trace_max_queries` | Defaults to `500`; additional calls are omitted from a session after this count. Configure a positive limit. |
| `batch.total_queries` | Recorded calls, which may be capped; not necessarily every database operation. |
| `batch.total_duration_ms` | Sum of recorded call durations; not total request duration or database-server execution time alone. |
| `batch.slow_queries` | Number of recorded calls meeting the snapshotted threshold. |
| `batch.n_plus_one_suspicions` | Heuristic messages for repeated query shapes; investigate rather than assuming a relation-loading defect. |

The instrumented `Database.execute`, `fetch`, `fetchrow`, and `fetchval` paths
record calls, including failed calls. Timings include connection acquisition
and client-side work within those methods. Row counts are not automatically
populated by these paths. SQL and table classification are best-effort, not a
SQL parser. Direct asyncpg connection calls bypass this instrumentation.

Tracing uses the current context, but it is not a nested-session stack. Finish
a manual session in `finally`, avoid overlapping sessions in the same context,
and keep traced work within its lifetime. The threshold and count limit are
snapshotted when a session starts. Stored history holds at most 100 identified
batches in each process and disappears on restart.

## Investigate the cause

For repeated relation reads, compare an actual query count before and after
using [eager loading](../orm/relations.md). A forward foreign-key attribute
is its stored ID; it is not an awaitable object accessor. Follow the relationship
guide for `select_related()` and `get_related()` rather than assuming that
reading `post.author` performs a query.

For a query plan, run explicit PostgreSQL `EXPLAIN` through a database tool or
`Database.fetch`; the trace batch does not automatically contain plans. For
example, `EXPLAIN (FORMAT JSON) SELECT 1` explains a read-only query. `EXPLAIN
ANALYZE` executes the statement being analyzed, so choose the statement and
environment deliberately. Tracing does not automatically create indexes or
apply query optimizations.

Keep raw traces private. SQL literals and bound parameters are retained without
secret redaction. Avoid exporting entire batches to responses or general logs;
prefer selected counts and timing summaries. Process-local tracing does not
supply access control, tenant-safe retention, durable audit storage, or a shared
cross-worker view. See [production guidance](../tutorials/deployment.md) for the
operator responsibilities beyond local diagnostics.
