# ORM Reference

Complete reference for Aksara's ORM — all field types, query methods, and model options.

---

## Field Types

All fields are imported from `aksara.fields`:

```python
from aksara import fields
```

### String Fields

| Field | Description | Common Options |
|-------|-------------|----------------|
| `fields.String` | Text with maximum length | `max_length`, `default`, `null` |
| `fields.Text` | Unlimited text | `default`, `null` |
| `fields.Email` | Email addresses (validated) | `unique`, `default`, `null` |
| `fields.URL` | Web URLs (validated) | `default`, `null` |
| `fields.Slug` | URL-safe strings | `max_length`, `unique` |
| `fields.UUID` | Unique identifiers | `default`, `primary_key` |

```python
# Example usage
class Article(Model):
    title = fields.String(max_length=200)      # Required, up to 200 chars
    body = fields.Text()                        # Unlimited length
    author_email = fields.Email(unique=True)   # Must be valid email
    source_url = fields.URL(null=True)         # Optional URL
    slug = fields.Slug(max_length=100)         # URL-safe: "my-article"
```

---

### Numeric Fields

| Field | Description | Common Options |
|-------|-------------|----------------|
| `fields.Integer` | Whole numbers | `default`, `null` |
| `fields.SmallInteger` | Small whole numbers (-32768..32767) | `default`, `null` |
| `fields.BigInteger` | Large whole numbers | `default`, `null` |
| `fields.PositiveInteger` | Non-negative integers | `default`, `null` |
| `fields.PositiveSmallInteger` | Non-negative small integers (0..32767) | `default`, `null` |
| `fields.PositiveBigInteger` | Non-negative large integers | `default`, `null` |
| `fields.Float` | Decimal numbers | `default`, `null` |
| `fields.Decimal` | Precise decimals (money) | `max_digits`, `decimal_places` |
| `fields.Boolean` | True/False | `default`, `null` |

```python
class Product(Model):
    quantity = fields.Integer(default=0)        # Stock count
    price = fields.Decimal(                     # Precise money
        max_digits=10,                          # Up to 10 total digits
        decimal_places=2                        # 2 after decimal point
    )
    rating = fields.Float(null=True)            # Average rating
    is_available = fields.Boolean(default=True) # In stock?
```

---

### Date and Time Fields

| Field | Description | Common Options |
|-------|-------------|----------------|
| `fields.DateTime` | Date and time | `auto_now`, `auto_now_add`, `default` |
| `fields.Date` | Date only | `auto_now`, `auto_now_add` |
| `fields.Time` | Time only | `default` |
| `fields.Duration` | Time spans | `default` |

```python
class Event(Model):
    # Automatically set when created
    created_at = fields.DateTime(auto_now_add=True)
    
    # Automatically updated on every save
    updated_at = fields.DateTime(auto_now=True)
    
    # User-provided values
    event_date = fields.Date()
    start_time = fields.Time()
    duration = fields.Duration()  # e.g., timedelta(hours=2)
```

---

### Relationship Fields

| Field | Description | Required Options |
|-------|-------------|------------------|
| `fields.ForeignKey` | Many-to-one relationship | `to`, `on_delete` |
| `fields.OneToOne` | One-to-one relationship | `to`, `on_delete` |
| `fields.ManyToMany` | Many-to-many relationship | `to` |

```python
class Comment(Model):
    # Many comments belong to one article
    article = fields.ForeignKey(
        to="Article",                           # Related model
        on_delete=fields.CASCADE,               # Delete comment if article deleted
        related_name="comments"                 # Access from article: article.comments
    )
    
class Profile(Model):
    # One profile per user
    user = fields.OneToOne(
        to="User",
        on_delete=fields.CASCADE,
        related_name="profile"                  # Access: user.profile
    )

class Article(Model):
    # Articles can have many tags, tags can be on many articles
    tags = fields.ManyToMany(
        to="Tag",
        related_name="articles"                 # Access: tag.articles
    )
```

---

### Special Fields

| Field | Description | Common Options |
|-------|-------------|----------------|
| `fields.JSON` | JSON data | `default`, `null` |
| `fields.Array` | List of values | `base_field` |
| `fields.File` | File uploads | `upload_to` |
| `fields.Image` | Image uploads | `upload_to` |
| `fields.IP` | IP addresses | `protocol`, `null` |
| `fields.Binary` | Raw binary data (BYTEA) | `null` |
| `fields.FilePath` | Filesystem paths | `path`, `match`, `recursive` |

```python
class Configuration(Model):
    settings = fields.JSON(default=dict)        # {"theme": "dark", "lang": "en"}
    tags = fields.Array(base_field=fields.String(max_length=50))  # ["python", "web"]
    
class Document(Model):
    file = fields.File(upload_to="documents/")
    thumbnail = fields.Image(upload_to="thumbnails/")
```

---

## Field Options

Options that work on all (or most) field types:

| Option | Type | Description |
|--------|------|-------------|
| `null` | bool | Allow NULL in database (default: False) |
| `blank` | bool | Allow empty in forms (default: False) |
| `default` | any | Default value when not provided |
| `unique` | bool | Must be unique across all rows |
| `primary_key` | bool | Use as primary key instead of auto `id` |
| `db_index` | bool | Create database index for faster lookups |
| `db_column` | str | Custom column name in database |
| `choices` | list | Limit to specific values |
| `validators` | list | Custom validation functions |
| `verbose_name` | str | Human-readable name |
| `help_text` | str | Description for forms/docs |

```python
class User(Model):
    email = fields.Email(
        unique=True,                            # No duplicates
        db_index=True,                          # Fast lookups by email
        verbose_name="Email Address",
        help_text="User's primary email"
    )
    
    status = fields.String(
        max_length=20,
        choices=[                               # Only these values allowed
            ("active", "Active"),
            ("inactive", "Inactive"),
            ("pending", "Pending"),
        ],
        default="pending"
    )
```

---

## on_delete Options

When a ForeignKey target is deleted:

| Option | What Happens |
|--------|--------------|
| `fields.CASCADE` | Delete this object too |
| `fields.PROTECT` | Prevent deletion (raise error) |
| `fields.SET_NULL` | Set to NULL (requires `null=True`) |
| `fields.SET_DEFAULT` | Set to default value |
| `fields.DO_NOTHING` | Do nothing (may break integrity) |

```python
class Comment(Model):
    # If article deleted, delete all its comments
    article = fields.ForeignKey(Article, on_delete=fields.CASCADE)
    
    # Can't delete author if they have comments
    author = fields.ForeignKey(User, on_delete=fields.PROTECT)
    
    # If parent comment deleted, set to NULL (orphan)
    parent = fields.ForeignKey(
        "self",
        on_delete=fields.SET_NULL,
        null=True
    )
```

---

## QuerySet Methods

### Retrieving Objects

| Method | Returns | Description |
|--------|---------|-------------|
| `.all()` | QuerySet | All objects |
| `.get(**kwargs)` | Object | Single object matching criteria |
| `.first()` | Object/None | First object or None |
| `.last()` | Object/None | Last object or None |
| `.filter(**kwargs)` | QuerySet | Objects matching criteria |
| `.exclude(**kwargs)` | QuerySet | Objects NOT matching criteria |

```python
# Get all users
users = await User.objects.all()

# Get one specific user (raises DoesNotExist if not found)
user = await User.objects.get(id=1)
user = await User.objects.get(email="test@example.com")

# Get first/last
first_user = await User.objects.first()
latest = await User.objects.order_by("-created_at").first()

# Filter (returns QuerySet, can have multiple results)
active_users = await User.objects.filter(is_active=True)
```

---

### Filter Lookups

Use double underscores for comparisons:

| Lookup | SQL Equivalent | Example |
|--------|----------------|---------|
| `field` | `=` | `name="John"` |
| `field__exact` | `=` | `name__exact="John"` |
| `field__iexact` | `ILIKE` | `name__iexact="john"` (case-insensitive) |
| `field__contains` | `LIKE '%x%'` | `name__contains="oh"` |
| `field__icontains` | `ILIKE '%x%'` | `name__icontains="oh"` |
| `field__startswith` | `LIKE 'x%'` | `name__startswith="J"` |
| `field__endswith` | `LIKE '%x'` | `name__endswith="n"` |
| `field__gt` | `>` | `age__gt=18` |
| `field__gte` | `>=` | `age__gte=18` |
| `field__lt` | `<` | `age__lt=65` |
| `field__lte` | `<=` | `age__lte=65` |
| `field__in` | `IN (...)` | `status__in=["active", "pending"]` |
| `field__isnull` | `IS NULL` | `deleted_at__isnull=True` |
| `field__range` | `BETWEEN` | `age__range=(18, 65)` |

```python
# Users named John (case-insensitive)
await User.objects.filter(name__iexact="john")

# Users with gmail addresses
await User.objects.filter(email__endswith="@gmail.com")

# Users older than 18
await User.objects.filter(age__gt=18)

# Users in multiple statuses
await User.objects.filter(status__in=["active", "pending"])

# Users created in date range
from datetime import date
await User.objects.filter(
    created_at__range=(date(2024, 1, 1), date(2024, 12, 31))
)
```

---

### Ordering

| Method | Description |
|--------|-------------|
| `.order_by("field")` | Ascending order |
| `.order_by("-field")` | Descending order (note the `-`) |
| `.order_by("f1", "f2")` | Multiple fields |

```python
# Oldest first
users = await User.objects.order_by("created_at")

# Newest first (note the minus sign)
users = await User.objects.order_by("-created_at")

# Sort by status, then by name within each status
users = await User.objects.order_by("status", "name")
```

---

### Limiting Results

| Method | Description |
|--------|-------------|
| `[:n]` | First n results |
| `[n:m]` | Results from n to m |
| `.limit(n)` | First n results |
| `.offset(n)` | Skip first n results |

```python
# First 10 users
first_ten = await User.objects.all()[:10]

# Skip first 10, get next 10 (pagination)
page_two = await User.objects.all()[10:20]

# Using methods
await User.objects.limit(10).offset(20)  # Page 3
```

---

### Aggregations

| Method | Returns | Description |
|--------|---------|-------------|
| `.count()` | int | Number of objects |
| `.exists()` | bool | True if any objects exist |
| `.aggregate(...)` | dict | Computed values |
| `.values("field")` | QuerySet | Dictionaries instead of objects |
| `.values_list("field")` | QuerySet | Tuples instead of objects |
| `.distinct()` | QuerySet | Remove duplicates |

```python
# How many users?
total = await User.objects.count()

# Any active users?
has_active = await User.objects.filter(is_active=True).exists()

# Sum and average
from aksara.db import Sum, Avg
stats = await Order.objects.aggregate(
    total=Sum("amount"),
    average=Avg("amount")
)
# {"total": 50000, "average": 125.50}

# Just the emails (as dictionaries)
emails = await User.objects.values("email")
# [{"email": "a@b.com"}, {"email": "c@d.com"}]

# Just the emails (as tuples)
emails = await User.objects.values_list("email", flat=True)
# ["a@b.com", "c@d.com"]
```

---

### Modifying Data

| Method | Description |
|--------|-------------|
| `.create(**kwargs)` | Create and save new object |
| `.update(**kwargs)` | Update all matching objects |
| `.delete()` | Delete all matching objects |
| `.get_or_create(**kwargs)` | Get existing or create new |
| `.update_or_create(**kwargs)` | Update existing or create new |
| `.bulk_create(objects)` | Create many objects at once |
| `.bulk_update(objects, fields)` | Update many objects at once |

```python
# Create
user = await User.objects.create(
    email="new@example.com",
    name="New User"
)

# Update all matching objects
await User.objects.filter(is_active=False).update(status="inactive")

# Delete all matching objects
await User.objects.filter(status="deleted").delete()

# Get or create (won't duplicate)
user, created = await User.objects.get_or_create(
    email="test@example.com",
    defaults={"name": "Test User"}  # Only used if creating
)

# Bulk create (efficient for many objects)
users = [
    User(email="a@b.com", name="A"),
    User(email="c@d.com", name="C"),
]
await User.objects.bulk_create(users)
```

---

## Model Class Options

Set in the `Meta` class inside your model:

```python
class Article(Model):
    title = fields.String(max_length=200)
    
    class Meta:
        table_name = "articles"          # Custom table name
        ordering = ["-created_at"]       # Default ordering
        unique_together = [              # Compound unique constraints
            ("author", "slug")
        ]
        indexes = [                      # Database indexes
            ["status", "created_at"]
        ]
        verbose_name = "Article"
        verbose_name_plural = "Articles"
```

| Option | Type | Description |
|--------|------|-------------|
| `table_name` | str | Custom database table name |
| `ordering` | list | Default sort order |
| `unique_together` | list | Compound uniqueness constraints |
| `indexes` | list | Database indexes |
| `verbose_name` | str | Human-readable name |
| `verbose_name_plural` | str | Plural form of name |
| `abstract` | bool | Don't create table (for inheritance) |

---

## Model Methods

| Method | Description |
|--------|-------------|
| `await obj.save()` | Save to database |
| `await obj.delete()` | Delete from database |
| `await obj.refresh_from_db()` | Reload from database |
| `obj.pk` | Primary key value |

```python
# Create and save
user = User(email="test@example.com", name="Test")
await user.save()

# Modify and save
user.name = "Updated Name"
await user.save()

# Delete
await user.delete()

# Reload from database (if modified elsewhere)
await user.refresh_from_db()
```

---

## Related Objects

### Following Relationships

```python
# Forward: Comment → Article
comment = await Comment.objects.get(id=1)
article = await comment.article  # Get the article

# Reverse: Article → Comments
article = await Article.objects.get(id=1)
comments = await article.comments.all()  # Get all comments
```

### Prefetching (Avoiding N+1 Queries)

```python
# BAD: N+1 queries
articles = await Article.objects.all()
for article in articles:
    author = await article.author  # Query for each article!

# GOOD: 2 queries total
articles = await Article.objects.select_related("author").all()
for article in articles:
    author = article.author  # Already loaded!

# For reverse relations (many), use prefetch_related
articles = await Article.objects.prefetch_related("comments").all()
```

---

## Manager Reference

Every model has a `objects` manager:

```python
User.objects.all()      # Default manager
User.objects.filter()   # Also on default manager
```

### Custom Managers

```python
class PublishedManager(Manager):
    def get_queryset(self):
        return super().get_queryset().filter(status="published")

class Article(Model):
    status = fields.String(max_length=20)
    
    objects = Manager()               # Default: all articles
    published = PublishedManager()    # Only published articles

# Usage
all_articles = await Article.objects.all()
published_only = await Article.published.all()
```

---

## See Also

- [Models Guide](../orm/models.md) — Step-by-step model creation
- [Querying Guide](../orm/querying.md) — In-depth query examples
- [Relations Guide](../orm/relations.md) — Working with relationships
- [Migrations Guide](../orm/migrations.md) — Database schema changes
