# Models and persistence

**Stable within the declared PostgreSQL contract.** Aksara's ORM maps model
fields to database columns and provides asynchronous methods for reading and
writing records. It is PostgreSQL-specific; it does not provide interchangeable
SQLite or MySQL backends.

Start with the [ticket desk](../getting-started/first-project.md) for a complete
installed-package application, database configuration, migration and HTTP tests.
This page explains the persistence concepts used by that application.

## Models describe tables; migrations change them

A model declares the data an application stores. Aksara supplies a UUID primary
key by default, along with its inherited timestamp fields. Declaring or importing
a model does not create its table. Generate and inspect migrations, then apply
them before running application code that depends on the new schema.

The [model guide](models.md) explains declaration and defaults. The
[field reference](fields.md) lists supported types, validation and options.
[Migration guidance](migrations.md) explains schema changes, and
[migration safety](migration-safety.md) describes transactional application,
checksums and deployment responsibilities. Generated migration SQL still needs
review; an ORM does not make arbitrary SQL or destructive schema changes safe.

## Build a query, then execute it

A query builder describes work without executing it. Call a terminal method
such as `all()`, `first()`, `get()` or `count()` and await that operation.

With the tutorial database connected and its Ticket model migrated, this
fragment reads unresolved tickets:

```python
from app.models import Ticket

query = Ticket.objects.filter(resolved=False)
tickets = await query.all()
```

Do not write `await query`: QuerySet itself is not awaitable. A manager's
`all()` is asynchronous too; omitting `await` gives a coroutine, not records.

The [query guide](querying.md) covers filters, explicit negation with `Q`,
ordering, aggregates and projections. Bound large result sets deliberately;
async execution does not make an unbounded query inexpensive. Use supported
parameterized query methods and validate any application-owned raw SQL or
identifier construction separately.

## Relations store identities

Foreign keys connect records. Forward attributes and their `*_id` aliases expose
the stored related ID; they do not asynchronously fetch an object when accessed.
Load a related object explicitly, or use `select_related()` followed by
`get_related()` for the eager result. Reverse relation managers provide their
own asynchronous query methods.

The [relations guide](relations.md) explains foreign keys, one-to-one and
many-to-many behavior. Object-valued lazy forward foreign keys and custom
many-to-many through models remain outside the supported contract. Do not infer
Django compatibility from similar names.

## Writes, validation and transactions

`create()`, instance `save()`/`delete()`, and queryset update/delete methods
perform database work. Field conversion and validation apply on their supported
write paths. HTTP serializers, request permissions and application business
rules are separate layers; an arbitrary ORM call does not automatically run
those request checks.

Use an explicit transaction when several supported database writes must commit
or roll back together. Keep them on the same Aksara database/session boundary.
A database rollback does not undo email, uploaded bytes, network calls or
already-observed signal callbacks. See [expressions and transactions](expressions-and-transactions.md)
and [signals](signals.md).

[Bulk operations](bulk-operations.md) have distinct batching, validation and
hook behavior, including documented limitations. Do not assume a bulk method
is equivalent to repeatedly calling instance `save()` in one transaction.
[Durable Operations](../advanced/durable-operations.md) add a separate, opt-in
contract for authorized work that must survive process loss or time.

## Find the relevant reference

| Task | Guide |
| --- | --- |
| Define records and fields | [Models](models.md), [Fields](fields.md) |
| Filter, sort, count or aggregate | [Querying](querying.md) |
| Load related records | [Relations](relations.md) |
| Evolve the database schema | [Migrations](migrations.md) |
| Inspect declared model metadata | [Model metadata](model-meta.md) |
| Group database writes | [Expressions and transactions](expressions-and-transactions.md) |
| Use bulk writes | [Bulk operations](bulk-operations.md) |
| Handle soft deletion or fixture data | [Soft deletes](soft-deletes.md), [Fixtures](fixtures.md) |
| Check the supported surface | [ORM reference](../reference/orm-reference.md), [v0.7 contract](../roadmap/v0-7-stability-contract.md) |
