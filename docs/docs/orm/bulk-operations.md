# Bulk writes and upserts

Use bulk writes when many rows need the same persistence operation. Aksara
builds batched PostgreSQL statements instead of calling `save()` on every
instance. That reduces statement overhead, but changes which hooks run.
It is not an automatic authorization boundary or an all-batches transaction.

## A complete helper for Ticket Desk

Use the Ticket model from the [first-project tutorial](../getting-started/first-project.md)
and apply its migrations before calling this helper. Save as `app/bulk_tickets.py`:

```python title="app/bulk_tickets.py"
from datetime import datetime, timezone

from aksara import transaction
from .models import Ticket


def checked_subject(value):
    subject = value.strip()
    if not subject or len(subject) > 200:
        raise ValueError("A subject must contain 1 to 200 characters")
    return subject


async def create_tickets(subjects, batch_size=1000):
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    tickets = [Ticket(subject=checked_subject(value)) for value in subjects]
    async with transaction.atomic():
        return await Ticket.objects.bulk_create(tickets, batch_size=batch_size)


async def append_note(tickets, note, batch_size=1000):
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    if not tickets:
        return 0
    for ticket in tickets:
        ticket.description += note
    async with transaction.atomic():
        return await Ticket.objects.bulk_update(
            tickets, fields=["description"], batch_size=batch_size
        )


async def import_ticket(ticket_id, subject):
    return await Ticket.objects.upsert(
        id=ticket_id,
        defaults={
            "subject": checked_subject(subject),
            "description": "",
            "resolved": False,
            "updated_at": datetime.now(timezone.utc),
        },
        update_fields=["subject", "updated_at"],
    )
```

The caller must authorize the import and select only tickets it may modify.
For a tenant model, establish the tenant context, supply server-owned tenant
values, and enforce database RLS as described in the
[tenant tutorial](../tutorials/ticket-desk-tenancy.md). Do not accept arbitrary
objects or primary keys from an untrusted request and pass them to these helpers.

The helper validates subjects explicitly because direct ORM writes do not invoke
HTTP serializer validation. `import_ticket()` uses a supplied UUID as its
conflict key: insert initializes description/resolved, while update changes only
subject/updated_at. It does not overwrite an existing ticket's resolved flag.

## Method contracts

| Method | Inputs | Return value |
|---|---|---|
| `bulk_create(objs, batch_size=1000, ignore_conflicts=False)` | Unsaved instances | List of inserted instances; empty input returns `[]` |
| `bulk_update(objs, fields, batch_size=1000)` | Saved instances and explicit field names | Number of affected rows; empty objects or fields raises `ValueError` |
| `upsert(defaults=None, update_fields=None, **kwargs)` | Conflict key fields plus insertion values | `(instance, created)` |

Pass a positive integer batch size. These methods materialize their inputs and
build statements in memory; batching is not a streaming-import API. Choose
batch size with row width and PostgreSQL parameter limits in mind. Field
preparation, such as file storage or relationship work, can perform additional
operations, so row count divided by batch size is not a universal query count.

## Current bulk-update limitation

**Known defect in 0.7.0 (BULK-001):** the generated CASE values for ordinary
Boolean and timestamp fields are inferred as text by PostgreSQL. Updating
`resolved` or `updated_at` with `bulk_update()` fails with a database type
mismatch. The text-only helper above was executed successfully, but this does
not establish general scalar bulk-update support. Vector fields use a separate
explicit cast path; they are not evidence that all other types work.

For a uniform change, use a filtered `QuerySet.update()`; for different values
per row, use supported individual updates within an explicit transaction until
a separately reviewed runtime patch fixes typed CASE generation. Do not coerce
your schema to text to accommodate this defect. Verify the actual fields used
by your application against PostgreSQL.

## Transactions and partial failure

Each individual PostgreSQL statement is atomic. An unwrapped multi-batch call
can commit earlier batches before a later batch fails. The two bulk helpers
above deliberately use `transaction.atomic()` so their supported PostgreSQL
writes commit or roll back together. Keep their calls sequential on the pinned
connection. See [transaction limits](expressions-and-transactions.md#limits-of-atomicity).

Rollback restores database state, not Python object attributes or `_is_new`
flags already changed by preparation/hydration. Reload or discard affected
instances after a failed operation. Storage uploads and other external effects
performed during preparation are not undone by a database rollback.

## Preparation, validation and signals

`bulk_create()` checks that instances are unsaved, rejects expression values,
runs async field/generic-relation preparation and field validation for all
objects before issuing its inserts, and populates `auto_now` fields. Explicit
`auto_now_add` values are retained. Returned rows hydrate database-generated
values into instances.

`bulk_update()` writes only the named fields through their database conversion.
It does not call `save()`, run full instance validation/preparation, or refresh
`auto_now` automatically. The text-only `append_note()` helper deliberately
leaves `updated_at` unchanged. This differs from `QuerySet.update()`, which refreshes `auto_now`
when updating regular fields unless the caller supplied that timestamp.

`upsert()` converts supplied fields to database values but does not construct
and prepare an unsaved instance as `create()` does. Supply required insertion
values and timestamps intentionally. A Python model default is not proof that
an omitted upsert column has a database default; inspect the applied migration.

These three manager methods do not emit per-instance `pre_save`/`post_save`
signals. Do not use a signal as the sole implementation of an invariant that
bulk or raw SQL writes must obey. Database constraints still apply.

Expression values are rejected by `bulk_create()`, `bulk_update()`, and the
insertion values of `upsert()`. Use the supported `QuerySet.update()` expression
path when you need an `F()` calculation. Unresolved File/Image upload objects
need a preparation-capable save/create path; bulk update and upsert are not
upload handlers. Vector conversion has its own
[advanced-field contract](advanced-field-policy.md).

## Ignoring conflicts

`ignore_conflicts=True` adds `ON CONFLICT DO NOTHING` to bulk insertion. It
returns only inserted rows; it does not suppress arbitrary validation, CHECK,
foreign-key, or permission failures.

When PostgreSQL returns fewer rows than a batch contained, Aksara constructs
returned instances from those rows rather than matching them back to every
input object. Use the returned list. Do not infer that all input objects were
saved, that each input's state was updated, or that a skipped row's existing
contents were changed.

## Upsert conflict keys

The names in `**kwargs` form the SQL conflict target; PostgreSQL must have a
matching unique constraint or index. The primary key in the helper satisfies
that requirement. Using a non-unique field does not turn it into a unique key.
An invalid conflict target fails at the database boundary; the manager does not
prevalidate every unique-index shape.

Keep key fields separate from `defaults`. If `update_fields` is omitted, fields
in `defaults` are updated on conflict. Explicit update fields missing from
`defaults` use PostgreSQL's proposed insertion value (`EXCLUDED`), which can
include database defaults. A keys-only upsert still emits a no-op `DO UPDATE`
to return a row; do not treat it as a read-only lookup or as free of database
update-trigger effects. `get_or_create()` is a separate lookup/create method
and does not inherit upsert's single-statement conflict handling.
