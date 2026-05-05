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

### Result Format

By default, durable results must be JSON-serializable. Common values like:

- dictionaries and lists
- strings, numbers, and booleans
- UUIDs and datetimes
- dataclasses and Pydantic models

are normalized automatically before being persisted.

If you need a different encoding strategy, pass custom `serializer` and
`deserializer` callables when constructing `DurableStep`.

---

## Operational Notes

- `ContentType` rows are synced on app startup and cached in memory for fast resolution.
- `DurableStep` creates `aksara_durable_state` lazily on first use.
- Both features rely on PostgreSQL-managed internal tables, so no extra service is required.