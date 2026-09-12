# Generic relations and persisted steps

These are separate helpers. A generic relation stores a reference to different
model types. `DurableStep` stores a callback's successful result for reuse.
Neither automatically supplies application permission checks.

!!! warning "Evolving workflow helper"
    `DurableStep` is outside the stable Durable Authorized Operations guarantee.
    It has no Operation/Attempt identity, lease, fence, current reauthorization,
    durable cancellation, or atomic application-mutation completion. Use
    [Durable Authorized Operations](durable-operations.md) for those guarantees.

## Generic relations

Use a normal [foreign key](../orm/relations.md) when the target model is known.
`GenericForeignKey` is a virtual descriptor backed by a content-type UUID and
an object ID string. It can resolve different registered model classes, but the
pair is not a database foreign key to the target row: it does not enforce target
existence or automatically cascade deletion.

```python title="app/generic_models.py"
from aksara import Model, fields


class Post(Model):
    title = fields.String(max_length=200)


class Comment(Model):
    body = fields.String(max_length=500)
    content_object = fields.GenericForeignKey()
```

The declaration adds `content_type_id` and `object_id` **model fields**. Create
and apply application [migrations](../orm/migrations.md) before using their
columns. The descriptor defaults to `nullable=True`; its object ID string has
`object_id_max_length=255`. For multiple generic relations on one model, give
each descriptor distinct `content_type_field` and `object_id_field` names.

The application must import the target models so they are registered, connect
the database, and provision internal content-type storage. A database-backed
Aksara startup synchronizes registered content types; a standalone script can
call `sync_content_types()` explicitly. These helpers can create/repair internal
storage and write registry rows, so account for their required privileges in
[deployment](../tutorials/deployment.md). Model registration does not create the
application's tables.

With the model tables migrated and the database connected:

```python title="app/generic_examples.py"
from aksara import sync_content_types
from app.generic_models import Comment, Post


async def create_comment_example():
    await sync_content_types()
    post = await Post.objects.create(title="Hello")
    comment = Comment(body="Nice post", content_object=post)
    await comment.save()
    assert comment.content_type_id is not None
    assert comment.object_id == str(post.id)

    loaded = await Comment.objects.get(id=comment.id)
    related = await loaded.content_object()
    assert related.id == post.id
    assert related.title == "Hello"
    return post, loaded
```

Call and await `comment.content_object()` to resolve the target. An unset pair
returns `None`; a missing target raises the target query's `aksara.manager.DoesNotExist` error.
An unknown content type or unregistered target class can raise `KeyError`.
Assignment accepts a model instance or `None`; `save()` prepares and persists
the backing fields. Assign a saved target when the reference must resolve.

The accessor caches a resolved/assigned object on that instance. Reading it
again is not a fresh database lookup or a permission check. Reload the comment
when a fresh lookup is needed. Validate allowed target types, current access and
tenant membership in application code; do not accept arbitrary backing IDs as
proof of authority. The registry helpers `get_content_type_for_model(ModelClass)`
and `sync_content_types()` expose identity lookup/synchronization, not access
control. Do not prune registry rows without considering retained references.

## Persisted step results

`DurableStep(workflow_id)` keys its state by **`(workflow_id, step_name)`**.
Arguments, callback code, tenant and Principal are not automatically included.
Applications must choose identities and versions that prevent unintended reuse
across inputs or customers, and check permission before returning cached data.
The helper does not create a tenant-scoped workflow service.

This example runs under an already connected database and uses a fresh,
application-owned workflow ID. It creates internal step storage on use:

```python title="app/step_examples.py"
from aksara import DurableStep


async def demonstrate_step(workflow_id):
    step = DurableStep(workflow_id)
    calls = 0

    async def summarize():
        nonlocal calls
        calls += 1
        return {"files": 3}

    first = await step.run("summary", summarize)
    repeated = await step.run("summary", summarize)
    assert first == repeated == {"files": 3}
    assert calls == 1
    state = await step.get_state("summary")
    assert state.status == "completed"
    return step
```

`run(step_name, func, *args, force=False, **kwargs)` accepts synchronous or async
callbacks. It returns the stored/decoded result, which need not have the original
Python type. `get_state(name)` returns a `DurableStepState` or `None` for no row.
It exposes status, result, error and timestamps; these are step records, not
Operation status or an audit-retention contract.

| Existing status | `force=False` | `force=True` |
| --- | --- | --- |
| No row | Claim and execute | Claim and execute |
| `failed` | Reclaim and execute | Execute again |
| `running` | Raise `ConcurrentStepError`, unless completion is observed on reread | Overwrite claim and execute again |
| `completed` | Return cached result | Execute again |

Normal claims use an atomic PostgreSQL insert/upsert. With `force=False`, a
competing caller cannot claim an existing running row. Catch
`aksara.workflows.ConcurrentStepError` to report that state or read it later;
there is no automatic wait or polling loop.

**`force=True` bypasses that protection.** It can execute while an earlier caller
is still running, and there is no ownership fence on completion. Use force or
`clear()` only after application orchestration has established that no earlier
caller is active. Neither is a safe worker-loss recovery protocol by itself.

Ordinary callback/serialization exceptions attempt to record `failed` and are
reraised; retry is another explicit call to `run()`. A process loss or task
cancellation can leave `running` indefinitely: no lease expires it. Callback
effects and step completion are not automatically one transaction, and a stored
result does not prove an external effect happened exactly once.

## Encoding results

The default JSON encoding supports normal JSON values and fallback conversion
for UUIDs, datetimes, sets, dataclasses, Pydantic models and objects with
`to_dict()`. Decoding returns JSON-shaped values, not reconstructed instances.
Values still need to be encodable after conversion.

A custom `serializer` is passed as **`json.dumps(default=...)`**: it runs only
for values JSON cannot already encode. It is not a whole-result transform.
The `deserializer` receives the decoded whole stored result, including on the
first successful execution. Match these two contracts explicitly. For example,
this pair is for callbacks whose result is a single `Decimal`:

```python title="app/decimal_steps.py"
from decimal import Decimal
from aksara import DurableStep


def encode_decimal(value):
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError("Expected a Decimal result")


def decimal_step(workflow_id):
    return DurableStep(
        workflow_id,
        serializer=encode_decimal,
        deserializer=Decimal,
    )
```

This pair is not a general nested-object codec. Use a deliberately specified
JSON schema when result structure or compatibility matters.

## Storage and cleanup

`ensure_table()`, `run()`, `get_state()` and `clear()` can issue internal
`CREATE TABLE IF NOT EXISTS` statements. Arrange schema provisioning and
privileges explicitly; connecting with a restricted role does not grant DDL.
No extra broker is required, but PostgreSQL storage and lifecycle remain your
responsibility.

`await step.clear("summary")` deletes that step; `await step.clear()` deletes
all rows for that workflow ID. Clearing does not stop active callbacks or undo
their effects. No automatic retention schedule, workflow scheduler, approval
process or cancellation endpoint is supplied by this helper.
