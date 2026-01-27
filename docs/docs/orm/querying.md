# Querying Data

Query, filter, and retrieve data using Aksara's intuitive QuerySet API.

---

## Overview

Every Aksara model has an `objects` manager that provides access to the QuerySet API:

```python
from myapp.models import Post

# Get all posts
posts = await Post.objects.all()

# Filter posts
python_posts = await Post.objects.filter(category="python")

# Get single post
post = await Post.objects.get(id=post_id)
```

!!! note "Async by Default"
    All QuerySet operations are async. Use `await` for any operation that hits the database.

---

## QuerySet Methods

### all()

Retrieve all records:

```python
posts = await Post.objects.all()
# Returns: List[Post]
```

### filter(**kwargs)

Retrieve records matching conditions:

```python
# Simple equality
published = await Post.objects.filter(is_published=True)

# Multiple conditions (AND)
featured = await Post.objects.filter(is_published=True, is_featured=True)

# Field lookups
recent = await Post.objects.filter(created_at__gt=last_week)
```

### exclude(**kwargs)

Retrieve records NOT matching conditions:

```python
# All non-draft posts
posts = await Post.objects.exclude(status="draft")

# Combine with filter
active = await Post.objects.filter(is_published=True).exclude(is_archived=True)
```

### get(**kwargs)

Retrieve exactly one record:

```python
post = await Post.objects.get(id=post_id)
```

!!! warning "Raises Exceptions"
    - `DoesNotExist` — No matching record
    - `MultipleObjectsReturned` — More than one match

### first()

Get the first record or `None`:

```python
# Returns single Post or None
oldest = await Post.objects.order_by("created_at").first()

# With filter
first_python = await Post.objects.filter(category="python").first()
```

### count()

Count matching records:

```python
total = await Post.objects.count()
published = await Post.objects.filter(is_published=True).count()
```

### exists()

Check if any records exist:

```python
has_posts = await Post.objects.filter(author=user).exists()
if has_posts:
    print("User has posts")
```

---

## Field Lookups

Lookups are specified using double underscores: `field__lookup=value`

### Comparison Lookups

| Lookup | SQL | Example |
|--------|-----|---------|
| `exact` | `=` | `name__exact="John"` |
| `gt` | `>` | `age__gt=18` |
| `gte` | `>=` | `price__gte=10.00` |
| `lt` | `<` | `created_at__lt=today` |
| `lte` | `<=` | `score__lte=100` |

```python
# Posts created after a date
recent = await Post.objects.filter(created_at__gt=last_week)

# Products in price range
affordable = await Product.objects.filter(price__gte=10, price__lte=50)
```

### String Lookups

| Lookup | Case | SQL | Example |
|--------|------|-----|---------|
| `contains` | Sensitive | `LIKE '%x%'` | `title__contains="Python"` |
| `icontains` | Insensitive | `ILIKE '%x%'` | `title__icontains="python"` |
| `startswith` | Sensitive | `LIKE 'x%'` | `email__startswith="admin"` |
| `istartswith` | Insensitive | `ILIKE 'x%'` | `email__istartswith="admin"` |
| `endswith` | Sensitive | `LIKE '%x'` | `email__endswith=".com"` |
| `iendswith` | Insensitive | `ILIKE '%x'` | `email__iendswith=".com"` |

```python
# Case-insensitive search
results = await Post.objects.filter(title__icontains="tutorial")

# Email domain filter
gmail_users = await User.objects.filter(email__endswith="@gmail.com")
```

### Null & Empty Checks

| Lookup | Description | Example |
|--------|-------------|---------|
| `isnull` | Check NULL | `bio__isnull=True` |

```python
# Users without profiles
no_bio = await User.objects.filter(bio__isnull=True)

# Users with profiles
has_bio = await User.objects.filter(bio__isnull=False)
```

### In Lookup

Match against a list of values:

```python
# Posts in multiple categories
posts = await Post.objects.filter(category__in=["python", "javascript", "rust"])

# Users by ID list
users = await User.objects.filter(id__in=user_ids)
```

---

## Chaining QuerySets

QuerySet methods can be chained for complex queries:

```python
posts = await (
    Post.objects
    .filter(is_published=True)
    .filter(category="python")
    .exclude(is_archived=True)
    .order_by("-created_at")
    .all()
)
```

!!! tip "Lazy Evaluation"
    Queries aren't executed until you call a terminal method (`all()`, `first()`, `count()`, etc.).

---

## Ordering Results

### order_by(*fields)

```python
# Ascending order
posts = await Post.objects.order_by("title").all()

# Descending order (prefix with -)
posts = await Post.objects.order_by("-created_at").all()

# Multiple fields
posts = await Post.objects.order_by("-is_featured", "-created_at").all()
```

### Default Ordering

Define default ordering in the model's Meta:

```python
class Post(Model):
    title = fields.String(max_length=200)
    created_at = fields.DateTime(auto_now_add=True)
    
    class Meta:
        ordering = ["-created_at"]  # Newest first by default
```

---

## Limiting Results

### Slicing

```python
# First 10 posts
posts = await Post.objects.order_by("-created_at")[:10]

# Posts 10-20 (pagination)
posts = await Post.objects.order_by("-created_at")[10:20]
```

### limit() and offset()

```python
# Alternative syntax
posts = await Post.objects.limit(10).offset(20).all()
```

---

## Selecting Specific Fields

### values(*fields)

Return dictionaries instead of model instances:

```python
# Only fetch specific fields
posts = await Post.objects.values("id", "title").all()
# Returns: [{"id": "...", "title": "..."}, ...]
```

### values_list(*fields)

Return tuples:

```python
# As tuples
posts = await Post.objects.values_list("id", "title").all()
# Returns: [("...", "..."), ...]

# Single field as flat list
titles = await Post.objects.values_list("title", flat=True).all()
# Returns: ["Title 1", "Title 2", ...]
```

---

## Related Object Queries

### select_related(*fields)

Eager load ForeignKey/OneToOne relations (JOIN query):

```python
# Without select_related: N+1 queries
posts = await Post.objects.all()
for post in posts:
    author = await post.author  # Query per post!

# With select_related: Single JOIN query
posts = await Post.objects.select_related("author").all()
for post in posts:
    print(post.author.name)  # Already loaded!
```

Multiple relations:

```python
posts = await Post.objects.select_related("author", "category").all()
```

Nested relations:

```python
# Load author and author's profile
posts = await Post.objects.select_related("author__profile").all()
```

### prefetch_related(*fields)

Efficient loading for ManyToMany relations:

```python
# Load posts with their tags
posts = await Post.objects.prefetch_related("tags").all()
for post in posts:
    for tag in post.tags:
        print(tag.name)
```

### Filtering by Related Fields

Use double underscores to traverse relations:

```python
# Posts by author name
posts = await Post.objects.filter(author__name="Jane")

# Posts by author email domain
posts = await Post.objects.filter(author__email__endswith="@company.com")

# Posts in a category by slug
posts = await Post.objects.filter(category__slug="python")

# Posts with a specific tag
posts = await Post.objects.filter(tags__name="tutorial")
```

---

## Aggregations

### Basic Aggregations

```python
from aksara.db import Count, Sum, Avg, Max, Min

# Count
count = await Post.objects.count()

# With aggregation functions
stats = await Post.objects.aggregate(
    total=Count("id"),
    avg_views=Avg("view_count"),
    max_views=Max("view_count"),
)
# Returns: {"total": 100, "avg_views": 250.5, "max_views": 10000}
```

### Annotate

Add computed fields to each object:

```python
# Annotate posts with comment count
posts = await Post.objects.annotate(
    comment_count=Count("comments")
).all()

for post in posts:
    print(f"{post.title}: {post.comment_count} comments")
```

---

## CRUD Operations

### Create

```python
# Create and save
post = await Post.objects.create(
    title="My Post",
    content="Content here",
    author_id=user_id,
)

# Alternative: instantiate then save
post = Post(title="My Post", content="Content here")
await post.save()
```

### Read

```python
# Get by ID
post = await Post.objects.get(id=post_id)

# Get or 404
post = await Post.objects.get_or_404(id=post_id)

# Get or create
post, created = await Post.objects.get_or_create(
    slug="my-post",
    defaults={"title": "My Post", "content": "..."},
)
```

### Update

```python
# Update single object
post = await Post.objects.get(id=post_id)
post.title = "New Title"
await post.save()

# Bulk update
await Post.objects.filter(is_draft=True).update(is_archived=True)

# Update or create
post, created = await Post.objects.update_or_create(
    slug="my-post",
    defaults={"title": "Updated Title"},
)
```

### Delete

```python
# Delete single object
post = await Post.objects.get(id=post_id)
await post.delete()

# Bulk delete
await Post.objects.filter(is_archived=True, is_old=True).delete()
```

---

## Raw SQL

For complex queries that can't be expressed with the ORM:

```python
# Raw query
posts = await Post.objects.raw(
    "SELECT * FROM posts WHERE EXTRACT(YEAR FROM created_at) = %s",
    [2024]
)

# Execute arbitrary SQL
from aksara.db import connection
result = await connection.execute(
    "SELECT category, COUNT(*) FROM posts GROUP BY category"
)
```

!!! warning "SQL Injection"
    Always use parameterized queries. Never interpolate user input directly into SQL strings.

---

## QuerySet Evaluation

QuerySets are lazy — they don't hit the database until evaluated.

### Operations That Evaluate

| Method | Returns | Hits DB |
|--------|---------|---------|
| `all()` | `List[Model]` | ✅ |
| `first()` | `Model \| None` | ✅ |
| `get()` | `Model` | ✅ |
| `count()` | `int` | ✅ |
| `exists()` | `bool` | ✅ |
| `update()` | `int` | ✅ |
| `delete()` | `int` | ✅ |

### Operations That Don't Evaluate

| Method | Returns |
|--------|---------|
| `filter()` | `QuerySet` |
| `exclude()` | `QuerySet` |
| `order_by()` | `QuerySet` |
| `select_related()` | `QuerySet` |
| `limit()` | `QuerySet` |

---

## Complete Example

```python
from datetime import datetime, timedelta
from myapp.models import Post, User, Category

async def get_dashboard_data(user_id: str):
    """Example of complex querying for a dashboard."""
    
    # Get user with profile
    user = await User.objects.select_related("profile").get(id=user_id)
    
    # Recent posts by user
    recent_posts = await (
        Post.objects
        .filter(author=user)
        .filter(is_published=True)
        .order_by("-created_at")
        .select_related("category")
        .prefetch_related("tags")
        [:5]
    )
    
    # Post statistics
    last_month = datetime.now() - timedelta(days=30)
    stats = await Post.objects.filter(author=user).aggregate(
        total=Count("id"),
        published=Count("id", filter=Q(is_published=True)),
        views=Sum("view_count"),
    )
    
    # Popular posts this month
    popular = await (
        Post.objects
        .filter(author=user)
        .filter(created_at__gte=last_month)
        .order_by("-view_count")
        .values("id", "title", "view_count")
        [:3]
    )
    
    # Categories with post counts
    categories = await (
        Category.objects
        .annotate(post_count=Count("posts"))
        .filter(posts__author=user)
        .order_by("-post_count")
        .all()
    )
    
    return {
        "user": user,
        "recent_posts": recent_posts,
        "stats": stats,
        "popular": popular,
        "categories": categories,
    }
```

---

## Best Practices

### Use select_related Proactively

```python
# Bad: N+1 queries
posts = await Post.objects.all()
for post in posts:
    print(post.author.name)  # Query per iteration

# Good: Single query
posts = await Post.objects.select_related("author").all()
```

### Filter Early

```python
# Bad: Filter in Python
posts = await Post.objects.all()
published = [p for p in posts if p.is_published]

# Good: Filter in database
published = await Post.objects.filter(is_published=True).all()
```

### Use values() for Read-Only Data

```python
# Bad: Full object when you only need ID and title
posts = await Post.objects.all()
data = [{"id": p.id, "title": p.title} for p in posts]

# Good: Only fetch needed fields
data = await Post.objects.values("id", "title").all()
```

### Limit Results

```python
# Bad: Fetch all, use first
posts = await Post.objects.all()
first_post = posts[0] if posts else None

# Good: Only fetch one
first_post = await Post.objects.first()
```

---

## Related Documentation

- [Models](models.md) — Model definition
- [Fields](fields.md) — Field types and options
- [Relations](relations.md) — ForeignKey, ManyToMany
