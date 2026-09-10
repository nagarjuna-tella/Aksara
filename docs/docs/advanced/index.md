# Advanced Topics

Deep dives into advanced Aksara features.

---

## Overview

These guides cover advanced patterns and features:

| Topic | Description |
|-------|-------------|
| [Signals](signals.md) | Model lifecycle hooks |
| [Custom Fields](custom-fields.md) | Creating custom field types |
| [Generic Relations and Durable Workflows](generic-relations-and-durable-workflows.md) | Model-agnostic relations and resumable step execution |
| [Background Tasks](background-tasks.md) | PostgreSQL-backed queueing and worker lifecycle |
| [Validation](validation.md) | Advanced validation patterns |
| [Caching](caching.md) | Query and response caching |
| [Testing](testing.md) | Testing patterns and fixtures |
| [Performance](performance.md) | Optimization techniques |

---

## Prerequisites

These guides assume familiarity with:

- [Models](../orm/models.md)
- [ViewSets](../api/viewsets.md)
- [Middleware](../middleware/index.md)

---

## Quick Links

### Signals

Hook into model lifecycle events:

```python
from aksara import Model, fields
from aksara.signals import pre_save, post_save

class Post(Model):
    title = fields.String(max_length=200)
    slug = fields.String(max_length=200)

@pre_save(Post)
async def generate_slug(sender, instance, **kwargs):
    if not instance.slug:
        instance.slug = slugify(instance.title)
```

→ [Learn about Signals](signals.md)

### Custom Fields

Create specialized field types:

```python
from aksara.fields import Field

class PhoneField(Field):
    def __init__(self, region="US", **kwargs):
        self.region = region
        super().__init__(**kwargs)
    
    def validate(self, value):
        # Custom validation
        pass
```

→ [Create Custom Fields](custom-fields.md)

### Validation

Complex validation patterns:

**Conceptual or legacy pseudocode (not an installed-package API):**

```text title="Conceptual or legacy pseudocode"
from aksara.validation import validator, ValidationError

class Order(Model):
    @validator("quantity")
    def validate_quantity(cls, v):
        if v <= 0:
            raise ValidationError("Must be positive")
        return v
```

→ [Advanced Validation](validation.md)

### Caching

Speed up your application:

**Conceptual or legacy pseudocode (not an installed-package API):**

```text title="Conceptual or legacy pseudocode"
from aksara.cache import cached, cache

# Cache query results
@cached(ttl=300)
async def get_popular_posts():
    return await Post.objects.filter(is_popular=True).all()
```

→ [Caching Guide](caching.md)

### Testing

Comprehensive testing:

**Conceptual or legacy pseudocode (not an installed-package API):**

```text title="Conceptual or legacy pseudocode"
from aksara.testing import AksaraTestCase, factory

class UserFactory(factory.Factory):
    class Meta:
        model = User
    
    email = factory.Faker("email")
    name = factory.Faker("name")
```

→ [Testing Patterns](testing.md)

### Performance

Optimize your application:

**Conceptual or legacy pseudocode (not an installed-package API):**

```text title="Conceptual or legacy pseudocode"
# N+1 prevention
posts = await Post.objects.select_related("author").prefetch_related("comments").all()

# Query profiling
from aksara.debug import profile_queries

@profile_queries
async def my_view():
    # Queries are logged and analyzed
    pass
```

→ [Performance Guide](performance.md)

---

## Related Documentation

- [ORM Guide](../orm/index.md)
- [API Guide](../api/index.md)
- [Reference](../reference/index.md)
