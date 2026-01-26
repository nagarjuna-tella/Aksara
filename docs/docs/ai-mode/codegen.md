# Codegen

Generate models, viewsets, serializers, and tests with AI.

---

## Overview

Codegen generates boilerplate code that matches your project's patterns:

```python
from vidyut.ai import Codegen

gen = Codegen()
code = await gen.model("BlogPost with title, content, author FK")
print(code)
```

---

## Quick Start

### Generate a Model

```python
from vidyut.ai import Codegen

gen = Codegen()

# From description
model_code = await gen.model(
    "UserProfile with bio, avatar URL, and user FK"
)

print(model_code)
# class UserProfile(Model):
#     bio = fields.TextField(null=True)
#     avatar_url = fields.URLField(null=True)
#     user = fields.ForeignKey("User", on_delete="CASCADE")
```

### Generate a ViewSet

```python
viewset_code = await gen.viewset(
    model="UserProfile",
    features=["pagination", "search", "filter_by_user"],
)
```

### Generate Tests

```python
test_code = await gen.test(
    model="UserProfile",
    test_types=["crud", "validation"],
)
```

---

## Model Generation

### Basic Model

```python
code = await gen.model("Product with name, price, description")

# Output:
# class Product(Model):
#     name = fields.StringField(max_length=200)
#     price = fields.DecimalField(max_digits=10, decimal_places=2)
#     description = fields.TextField(null=True)
#     
#     class Meta:
#         table_name = "products"
```

### With Relations

```python
code = await gen.model(
    "OrderItem with order FK, product FK, quantity, unit_price"
)

# Output:
# class OrderItem(Model):
#     order = fields.ForeignKey("Order", on_delete="CASCADE", related_name="items")
#     product = fields.ForeignKey("Product", on_delete="PROTECT")
#     quantity = fields.IntegerField()
#     unit_price = fields.DecimalField(max_digits=10, decimal_places=2)
```

### With Many-to-Many

```python
code = await gen.model(
    "Article with title, content, and tags M2M"
)

# Output:
# class Article(Model):
#     title = fields.StringField(max_length=200)
#     content = fields.TextField()
#     tags = fields.ManyToManyField("Tag", related_name="articles")
```

### With Constraints

```python
code = await gen.model(
    "User with email (unique), username (unique), password"
)

# Output:
# class User(Model):
#     email = fields.EmailField(unique=True)
#     username = fields.StringField(max_length=150, unique=True)
#     password = fields.StringField(max_length=128)
```

### With Indexes

```python
code = await gen.model(
    "Event with title, start_date, end_date, indexed by start_date"
)

# Output includes:
# class Meta:
#     indexes = [
#         {"fields": ["start_date"]},
#     ]
```

---

## ViewSet Generation

### Basic ViewSet

```python
code = await gen.viewset(model="Product")

# Output:
# class ProductViewSet(ModelViewSet):
#     model = Product
#     serializer_class = ProductSerializer
```

### With Features

```python
code = await gen.viewset(
    model="Product",
    features=[
        "pagination",
        "search",
        "filtering",
        "ordering",
    ],
)

# Output:
# class ProductViewSet(ModelViewSet):
#     model = Product
#     serializer_class = ProductSerializer
#     pagination_class = PageNumberPagination
#     search_fields = ["name", "description"]
#     filterset_fields = ["category", "is_active"]
#     ordering_fields = ["name", "price", "created_at"]
```

### With Custom Actions

```python
code = await gen.viewset(
    model="Order",
    features=["pagination"],
    actions=["mark_shipped", "cancel", "refund"],
)

# Output includes:
# @action(detail=True, methods=["post"])
# async def mark_shipped(self, request, pk=None):
#     order = await self.get_object()
#     order.status = "shipped"
#     await order.save()
#     return Response({"status": "shipped"})
```

### With Permissions

```python
code = await gen.viewset(
    model="User",
    permissions=["IsAuthenticated", "IsAdminUser"],
)
```

---

## Serializer Generation

### Basic Serializer

```python
code = await gen.serializer(model="Product")

# Output:
# class ProductSerializer(ModelSerializer):
#     class Meta:
#         model = Product
#         fields = ["id", "name", "price", "description", "created_at"]
```

### With Nested Relations

```python
code = await gen.serializer(
    model="Order",
    nested=["items", "customer"],
)

# Output:
# class OrderSerializer(ModelSerializer):
#     items = OrderItemSerializer(many=True, read_only=True)
#     customer = CustomerSerializer(read_only=True)
#     
#     class Meta:
#         model = Order
#         fields = ["id", "items", "customer", "total", "status"]
```

### With Custom Fields

```python
code = await gen.serializer(
    model="User",
    extra_fields=["full_name", "post_count"],
)

# Output includes:
# full_name = serializers.SerializerMethodField()
# post_count = serializers.IntegerField(read_only=True)
# 
# def get_full_name(self, obj):
#     return f"{obj.first_name} {obj.last_name}"
```

---

## Test Generation

### CRUD Tests

```python
code = await gen.test(
    model="Product",
    test_types=["crud"],
)

# Output:
# class TestProduct(VidyutTestCase):
#     async def test_create_product(self):
#         product = await Product.objects.create(
#             name="Test Product",
#             price=Decimal("29.99"),
#         )
#         assert product.id is not None
#     
#     async def test_read_product(self):
#         ...
#     
#     async def test_update_product(self):
#         ...
#     
#     async def test_delete_product(self):
#         ...
```

### Validation Tests

```python
code = await gen.test(
    model="User",
    test_types=["validation"],
)

# Output:
# async def test_email_required(self):
#     with pytest.raises(ValidationError):
#         await User.objects.create(username="test")
# 
# async def test_email_unique(self):
#     await User.objects.create(email="test@example.com")
#     with pytest.raises(IntegrityError):
#         await User.objects.create(email="test@example.com")
```

### API Tests

```python
code = await gen.test(
    model="Product",
    test_types=["api"],
    viewset="ProductViewSet",
)

# Output:
# async def test_list_products(self):
#     response = await self.client.get("/api/products/")
#     assert response.status_code == 200
# 
# async def test_create_product(self):
#     response = await self.client.post("/api/products/", {
#         "name": "New Product",
#         "price": "29.99",
#     })
#     assert response.status_code == 201
```

---

## Migration Generation

### From Model Changes

```python
code = await gen.migration(
    description="Add phone field to User",
)

# Output:
# class Migration:
#     dependencies = [("myapp", "0004_previous")]
#     
#     operations = [
#         AddField(
#             model_name="user",
#             name="phone",
#             field=fields.StringField(max_length=20, null=True),
#         ),
#     ]
```

### Data Migration

```python
code = await gen.migration(
    description="Populate user full_name from first_name and last_name",
    migration_type="data",
)

# Output includes:
# async def forwards(apps, schema_editor):
#     User = apps.get_model("myapp", "User")
#     async for user in User.objects.all():
#         user.full_name = f"{user.first_name} {user.last_name}"
#         await user.save()
```

---

## Context-Aware Generation

### Using Project Context

```python
from vidyut.ai import Codegen, ContextEngine

context_engine = ContextEngine()
gen = Codegen()

# Gather existing patterns
context = await context_engine.gather("Model patterns")

# Generate matching existing style
code = await gen.model(
    "Comment with text, author, post",
    context=context,
)
```

### Style Matching

Codegen analyzes your existing code to match:

- Field naming conventions
- Import styles
- Docstring formats
- Meta class patterns

---

## CLI Usage

### Generate Model

```bash
vidyut ai generate model "Product with name, price, category FK"
```

### Generate ViewSet

```bash
vidyut ai generate viewset Product --features pagination,search
```

### Generate Test

```bash
vidyut ai generate test Product --types crud,validation
```

### Interactive Mode

```bash
vidyut ai generate

? What would you like to generate? Model
? Describe the model: BlogPost with title, slug, content, author FK, tags M2M
? Add any constraints? title unique, slug unique
? Generate migration? Yes

✓ Generated model in models.py
✓ Generated migration 0005_create_blogpost.py
```

---

## Output Options

### Return Code String

```python
code = await gen.model("Product")
print(code)  # String of code
```

### Write to File

```python
await gen.model(
    "Product",
    output_file="models.py",
    append=True,  # Append to existing file
)
```

### Return Structured

```python
result = await gen.model(
    "Product",
    return_structured=True,
)

print(result.code)       # The code
print(result.imports)    # Required imports
print(result.file_path)  # Suggested file path
```

---

## Configuration

```python
# settings.py
VIDYUT = {
    "AI_CODEGEN": {
        # Style preferences
        "docstring_style": "google",  # or "numpy", "sphinx"
        "import_style": "absolute",    # or "relative"
        
        # Defaults
        "default_field_null": False,
        "include_timestamps": True,     # Add created_at, updated_at
        "include_uuid_pk": True,        # Use UUID primary keys
        
        # Output
        "models_file": "models.py",
        "viewsets_file": "viewsets.py",
        "tests_dir": "tests/",
    },
}
```

---

## Best Practices

### 1. Be Specific

```python
# Less specific
await gen.model("User")

# More specific
await gen.model(
    "User with email (unique, required), "
    "username (unique, max 150), "
    "password (required, max 128), "
    "is_active (boolean, default true)"
)
```

### 2. Review Generated Code

Always review generated code before using:

```python
code = await gen.model("...")
print(code)  # Review this!
# Then manually add to your file
```

### 3. Use Context

```python
# Better results with context
context = await context_engine.gather("existing models")
code = await gen.model("...", context=context)
```

---

## Related Documentation

- [AI Mode Overview](index.md)
- [Context Engine](context-engine.md)
- [Patch Engine](patch-engine.md)
- [Models](../orm/models.md) — Model reference
- [ViewSets](../api/viewsets.md) — ViewSet reference
