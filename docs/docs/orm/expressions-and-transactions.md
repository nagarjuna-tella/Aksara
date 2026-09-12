# Expressions and Transactions

Use Aksara's expression system when you need more than simple field equality.

This page covers:

- `Q()` objects for grouped boolean logic
- `F()` expressions for database-side arithmetic
- `annotate()` and `aggregate()` for summaries and per-row metrics
- one-hop relation-aware aggregate paths
- `transaction.atomic` for safe multi-step writes

---

## `Q()` Objects

`Q()` lets you group filter conditions and combine them explicitly.

```python
from aksara import Q

posts = await Post.objects.filter(
    Q(title__icontains="orm") | ~Q(status="archived"),
    published=True,
).all()
```

This compiles nested boolean SQL while keeping parameter binding safe.

Use `Q()` when:

- you need `OR` logic
- you need grouped conditions
- you need negation with `~`

---

## `F()` Expressions

`F()` references a field directly in SQL instead of loading it into Python first.

```python
from aksara import F

await Post.objects.filter(published=True).update(views=F("views") + 1)
```

This avoids race-prone read-modify-write patterns for counters and similar updates.

You can also compare fields in filters:

```python
posts = await Post.objects.filter(views__gt=F("likes")).all()
```

### Create-path restriction

Expressions are intentionally rejected in insert-style operations such as `create()`, `bulk_create()`, and `upsert()` input values. They are supported in `QuerySet.update()` and annotations. `bulk_update()`
also rejects expression values; it is not the expression-update path.

---

## `annotate()`

`annotate()` adds computed values to each returned model instance.

```python
from aksara import Count, Sum

posts = await Post.objects.annotate(
    comment_count=Count("comments"),
    total_comment_views=Sum("comments__views"),
).all()

for post in posts:
    print(post.title, post.comment_count, post.total_comment_views)
```

Annotated values are attached dynamically to the model instance, even though they are not declared fields.

---

## `aggregate()`

`aggregate()` returns a dictionary instead of model instances.

```python
from aksara import Count, Sum

summary = await Post.objects.filter(published=True).aggregate(
    total_views=Sum("views"),
    published_posts=Count("*"),
)

print(summary)
# {"total_views": 12500, "published_posts": 42}
```

---

## Relation-Aware Aggregate Paths

Aggregate paths support one relation hop.

### Reverse FK / O2O

```python
posts = await Post.objects.annotate(comment_count=Count("comments")).all()
```

If `Comment.post = ForeignKey(Post, related_name="comments")`, Aksara generates the join automatically.

### Aggregate a related field

```python
posts = await Post.objects.annotate(total_comment_views=Sum("comments__views")).all()
```

### Forward many-to-many

```python
posts = await Post.objects.annotate(tag_count=Count("tags")).all()
```

### Reverse many-to-many

```python
summary = await Tag.objects.aggregate(post_count=Count("posts"))
```

### Notes

- Reverse relation names rely on your registered `related_name` values.
- Reverse relation aggregates assume your app has finalized relations during startup.
- Current support is intentionally scoped to one hop, such as `comments` or `comments__views`.

---

## `transaction.atomic`

Use `transaction.atomic` to make multiple ORM operations commit or roll back together.

### As a context manager

```python
from aksara import F, transaction

async with transaction.atomic():
    await Account.objects.filter(id=from_id).update(balance=F("balance") - amount)
    await Account.objects.filter(id=to_id).update(balance=F("balance") + amount)
```

### As a decorator

```python
from aksara import transaction

@transaction.atomic
async def publish_post(post_id: str) -> None:
    post = await Post.objects.get(id=post_id)
    post.status = "published"
    await post.save()
```

### Nested transactions

Nested `atomic()` blocks reuse the active connection and use asyncpg savepoints.
If an inner failure is caught outside its block, that savepoint can roll back
while the outer transaction continues and commits. Let the error escape the
outer block when the whole unit must fail.

### Limits of atomicity

The guarantee covers database work participating in the same active Aksara
connection and PostgreSQL transaction. Independent pool acquisitions, separate
drivers, and subprocess writes do not join that transaction automatically.
Do not run concurrent child tasks against the inherited pinned connection;
asyncpg connections do not support overlapping operations.

Email, file writes, remote APIs, and already-dispatched jobs are not undone by
PostgreSQL rollback. Model `post_save` callbacks run before an outer commit,
not as after-commit hooks. See [signals](signals.md) and
[Durable Operations](../advanced/durable-operations.md) for the separate
execution and external-effect boundaries.

---

## Common Patterns

### Counter increment

```python
await Article.objects.filter(id=article_id).update(view_count=F("view_count") + 1)
```

### Aggregate with grouped filters

```python
from aksara import Count, Q

posts = await Post.objects.filter(
    Q(status="published") | Q(status="scheduled"),
).annotate(comment_count=Count("comments")).all()
```

### Summary dashboard metrics

```python
from aksara import Count, Sum

metrics = await Invoice.objects.aggregate(
    invoice_count=Count("*"),
    total_amount=Sum("amount"),
)
```