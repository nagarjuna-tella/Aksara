# ORM

Vidyut's Object-Relational Mapping layer provides a Django-like API that's fully async and PostgreSQL-native.

---

## Overview

The Vidyut ORM is designed with three core principles:

1. **Async-Native** — Every operation is async, no blocking calls
2. **Django-Like API** — Familiar patterns if you've used Django
3. **PostgreSQL-Optimized** — Leverages PostgreSQL-specific features

---

## Quick Example

```python
from vidyut import Model, fields

# Define a model
class Article(Model):
    title = fields.String(max_length=200)
    content = fields.Text()
    published = fields.Boolean(default=False)
    created_at = fields.DateTime(auto_now_add=True)

# Create
article = await Article.objects.create(
    title="Hello World",
    content="My first article"
)

# Query
articles = await Article.objects.filter(published=True).order_by("-created_at")

# Update
article.published = True
await article.save()

# Delete
await article.delete()
```

---

## Sections

<div class="grid cards" markdown>

-   :material-shape:{ .lg .middle } **Models**

    ---

    Define your data structures with model classes.

    [:octicons-arrow-right-24: Models Guide](models.md)

-   :material-format-list-bulleted-type:{ .lg .middle } **Fields**

    ---

    All available field types and options.

    [:octicons-arrow-right-24: Fields Reference](fields.md)

-   :material-relation-many-to-many:{ .lg .middle } **Relations**

    ---

    ForeignKey, ManyToMany, OneToOne relationships.

    [:octicons-arrow-right-24: Relations Guide](relations.md)

-   :material-database-search:{ .lg .middle } **Querying**

    ---

    Filter, order, and retrieve data efficiently.

    [:octicons-arrow-right-24: Query Guide](querying.md)

-   :material-database-sync:{ .lg .middle } **Migrations**

    ---

    Manage database schema changes.

    [:octicons-arrow-right-24: Migrations Guide](migrations.md)

-   :material-information:{ .lg .middle } **Model Meta**

    ---

    Introspection and metadata APIs.

    [:octicons-arrow-right-24: Meta API](model-meta.md)

</div>

---

## Key Features

### Automatic Primary Keys

Every model gets a UUID primary key:

```python
class User(Model):
    email = fields.Email(unique=True)
    # `id` is automatically added as UUID primary key
```

### Automatic Timestamps

Use `auto_now_add` and `auto_now` for automatic timestamps:

```python
class Article(Model):
    created_at = fields.DateTime(auto_now_add=True)  # Set on create
    updated_at = fields.DateTime(auto_now=True)      # Set on every save
```

### AI Metadata

Every field supports AI metadata for LLM integration:

```python
class User(Model):
    email = fields.Email(
        ai_description="User's email address for login",
        ai_sensitive=False,
        ai_agent_writable=True,
    )
    password = fields.String(
        ai_description="Hashed password",
        ai_sensitive=True,
        ai_agent_writable=False,  # AI can't modify passwords
    )
```

### Type Safety

Full type hints for IDE support:

```python
article: Article = await Article.objects.get(id=article_id)
articles: list[Article] = await Article.objects.filter(published=True)
```

---

## Comparison with Other ORMs

| Feature | Vidyut | Django ORM | SQLAlchemy | Tortoise ORM |
|---------|--------|------------|------------|--------------|
| Async Native | ✅ | ❌ | ⚠️ (2.0+) | ✅ |
| Django-like API | ✅ | ✅ | ❌ | ⚠️ |
| Auto Migrations | ✅ | ✅ | ⚠️ (Alembic) | ✅ |
| AI Metadata | ✅ | ❌ | ❌ | ❌ |
| PostgreSQL-Only | ✅ | ❌ | ❌ | ❌ |

---

## Next Steps

Start with [Models](models.md) to learn how to define your data structures.
