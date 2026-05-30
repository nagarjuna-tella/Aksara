# Querying Data

Retrieve, filter, and manipulate data using Aksara's QuerySet API.

---

## What is a QuerySet?

A **QuerySet** is a way to request data from your database without writing SQL. It's like asking questions:

- "Give me all posts" → `Post.objects.all()`
- "Give me posts that are published" → `Post.objects.filter(published=True)`
- "Give me the newest post" → `Post.objects.order_by("-created_at").first()`

QuerySets are:

- **Lazy** — They don't hit the database until you need the data
- **Chainable** — You can add conditions one after another
- **Async** — Use `await` when you actually want the results

```python
from myapp.models import Post

# Build the query (no database call yet)
query = Post.objects.filter(published=True).order_by("-created_at")

# Execute the query (hits the database)
posts = await query
```

---

## The `objects` Manager

Every model has an `objects` attribute that gives you access to QuerySet methods:

```python
# Get all posts
posts = await Post.objects.all()

# Filter posts
published = await Post.objects.filter(published=True)

# Get a single post
post = await Post.objects.get(id=some_id)
```

---

## Basic Operations

### Get All Records

**`all()`** — Retrieve every record in the table.

```python
posts = await Post.objects.all()
# Returns: [Post, Post, Post, ...]
```

**When to use**: When you need every record (be careful with large tables!).

---

### Get One Record

**`get(**kwargs)`** — Retrieve exactly ONE record matching your conditions.

```python
# By ID
post = await Post.objects.get(id=post_id)

# By any field
user = await User.objects.get(email="alice@example.com")
```

**What can go wrong**:

| Situation | What Happens |
|-----------|--------------|
| No match found | Raises `DoesNotExist` error |
| Multiple matches | Raises `MultipleObjectsReturned` error |

**Safe pattern** — Use `first()` if the record might not exist:

```python
# Returns None instead of raising an error
post = await Post.objects.filter(slug="hello-world").first()
if post is None:
    print("Post not found")
```

---

### Get First Record

**`first()`** — Get the first matching record, or `None` if no match.

```python
# Oldest post
oldest = await Post.objects.order_by("created_at").first()

# First matching post (or None)
draft = await Post.objects.filter(published=False).first()

if draft:
    print(f"Found draft: {draft.title}")
else:
    print("No drafts found")
```

---

### Filter Records

**`filter(**kwargs)`** — Get records matching your conditions.

```python
# Simple equality
published_posts = await Post.objects.filter(published=True)

# Multiple conditions (AND)
featured = await Post.objects.filter(published=True, featured=True)
```

**How filters combine**: Multiple arguments use AND logic:

```python
# published=True AND author_id=123
posts = await Post.objects.filter(published=True, author_id=author_id)
```

---

### Exclude Records

**`exclude(**kwargs)`** — Get records NOT matching conditions (opposite of filter).

```python
# All posts except drafts
posts = await Post.objects.exclude(status="draft")

# Combine with filter: published posts that aren't archived
active = await Post.objects.filter(published=True).exclude(archived=True)
```

---

### Count Records

**`count()`** — Count matching records without loading them.

```python
total_posts = await Post.objects.count()
published_count = await Post.objects.filter(published=True).count()
```

**Why use count()?** It's much faster than loading all records just to count them:

```python
# ❌ Bad: loads all records into memory
count = len(await Post.objects.all())

# ✅ Good: counts in the database
count = await Post.objects.count()
```

---

### Check if Records Exist

**`exists()`** — Check if any matching records exist (returns True/False).

```python
has_posts = await Post.objects.exists()
has_drafts = await Post.objects.filter(published=False).exists()

if has_drafts:
    print("You have unpublished drafts!")
```

**Why use exists()?** It stops as soon as it finds one match:

```python
# ❌ Loads all records just to check
if await Post.objects.filter(published=False):
    ...

# ✅ Stops at first match
if await Post.objects.filter(published=False).exists():
    ...
```

---

## Filtering with Lookups

**Lookups** let you do more than just equality checks. Add them after the field name with double underscores (`__`).

### Comparison Lookups

```python
# Greater than
recent = await Post.objects.filter(view_count__gt=1000)

# Greater than or equal
popular = await Post.objects.filter(view_count__gte=100)

# Less than
low_views = await Post.objects.filter(view_count__lt=10)

# Less than or equal
old_posts = await Post.objects.filter(created_at__lte=last_month)
```

| Lookup | Meaning | SQL Equivalent |
|--------|---------|----------------|
| `__gt` | Greater than | `>` |
| `__gte` | Greater than or equal | `>=` |
| `__lt` | Less than | `<` |
| `__lte` | Less than or equal | `<=` |

### Text Lookups

```python
# Contains (case-sensitive)
posts = await Post.objects.filter(title__contains="Python")

# Contains (case-insensitive)
posts = await Post.objects.filter(title__icontains="python")

# Starts with
posts = await Post.objects.filter(title__startswith="How to")

# Ends with
posts = await Post.objects.filter(slug__endswith="-tutorial")
```

| Lookup | Meaning | Example Match |
|--------|---------|---------------|
| `__contains` | Contains substring | "Learn **Python** Today" |
| `__icontains` | Contains (case-insensitive) | "learn **python** today" |
| `__startswith` | Starts with | "**How to** code" |
| `__istartswith` | Starts with (case-insensitive) | "**how to** code" |
| `__endswith` | Ends with | "Python **Tutorial**" |
| `__iendswith` | Ends with (case-insensitive) | "python **tutorial**" |
| `__exact` | Exact match | (default behavior) |
| `__iexact` | Exact match (case-insensitive) | "python" matches "Python" |

### List Lookups

```python
# In a list of values
featured = await Post.objects.filter(category__in=["tech", "news", "tutorial"])

# Not in a list (use exclude)
posts = await Post.objects.exclude(status__in=["draft", "archived"])
```

### NULL Lookups

```python
# Is NULL
no_category = await Post.objects.filter(category__isnull=True)

# Is NOT NULL
has_category = await Post.objects.filter(category__isnull=False)
```

### Nested JSON Path Lookups

JSON fields support nested key traversal by chaining double underscores after
the JSON field name.

```python
dark_mode_users = await User.objects.filter(
    preferences__ui__theme="dark",
)

high_scores = await Player.objects.filter(
    profile__stats__score__gte=900,
)

named_users = await User.objects.filter(
    profile__display_name__icontains="ada",
)
```

These lookups compile to PostgreSQL JSONB path expressions using `->` and `->>`.

### Date Lookups

```python
from datetime import date

# Posts from a specific year
posts_2024 = await Post.objects.filter(created_at__year=2024)

# Posts from January
january = await Post.objects.filter(created_at__month=1)

# Posts from a specific date
today = await Post.objects.filter(created_at__date=date.today())
```

| Lookup | Extracts |
|--------|----------|
| `__year` | Year (2024) |
| `__month` | Month (1-12) |
| `__day` | Day (1-31) |
| `__date` | Date part (ignores time) |
| `__hour` | Hour (0-23) |
| `__minute` | Minute (0-59) |

---

## Chaining QuerySets

QuerySets are **chainable** — you can add methods one after another:

```python
posts = await Post.objects \
    .filter(published=True) \
    .filter(category="tech") \
    .exclude(archived=True) \
    .order_by("-created_at") \
    .all()
```

Each method returns a new QuerySet, so you can build queries step by step:

```python
# Start with all posts
query = Post.objects.all()

# Add filters conditionally
if category:
    query = query.filter(category=category)

if search_term:
    query = query.filter(title__icontains=search_term)

if published_only:
    query = query.filter(published=True)

# Execute
posts = await query
```

---

## Ordering Results

**`order_by(*fields)`** — Sort results by one or more fields.

```python
# Ascending (A-Z, oldest first)
posts = await Post.objects.order_by("title")

# Descending (Z-A, newest first) — prefix with minus
posts = await Post.objects.order_by("-created_at")

# Multiple fields: first by category, then by date
posts = await Post.objects.order_by("category", "-created_at")
```

**Clear existing ordering**:

```python
# Remove any default ordering
posts = await Post.objects.order_by()
```

---

## Limiting Results

### Slicing

Use Python slice syntax to limit results:

```python
# First 10 posts
top_10 = await Post.objects.all()[:10]

# Posts 11-20 (skip first 10, get next 10)
page_2 = await Post.objects.all()[10:20]

# Single item by index
first = await Post.objects.order_by("created_at")[0]
```

### Pagination Pattern

```python
page = 1
page_size = 20

offset = (page - 1) * page_size
posts = await Post.objects.order_by("-created_at")[offset:offset + page_size]
```

---

## Getting Specific Fields

### values()

**`values(*fields)`** — Get dictionaries instead of model instances.

```python
# Get all fields as dictionaries
posts = await Post.objects.values()
# [{"id": "...", "title": "...", "content": "..."}, ...]

# Get specific fields only
posts = await Post.objects.values("id", "title")
# [{"id": "...", "title": "..."}, ...]
```

**When to use**: When you only need a few fields and want to avoid loading full objects.

### values_list()

**`values_list(*fields)`** — Get tuples instead of dictionaries.

```python
# Get tuples
posts = await Post.objects.values_list("id", "title")
# [("id1", "Title 1"), ("id2", "Title 2"), ...]

# Get flat list (single field only)
titles = await Post.objects.values_list("title", flat=True)
# ["Title 1", "Title 2", "Title 3", ...]
```

---

## Aggregation

Perform calculations across records:

```python
from aksara.db import Avg, Count, Max, Min, Sum

# Average view count
avg_views = await Post.objects.aggregate(Avg("view_count"))

# Multiple aggregations
stats = await Post.objects.aggregate(
    total=Count("id"),
    avg_views=Avg("view_count"),
    max_views=Max("view_count"),
)
# {"total": 150, "avg_views": 523.4, "max_views": 10000}
```

### Vector Distance Annotations

Use vector distance expressions with `annotate()` when ranking embeddings.

```python
from aksara.db import CosineDistance, EuclideanDistance

documents = await Document.objects.annotate(
    distance=CosineDistance("embedding", query_embedding),
).order_by("distance").all()
```

Available expressions:

- `CosineDistance("embedding", vector)`
- `EuclideanDistance("embedding", vector)`

The vector literal is parameterized and cast to PostgreSQL `vector`, so the
same expression works cleanly in annotations and ordering.

---

## Filtering on Related Models

Use double underscores (`__`) to filter through relationships:

```python
# Posts by author named "Alice"
posts = await Post.objects.filter(author__name="Alice")

# Posts by verified authors
posts = await Post.objects.filter(author__is_verified=True)

# Posts in categories that are active
posts = await Post.objects.filter(category__is_active=True)
```

**How it works**: `author__name` means "the `name` field of the related `author` model."

---

## Optimizing Queries

### select_related()

**Problem**: Loading related objects one by one (N+1 query problem):

```python
# ❌ Bad: 1 query for posts + 1 query per post to get author
posts = await Post.objects.all()
for post in posts:
    author = await Author.objects.get(id=post.author_id)
    print(f"{post.title} by {author.name}")
```

**Solution**: Load related objects in one query:

```python
# ✅ Good: 1 query gets posts AND authors
posts = await Post.objects.select_related("author").all()
for post in posts:
    author = post.get_related("author")
    print(f"{post.title} by {author.name}")  # No extra query!
```

Forward FK/O2O attributes such as `post.author` and `post.author_id` expose the
stored FK value/id. They are not lazy-loaded related objects; use explicit
queries or `select_related()` with `get_related()` when you need the object.

### prefetch_related()

For **many-to-many** or **reverse foreign key** relationships:

```python
# Load posts and their tags efficiently
posts = await Post.objects.prefetch_related("tags").all()
for post in posts:
    tag_names = [tag.name for tag in post.tags]  # No extra query!
```

### When to Use Which

| Method | Use For | Example |
|--------|---------|---------|
| `select_related` | ForeignKey (single related object) | `post.get_related("author")` |
| `prefetch_related` | ManyToMany, reverse FK (multiple objects) | `post.tags`, `author.posts` |

---

## Raw SQL

When you need full SQL control:

```python
# Execute raw SQL
posts = await Post.objects.raw(
    "SELECT * FROM posts WHERE title ILIKE %s",
    ["%python%"]
)

# Or use the database connection directly
from aksara.db import get_db

async with get_db() as conn:
    rows = await conn.fetch("SELECT COUNT(*) FROM posts WHERE published = true")
```

**When to use raw SQL**:

- Complex queries that can't be expressed with the ORM
- Performance-critical queries
- Database-specific features

---

## Common Patterns

### Get or Create

```python
# Get existing record or create new one
post, created = await Post.objects.get_or_create(
    slug="hello-world",
    defaults={
        "title": "Hello World",
        "content": "Welcome to my blog!",
    }
)

if created:
    print("Created new post")
else:
    print("Found existing post")
```

### Update or Create

```python
# Update if exists, create if not
post, created = await Post.objects.update_or_create(
    slug="hello-world",
    defaults={
        "title": "Hello World (Updated)",
        "content": "New content here",
    }
)
```

### Bulk Create

```python
# Create many records efficiently
posts = await Post.objects.bulk_create([
    Post(title="Post 1", content="Content 1"),
    Post(title="Post 2", content="Content 2"),
    Post(title="Post 3", content="Content 3"),
])
```

### Bulk Update

```python
# Update many records at once
updated_count = await Post.objects.filter(
    published=False
).update(
    published=True,
    published_at=datetime.now(),
)
print(f"Published {updated_count} posts")
```

---

## Quick Reference

| Method | Returns | Description |
|--------|---------|-------------|
| `all()` | List | All records |
| `get(**kwargs)` | Instance | One record (error if 0 or 2+) |
| `first()` | Instance or None | First matching record |
| `filter(**kwargs)` | QuerySet | Records matching conditions |
| `exclude(**kwargs)` | QuerySet | Records NOT matching conditions |
| `count()` | int | Number of matching records |
| `exists()` | bool | True if any records match |
| `order_by(*fields)` | QuerySet | Sort results |
| `values(*fields)` | List of dicts | Get specific fields as dicts |
| `values_list(*fields)` | List of tuples | Get specific fields as tuples |
| `select_related(*fields)` | QuerySet | Optimize ForeignKey loading |
| `prefetch_related(*fields)` | QuerySet | Optimize M2M/reverse FK loading |

---

## Related Documentation

- [Models](models.md) — Define your data structure
- [Relations](relations.md) — Work with related models
- [Fields](fields.md) — Field types and lookups
