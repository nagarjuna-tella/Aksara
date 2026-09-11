# Querying data

This guide uses the Ticket model from the
[first project](../getting-started/first-project.md). Configure and connect the
database and apply the model's migration before executing queries. The model
has `subject`, `description`, and `resolved` fields in addition to its ID.

## Build first, execute explicitly

`filter()` and `order_by()` build a QuerySet without contacting PostgreSQL.
Call an async terminal method such as `.all()`, `.first()`, `.count()`, or
`.exists()` to execute it. The QuerySet itself is not awaitable.

```python
from app.models import Ticket

query = Ticket.objects.filter(resolved=False).order_by("subject", "id")
tickets = await query.all()
```

`await Ticket.objects.all()` returns a list. It is useful for small complete
sets, but does not create a query builder you can subsequently filter or slice.

## Retrieve one record

```python
from aksara.manager import DoesNotExist

try:
    ticket = await Ticket.objects.get(id=ticket_id)
except DoesNotExist:
    ticket = None
```

`get()` raises `MultipleObjectsReturned` when more than one row matches. Use a
unique lookup when exactly one result is required. For an optional first match:

```python
ticket = await Ticket.objects.filter(resolved=False).order_by("subject", "id").first()
```

`first()` returns `None` when empty. `get_or_none()` also returns a first match
and does not check uniqueness. Use explicit ordering when selection order matters.

## Filters and negation

Keyword conditions combine with AND. Use `Q` for grouped OR and negation;
there is no `exclude()` method on the ordinary Manager/QuerySet.

```python
from aksara import Q

matches = await Ticket.objects.filter(
    Q(subject__icontains="login") | Q(description__icontains="login"),
    resolved=False,
).all()

other_tickets = await Ticket.objects.filter(~Q(subject="Archived")).all()
```

Supported ordinary comparisons include `gt`, `gte`, `lt`, `lte`, `in`,
`isnull`, `contains`, and `icontains`, applied to appropriate field types.
Do not assume every lookup from another ORM is available. JSON path and
relation lookups have additional type and relationship requirements; see
[advanced fields](advanced-field-policy.md) and [relations](relations.md).

## Conditional queries

Start with `filter()`, not `all()`, when building up a query:

```python
query = Ticket.objects.filter()
if search_term:
    query = query.filter(subject__icontains=search_term)
if unresolved_only:
    query = query.filter(resolved=False)
rows = await query.order_by("subject", "id").limit(20).all()
```

The builder methods return a new QuerySet. Keep their return value.
Filtering data is separate from checking whether the caller may access it.
Applications must establish identity, tenant scope, and object policy explicitly.

## Pagination

Use `.limit()` and `.offset()` on the QuerySet. Python slicing is not a
supported query interface. Validate application page inputs before building the
query and cap the page size.

```python
page = 2
page_size = 20
if page < 1 or not 1 <= page_size <= 100:
    raise ValueError("Invalid page or page size")
rows = await Ticket.objects.order_by("subject", "id").limit(page_size).offset(
    (page - 1) * page_size
).all()
```

Including a unique tie-breaker makes ordering deterministic for an unchanged
dataset. Offset pagination does not promise a stable snapshot across requests
while records are being inserted, deleted, or reordered.

## Counts, existence, and aggregates

```python
from aksara import Count

total = await Ticket.objects.count()
open_count = await Ticket.objects.filter(resolved=False).count()
has_open_tickets = await Ticket.objects.filter(resolved=False).exists()
summary = await Ticket.objects.aggregate(total=Count("*"))
```

Use `.filter().exists()` when testing the whole table; the ordinary Manager
has no direct `exists()` method. Aggregates take named expressions, not a
positional `Avg(...)`. See [expressions and transactions](expressions-and-transactions.md)
for `F`, grouped filters, annotations, and supported one-hop aggregates.

## Output projection

The ordinary Manager/QuerySet has no `values()` or `values_list()` methods.
For small bounded results, explicitly shape application output:

```python
rows = await Ticket.objects.order_by("subject", "id").limit(20).all()
public_rows = [{"id": str(row.id), "subject": row.subject} for row in rows]
```

This Python projection still loads model rows; it is not a SQL column-selection
optimization. For generated HTTP responses, configure the supported
[serializer](../api/serializers.md) and field-policy boundary instead.

## Related data

Use `select_related()` and `get_related()` for supported forward relation
loading, and the documented prefetch interfaces for collections. A forward FK
attribute contains the stored identifier, not an awaitable object. The
[relationship tutorial](../tutorials/ticket-desk.md) adds an Agent to Ticket;
[relations](relations.md) explains the corresponding loading APIs.

## Writes and concurrency

Use `.create()`, individual `.save()`, or explicit filtered `.update()` and
`.delete()` operations according to their contracts. `get_or_create()` is a
lookup followed by creation, not an atomic uniqueness guarantee. The ordinary
Manager does not supply `update_or_create()`.

See [bulk operations](bulk-operations.md) for bulk and upsert behavior and
[transactions](expressions-and-transactions.md) for multi-step atomic work.
Neither an ORM query nor a transaction makes email, files, or remote API calls
atomic with PostgreSQL.

## Raw SQL

The ordinary Manager does not offer `.raw()`. Use the documented Database
connection boundary when application SQL is necessary, with asyncpg `$1`, `$2`
parameters for values. Raw SQL must explicitly preserve authorization and
tenant restrictions; it does not inherit ORM query filtering. Keep it on the
active pinned connection when it must participate in an existing transaction.
