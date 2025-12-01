# ⚡ Vidyut

> Async Postgres ORM for FastAPI

Vidyut (meaning "electricity" in Sanskrit) is a lightweight, async-native ORM designed specifically for PostgreSQL and FastAPI. It provides a clean, Django-like API for defining models and performing CRUD operations.

## Features

- 🚀 **Async-first**: Built from the ground up for async/await
- 🐘 **Postgres-native**: Designed specifically for PostgreSQL
- ⚡ **FastAPI integration**: Seamless dependency injection and lifecycle management
- 🎯 **Django-like API**: Familiar model definition and query syntax
- 🔧 **Full migrations**: Generate and apply schema changes with `makemigrations` and `migrate`
- 📦 **Unified imports**: Everything you need from a single package
- 🔗 **Rich relationships**: ForeignKey, OneToOne, and ManyToMany support
- 🛡️ **Field validation**: Email, URL, Decimal, Enum fields with built-in validation

---

## 🚀 Quick Start (10 minutes)

### Step 1: Install Vidyut

```bash
# Clone and install in development mode
git clone https://github.com/yourusername/vidyut.git
cd vidyut
pip install -e .
```

Or if published to PyPI:
```bash
pip install vidyut
```

### Step 2: Start Postgres

Using Docker (recommended):
```bash
docker run --name vidyut-postgres \
    -e POSTGRES_PASSWORD=secret \
    -p 5432:5432 \
    -d postgres

# Create your database
docker exec vidyut-postgres psql -U postgres -c "CREATE DATABASE myapp;"
```

### Step 3: Set DATABASE_URL

```bash
export DATABASE_URL="postgresql://postgres:secret@localhost:5432/myapp"
```

### Step 4: Create Your App (`main.py`)

```python
import os
from vidyut import Vidyut, Model, fields

# Define your model
class User(Model):
    email = fields.String(max_length=255, unique=True)
    name = fields.String(max_length=100, nullable=True)
    is_active = fields.Boolean(default=True)

# Create the app (DB connection is automatic!)
app = Vidyut(
    database_url=os.environ["DATABASE_URL"],
    title="My API",
)

# ===== CRUD Routes =====

@app.post("/users")
async def create_user(email: str, name: str = None):
    user = await User.objects.create(email=email, name=name)
    return {"id": str(user.id), "email": user.email, "name": user.name}

@app.get("/users")
async def list_users():
    users = await User.objects.filter(is_active=True).all()
    return [{"id": str(u.id), "email": u.email} for u in users]

@app.get("/users/{user_id}")
async def get_user(user_id: str):
    user = await User.objects.get(id=user_id)
    return {"id": str(user.id), "email": user.email, "name": user.name}

@app.delete("/users/{user_id}")
async def delete_user(user_id: str):
    user = await User.objects.get(id=user_id)
    await user.delete()
    return {"deleted": True}
```

### Step 5: Run Migrations

```bash
# Generate and apply CREATE TABLE SQL
vidyut migrate --app main

# Output:
# ⚡ Vidyut Migrate
# ----------------------------------------
# ✓ Discovered models from 'main'
# Found 1 model(s)
# ✓ Connected to database
# → Creating table 'users'...
#   ✓ Table 'users' created/verified
# ========================================
# ✓ Migrations complete!
```

### Step 6: Run Your App

```bash
vidyut run main:app --reload

# Output:
#   ⚡ Vidyut v0.3.1
#   Async Framework
#
#   → Running: main:app
#   → Server:  http://127.0.0.1:8000
#   → Reload:  enabled
#
#   ⚡ Vidyut - Async Framework
#   ✓ Database connected
```

### Step 7: Test Your API

```bash
# Create a user
curl -X POST "http://localhost:8000/users?email=hello@vidyut.dev&name=Alice"
# {"id":"abc123...","email":"hello@vidyut.dev","name":"Alice"}

# List users
curl http://localhost:8000/users
# [{"id":"abc123...","email":"hello@vidyut.dev"}]

# Get single user
curl http://localhost:8000/users/abc123...

# Delete user  
curl -X DELETE http://localhost:8000/users/abc123...
```

**That's it!** You now have a fully async FastAPI app with PostgreSQL. 🎉

---

## CRUD Operations

```python
# Create
user = await User.objects.create(email="hello@example.com", name="Alice")

# Get by ID
user = await User.objects.get(id="uuid-here")

# Get by any field
user = await User.objects.get(email="hello@example.com")

# Get or None (no exception if not found)
user = await User.objects.get_or_none(email="maybe@exists.com")

# Get or Create
user, created = await User.objects.get_or_create(
    email="hello@example.com",
    defaults={"name": "Default Name"}
)

# Filter and fetch all
users = await User.objects.filter(is_active=True).all()

# Filter and fetch first
user = await User.objects.filter(email="hello@example.com").first()

# Count
count = await User.objects.filter(is_active=True).count()

# Update (modify and save)
user.name = "New Name"
await user.save()  # updated_at is auto-updated

# Delete
await user.delete()
```

---

## Model Fields

### Basic Fields

| Field | PostgreSQL Type | Key Arguments |
|-------|-----------------|---------------|
| `String` | `VARCHAR(n)` | `max_length=255`, `unique`, `nullable`, `default` |
| `Text` | `TEXT` | `nullable`, `default` |
| `Integer` | `INTEGER` | `unique`, `nullable`, `default` |
| `Boolean` | `BOOLEAN` | `nullable`, `default` |
| `DateTime` | `TIMESTAMP WITH TIME ZONE` | `auto_now`, `auto_now_add`, `nullable` |
| `UUID` | `UUID` | `primary_key` |
| `JSON` | `JSONB` | `nullable`, `default` |
| `Decimal` | `NUMERIC(p,s)` | `max_digits`, `decimal_places`, `nullable` |

### Validated Fields

| Field | PostgreSQL Type | Validation |
|-------|-----------------|------------|
| `Email` | `VARCHAR(254)` | RFC email format, auto-lowercase |
| `URL` | `TEXT` | Must start with `http://` or `https://` |
| `EnumField` | `TEXT` | Validates against Python Enum values |

### Relationship Fields

| Field | Description |
|-------|-------------|
| `ForeignKey` | Many-to-one relationship |
| `OneToOne` | One-to-one relationship (FK with unique constraint) |
| `ManyToMany` | Many-to-many with auto-generated join table |

### Built-in Fields (auto-added to every model)

```python
id         # UUID primary key (auto-generated)
created_at # TIMESTAMP - set once on insert
updated_at # TIMESTAMP - updated on every save()
```

---

## Relationships

### ForeignKey (Many-to-One)

```python
from vidyut import Model, fields

class Author(Model):
    name = fields.String(max_length=100)

class Book(Model):
    title = fields.String(max_length=200)
    author = fields.ForeignKey(Author, on_delete="CASCADE")

# Usage
author = await Author.objects.create(name="Jane Austen")
book = await Book.objects.create(title="Pride and Prejudice", author_id=author.id)
```

### OneToOne

```python
class User(Model):
    email = fields.Email(unique=True)

class Profile(Model):
    bio = fields.Text(nullable=True)
    user = fields.OneToOne(User)  # Unique constraint enforced

# Usage
user = await User.objects.create(email="jane@example.com")
profile = await Profile.objects.create(bio="Author", user_id=user.id)
```

### ManyToMany

```python
class Tag(Model):
    name = fields.String(max_length=50, unique=True)

class Article(Model):
    title = fields.String(max_length=200)
    tags = fields.ManyToMany(Tag, related_name="articles")

# Usage
article = await Article.objects.create(title="Async Python Guide")
python_tag = await Tag.objects.create(name="python")
async_tag = await Tag.objects.create(name="async")

# Add tags
await article.tags.add(python_tag, async_tag)

# Get all tags for article
tags = await article.tags.all()

# Count tags
count = await article.tags.count()

# Remove a tag
await article.tags.remove(python_tag)

# Replace all tags
await article.tags.set([async_tag])

# Clear all tags
await article.tags.clear()

# Get just the IDs
tag_ids = await article.tags.ids()
```

---

## Validated Fields

### Email Field

```python
class User(Model):
    email = fields.Email(unique=True)  # Auto-lowercased, RFC validated

user = await User.objects.create(email="John.Doe@Example.COM")
print(user.email)  # "john.doe@example.com"
```

### URL Field

```python
class Website(Model):
    url = fields.URL()  # Must be http:// or https://

site = await Website.objects.create(url="https://github.com")
```

### Decimal Field

```python
class Product(Model):
    price = fields.Decimal(max_digits=10, decimal_places=2)

product = await Product.objects.create(price=Decimal("19.99"))
```

### Enum Field

```python
from enum import Enum

class Status(Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"

class Post(Model):
    title = fields.String(max_length=200)
    status = fields.EnumField(Status, default=Status.DRAFT)

post = await Post.objects.create(title="Hello World")
print(post.status)  # Status.DRAFT
```

---

## Unified Imports

Everything you need comes from one place:

```python
from vidyut import (
    # ORM Core
    Model, fields, Database,
    DoesNotExist, MultipleObjectsReturned,
    
    # Vidyut App (FastAPI + auto-DB)
    Vidyut,
    
    # FastAPI (re-exported for convenience)
    FastAPI, APIRouter, Depends,
    HTTPException, Request, Response,
    Query, Path, Header, status,
    JSONResponse, HTMLResponse,
)
```

---

## CLI Commands

```bash
# Run your app
vidyut run main:app --reload
vidyut run main:app --host 0.0.0.0 --port 8080

# Create new project
vidyut startproject myproject

# Create new app within project
vidyut startapp blog
vidyut startapp users

# Migrations
vidyut makemigrations --app mymodule          # Preview CREATE TABLE SQL
vidyut migrate --app mymodule                  # Apply to database
vidyut migrate --app mymodule --dry-run        # Preview without executing

# Inspect
vidyut models --app mymodule                   # List all models and fields

# Interactive shell
vidyut shell                                   # Async REPL with DB access
```

---

## Multi-App Projects (v0.3.6)

Vidyut supports multi-app architecture for larger projects:

### Create Apps with CLI

```bash
# Create project structure
vidyut startproject myapi
cd myapi

# Add more apps
vidyut startapp blog
vidyut startapp users
vidyut startapp orders
```

### Configure Apps in Settings

```python
# settings.py
from vidyut import Settings, configure

settings = Settings(
    database_url="postgresql://...",
    apps=["app", "blog", "users", "orders"],  # List all your apps
)
configure(settings)
```

### Auto-Discovery of ViewSets

```python
from vidyut import Vidyut

# ViewSets are auto-discovered from all apps in settings.apps
app = Vidyut(
    database_url="...",
    auto_discover_views=True,  # Default: True
)

# Or specify a single module
app = Vidyut(
    database_url="...",
    views_module="blog.views",  # Only discover from this module
)
```

### App Structure

Each app created with `vidyut startapp` includes:

```
blog/
├── __init__.py
├── models.py      # Define your Vidyut models
├── views.py       # Define your ModelViewSets
└── serializers.py # Define your ModelSerializers
```

---

## Example Project Structure

```
myproject/
├── main.py              # App + models
├── pyproject.toml       # Dependencies
└── .env                 # DATABASE_URL=postgresql://...
```

Or for larger projects:

```
myproject/
├── app/
│   ├── __init__.py
│   ├── main.py          # Vidyut app
│   ├── models.py        # Model definitions
│   └── routes/
│       ├── users.py
│       └── posts.py
├── pyproject.toml
└── .env
```

---

## Requirements

- Python 3.11+
- PostgreSQL 12+
- FastAPI 0.104+
- asyncpg 0.29+

---

## Changelog

### v0.3.6 (Latest)
- 🏗️ **Multi-app support**: Configure `apps: List[str]` in settings for multi-app projects
- 🔍 **Auto-discovery**: Automatically discover and register `ModelViewSet` classes
- 🛠️ **`vidyut startapp`**: New CLI command to scaffold new apps with `models.py`, `views.py`, `serializers.py`
- 🏷️ **OpenAPI tags**: `ModelViewSet.get_tags()` classmethod for improved API documentation
- 🚀 Vidyut app now supports `auto_discover_views` and `views_module` parameters
- ✅ 526 tests passing

### v0.3.5
- ✨ New field types: `Email`, `URL`, `Text`, `Decimal`, `EnumField`
- 🔗 `OneToOne` field (ForeignKey with unique constraint)
- 🔗 `ManyToMany` field with auto-generated join tables
- 🛠️ `ManyToManyManager` with `add()`, `remove()`, `clear()`, `all()`, `set()`, `ids()`, `count()`
- 📦 Migration support for all new field types
- ✅ 549 tests passing

### v0.3.4
- 🔧 Migration scaffolding and operations
- 📝 `makemigrations` and `migrate` CLI commands

### v0.3.3
- 🚀 Full migration system

### v0.3.2
- 📦 `ModelSerializer` for DRF-style serialization

### v0.3.1
- 🎯 `@action` decorator for custom ViewSet actions

### v0.3.0
- 🌐 `ModelViewSet` for auto-generated CRUD APIs
- 📋 Schema generation for Pydantic models

---

## License

MIT License
