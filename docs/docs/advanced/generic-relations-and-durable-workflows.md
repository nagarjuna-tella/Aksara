# Generic Relations and Durable Workflows

Phase 4 finishes with two framework primitives aimed at real production
applications: model-agnostic relations and resumable workflow steps.

---

## Generic Relations

`fields.GenericForeignKey()` lets one model point at any other registered
model without hardcoding a specific `ForeignKey`.

```python
from aksara import Model, fields


class Post(Model):
    title = fields.String(max_length=200)


class Comment(Model):
    body = fields.String(max_length=500)
    content_object = fields.GenericForeignKey()
```

When you define a generic relation, Aksara automatically adds these backing
columns to the model table:

- `content_type_id`
- `object_id`

### Saving a Generic Relation

```python
post = await Post.objects.create(title="Hello")

comment = Comment(body="Nice post", content_object=post)
await comment.save()

assert comment.content_type_id is not None
assert comment.object_id == str(post.id)
```

### Resolving the Related Object

Generic relations are async. Resolve them by awaiting the accessor:

```python
comment = await Comment.objects.get(id=comment_id)
related = await comment.content_object()

assert related.title == "Hello"
```

Under the hood, Aksara:

- keeps an internal `ContentType` registry table in PostgreSQL
- syncs registered models into that table at startup
- resolves `content_type_id` back to the runtime model class
- executes `model.objects.get(id=object_id)` for the final lookup

### Content Type Helpers

You can work with the content type registry directly when needed:

```python
from aksara import get_content_type_for_model, sync_content_types

await sync_content_types()
content_type = await get_content_type_for_model(Post)
```

---

## Durable Workflow Steps

!!! warning "Evolving workflow helper"
    `DurableStep` remains available in v0.7, but it is not the Durable
    Authorized Operations substrate. It does not provide Operation/Attempt
    identity, leases, fencing, current reauthorization, durable cancellation,
    or atomic application-mutation completion. Use
    [Durable Authorized Operations](durable-operations.md) when those guarantees
    are required.

`DurableStep` persists successful step results in PostgreSQL so repeated runs
can reuse the stored output instead of re-executing expensive work.

```python
from aksara import DurableStep


step = DurableStep("wf-codegen")


async def generate_code():
    return {"status": "ok", "files": 3}


result = await step.run("generate_code", generate_code)
repeat = await step.run("generate_code", generate_code)

assert result == repeat
```

### Failure and Retry Behavior

Only successful steps are reused. Failed runs are recorded and can be retried.

```python
state = await step.get_state("generate_code")
assert state.status == "completed"
```

If you need to recompute a successful step anyway, use `force=True`:

```python
fresh = await step.run("generate_code", generate_code, force=True)
```

### Step Re-entry Rules

The table below summarises what `step.run(name, fn)` does depending on the
current persisted state of the step:

| Existing status | `force=False` (default) | `force=True` |
|-----------------|-------------------------|--------------|
| No row          | Execute, cache result   | Execute, cache result |
| `failed`        | Re-execute, overwrite   | Re-execute, overwrite |
| `running`       | Raise `ConcurrentStepError` | Execute, overwrite |
| `completed`     | Return cached result    | Re-execute, overwrite |

### Concurrent Execution Protection

`DurableStep` is designed for **sequential** orchestration: one orchestrator
calls steps one after the other.

Calling the same step from two concurrent tasks at the same time is detected
atomically (via `INSERT … ON CONFLICT DO UPDATE … WHERE status = 'failed'`) and
raises `ConcurrentStepError` on the losing caller rather than silently
double-executing:

```python
from aksara.workflows import ConcurrentStepError

try:
    result = await step.run("send_invoice", generate_invoice)
except ConcurrentStepError:
    # Another caller already holds this step.
    # Wait and re-read, or surface the error upstream.
    ...
```

If the winning caller completes before the loser re-reads, the loser
transparently returns the cached result instead of raising.

### Result Format

By default, durable results must be JSON-serializable. Common values like:

- dictionaries and lists
- strings, numbers, and booleans
- UUIDs and datetimes
- dataclasses and Pydantic models

are normalized automatically before being persisted.

If you need a different encoding strategy, pass custom `serializer` and
`deserializer` callables when constructing `DurableStep`:

```python
import pickle, base64

step = DurableStep(
    "wf-ml-pipeline",
    serializer=lambda v: base64.b64encode(pickle.dumps(v)).decode(),
    deserializer=lambda v: pickle.loads(base64.b64decode(v)),
)
```

### Clearing Step State

```python
await step.clear("generate_code")   # clear one step
await step.clear()                  # clear all steps for this workflow_id
```

---

## Operational Notes

- `ContentType` rows are synced on app startup and cached in memory for fast resolution.
- `DurableStep` creates `aksara_durable_state` lazily on first use.
- The step claim is atomic — `INSERT … ON CONFLICT DO UPDATE … WHERE` — so
  concurrent callers never both execute the same step.
- Both features rely on PostgreSQL-managed internal tables, so no extra service is required.
