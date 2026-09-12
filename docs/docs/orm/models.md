# Models

Define your data structure using Python classes that map directly to PostgreSQL tables.

---

## What is a Model?

A **model** is a Python class that represents a table in your database. Each model:

- Defines what data you want to store (fields like title, email, price)
- Maps to a PostgreSQL table after its migration is applied
- Provides methods to create, read, update, and delete records
- Validates data before saving

Think of a model as a blueprint: it describes what a "Post" or "User" looks
like. Aksara provides the persistence operations, while your application keeps
schema migration, authorization, and transaction boundaries explicit.

```python
from aksara import Model, fields

class Article(Model):
    """A blog article stored in the 'articles' table."""
    
    title = fields.String(max_length=200)
    content = fields.Text()
    published = fields.Boolean(default=False)
    created_at = fields.DateTime(auto_now_add=True)
```

**Schema intent after migrations are generated and applied**:
```
PostgreSQL table: articles
┌──────────────┬─────────────────┬─────────────┐
│ Column       │ Type            │ Constraints │
├──────────────┼─────────────────┼─────────────┤
│ id           │ UUID            │ PRIMARY KEY │
│ title        │ VARCHAR(200)    │ NOT NULL    │
│ content      │ TEXT            │ NOT NULL    │
│ published    │ BOOLEAN         │ DEFAULT false│
│ created_at   │ TIMESTAMPTZ     │ timestamp   │
│ updated_at   │ TIMESTAMPTZ     │ timestamp   │
└──────────────┴─────────────────┴─────────────┘
```

---

## Model names and discovery

Use distinct model class names across loaded applications, including framework
models. The registry keys classes by their Python name, not their module or
`Meta.table_name`. In the historical multitenant example, CLI discovery of the
built-in auth `User` replaces the example's `User`, so its `tenant_users` table
is omitted from generated migrations even though the commands succeed. This
known limitation is not fixed in the documentation release. Inspect generated
operations and actual tables; do not treat a successful command as proof that
every declared model was included. See the
[historical example's status](../patterns/multitenant.md).

## Creating a Model

### Step 1: Import the Base Class and Fields

```python
from aksara import Model, fields
```

- `Model` — The base class all your models inherit from
- `fields` — Contains all field types (String, Integer, Boolean, etc.)

### Step 2: Define Your Class

```python
class Task(Model):
    """A task that users can complete."""
    
    title = fields.String(max_length=200)
    description = fields.Text(nullable=True)
    completed = fields.Boolean(default=False)
    due_date = fields.DateTime(nullable=True)
```

### Step 3: Create the Table

Run migrations to create the actual PostgreSQL table:

```bash
aksara makemigrations
aksara migrate
```

---

## What You Get Automatically

### Primary Key (`id`)

Unless explicitly overridden, a model gets a UUID primary key. You don't need to define it:

```python
class User(Model):
    email = fields.Email(unique=True)
    # 'id' is automatically added as a UUID

user = await User.objects.create(email="alice@example.com")
print(user.id)  # UUID('550e8400-e29b-41d4-a716-446655440000')
```

**Why UUID instead of auto-increment?**

- Globally unique (safe for distributed systems)
- Can be generated client-side
- Nonsequential identifiers; possession of an ID does not grant access
- PostgreSQL-native with `gen_random_uuid()`

### Table Name

The table name is derived from your class name:

| Model Name | Table Name |
|------------|------------|
| `Article` | `articles` |
| `User` | `users` |
| `Category` | `categories` |
| `UserProfile` | `user_profiles` |

**Override the table name** if needed:

```python
class Article(Model):
    __tablename__ = "blog_posts"  # Custom table name
    
    title = fields.String(max_length=200)
```

### Timestamps

The base model supplies `created_at` and `updated_at` when they are not
explicitly defined. Declare timestamp fields explicitly when configuring their
behavior with `auto_now` and `auto_now_add`:

```python
class Article(Model):
    title = fields.String(max_length=200)
    
    # Initialized on creation; not an immutable database constraint
    created_at = fields.DateTime(auto_now_add=True)
    
    # Updated every time you save
    updated_at = fields.DateTime(auto_now=True)
```

---

## Working with Models

### Creating Records

```python
# Method 1: Create and save in one step
article = await Article.objects.create(
    title="Hello World",
    content="My first article!",
    published=True,
)

# Method 2: Create an instance, then save
article = Article(
    title="Hello World",
    content="My first article!",
)
await article.save()
```

### Reading Records

```python
# Get one record by ID
article = await Article.objects.get(id=article_id)

# Get one record by any field
article = await Article.objects.get(title="Hello World")

# Get all records
articles = await Article.objects.all()

# Filter records
published = await Article.objects.filter(published=True).all()
```

### Updating Records

```python
# Method 1: Modify and save
article = await Article.objects.get(id=article_id)
article.title = "New Title"
await article.save()

# Method 2: Update multiple at once
await Article.objects.filter(published=False).update(published=True)
```

### Deleting Records

```python
# Delete one record
article = await Article.objects.get(id=article_id)
await article.delete()

# Delete multiple records
await Article.objects.filter(published=False).delete()
```

---

## Field Types

Here's a quick reference of common fields:

### Text Fields

```python
class Example(Model):
    # Short text with max length
    name = fields.String(max_length=100)
    
    # Unlimited text
    bio = fields.Text()
    
    # Email with validation
    email = fields.Email(unique=True)
    
    # URL with validation
    website = fields.URL(nullable=True)
```

### Numeric Fields

```python
class Product(Model):
    # Whole numbers
    quantity = fields.Integer(default=0)
    
    # Decimal numbers (for money)
    price = fields.Decimal(max_digits=10, decimal_places=2)
    
    # Floating point (for calculations)
    rating = fields.Float(nullable=True)
```

### Date and Time

```python
class Event(Model):
    # Date only (no time)
    date = fields.Date()
    
    # Time only (no date)
    start_time = fields.Time()
    
    # Full timestamp with timezone
    created_at = fields.DateTime(auto_now_add=True)
```

### Other Types

```python
class Settings(Model):
    # True/False
    is_active = fields.Boolean(default=True)
    
    # JSON data (objects, arrays or scalars)
    preferences = fields.JSON(default=dict)
    
    # PostgreSQL arrays
    tags = fields.Array(item_type=str, default=list)
    
    # UUID
    external_id = fields.UUID(nullable=True)
```

See [Fields Reference](fields.md) for complete documentation.

---

## Field Options

Common field options include the following; check the concrete constructor
for type-specific support. Index and uniqueness declarations require migrations
to take effect:

| Option | What It Does | Example |
|--------|--------------|---------|
| `nullable` | Allow NULL values | `fields.String(nullable=True)` |
| `default` | Default value | `fields.Boolean(default=False)` |
| `unique` | Ensure uniqueness | `fields.Email(unique=True)` |
| `db_index` | Create database index | `fields.String(db_index=True)` |
| `primary_key` | Mark as primary key | `fields.UUID(primary_key=True)` |

### Examples

```python
class User(Model):
    # Required, must be unique
    email = fields.Email(unique=True)
    
    # Optional (can be empty)
    phone = fields.String(max_length=20, nullable=True)
    
    # Has a default value
    is_active = fields.Boolean(default=True)
    
    # Indexed for fast lookups
    username = fields.String(max_length=50, unique=True, db_index=True)
```

---

## Model Meta Options

Configure model-wide settings using the `Meta` class:

```python
class Article(Model):
    title = fields.String(max_length=200)
    created_at = fields.DateTime(auto_now_add=True)
    
    class Meta:
        # Custom table name
        table_name = "blog_articles"
        
        # App label for admin grouping
        app_label = "blog"
```

### Meta Options Reference

| Option | What It Does | Example |
|--------|--------------|---------|
| `table_name` | Custom database table name | `"blog_posts"` |
| `app_label` | Group in admin | `"blog"` |

---

`Meta.ordering`, `Meta.indexes` and `Meta.unique_together` are not implemented
configuration options. Use explicit `order_by()` calls and reviewed migrations
for database constraints/indexes. See [model metadata](model-meta.md) for the
actual introspection interface and supported declarations.

## AI Metadata

Aksara models can include metadata that helps AI agents understand your data:

```python
class Product(Model):
    name = fields.String(
        max_length=200,
        ai_description="The product's display name shown to customers",
    )
    
    price = fields.Decimal(
        max_digits=10,
        decimal_places=2,
        ai_description="Price in USD, excluding tax",
    )
    
    internal_cost = fields.Decimal(
        max_digits=10,
        decimal_places=2,
        ai_sensitive=True,  # Hide from AI context
    )
    
    class Meta:
        ai_description = "Products available for purchase in the store"
```

| Option | What It Does |
|--------|--------------|
| `ai_description` | Human-readable description for AI |
| `ai_sensitive` | Hide field from AI context |
| `ai_agent_writable` | Allow/prevent AI from modifying |

---

## Relationships

Models can reference other models:

```python
from aksara import Model, fields, CASCADE

class Author(Model):
    name = fields.String(max_length=100)

class Post(Model):
    title = fields.String(max_length=200)
    
    # Many posts can have one author
    author = fields.ForeignKey(Author, on_delete=CASCADE, related_name="posts")
```

See [Relations](relations.md) for complete documentation.

---

## Complete model example

The following declarations and function belong in a configured application.
Import the models for migration discovery and apply the migration before calling
`example()` with a connected database. The snippet is not a standalone startup
script. It uses separate writes; wrap them in an explicit supported transaction
if creating both records must be atomic.

```python
from aksara import Model, fields, CASCADE
from decimal import Decimal

class Category(Model):
    """Product categories like Electronics, Clothing, etc."""
    
    name = fields.String(max_length=100, unique=True)
    slug = fields.String(max_length=100, unique=True)
    description = fields.Text(nullable=True)
    
    class Meta:
        app_label = "store"


class Product(Model):
    """Items available for purchase."""
    
    # Basic info
    name = fields.String(max_length=200)
    slug = fields.String(max_length=200, unique=True)
    description = fields.Text()
    
    # Pricing
    price = fields.Decimal(max_digits=10, decimal_places=2)
    sale_price = fields.Decimal(max_digits=10, decimal_places=2, nullable=True)
    
    # Inventory
    sku = fields.String(max_length=50, unique=True)
    stock_quantity = fields.Integer(default=0)
    
    # Status
    is_active = fields.Boolean(default=True)
    is_featured = fields.Boolean(default=False)
    
    # Relationships
    category = fields.ForeignKey(
        Category,
        on_delete=CASCADE,
        related_name="products",
    )
    
    # Metadata
    tags = fields.Array(item_type=str, default=list)
    attributes = fields.JSON(default=dict)  # e.g., {"color": "red", "size": "M"}
    
    # Timestamps
    created_at = fields.DateTime(auto_now_add=True)
    updated_at = fields.DateTime(auto_now=True)
    
    class Meta:
        app_label = "store"


# Using the models
async def example():
    # Create a category
    electronics = await Category.objects.create(
        name="Electronics",
        slug="electronics",
        description="Gadgets and devices",
    )
    
    # Create a product
    phone = await Product.objects.create(
        name="Smartphone X",
        slug="smartphone-x",
        description="Latest smartphone with amazing features",
        price=Decimal("999.99"),
        sku="PHONE-001",
        stock_quantity=100,
        category=electronics,
        tags=["smartphone", "mobile", "5g"],
        attributes={"color": "black", "storage": "256GB"},
    )
    
    # Query products
    active_products = await Product.objects.filter(
        is_active=True,
        stock_quantity__gt=0,
    ).select_related("category").order_by("-created_at").all()
    
    # Access the eagerly loaded relationship; product.category is the stored ID
    for product in active_products:
        category = product.get_related("category")
        print(f"{product.name} in {category.name}")
```

---

## Related Documentation

- [Fields](fields.md) — All field types and options
- [Querying](querying.md) — Filter, sort, and retrieve data
- [Relations](relations.md) — ForeignKey, ManyToMany, OneToOne
- [Migrations](migrations.md) — Create and update tables
