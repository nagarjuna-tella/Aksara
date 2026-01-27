# Models

Models are the foundation of your Aksara application. They define your data structures and map to PostgreSQL tables.

---

## Overview

A Aksara model is a Python class that:

- Inherits from `aksara.Model`
- Defines fields as class attributes
- Maps to a PostgreSQL table
- Provides async methods for database operations

---

## When to Use Models

Use Aksara models when you need to:

- Store data in PostgreSQL
- Define relationships between entities
- Validate data before saving
- Expose data through APIs
- Generate migrations automatically

---

## Defining a Model

```python
from aksara import Model, fields

class Article(Model):
    """A blog article."""
    
    title = fields.String(max_length=200)
    slug = fields.String(max_length=200, unique=True)
    content = fields.Text()
    excerpt = fields.Text(nullable=True)
    published = fields.Boolean(default=False)
    view_count = fields.Integer(default=0)
    created_at = fields.DateTime(auto_now_add=True)
    updated_at = fields.DateTime(auto_now=True)
```

This creates a table named `articles` with all specified columns plus an auto-generated `id` column.

---

## Automatic Features

### Primary Key

Every model automatically gets a UUID primary key:

```python
class User(Model):
    email = fields.Email(unique=True)
    # `id` field is automatically added

user = await User.objects.create(email="test@example.com")
print(user.id)  # UUID('550e8400-e29b-41d4-a716-446655440000')
```

### Table Name

The table name is automatically derived from the model name:

| Model Name | Table Name |
|------------|------------|
| `Article` | `articles` |
| `User` | `users` |
| `Category` | `categories` |
| `UserProfile` | `user_profiles` |

Override with `__tablename__`:

```python
class Article(Model):
    __tablename__ = "blog_articles"
```

---

## Field Types

Aksara provides many field types. Here's a quick overview:

```python
from aksara import Model, fields

class Product(Model):
    # Text fields
    name = fields.String(max_length=100)
    description = fields.Text()
    sku = fields.String(max_length=50, unique=True)
    
    # Numeric fields
    price = fields.Decimal(precision=10, scale=2)
    quantity = fields.Integer(default=0)
    weight = fields.Float(nullable=True)
    
    # Boolean
    is_active = fields.Boolean(default=True)
    
    # Date/Time
    created_at = fields.DateTime(auto_now_add=True)
    updated_at = fields.DateTime(auto_now=True)
    launch_date = fields.Date(nullable=True)
    
    # Special types
    metadata = fields.JSON(default=dict)
    category = fields.Enum(enum_class=CategoryType)
```

See [Fields](fields.md) for complete documentation.

---

## Model Methods

### Create

```python
# Method 1: Create and save in one step
article = await Article.objects.create(
    title="Hello World",
    content="My first article",
)

# Method 2: Instantiate then save
article = Article(
    title="Hello World",
    content="My first article",
)
await article.save()
```

### Read

```python
# Get by ID
article = await Article.objects.get(id=article_id)

# Get with filters
article = await Article.objects.get(slug="hello-world")

# Get or raise DoesNotExist
from aksara import DoesNotExist

try:
    article = await Article.objects.get(id=invalid_id)
except DoesNotExist:
    print("Article not found")
```

### Update

```python
# Method 1: Modify and save
article.title = "Updated Title"
await article.save()

# Method 2: Update via queryset
await Article.objects.filter(id=article_id).update(title="Updated Title")
```

### Delete

```python
# Method 1: Delete instance
await article.delete()

# Method 2: Delete via queryset
await Article.objects.filter(published=False).delete()
```

---

## Model Meta

Customize model behavior with a `Meta` class:

```python
class Article(Model):
    title = fields.String(max_length=200)
    content = fields.Text()
    
    class Meta:
        app_label = "blog"
        ordering = ["-created_at"]
```

### Available Meta Options

| Option | Type | Description |
|--------|------|-------------|
| `app_label` | `str` | Application namespace |
| `ordering` | `list[str]` | Default ordering |

---

## AI Metadata

Aksara models support AI metadata for LLM integration:

### Model-Level AI Metadata

```python
class User(Model):
    """User account for the application."""
    
    email = fields.Email(unique=True)
    name = fields.String(max_length=100)
    
    class AIMeta:
        ai_name = "User Account"
        ai_description = "Represents a registered user in the system"
        ai_agent_exposed = True
        ai_permissions = ["read", "write"]
```

### Field-Level AI Metadata

```python
class User(Model):
    email = fields.Email(
        unique=True,
        ai_description="User's email address for authentication",
        ai_sensitive=False,
        ai_agent_writable=True,
    )
    
    hashed_password = fields.String(
        ai_description="Bcrypt-hashed password",
        ai_sensitive=True,       # Hidden from AI context
        ai_agent_writable=False, # AI cannot modify
    )
    
    is_active = fields.Boolean(
        default=True,
        ai_description="Whether the user can log in",
        ai_agent_writable=True,
    )
```

### AI Metadata Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `ai_description` | `str` | `""` | Human-readable description |
| `ai_sensitive` | `bool` | `False` | Hide from AI context |
| `ai_agent_writable` | `bool` | `True` | Allow AI modifications |

---

## Timestamps

Automatic timestamp handling:

```python
class Article(Model):
    title = fields.String(max_length=200)
    
    # Set once on creation
    created_at = fields.DateTime(auto_now_add=True)
    
    # Updated on every save
    updated_at = fields.DateTime(auto_now=True)
```

Behavior:

| Field Option | On Create | On Update |
|--------------|-----------|-----------|
| `auto_now_add=True` | Current time | Unchanged |
| `auto_now=True` | Current time | Current time |

---

## Abstract Models

Create reusable base models:

```python
class TimestampMixin(Model):
    """Mixin for automatic timestamps."""
    __abstract__ = True
    
    created_at = fields.DateTime(auto_now_add=True)
    updated_at = fields.DateTime(auto_now=True)


class Article(TimestampMixin):
    title = fields.String(max_length=200)
    content = fields.Text()
    # Inherits created_at and updated_at
```

The `__abstract__ = True` prevents table creation for the base class.

---

## Model Validation

Aksara validates data before saving:

```python
class User(Model):
    email = fields.Email(unique=True)  # Validates email format
    age = fields.Integer()

# This raises ValidationError
user = User(email="invalid-email", age="not-a-number")
await user.save()  # ValidationError
```

### Custom Validation

Override `clean()` for custom validation:

```python
class Event(Model):
    start_date = fields.DateTime()
    end_date = fields.DateTime()
    
    async def clean(self):
        if self.end_date <= self.start_date:
            raise ValidationError("End date must be after start date")
```

---

## Example: Complete Model

```python
from aksara import Model, fields
from enum import Enum


class ArticleStatus(str, Enum):
    DRAFT = "draft"
    REVIEW = "review"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class Article(Model):
    """
    A blog article with full content management features.
    """
    
    # Core content
    title = fields.String(
        max_length=200,
        ai_description="Article headline",
    )
    slug = fields.String(
        max_length=200,
        unique=True,
        ai_description="URL-friendly identifier",
    )
    content = fields.Text(
        ai_description="Full article content in Markdown",
    )
    excerpt = fields.Text(
        nullable=True,
        ai_description="Short summary for previews",
    )
    
    # Metadata
    status = fields.Enum(
        enum_class=ArticleStatus,
        default=ArticleStatus.DRAFT,
        ai_description="Publication status",
    )
    featured = fields.Boolean(
        default=False,
        ai_description="Show in featured section",
    )
    view_count = fields.Integer(
        default=0,
        ai_agent_writable=False,
        ai_description="Number of page views",
    )
    
    # SEO
    meta_title = fields.String(max_length=60, nullable=True)
    meta_description = fields.String(max_length=160, nullable=True)
    
    # Timestamps
    created_at = fields.DateTime(auto_now_add=True)
    updated_at = fields.DateTime(auto_now=True)
    published_at = fields.DateTime(nullable=True)
    
    class Meta:
        app_label = "blog"
    
    class AIMeta:
        ai_name = "Blog Article"
        ai_description = "A blog post with content and metadata"
        ai_permissions = ["read", "write"]
    
    def __str__(self) -> str:
        return self.title
    
    async def publish(self):
        """Publish the article."""
        from datetime import datetime, timezone
        self.status = ArticleStatus.PUBLISHED
        self.published_at = datetime.now(timezone.utc)
        await self.save()
```

---

## Best Practices

### Use Descriptive Names

```python
# Good
class UserSubscription(Model):
    plan_type = fields.String(max_length=50)
    expires_at = fields.DateTime()

# Avoid
class Sub(Model):
    type = fields.String(max_length=50)
    exp = fields.DateTime()
```

### Add AI Metadata for Sensitive Fields

```python
class User(Model):
    email = fields.Email(ai_sensitive=False)
    ssn = fields.String(ai_sensitive=True)  # Hidden from AI
    password = fields.String(ai_sensitive=True, ai_agent_writable=False)
```

### Use Abstract Models for Shared Fields

```python
class AuditMixin(Model):
    __abstract__ = True
    created_at = fields.DateTime(auto_now_add=True)
    updated_at = fields.DateTime(auto_now=True)
    created_by = fields.ForeignKey("User", nullable=True)

class Article(AuditMixin):
    title = fields.String(max_length=200)
```

### Keep Models Focused

Each model should represent one entity:

```python
# Good: Separate models
class User(Model):
    email = fields.Email(unique=True)

class UserProfile(Model):
    user = fields.OneToOne(User)
    bio = fields.Text()
    avatar_url = fields.URL(nullable=True)

# Avoid: Everything in one model
class User(Model):
    email = fields.Email()
    bio = fields.Text()
    avatar_url = fields.URL()
    # ... 50 more fields
```

---

## Related Documentation

- [Fields](fields.md) — All available field types
- [Relations](relations.md) — Model relationships
- [Querying](querying.md) — Query API
- [Migrations](migrations.md) — Schema management
- [Model Meta](model-meta.md) — Introspection API
