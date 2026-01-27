# Model Meta & Introspection

Access model metadata and schema information programmatically.

---

## Overview

Aksara models expose metadata through the `_meta` attribute, enabling introspection for:

- Building admin interfaces
- Generating API schemas
- Creating migrations
- AI-powered tooling

```python
from myapp.models import Post

# Access meta information
print(Post._meta.model_name)     # "Post"
print(Post._meta.table_name)     # "posts"
print(Post._meta.fields)         # List of field objects
```

---

## Meta Class Options

Configure model behavior using the inner `Meta` class:

```python
from aksara import Model, fields

class Post(Model):
    title = fields.String(max_length=200)
    content = fields.Text()
    created_at = fields.DateTime(auto_now_add=True)
    
    class Meta:
        table_name = "blog_posts"           # Custom table name
        ordering = ["-created_at"]          # Default ordering
        unique_together = [("author", "slug")]  # Composite unique
        indexes = [                         # Database indexes
            ("created_at",),
            ("author_id", "created_at"),
        ]
        verbose_name = "Blog Post"          # Human-readable name
        verbose_name_plural = "Blog Posts"  # Plural name
```

### Available Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `table_name` | `str` | `{model_name}s` | Database table name |
| `ordering` | `list[str]` | `[]` | Default ordering |
| `unique_together` | `list[tuple]` | `[]` | Composite unique constraints |
| `indexes` | `list[tuple]` | `[]` | Database indexes |
| `verbose_name` | `str` | `{model_name}` | Human-readable name |
| `verbose_name_plural` | `str` | `{verbose_name}s` | Plural name |
| `abstract` | `bool` | `False` | Abstract base model |

---

## Accessing _meta

### Model Information

```python
# Model name
Post._meta.model_name        # "Post"
Post._meta.verbose_name      # "Blog Post" or "post"
Post._meta.verbose_name_plural  # "Blog Posts" or "posts"

# Database table
Post._meta.table_name        # "blog_posts" or "posts"
Post._meta.db_table          # Alias for table_name

# App information
Post._meta.app_label         # "myapp"
```

### Field Information

```python
# All fields
fields = Post._meta.fields  # List[FieldInfo]

# Get field by name
title_field = Post._meta.get_field("title")
print(title_field.name)           # "title"
print(title_field.field_type)     # "String"
print(title_field.max_length)     # 200

# Field names
names = Post._meta.field_names    # ["id", "title", "content", ...]

# Concrete fields (excluding relations)
concrete = Post._meta.concrete_fields

# Primary key
pk_field = Post._meta.pk
print(pk_field.name)              # "id"
```

### Relation Information

```python
# All relations
relations = Post._meta.relations  # List[RelationInfo]

# ForeignKey fields
fks = Post._meta.foreign_keys     # List[ForeignKeyInfo]

# ManyToMany fields
m2ms = Post._meta.many_to_many    # List[ManyToManyInfo]

# Reverse relations
reverse = Post._meta.reverse_relations
```

---

## Field Introspection

### FieldInfo Object

```python
field = Post._meta.get_field("title")

# Basic info
field.name                  # "title"
field.field_type           # "String"
field.python_type          # str
field.db_column            # "title" (database column name)

# Constraints
field.max_length           # 200
field.nullable             # False
field.unique               # False
field.primary_key          # False
field.default              # None

# Choices (for Enum fields)
field.choices              # None or list of choices

# AI metadata (if defined)
field.ai_description       # "The title of the blog post"
field.ai_visible           # True
```

### Checking Field Types

```python
from aksara.fields import String, ForeignKey, ManyToMany

field = Post._meta.get_field("author")

# Check type
isinstance(field, ForeignKey)  # True

# Or use string check
field.field_type == "ForeignKey"  # True

# Check if relation
field.is_relation              # True
field.is_foreign_key           # True
field.is_many_to_many          # False
```

---

## Relation Introspection

### ForeignKey Meta

```python
author_field = Post._meta.get_field("author")

# Related model
author_field.related_model        # User class
author_field.related_model_name   # "User"

# Relation details
author_field.on_delete            # "CASCADE"
author_field.related_name         # "posts"
author_field.db_column            # "author_id"
```

### ManyToMany Meta

```python
tags_field = Post._meta.get_field("tags")

# Related model
tags_field.related_model          # Tag class

# Junction table
tags_field.through_model          # PostTag (auto or custom)
tags_field.through_table          # "post_tags"

# Relation details
tags_field.related_name           # "posts"
```

### Reverse Relations

```python
# Get reverse relations to a model
for rel in User._meta.reverse_relations:
    print(f"{rel.related_model_name}.{rel.field_name}")
    # "Post.author"
    # "Comment.user"
```

---

## Practical Use Cases

### Generate API Schema

```python
def model_to_schema(model_class):
    """Convert model to OpenAPI schema."""
    properties = {}
    required = []
    
    for field in model_class._meta.fields:
        if field.name == "id":
            continue
            
        prop = {
            "type": python_type_to_json(field.python_type),
        }
        
        if field.max_length:
            prop["maxLength"] = field.max_length
            
        if field.ai_description:
            prop["description"] = field.ai_description
            
        properties[field.name] = prop
        
        if not field.nullable and field.default is None:
            required.append(field.name)
    
    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }
```

### Build Admin Interface

```python
def get_admin_columns(model_class):
    """Get columns for admin list view."""
    columns = []
    
    for field in model_class._meta.fields:
        columns.append({
            "name": field.name,
            "label": field.name.replace("_", " ").title(),
            "sortable": not field.is_relation,
            "type": field.field_type,
        })
    
    return columns
```

### Dynamic Form Generation

```python
def model_to_form_fields(model_class):
    """Generate form fields from model."""
    form_fields = {}
    
    for field in model_class._meta.concrete_fields:
        if field.name == "id" or field.name.endswith("_at"):
            continue
            
        form_field = {
            "name": field.name,
            "required": not field.nullable,
            "type": get_input_type(field),
        }
        
        if field.max_length:
            form_field["maxlength"] = field.max_length
            
        if field.choices:
            form_field["options"] = field.choices
            
        form_fields[field.name] = form_field
    
    return form_fields
```

---

## AI Metadata

Aksara models support AI-specific metadata for LLM integration.

### Field-Level AI Metadata

```python
class Product(Model):
    name = fields.String(
        max_length=200,
        ai_description="The product name shown to customers",
    )
    price = fields.Decimal(
        max_digits=10,
        decimal_places=2,
        ai_description="Price in USD, must be positive",
    )
    sku = fields.String(
        max_length=50,
        ai_visible=False,  # Hide from AI tools
    )
```

### Model-Level AI Metadata

```python
class Product(Model):
    class Meta:
        ai_description = "Products available for sale"
        ai_examples = [
            "List all products under $50",
            "Find products with 'laptop' in the name",
        ]
```

### Accessing AI Metadata

```python
# Field AI description
field = Product._meta.get_field("price")
print(field.ai_description)  # "Price in USD, must be positive"

# Model AI metadata
print(Product._meta.ai_description)  # "Products available for sale"
print(Product._meta.ai_examples)     # List of example queries

# Get all AI-visible fields
visible_fields = [
    f for f in Product._meta.fields
    if f.ai_visible
]
```

---

## Constraints Introspection

```python
# Unique together constraints
for constraint in Post._meta.unique_together:
    print(constraint)  # ("author", "slug")

# Indexes
for index in Post._meta.indexes:
    print(index)  # ("created_at",) or ("author_id", "created_at")

# Check constraints (from field definitions)
for field in Post._meta.fields:
    if field.unique:
        print(f"{field.name} has unique constraint")
```

---

## Complete Example

```python
from aksara import Model, fields

class Article(Model):
    """Blog article model with full metadata."""
    
    title = fields.String(
        max_length=200,
        ai_description="Article headline",
    )
    slug = fields.String(
        max_length=200,
        unique=True,
        ai_description="URL-safe identifier",
    )
    content = fields.Text(
        ai_description="Full article content in Markdown",
    )
    author = fields.ForeignKey(
        "User",
        on_delete="CASCADE",
        related_name="articles",
    )
    category = fields.ForeignKey(
        "Category",
        on_delete="SET_NULL",
        nullable=True,
        related_name="articles",
    )
    tags = fields.ManyToMany(
        "Tag",
        related_name="articles",
    )
    view_count = fields.Integer(
        default=0,
        ai_visible=False,  # Internal metric
    )
    is_published = fields.Boolean(default=False)
    published_at = fields.DateTime(nullable=True)
    created_at = fields.DateTime(auto_now_add=True)
    updated_at = fields.DateTime(auto_now=True)
    
    class Meta:
        table_name = "articles"
        ordering = ["-published_at"]
        unique_together = [("author", "slug")]
        indexes = [
            ("is_published", "published_at"),
            ("category_id",),
        ]
        verbose_name = "Article"
        verbose_name_plural = "Articles"
        ai_description = "Blog articles with rich content"
        ai_examples = [
            "Find published articles by author",
            "Get articles in the Python category",
        ]


# Introspection example
def describe_model(model_class):
    """Generate a complete model description."""
    meta = model_class._meta
    
    description = {
        "name": meta.model_name,
        "table": meta.table_name,
        "description": getattr(meta, "ai_description", None),
        "fields": [],
        "relations": [],
        "constraints": {
            "unique_together": list(meta.unique_together),
            "indexes": list(meta.indexes),
        },
    }
    
    for field in meta.fields:
        field_info = {
            "name": field.name,
            "type": field.field_type,
            "required": not field.nullable and field.default is None,
            "unique": field.unique,
        }
        
        if field.is_relation:
            field_info["related_to"] = field.related_model_name
            description["relations"].append(field_info)
        else:
            description["fields"].append(field_info)
    
    return description


# Usage
info = describe_model(Article)
print(info)
# {
#     "name": "Article",
#     "table": "articles",
#     "description": "Blog articles with rich content",
#     "fields": [
#         {"name": "title", "type": "String", "required": True, "unique": False},
#         ...
#     ],
#     "relations": [
#         {"name": "author", "type": "ForeignKey", "related_to": "User"},
#         ...
#     ],
#     ...
# }
```

---

## Related Documentation

- [Models](models.md) — Model definition
- [Fields](fields.md) — Field types
- [AI Mode](../ai-mode/context-engine.md) — AI integration
