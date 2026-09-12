# ORM Reference

Aksara's ORM targets PostgreSQL. Start with the
[first project](../getting-started/first-project.md) for a migrated, runnable
model and API. This page summarizes the manager/query boundary and directs you
to the detailed field, relation, and migration references.

## Field types and options

Import `Model` and `fields` from `aksara`. Use `nullable=True` for nullable
fields, not Django's `null=True`. The common base-field options are `nullable`,
`default`, `unique`, `primary_key`, `db_index`, `ai_description`, `ai_sensitive`,
and `ai_agent_writable`. Type-specific constructors add their own options.
Do not assume `blank`, `choices`, `validators`, `db_column`, or `verbose_name`
are accepted by all fields.

- [Fields](../orm/fields.md) covers concrete field types and constructor options.
- [Advanced field policy](../orm/advanced-field-policy.md) explains validation and policy boundaries.
- [Media and email](../advanced/media-and-email.md) explains file storage and its known limitations.

## QuerySet methods

Build a query synchronously, then await a terminal operation. For the tutorial
Ticket model, this is a query-building example that does not access a database:

```python title="query_shape.py"
import inspect

from aksara import Model, fields
from aksara.manager import QuerySet


class ReferenceTicket(Model):
    subject = fields.String(max_length=200)
    resolved = fields.Boolean(default=False)


query = ReferenceTicket.objects.filter(resolved=False).order_by("subject").limit(10).offset(0)
assert isinstance(query, QuerySet)
assert not inspect.isawaitable(query)
assert inspect.iscoroutinefunction(query.all)
```

To execute that query in a configured, migrated application, use
`rows = await query.all()`. It returns a list of model instances. Do not use
`await Model.objects.filter(...)` or slice `Model.objects.all()`; the query is
not itself awaitable, and `.all()` is an async method rather than a sliceable
query builder.

| Operation | Result |
| --- | --- |
| `Model.objects.filter(*conditions, **lookups)` | QuerySet |
| `query.order_by(*fields).limit(n).offset(n)` | QuerySet |
| `await query.all()` | List of model instances |
| `await query.first()` | First instance or `None` |
| `await query.count()` | Integer count |
| `await query.exists()` | Boolean |
| `await Model.objects.get(**lookups)` | One instance; raises on zero or multiple matches |
| `await Model.objects.get_or_none(**lookups)` | First match or `None`; does not enforce uniqueness |

The ordinary Manager/QuerySet do not supply DRF/Django-style `exclude`, `last`,
`values`, `values_list`, `distinct`, or `update_or_create` methods. Use supported
queries and explicit application logic. See [querying](../orm/querying.md) and
[expressions](../orm/expressions-and-transactions.md) for filters, `Q`, `F`,
ordering, and aggregations.

## Modifying data

`await Model.objects.create(**values)` constructs and saves one model.
`await instance.save()` persists an individual instance;
`await instance.delete()` performs its deletion path. For set-based changes,
use `await Model.objects.filter(...).update(...)` or the corresponding queryset
`delete()`. Review the affected rows and policy scope explicitly.

`get_or_create(defaults=None, **lookups)` performs a lookup followed by creation
when missing. It is not an atomic concurrency or deduplication guarantee.
Enforce uniqueness in PostgreSQL and choose an explicit conflict-handling
strategy when callers can race. See [bulk operations](../orm/bulk-operations.md)
for `bulk_create`, `bulk_update`, and `upsert` contracts; they are not equivalent
to calling `save()` and its lifecycle signals for every row.

## Model class options

See [Model Meta](../orm/model-meta.md) for supported metadata and
[migrations](../orm/migrations.md) for applying database changes. Defining a
Python field or index does not apply a migration. Use only metadata described
by the current implementation, rather than copying another ORM's `Meta` options.

## Related objects

A forward foreign-key attribute stores the related identifier, not an awaitable
related model. Load the object explicitly, or use `select_related()` and
`get_related()` as documented in [relations](../orm/relations.md). Relation
loading and prefetching do not establish tenant or object authorization.

The [ticket desk relationship chapter](../tutorials/ticket-desk.md) provides a
runnable example; the [tenant chapter](../tutorials/ticket-desk-tenancy.md) adds
ownership validation and restricted-role RLS.

## Transactions and signals

[Transactions](../orm/expressions-and-transactions.md) cover participating work
on the same pinned PostgreSQL connection. Independent connections and external
effects are outside that atomic boundary. [Signals](../orm/signals.md) are local
callbacks; `post_save` is not an after-commit event or durable audit record.

## Manager reference

`Model.objects` is bound to the model. Do not instantiate `Manager()` without
its required model argument or assume a Django-style `get_queryset()` subclass
hook controls every query. Prefer explicit application query functions when
you need reusable filtering, and verify all access paths that must enforce a
policy.
