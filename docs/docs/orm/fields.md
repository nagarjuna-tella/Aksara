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
| `ai_description` | `str` | `""` | Human-readable field purpose used in AI context and tool exports |
| `ai_sensitive` | `bool` | `False` | Hide the field from AI context, Studio AI features, and MCP exports |
| `ai_agent_writable` | `bool` | `True` | Whether AI-driven write paths are allowed to modify the field |

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

# With validation parameters
severity = fields.String(
    max_length=20,
    choices=["low", "medium", "high", "critical"],
    default="medium",
    ai_description="Impact level for triage priority",
)
password = fields.String(max_length=128, min_length=8)
phone = fields.String(max_length=20, regex=r"^\+?[\d\s\-]{7,15}$")
clean_name = fields.String(max_length=100, strip_whitespace=True)
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `max_length` | `int` | `255` | Maximum character length |
| `min_length` | `int` | `None` | Minimum character length (validated on save) |
| `choices` | `list` | `None` | Restrict to these values — flat list or `[(value, label)]` pairs |
| `regex` | `str` | `None` | Regex pattern the value must fully match |
| `strip_whitespace` | `bool` | `False` | Strip leading/trailing whitespace on save |

PostgreSQL type: `VARCHAR(max_length)`

!!! info "Validation Order"
    When multiple validation parameters are set, they run in this order:
    `strip_whitespace` → `min_length` → `choices` → `regex`

### Text

Unlimited length text for large content.

```python
content = fields.Text()
description = fields.Text(nullable=True)
notes = fields.Text(default="")
bio = fields.Text(min_length=20, strip_whitespace=True)
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `max_length` | `int` | `None` | Optional max length (validated, DB stays TEXT) |
| `min_length` | `int` | `None` | Minimum character length (validated on save) |
| `strip_whitespace` | `bool` | `False` | Strip leading/trailing whitespace on save |

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

## Media Fields

### FileField

Store files through Aksara's media storage abstraction.

```python
class Document(Model):
    title = fields.String(max_length=200)
    attachment = fields.FileField(upload_to="documents")
```

PostgreSQL type: `VARCHAR(500)` by default.

When you access the field on a model instance, Aksara returns a `FieldFile`
wrapper instead of a raw string:

```python
document = await Document.objects.get(id=doc_id)

document.attachment.url          # "/media/documents/..." or S3 URL
document.attachment.path         # Local filesystem path when available
await document.attachment.exists()
await document.attachment.size()
await document.attachment.read()
```

You can assign either an existing stored path string or an upload-like value:

```python
document.attachment = ("report.pdf", pdf_bytes)
await document.save()
```

Internally and in the database, the field stores a normalized path string (or
`None`); the `FieldFile` wrapper is only the model attribute view. Upload-like
values are persisted only through `save()`, `create()`, and `bulk_create()`,
which run the storage preparation step. `update()` and `bulk_update()` cannot
persist file content, so they reject unresolved upload-like values with a clear
error — pass an already-stored path string or `FieldFile` to those paths. See
the [Advanced Field Policy](advanced-field-policy.md).

### ImageField

Image-specialized file field with Pillow-backed validation.

```python
class Profile(Model):
    avatar = fields.ImageField(upload_to="avatars", nullable=True)
```

`ImageField` accepts the same inputs as `FileField`, but verifies that the
uploaded content is a real image before saving it.

!!! tip "Custom upload endpoints"
    `ModelViewSet` schemas still expose file and image fields as strings.
    For browser uploads, add a custom FastAPI endpoint that accepts
    `UploadFile`, then assign that object to the model field and call
    `await instance.save()`.

See [Advanced Media & Email](../advanced/media-and-email.md) for storage
configuration, S3 usage, and upload endpoint examples.

---

## Numeric Fields

### Integer

Standard 32-bit integer.

```python
age = fields.Integer()
quantity = fields.Integer(default=0)
position = fields.Integer(nullable=True)

# With validation parameters
rating = fields.Integer(min_value=1, max_value=5)
priority = fields.Integer(choices=[1, 2, 3, 4, 5], default=3)
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `min_value` | `int` | `None` | Minimum allowed value |
| `max_value` | `int` | `None` | Maximum allowed value |
| `choices` | `list` | `None` | Restrict to these values |

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

Validation: Values outside the 64-bit signed integer range are rejected at the Python level before reaching the database.

### SmallInteger

16-bit integer for compact storage.

```python
priority = fields.SmallInteger(default=0)
day_of_week = fields.SmallInteger(choices=[0, 1, 2, 3, 4, 5, 6])
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `choices` | `list` | `None` | Restrict to these values |

PostgreSQL type: `SMALLINT`

Range: -32,768 to 32,767

### Positive Integer Variants

Integer fields that reject negative values at the Python level.

```python
view_count = fields.PositiveInteger(default=0)      # INTEGER, >= 0
retry_count = fields.PositiveSmallInteger(default=0) # SMALLINT, 0..32767
big_counter = fields.PositiveBigInteger(default=0)   # BIGINT, >= 0
```

| Field | PostgreSQL Type | Range |
|-------|----------------|-------|
| `PositiveInteger` | `INTEGER` | 0 to 2,147,483,647 |
| `PositiveSmallInteger` | `SMALLINT` | 0 to 32,767 |
| `PositiveBigInteger` | `BIGINT` | 0 to 9,223,372,036,854,775,807 |

### Float

Floating-point number.

```python
rating = fields.Float()
latitude = fields.Float()
longitude = fields.Float()
```

PostgreSQL type: `DOUBLE PRECISION`

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `min_value` | `float` | `None` | Minimum allowed value |
| `max_value` | `float` | `None` | Maximum allowed value |

!!! warning "Precision"
    Float is not suitable for monetary values due to precision issues. Use `Decimal` instead.

### Decimal

Exact decimal for financial data.

```python
price = fields.Decimal(precision=10, scale=2)
tax_rate = fields.Decimal(precision=5, scale=4)
percentage = fields.Decimal(precision=5, scale=2, min_value=0, max_value=100)
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `precision` | `int` | `10` | Total digits |
| `scale` | `int` | `2` | Digits after decimal |
| `min_value` | `float` | `None` | Minimum allowed value |
| `max_value` | `float` | `None` | Maximum allowed value |

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

### Time

Time of day without a date component.

```python
start_time = fields.Time()
reminder_at = fields.Time(nullable=True)
```

PostgreSQL type: `TIME`

Accepts `datetime.time` objects, `datetime.datetime` (extracts the time part), and ISO 8601 time strings including fractional seconds:

```python
from datetime import time

class Schedule(Model):
    alarm = fields.Time()

schedule = await Schedule.objects.create(alarm=time(7, 30, 0))
# Also accepts: alarm="07:30:00" or alarm="07:30:00.123456"
```

### Duration

Time spans stored as PostgreSQL intervals.

```python
cooking_time = fields.Duration()
timeout = fields.Duration(nullable=True)
```

PostgreSQL type: `INTERVAL`

Accepts `datetime.timedelta` objects, or numeric values interpreted as seconds:

```python
from datetime import timedelta

class Recipe(Model):
    prep_time = fields.Duration()

recipe = await Recipe.objects.create(prep_time=timedelta(minutes=30))
# Also accepts: prep_time=1800 (seconds)
```

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

Nested JSON keys can be queried with double-underscore paths:

```python
dark_mode_users = await User.objects.filter(
    preferences__theme="dark",
).all()
```

`JSON` accepts any JSON-compatible value, including top-level scalars (`"draft"`,
`3.14`, `True`) as well as objects and arrays. Top-level `None` is stored as SQL
`NULL`. Values are serialized with `allow_nan=False`, so `NaN`/infinity and
non-JSON-serializable objects raise a validation error before reaching the
database. See the [Advanced Field Policy](advanced-field-policy.md).

### Vector

pgvector-backed embeddings for similarity search and ranking.

```python
class Document(Model):
    title = fields.String(max_length=200)
    embedding = fields.Vector(dimensions=384)
```

PostgreSQL type: `VECTOR(n)` when dimensions are specified, otherwise `VECTOR`

`Vector` values are stored as Python lists and serialized to pgvector literals
for inserts, updates, and filters.

```python
document = await Document.objects.create(
    title="Intro",
    embedding=[0.12, 0.33, 0.98],
)

assert document.embedding == [0.12, 0.33, 0.98]
```

Vector components must be finite numbers. `NaN`, `Infinity`, `-Infinity`,
boolean items, and empty vectors are rejected before SQL execution, and a
configured `dimensions` is enforced on every write path. Values are serialized
with high precision (`repr(float)`), so persisted text may show more digits than
older output; compare numeric values rather than exact strings in tests. See the
[Advanced Field Policy](advanced-field-policy.md).

!!! note
    `Vector` requires PostgreSQL's `vector` extension. Enable it with
    `CREATE EXTENSION IF NOT EXISTS vector` before creating tables that use the field.

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

Homogeneous, one-dimensional PostgreSQL array columns for storing lists of
values.

```python
import uuid

tags = fields.Array(item_type=str, default=list)
scores = fields.Array(item_type=int, nullable=True)
ratings = fields.Array(item_type=float)
ids = fields.Array(item_type=uuid.UUID, default=list)
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `item_type` | `type` | `str` | Element type: `str`, `int`, `float`, `bool`, `uuid.UUID` |

PostgreSQL types:

| `item_type` | PostgreSQL Type |
|-------------|----------------|
| `str` | `TEXT[]` |
| `int` | `INTEGER[]` |
| `float` | `DOUBLE PRECISION[]` |
| `bool` | `BOOLEAN[]` |
| `uuid.UUID` | `UUID[]` |

Example usage:

```python
class Article(Model):
    tags = fields.Array(item_type=str, default=list)
    view_counts = fields.Array(item_type=int, default=list)

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
    - Use `JSON` for heterogeneous data, nested structures, or null elements
    - PostgreSQL array operators work with `Array` fields

!!! note "Array values must be Python lists"
    Assign explicit Python lists whose items match `item_type`. The ORM
    validates each element and rejects nested lists, `None` items, and
    type mismatches (for example, a string in an `int` array). Delimited
    strings are not parsed into arrays by the ORM — convert them before
    assignment. See the [Advanced Field Policy](advanced-field-policy.md).

### Slug

URL-safe slugs with pattern validation and optional auto-generation.

```python
slug = fields.Slug(max_length=100, unique=True)

# Auto-generate from another field
slug = fields.Slug(max_length=200, auto_from="title", unique=True)
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `max_length` | `int` | `50` | Maximum character length |
| `allow_unicode` | `bool` | `False` | Allow non-ASCII characters (e.g., `héllo-wörld`) |
| `auto_from` | `str` | `None` | Auto-generate slug from this field when slug is empty |
| `db_index` | `bool` | `False` | Create database index |

PostgreSQL type: `VARCHAR(max_length)`

Validation: Only letters, numbers, hyphens, and underscores are accepted. When `allow_unicode=False` (the default), only ASCII characters are valid.

```python
class Article(Model):
    title = fields.String(max_length=200)
    slug = fields.Slug(max_length=200, auto_from="title", unique=True)

# When slug is empty/None on save, it's auto-generated from title:
# "Hello World Article" → "hello-world-article"
# Existing slug values are preserved (no overwrite on update)
```

### IPAddress / GenericIPAddress

IP addresses with protocol validation.

```python
server_ip = fields.IPAddress()
client_ip = fields.IPAddress(protocol="ipv4")
gateway = fields.IPAddress(protocol="ipv6")
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `protocol` | `str` | `"both"` | Restrict to `"ipv4"`, `"ipv6"`, or `"both"` |
| `unpack_ipv4` | `bool` | `False` | Convert IPv4-mapped IPv6 (e.g., `::ffff:192.0.2.1`) to plain IPv4 |

PostgreSQL type: `INET`

`GenericIPAddressField` is an alias for `IPAddressField`.

### Binary

Raw binary data.

```python
file_hash = fields.Binary()
encryption_key = fields.Binary(nullable=True)
```

PostgreSQL type: `BYTEA`

Accepts `bytes`, `bytearray`, `memoryview`, and strings (encoded as UTF-8).

!!! note "AI Metadata Defaults"
    `BinaryField` defaults to `ai_sensitive=True` and `ai_agent_writable=False` to prevent AI agents from reading or modifying raw binary data.

### FilePath

File system paths with dynamic choice generation.

```python
template = fields.FilePath(
    path="/app/templates",
    match=r".*\.html$",
    recursive=True,
    max_length=200,
)
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `path` | `str` | `""` | Root directory to scan |
| `match` | `str` | `None` | Regex pattern to filter file names |
| `recursive` | `bool` | `False` | Scan subdirectories |
| `allow_files` | `bool` | `True` | Include files in choices |
| `allow_folders` | `bool` | `False` | Include directories in choices |
| `max_length` | `int` | `100` | Maximum path length |

PostgreSQL type: `VARCHAR(max_length)`

The `choices()` method returns a list of `(path, display_name)` tuples based on the configured directory scan.

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
| `through` | `str` | Unsupported | Custom through models are not supported yet |

Passing `through=` currently raises a clear configuration error. Aksara creates
its own junction table for built-in many-to-many relations.

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

Values are normalized case-insensitively. `SET_NULL` and `SET NULL` are both
accepted, and enum values from `aksara.relations.OnDelete` may be used.

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
| `ai_description` | `str` | `""` | Human-readable field purpose used in AI context and tool exports |
| `ai_sensitive` | `bool` | `False` | Hide the field from AI context, Studio AI features, and MCP exports |
| `ai_agent_writable` | `bool` | `True` | Whether AI-driven write paths are allowed to modify the field |

---

## AI Metadata and Guardrails

These three options control how Aksara presents your schema to AI features.

`ai_description` gives the field intent instead of just a type name. That description is reused in Studio AI Console prompts, exported tool schemas, and other AI-facing context builders, so it is worth writing as if another developer has to understand the field without opening the model.

`ai_sensitive=True` removes a field from AI-facing exports. Use it for hashed passwords, secret tokens, internal identifiers, or any value that should never appear in generated context for external agents.

`ai_agent_writable=False` keeps a field visible while blocking agent-initiated updates. That is the right choice for computed totals, audit fields, approval states, or any value a human or a trusted backend process owns.

```python
class Customer(Model):
    email = fields.Email(
        ai_description="Primary contact email for the customer"
    )
    stripe_customer_id = fields.String(
        ai_sensitive=True,
        ai_description="Internal billing identifier"
    )
    lifetime_value = fields.Decimal(
        precision=10,
        scale=2,
        ai_description="Computed revenue total in USD",
        ai_agent_writable=False,
    )
```

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
    slug = fields.Slug(
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
