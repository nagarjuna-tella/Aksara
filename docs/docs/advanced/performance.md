# Application performance

Measure a representative application path before changing it. Record the data
volume, query count, latency distribution, concurrency, database role, and
runtime versions. A local smoke check is not a throughput guarantee.

## Bound database work

Use explicit QuerySet limits and deterministic ordering. The
[querying guide](../orm/querying.md) demonstrates these operations against the
tutorial Ticket model. Start pagination with a QuerySet, not a manager-level
`limit()` call or a slice of the async `.all()` method.

For generated APIs, use the actual [ViewSet](../api/viewsets.md) limits and
supported filter backends. `page_size` is not a general ModelViewSet switch.
Avoid unbounded reads merely to compute a count or check existence: use the
terminal `.count()` or `.exists()` query methods.

The ordinary Manager/QuerySet does not offer `only()` or `defer()`. Shaping a
small result into a dictionary in Python does not reduce columns fetched by
SQL. Do not describe that transformation as database projection.

## Load related objects deliberately

Forward foreign-key attributes hold identifiers. Accessing or awaiting
`post.author` does not lazily fetch an author object. Use an explicit query or
`select_related()` followed by `get_related()` as described in
[relations](../orm/relations.md).

Use only supported prefetch paths and accessors. Do not assume arbitrary nested
prefetch traversal or collection iteration matches another ORM. Measure actual
queries on the relationship shape you use; an illustrative query count is not a
guarantee for every combination of relations and filters.

## Index the workload

Declare supported indexes through [model metadata](../orm/model-meta.md) and
apply them through migrations. An index that helps one read pattern can add
write and storage cost. Inspect the deployed PostgreSQL schema and query plan
before concluding an index is present or used.

There is no documented QuerySet `.explain()` shortcut here. Use PostgreSQL
planning tools through your database tooling for the actual SQL and bound
values. `EXPLAIN ANALYZE` executes its statement; use an appropriate test
environment for statements with effects. Do not include credentials or
sensitive values in profiling artifacts.

## Keep serialization predictable

Use the supported [serializer](../api/serializers.md) hooks and relation
expansion contract. DRF-style `SerializerMethodField` and declarative
`serializers.String(source=...)` recipes are not Aksara APIs. Avoid hidden
per-row database operations in application transformation code, and measure
both database work and output size.

## Concurrency and transactions

Async functions allow other work to proceed while awaiting I/O. They do not
make one database connection safe for overlapping queries. Inside
`transaction.atomic()`, run participating database operations sequentially on
the pinned connection; do not use `asyncio.gather()` to share it across child
tasks.

Independent pool connections can execute independent work, but do not join the
same atomic transaction. Keep transaction duration short and avoid waiting on
remote services while holding database locks. See
[transaction limits](../orm/expressions-and-transactions.md).

## Caching and background work

Aksara has no public general-purpose `aksara.cache` API. Application caches
need explicit tenant keys, invalidation, lifetime, and authorization rules;
see [caching](caching.md). Cache hits must not substitute stale access decisions
for current policy.

Use [ordinary tasks](background-tasks.md) when their execution semantics fit.
Use [Durable Operations](durable-operations.md) when recovery and authorization
across time are required. Moving work to a worker does not reduce its resource
cost or prove a performance improvement; measure queue delay and completion
latency as well as request latency.

## Validate the change

Compare the same workload before and after, including error rates, pool waits,
and database resource use. Preserve authorization, tenant isolation, validation,
and transaction guarantees in the test. Do not remove those checks to produce
a faster benchmark.

The [production guide](../tutorials/deployment.md) and
[diagnostics](../diagnostics.md) cover operational checks. Doctor readiness
is not a load-test result or a capacity estimate.
