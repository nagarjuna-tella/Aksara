# ORM Reference

Complete reference for Vidyut's ORM.

---

## Models

### Model Definition

```python
from vidyut import Model, fields

class Post(Model):
    title = fields.StringField(max_length=200)
    content = fields.TextField()
    author = fields.ForeignKey("User", on_delete="CASCADE")
    
    class Meta:
        table_name = "posts"
        ordering = ["-created_at"]
```

### Model Meta Options

| Option | Type | Description |
|--------|------|-------------|
| `table_name` | str | Database table name |
| `ordering` | list | Default ordering |
| `unique_together` | list | Unique constraints |
| `indexes` | list | Database indexes |
| `abstract` | bool | Abstract base model |

### Model Methods

| Method | Description |
|--------|-------------|
| `save(**kwargs)` | Save instance |
| `delete()` | Delete instance |
| `refresh_from_db()` | Reload from database |
| `to_dict()` | Convert to dictionary |
| `clean()` | Validation hook |

### Model Properties

| Property | Description |
|----------|-------------|
| `id` | Primary key (UUID) |
| `created_at` | Creation timestamp |
| `updated_at` | Last update timestamp |
| `pk` | Alias for primary key |

---

## Fields

### String Fields

```python
# Basic string
name = fields.StringField(max_length=100)

# Text (unlimited)
content = fields.TextField()

# Email
email = fields.EmailField(unique=True)

# URL
website = fields.URLField(null=True)

# UUID
code = fields.UUIDField(default=uuid.uuid4)

# Slug
slug = fields.SlugField(max_length=100)
```

### Numeric Fields

```python
# Integer
count = fields.IntegerField(default=0)

# Float
price = fields.FloatField()

# Decimal
amount = fields.DecimalField(max_digits=10, decimal_places=2)

# Boolean
is_active = fields.BooleanField(default=True)
```

### Date/Time Fields

```python
# DateTime
published_at = fields.DateTimeField(null=True)

# Date
birth_date = fields.DateField()

# Time
start_time = fields.TimeField()

# Auto timestamps
created_at = fields.DateTimeField(auto_now_add=True)
updated_at = fields.DateTimeField(auto_now=True)
```

### Complex Fields

```python
# JSON
metadata = fields.JSONField(default=dict)

# Binary
file_data = fields.BinaryField()
```

### Relationship Fields

```python
# Foreign Key
author = fields.ForeignKey(
    "User",
    on_delete="CASCADE",
    related_name="posts",
    null=True
)

# Many-to-Many
tags = fields.ManyToManyField(
    "Tag",
    related_name="posts",
    through="PostTag"  # Optional intermediate model
)

# Self-referential
parent = fields.ForeignKey(
    "self",
    on_delete="CASCADE",
    null=True,
    related_name="children"
)
```

### Field Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `null` | bool | False | Allow NULL |
| `default` | any | None | Default value |
| `unique` | bool | False | Unique constraint |
| `db_index` | bool | False | Create index |
| `primary_key` | bool | False | Primary key |
| `choices` | list | None | Allowed values |
| `validators` | list | [] | Validator functions |
| `error_messages` | dict | {} | Custom error messages |

### on_delete Options

| Option | Description |
|--------|-------------|
| `CASCADE` | Delete related objects |
| `SET_NULL` | Set to NULL (requires null=True) |
| `PROTECT` | Prevent deletion |
| `SET_DEFAULT` | Set to default value |
| `DO_NOTHING` | No action |

---

## QuerySet

### Basic Queries

```python
# Get all
posts = await Post.objects.all()

# Filter
posts = await Post.objects.filter(is_published=True).all()

# Get single
post = await Post.objects.get(id=post_id)

# First/Last
first = await Post.objects.first()
last = await Post.objects.last()

# Count
count = await Post.objects.count()

# Exists
exists = await Post.objects.filter(title="Test").exists()
```

### Filter Lookups

| Lookup | SQL | Example |
|--------|-----|---------|
| `exact` | `=` | `title="Hello"` |
| `iexact` | `ILIKE` | `title__iexact="hello"` |
| `contains` | `LIKE %x%` | `title__contains="world"` |
| `icontains` | `ILIKE %x%` | `title__icontains="world"` |
| `startswith` | `LIKE x%` | `title__startswith="Hello"` |
| `endswith` | `LIKE %x` | `title__endswith="world"` |
| `gt` | `>` | `views__gt=100` |
| `gte` | `>=` | `views__gte=100` |
| `lt` | `<` | `views__lt=100` |
| `lte` | `<=` | `views__lte=100` |
| `in` | `IN` | `status__in=["a", "b"]` |
| `isnull` | `IS NULL` | `deleted_at__isnull=True` |
| `range` | `BETWEEN` | `date__range=(start, end)` |

### Complex Filters

```python
from vidyut.db import Q

# OR conditions
posts = await Post.objects.filter(
    Q(is_published=True) | Q(author=user)
).all()

# AND conditions (default)
posts = await Post.objects.filter(
    Q(is_published=True) & Q(views__gt=100)
).all()

# NOT conditions
posts = await Post.objects.filter(
    ~Q(status="draft")
).all()

# Combined
posts = await Post.objects.filter(
    Q(is_published=True) & (Q(views__gt=100) | Q(featured=True))
).all()
```

### Ordering

```python
# Ascending
posts = await Post.objects.order_by("created_at").all()

# Descending
posts = await Post.objects.order_by("-created_at").all()

# Multiple fields
posts = await Post.objects.order_by("-is_featured", "-created_at").all()
```

### Limiting

```python
# Limit
posts = await Post.objects.limit(10).all()

# Offset
posts = await Post.objects.offset(20).all()

# Combined (pagination)
posts = await Post.objects.limit(10).offset(20).all()

# Slice notation
posts = await Post.objects[10:20].all()
```

### Aggregations

```python
from vidyut.db import Count, Sum, Avg, Min, Max

# Single aggregation
total = await Post.objects.aggregate(count=Count("id"))

# Multiple
stats = await Post.objects.aggregate(
    count=Count("id"),
    total_views=Sum("views"),
    avg_views=Avg("views"),
)

# Group by
by_author = await Post.objects.values("author_id").annotate(
    post_count=Count("id"),
    total_views=Sum("views"),
).all()
```

### Related Objects

```python
# Select related (ForeignKey)
posts = await Post.objects.select_related("author").all()
# Access: post.author (already loaded)

# Prefetch related (ManyToMany, reverse FK)
posts = await Post.objects.prefetch_related("tags", "comments").all()
# Access: post.tags, post.comments (already loaded)

# Nested prefetch
posts = await Post.objects.prefetch_related(
    "comments",
    "comments__author"
).all()
```

### Field Selection

```python
# Only specific fields
posts = await Post.objects.only("id", "title").all()

# Exclude fields
posts = await Post.objects.defer("content").all()

# Values (dict)
posts = await Post.objects.values("id", "title").all()
# Returns: [{"id": "...", "title": "..."}, ...]

# Values list (tuple)
posts = await Post.objects.values_list("id", "title").all()
# Returns: [("...", "..."), ...]

# Flat values list
ids = await Post.objects.values_list("id", flat=True).all()
# Returns: ["...", "...", ...]
```

### Update & Delete

```python
# Update
await Post.objects.filter(author=user).update(is_published=False)

# Bulk update with F expressions
from vidyut.db import F
await Post.objects.filter(id=post_id).update(views=F("views") + 1)

# Delete
await Post.objects.filter(is_archived=True).delete()
```

### Create

```python
# Single create
post = await Post.objects.create(
    title="Hello",
    content="World",
    author=user
)

# Get or create
post, created = await Post.objects.get_or_create(
    slug="hello-world",
    defaults={"title": "Hello World", "author": user}
)

# Update or create
post, created = await Post.objects.update_or_create(
    slug="hello-world",
    defaults={"title": "Updated Title"}
)

# Bulk create
posts = await Post.objects.bulk_create([
    Post(title="Post 1", author=user),
    Post(title="Post 2", author=user),
])
```

### Raw Queries

```python
# Raw SQL
posts = await Post.objects.raw(
    "SELECT * FROM posts WHERE views > $1",
    [100]
)

# Execute arbitrary SQL
result = await Post.objects.execute(
    "UPDATE posts SET views = views + 1 WHERE id = $1",
    [post_id]
)
```

---

## Manager

### Custom Manager

```python
from vidyut.manager import Manager

class PublishedManager(Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_published=True)
    
    async def featured(self):
        return await self.filter(is_featured=True).all()

class Post(Model):
    # ... fields ...
    
    objects = Manager()  # Default
    published = PublishedManager()  # Custom

# Usage
all_posts = await Post.objects.all()
published_posts = await Post.published.all()
featured_posts = await Post.published.featured()
```

---

## Transactions

```python
from vidyut.db import transaction

# Context manager
async with transaction():
    user = await User.objects.create(email="test@example.com")
    await Profile.objects.create(user=user)

# Decorator
@transaction()
async def create_user_with_profile(email):
    user = await User.objects.create(email=email)
    await Profile.objects.create(user=user)
    return user

# Savepoints
async with transaction():
    user = await User.objects.create(email="test@example.com")
    
    try:
        async with transaction(savepoint=True):
            # This can be rolled back independently
            await send_welcome_email(user)
    except EmailError:
        pass  # Continue without email
```

---

## Migrations

### Commands

```bash
# Create migrations
vidyut makemigrations

# Apply migrations
vidyut migrate

# Show status
vidyut migrate --list

# Rollback
vidyut migrate myapp 0005
```

### Migration File

```python
# migrations/0001_initial.py
from vidyut.migrations import Migration, operations

class Migration(Migration):
    dependencies = []
    
    operations = [
        operations.CreateTable(
            name="posts",
            fields=[
                operations.Column("id", "UUID", primary_key=True),
                operations.Column("title", "VARCHAR(200)"),
                operations.Column("content", "TEXT"),
                operations.Column("created_at", "TIMESTAMP"),
            ]
        ),
        operations.CreateIndex(
            name="posts_title_idx",
            table="posts",
            columns=["title"]
        ),
    ]
```

---

## Related Documentation

- [Models Guide](../orm/models.md)
- [Fields Guide](../orm/fields.md)
- [Querying Guide](../orm/querying.md)
- [Migrations Guide](../orm/migrations.md)
