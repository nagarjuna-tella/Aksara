# Fields

Field types define how data is stored in PostgreSQL and validated in Python.

---

## Overview

Every field in Aksara maps to a PostgreSQL column type and provides:

- **Type validation** — Ensures correct Python types
- **Database mapping** — Converts to/from PostgreSQL types
- **AI metadata** — Describes the field to LLMs
- **Constraints** — Unique, nullable, default values

---

## Common Field Options

All fields support these options:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `nullable` | `bool` | `False` | Allow NULL values |
| `default` | `Any` | `None` | Default value |
| `unique` | `bool` | `False` | Enforce uniqueness |
| `primary_key` | `bool` | `False` | Mark as primary key |
| `db_index` | `bool` | `False` | Create database index |
| `ai_description` | `str` | `""` | Description for AI agents |
| `ai_sensitive` | `bool` | `False` | Hide from AI context |
| `ai_agent_writable` | `bool` | `True` | Allow AI to modify |

Example:

```python
class User(Model):
    email = fields.Email(
        unique=True,
        nullable=False,
        ai_description="User's login email address",
        ai_sensitive=False,
    )
```

---

## Text Fields

### String

Variable-length text with a maximum length.

```python
name = fields.String(max_length=100)
code = fields.String(max_length=10, unique=True)
nickname = fields.String(max_length=50, nullable=True)
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `max_length` | `int` | `255` | Maximum character length |

PostgreSQL type: `VARCHAR(max_length)`

### Text

Unlimited length text for large content.

```python
content = fields.Text()
description = fields.Text(nullable=True)
notes = fields.Text(default="")
```

PostgreSQL type: `TEXT`

!!! tip "When to Use Text vs String"
    - Use `String` for short, bounded content (names, codes, slugs)
    - Use `Text` for long content (articles, descriptions, JSON strings)

### Email

Email addresses with format validation.

```python
email = fields.Email(unique=True)
contact_email = fields.Email(nullable=True)
```

PostgreSQL type: `VARCHAR(254)` (maximum email length per RFC)

Validation: Must match email format pattern.

### URL

URLs with format validation.

```python
website = fields.URL(nullable=True)
avatar_url = fields.URL()
```

PostgreSQL type: `TEXT`

Validation: Must be a valid HTTP/HTTPS URL.

---

## Numeric Fields

### Integer

Standard 32-bit integer.

```python
age = fields.Integer()
quantity = fields.Integer(default=0)
position = fields.Integer(nullable=True)
```

PostgreSQL type: `INTEGER`

Range: -2,147,483,648 to 2,147,483,647

### BigInteger

64-bit integer for large numbers.

```python
view_count = fields.BigInteger(default=0)
file_size = fields.BigInteger()
```

PostgreSQL type: `BIGINT`

Range: -9,223,372,036,854,775,808 to 9,223,372,036,854,775,807

### Float

Floating-point number.

```python
rating = fields.Float()
latitude = fields.Float()
longitude = fields.Float()
```

PostgreSQL type: `DOUBLE PRECISION`

!!! warning "Precision"
    Float is not suitable for monetary values due to precision issues. Use `Decimal` instead.

### Decimal

Exact decimal for financial data.

```python
price = fields.Decimal(precision=10, scale=2)
tax_rate = fields.Decimal(precision=5, scale=4)
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `precision` | `int` | `10` | Total digits |
| `scale` | `int` | `2` | Digits after decimal |

PostgreSQL type: `NUMERIC(precision, scale)`

Example values with `precision=10, scale=2`:
- Valid: `12345678.90`, `0.01`, `-999.99`
- Invalid: `123456789.00` (too many digits)

---

## Boolean Field

### Boolean

True/False values.

```python
is_active = fields.Boolean(default=True)
is_verified = fields.Boolean(default=False)
newsletter_opted_in = fields.Boolean(nullable=True)  # True, False, or unknown
```

PostgreSQL type: `BOOLEAN`

---

## Date and Time Fields

### DateTime

Timestamp with timezone.

```python
created_at = fields.DateTime(auto_now_add=True)
updated_at = fields.DateTime(auto_now=True)
scheduled_at = fields.DateTime(nullable=True)
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `auto_now_add` | `bool` | `False` | Set on creation only |
| `auto_now` | `bool` | `False` | Set on every save |

PostgreSQL type: `TIMESTAMP WITH TIME ZONE`

### Date

Date without time.

```python
birth_date = fields.Date()
expiry_date = fields.Date(nullable=True)
```

PostgreSQL type: `DATE`

---

## Special Fields

### UUID

Universally unique identifier.

```python
external_id = fields.UUID()
reference = fields.UUID(unique=True)
```

PostgreSQL type: `UUID`

!!! note "Primary Key"
    The model's `id` field is automatically a UUID primary key. You don't need to define it.

### JSON

JSON/JSONB data.

```python
metadata = fields.JSON(default=dict)
settings = fields.JSON(default=list)
config = fields.JSON(nullable=True)
```

PostgreSQL type: `JSONB` (binary JSON for efficient querying)

Example usage:

```python
class User(Model):
    preferences = fields.JSON(default=dict)

user = await User.objects.create(
    preferences={"theme": "dark", "notifications": True}
)
```

### Enum

Enumerated values.

```python
from enum import Enum

class Status(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"

class Article(Model):
    status = fields.Enum(enum_class=Status, default=Status.DRAFT)
```

| Option | Type | Required | Description |
|--------|------|----------|-------------|
| `enum_class` | `type[Enum]` | Yes | The enum class |

PostgreSQL type: `VARCHAR` (stores the string value)

### Array

PostgreSQL array columns for storing lists of values.

```python
tags = fields.Array(base_type="text", default=list)
scores = fields.Array(base_type="integer", nullable=True)
ratings = fields.Array(base_type="float")
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `base_type` | `str` | `"text"` | Element type: `text`, `integer`, `float`, `boolean`, `uuid` |

PostgreSQL types:

| `base_type` | PostgreSQL Type |
|-------------|----------------|
| `text` | `TEXT[]` |
| `integer` | `INTEGER[]` |
| `float` | `DOUBLE PRECISION[]` |
| `boolean` | `BOOLEAN[]` |
| `uuid` | `UUID[]` |

Example usage:

```python
class Article(Model):
    tags = fields.Array(base_type="text", default=list)
    view_counts = fields.Array(base_type="integer", default=list)

article = await Article.objects.create(
    tags=["python", "async", "orm"],
    view_counts=[100, 250, 180],
)

# Access as Python lists
print(article.tags)  # ['python', 'async', 'orm']
article.tags.append("database")
await article.save()
```

!!! tip "When to Use Array vs JSON"
    - Use `Array` for homogeneous lists (all same type) that need indexing
    - Use `JSON` for heterogeneous data or nested structures
    - PostgreSQL array operators work with `Array` fields

---

## Relationship Fields

### ForeignKey

Many-to-one relationship.

```python
from aksara import fields, CASCADE

class Post(Model):
    author = fields.ForeignKey(
        "User",
        on_delete=CASCADE,
        related_name="posts",
    )
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `to` | `str` or `type` | Required | Target model |
| `on_delete` | `str` | `CASCADE` | Delete behavior |
| `related_name` | `str` | Auto | Reverse accessor name |
| `nullable` | `bool` | `False` | Allow NULL |

See [Relations](relations.md) for detailed documentation.

### ManyToMany

Many-to-many relationship.

```python
class Post(Model):
    tags = fields.ManyToMany(
        "Tag",
        related_name="posts",
    )
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `to` | `str` or `type` | Required | Target model |
| `related_name` | `str` | Auto | Reverse accessor name |
| `through` | `str` | Auto | Junction table name |

### OneToOne

One-to-one relationship.

```python
class UserProfile(Model):
    user = fields.OneToOne(
        "User",
        on_delete=CASCADE,
        related_name="profile",
    )
```

Similar to ForeignKey but enforces uniqueness.

---

## on_delete Options

When a referenced object is deleted:

| Value | Behavior |
|-------|----------|
| `CASCADE` | Delete this object too |
| `SET_NULL` | Set the FK to NULL (requires `nullable=True`) |
| `RESTRICT` | Prevent deletion if references exist |
| `PROTECT` | Alias for RESTRICT |

```python
from aksara import fields, CASCADE, SET_NULL, RESTRICT

class Post(Model):
    # Delete posts when author is deleted
    author = fields.ForeignKey(User, on_delete=CASCADE)
    
    # Set to NULL when category is deleted
    category = fields.ForeignKey(Category, on_delete=SET_NULL, nullable=True)
    
    # Prevent deletion if posts reference this tag
    primary_tag = fields.ForeignKey(Tag, on_delete=RESTRICT)
```

---

## AI Metadata

Every field supports AI metadata:

```python
class User(Model):
    email = fields.Email(
        unique=True,
        ai_description="User's email address for login and notifications",
        ai_sensitive=False,
        ai_agent_writable=True,
    )
    
    hashed_password = fields.String(
        ai_description="Bcrypt-hashed password (never expose raw)",
        ai_sensitive=True,       # Hidden from AI context exports
        ai_agent_writable=False, # AI cannot modify this field
    )
    
    role = fields.String(
        max_length=20,
        default="user",
        ai_description="User role: 'user', 'admin', or 'moderator'",
        ai_agent_writable=True,  # AI can change roles
    )
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `ai_description` | `str` | `""` | Human-readable description for LLMs |
| `ai_sensitive` | `bool` | `False` | Exclude from AI context exports |
| `ai_agent_writable` | `bool` | `True` | Whether AI agents can modify |

---

## Field Validation

Fields validate data automatically:

```python
from aksara.exceptions import ValidationError

class User(Model):
    email = fields.Email()
    age = fields.Integer()

# Invalid email format
try:
    user = User(email="not-an-email", age=25)
    await user.save()
except ValidationError as e:
    print(e)  # "Invalid email format"

# Invalid integer
try:
    user = User(email="test@example.com", age="twenty")
    await user.save()
except ValidationError as e:
    print(e)  # "Expected integer"
```

---

## Complete Example

```python
from aksara import Model, fields, CASCADE
from enum import Enum
from decimal import Decimal


class ProductStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DISCONTINUED = "discontinued"


class Product(Model):
    """E-commerce product model."""
    
    # Basic info
    name = fields.String(
        max_length=200,
        ai_description="Product display name",
    )
    slug = fields.String(
        max_length=200,
        unique=True,
        ai_description="URL-friendly identifier",
    )
    description = fields.Text(
        nullable=True,
        ai_description="Full product description",
    )
    
    # Pricing
    price = fields.Decimal(
        precision=10,
        scale=2,
        ai_description="Current price in USD",
    )
    compare_at_price = fields.Decimal(
        precision=10,
        scale=2,
        nullable=True,
        ai_description="Original price for showing discounts",
    )
    
    # Inventory
    sku = fields.String(
        max_length=50,
        unique=True,
        ai_description="Stock keeping unit",
    )
    quantity = fields.Integer(
        default=0,
        ai_description="Available inventory count",
    )
    
    # Status
    status = fields.Enum(
        enum_class=ProductStatus,
        default=ProductStatus.DRAFT,
        ai_description="Product visibility status",
    )
    
    # Relations
    category = fields.ForeignKey(
        "Category",
        on_delete=SET_NULL,
        nullable=True,
        related_name="products",
    )
    
    # Metadata
    metadata = fields.JSON(
        default=dict,
        ai_description="Additional product attributes",
    )
    
    # Timestamps
    created_at = fields.DateTime(auto_now_add=True)
    updated_at = fields.DateTime(auto_now=True)
```

---

## Best Practices

### Choose Appropriate Types

```python
# Good
price = fields.Decimal(precision=10, scale=2)  # Exact for money
rating = fields.Float()  # Approximate is fine for ratings

# Avoid
price = fields.Float()  # Precision issues with money
```

### Use Meaningful Defaults

```python
# Good
is_active = fields.Boolean(default=True)
view_count = fields.Integer(default=0)

# Avoid
status = fields.String()  # No default, must always specify
```

### Document with AI Metadata

```python
# Good
email = fields.Email(
    ai_description="Primary contact email for the user"
)

# Less helpful
email = fields.Email()  # What email? For what purpose?
```

### Mark Sensitive Fields

```python
# Secure
password_hash = fields.String(ai_sensitive=True, ai_agent_writable=False)
ssn = fields.String(ai_sensitive=True)
api_key = fields.String(ai_sensitive=True)
```

---

## Related Documentation

- [Models](models.md) — Model definition basics
- [Relations](relations.md) — Relationship fields in depth
- [Querying](querying.md) — Filter and retrieve data
- [Custom Fields](../advanced/custom-fields.md) — Create your own field types
