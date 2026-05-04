# ORM Overview

Learn how Aksara's ORM helps you work with databases using Python code.

---

## What is an ORM?

**ORM** stands for **Object-Relational Mapper**. It's a bridge between:

- **Your Python code** — classes, objects, methods
- **Your database** — tables, rows, SQL queries

Instead of writing SQL:

```sql
SELECT * FROM users WHERE is_active = true AND age > 18;
```

You write Python:

```python
await User.objects.filter(is_active=True, age__gt=18)
```

The ORM translates your Python into SQL automatically.

---

## Why Use an ORM?

| Without ORM | With ORM |
|-------------|----------|
| Write raw SQL strings | Write Python methods |
| Manual SQL injection protection | Automatic protection |
| Database-specific syntax | Works with any database |
| Manage schema changes manually | Automatic migrations |

---

## Core Concepts

### Models = Database Tables

A **model** is a Python class that represents a database table:

```python
from aksara import Model, fields

class User(Model):
    email = fields.Email(unique=True)
    name = fields.String(max_length=100)
    is_active = fields.Boolean(default=True)
```

This creates a table like:

| Column | Type | Constraints |
|--------|------|-------------|
| id | integer | PRIMARY KEY (auto-created) |
| email | varchar | UNIQUE |
| name | varchar(100) | |
| is_active | boolean | DEFAULT true |

👉 [Learn more about Models](models.md)

---

### Fields = Table Columns

**Fields** define what data each column can hold:

```python
from aksara import fields

# Common field types
fields.String(max_length=100)    # Text up to 100 characters
fields.Text()                     # Unlimited text
fields.Integer()                  # Whole numbers
fields.Boolean(default=True)      # True/False
fields.DateTime(auto_now_add=True)# Timestamps
fields.Email(unique=True)         # Validated email addresses
fields.ForeignKey(to="OtherModel")# Relationships
```

👉 [Learn more about Fields](fields.md)

---

### QuerySets = Database Queries

A **QuerySet** is a collection of database queries that haven't run yet:

```python
# Build a query (doesn't hit database yet)
query = User.objects.filter(is_active=True)

# Execute the query (hits database)
users = await query  # Now it runs!
```

This is called **lazy evaluation** — queries only run when you need the results.

👉 [Learn more about Querying](querying.md)

### Expressions, Aggregates, and Transactions

For more advanced ORM work, Aksara now supports:

- `Q()` objects for complex boolean filters
- `F()` expressions for database-side arithmetic
- `annotate()` and `aggregate()` for summary and per-row aggregation
- `transaction.atomic` for safe multi-query transactions

👉 [Learn about Expressions & Transactions](expressions-and-transactions.md)

---

### Relationships = Table Connections

Connect models together:

```python
class Author(Model):
    name = fields.String(max_length=100)

class Book(Model):
    title = fields.String(max_length=200)
    author = fields.ForeignKey(
        to=Author,
        on_delete=fields.CASCADE,
        related_name="books"
    )
```

Now you can:

```python
# Get an author's books
author = await Author.objects.get(id=1)
books = await author.books.all()

# Get a book's author
book = await Book.objects.get(id=1)
author = await book.author
```

👉 [Learn more about Relations](relations.md)

---

## Quick Start Example

Here's a complete example:

```python
# 1. Define your models
from aksara import Model, fields

class Category(Model):
    name = fields.String(max_length=50)
    
class Product(Model):
    name = fields.String(max_length=100)
    price = fields.Decimal(max_digits=10, decimal_places=2)
    in_stock = fields.Boolean(default=True)
    category = fields.ForeignKey(
        to=Category,
        on_delete=fields.CASCADE,
        related_name="products"
    )
    created_at = fields.DateTime(auto_now_add=True)

# 2. Create records
electronics = await Category.objects.create(name="Electronics")

laptop = await Product.objects.create(
    name="Laptop",
    price=999.99,
    category=electronics
)

# 3. Query records
# All products
products = await Product.objects.all()

# Filtered products
cheap_products = await Product.objects.filter(price__lt=100)

# Products in category
electronics_products = await electronics.products.all()

# 4. Update records
laptop.price = 899.99
await laptop.save()

# Or update multiple at once
await Product.objects.filter(category=electronics).update(in_stock=True)

# 5. Delete records
await laptop.delete()
```

---

## Common Patterns

### CRUD Operations

| Operation | Code |
|-----------|------|
| **C**reate | `await Model.objects.create(field=value)` |
| **R**ead | `await Model.objects.get(id=1)` |
| **U**pdate | `obj.field = value; await obj.save()` |
| **D**elete | `await obj.delete()` |

### Filtering

```python
# Exact match
await User.objects.filter(name="John")

# Comparison
await Product.objects.filter(price__gt=100)  # Greater than
await Product.objects.filter(price__lt=50)   # Less than

# Contains (case-insensitive)
await User.objects.filter(name__icontains="john")

# Multiple conditions (AND)
await User.objects.filter(is_active=True, age__gte=18)

# Exclude
await User.objects.exclude(status="deleted")
```

### Ordering

```python
# Ascending (oldest first)
await User.objects.order_by("created_at")

# Descending (newest first) — note the minus sign
await User.objects.order_by("-created_at")

# Multiple fields
await User.objects.order_by("status", "-created_at")
```

### Counting

```python
# Count all
total = await User.objects.count()

# Count filtered
active = await User.objects.filter(is_active=True).count()
```

---

## Async by Default

Aksara's ORM is **async-first**. All database operations use `await`:

```python
# ✅ Correct - using await
users = await User.objects.all()
user = await User.objects.get(id=1)
await user.save()

# ❌ Wrong - missing await
users = User.objects.all()  # Returns QuerySet, not results!
```

This makes Aksara fast and efficient for modern web applications.

---

## ORM Documentation

| Guide | What You'll Learn |
|-------|-------------------|
| [Models](models.md) | Creating and configuring database models |
| [Fields](fields.md) | All available field types and options |
| [Querying](querying.md) | Filtering, ordering, aggregating data |
| [Relations](relations.md) | ForeignKey, ManyToMany, OneToOne |
| [Migrations](migrations.md) | Managing database schema changes |
| [Model Meta](model-meta.md) | Advanced model configuration |

---

## Reference

For complete API documentation:

👉 [ORM Reference](../reference/orm-reference.md)
