# ⚡ Vidyut

> The Async Python Web Framework

**Vidyut** (meaning "electricity" in Sanskrit) is a batteries-included, async-native web framework for Python. Built on top of FastAPI and PostgreSQL, it combines Django's developer experience with modern async performance.

[![Tests](https://img.shields.io/badge/tests-925%20passing-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.11+-blue)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()

## Why Vidyut?

Vidyut gives you everything you need to build production-ready async APIs:

- 🚀 **Full Framework**: ORM, migrations, auth, permissions, admin — all included
- ⚡ **Async-Native**: Built from the ground up for async/await
- 🐘 **PostgreSQL-First**: Designed specifically for Postgres with asyncpg
- 🎯 **Django-Style DX**: Familiar APIs if you know Django/DRF
- 🔧 **Zero Boilerplate**: Auto-generated CRUD, schemas, and routing
- 🛡️ **Security Built-in**: Authentication, permissions, and rate limiting

---

## Features

| Feature | Description |
|---------|-------------|
| **ORM** | Django-like models with async queries, relationships, and validation |
| **Migrations** | `makemigrations` & `migrate` commands with SQL generation |
| **ViewSets** | Auto-generated CRUD APIs with `ModelViewSet` |
| **Serializers** | DRF-style `ModelSerializer` with nested relationships |
| **Auth** | Session & token auth with `VidyutUserProtocol` |
| **Permissions** | `IsAuthenticated`, `IsAdminUser`, `IsOwnerOrReadOnly`, composable |
| **Admin Interface** | Django-style server-rendered admin panel |
| **CLI** | Project scaffolding, migrations, shell, and more |
| **Multi-App** | Support for modular app architecture |

---

## 🚀 Quick Start

### Install

```bash
pip install vidyut
```

### Create a Project

```bash
vidyut startproject myapi
cd myapi
```

### Start Postgres

```bash
docker run --name postgres -e POSTGRES_PASSWORD=postgres -p 5432:5432 -d postgres
docker exec postgres psql -U postgres -c "CREATE DATABASE myapi;"
```

### Run Migrations & Start

```bash
vidyut migrate --app app.models
vidyut run main:app --reload
```

Visit:
- **API Docs**: http://localhost:8000/docs
- **Admin Panel**: http://localhost:8000/admin/ (debug mode)

---

## 📖 Core Concepts

### Models

```python
from vidyut import Model, fields

class User(Model):
    email = fields.Email(unique=True)
    name = fields.String(max_length=100)
    is_active = fields.Boolean(default=True)
    
class Post(Model):
    title = fields.String(max_length=200)
    content = fields.Text()
    author = fields.ForeignKey(User, on_delete="CASCADE")
    tags = fields.ManyToMany("Tag", related_name="posts")
    status = fields.EnumField(PostStatus, default=PostStatus.DRAFT)
```

#### CRUD Operations

```python
# Create
user = await User.objects.create(email="hello@example.com", name="Alice")

# Read
user = await User.objects.get(id=user_id)
user = await User.objects.get_or_none(email="maybe@exists.com")
users = await User.objects.filter(is_active=True).all()

# Update
user.name = "New Name"
await user.save()

# Delete
await user.delete()

# Advanced queries
count = await User.objects.filter(is_active=True).count()
user, created = await User.objects.get_or_create(
    email="hello@example.com",
    defaults={"name": "Default"}
)
```

### ViewSets (Auto CRUD)

```python
from vidyut import ModelViewSet, ModelSerializer

class UserSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "name", "is_active"]

class UserViewSet(ModelViewSet):
    model = User
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
```

This auto-generates:
- `GET /users/` - List (paginated)
- `POST /users/` - Create
- `GET /users/{id}` - Retrieve
- `PATCH /users/{id}` - Update
- `DELETE /users/{id}` - Delete

### Permissions

```python
from vidyut import (
    IsAuthenticated,
    IsAdminUser,
    IsOwnerOrReadOnly,
    AND, OR,
)

class PostViewSet(ModelViewSet):
    model = Post
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    
    # Or compose permissions
    permission_classes = [OR(IsAdminUser, IsOwnerOrReadOnly)]
```

### Admin Interface

```python
from vidyut.contrib.admin import site

# Register models
site.register(User)
site.register(Post)
```

Create a superuser:
```bash
vidyut createsuperuser --email admin@example.com
```

Access at `/admin/` (auto-enabled in debug mode).

---

## 🔧 CLI Commands

```bash
# Project management
vidyut startproject myapi      # Create new project
vidyut startapp blog           # Create new app

# Database
vidyut makemigrations --app app.models   # Generate migrations
vidyut migrate --app app.models          # Apply migrations
vidyut status --app app.models           # Check migration status

# Development
vidyut run main:app --reload   # Run dev server
vidyut shell                   # Async REPL
vidyut models --app app.models # List models

# Admin
vidyut createsuperuser         # Create admin user
vidyut info                    # Show environment info
```

---

## 📋 Field Types

| Field | PostgreSQL | Description |
|-------|------------|-------------|
| `String` | `VARCHAR(n)` | Text with max length |
| `Text` | `TEXT` | Unlimited text |
| `Integer` | `INTEGER` | Whole numbers |
| `Boolean` | `BOOLEAN` | True/False |
| `DateTime` | `TIMESTAMPTZ` | Date and time |
| `UUID` | `UUID` | Unique identifier |
| `JSON` | `JSONB` | JSON data |
| `Decimal` | `NUMERIC` | Precise decimals |
| `Email` | `VARCHAR(254)` | Validated email |
| `URL` | `TEXT` | Validated URL |
| `EnumField` | `TEXT` | Python Enum values |
| `ForeignKey` | `UUID` | Many-to-one relation |
| `OneToOne` | `UUID` | One-to-one relation |
| `ManyToMany` | Junction table | Many-to-many relation |

All models automatically include `id`, `created_at`, and `updated_at` fields.

---

## 🔗 Relationships

```python
# ForeignKey (Many-to-One)
class Post(Model):
    author = fields.ForeignKey(User, on_delete="CASCADE")

# OneToOne
class Profile(Model):
    user = fields.OneToOne(User)

# ManyToMany
class Article(Model):
    tags = fields.ManyToMany(Tag, related_name="articles")

# Usage
await article.tags.add(tag1, tag2)
await article.tags.remove(tag1)
await article.tags.all()
await article.tags.clear()
```

---

## 📦 Unified Imports

Everything from one package:

```python
from vidyut import (
    # Framework
    Vidyut, Model, fields, Database,
    
    # API Layer
    ModelViewSet, ModelSerializer, action,
    
    # Auth & Permissions
    IsAuthenticated, IsAdminUser, IsOwnerOrReadOnly,
    
    # FastAPI (re-exported)
    FastAPI, APIRouter, Request, Response,
    HTTPException, Depends, Query, Path,
)
```

---

## 🏗️ Project Structure

```
myapi/
├── app/
│   ├── models.py        # Vidyut models
│   ├── views.py         # ViewSets
│   ├── serializers.py   # Serializers
│   └── urls.py          # URL patterns
├── migrations/          # Database migrations
├── settings.py          # Configuration
├── main.py              # App entry point
└── .env                 # Environment variables
```

---

## 📋 Requirements

- Python 3.11+
- PostgreSQL 12+

---

## 📜 Changelog

### v0.3.15 (Latest)
- 🎛️ **Admin Interface**: Django-style server-rendered admin panel
- 👤 **createsuperuser**: CLI command for admin user creation
- 🎨 **Admin UI**: Neumorphic design with loading states

### v0.3.14
- 🔗 **Django-style URLs**: `path()`, `include()`, URL namespacing
- 🔄 **ViewSet auto-registration**: `include_viewset()`, `include_all_app_viewsets()`
- 📚 **Apps system**: `load_app_models()`, `get_app_models()`

### v0.3.13
- 🔒 **Rate limiting**: `RateLimiter`, `rate_limit()` decorator
- 📊 **Query optimization**: `select_related()`, `prefetch_related()`

### v0.3.12
- 🛡️ **Permission system**: `IsAuthenticated`, `IsAdminUser`, `IsOwnerOrReadOnly`
- 🔐 **Permission composition**: `AND()`, `OR()` combinators

### v0.3.11
- ✨ **Soft delete**: `SoftDeleteMixin` with `is_deleted`, `deleted_at`
- 🔍 **QuerySet chaining**: `exclude()`, `order_by()`, `values()`

### v0.3.10
- 👤 **Identity system**: `VidyutUserProtocol`, `AnonymousUser`
- 🔑 **Auth integration**: Session and token authentication support

### v0.3.8
- 🔗 **Relationship cascade**: `CASCADE`, `SET_NULL`, `RESTRICT`, `PROTECT`
- 🏷️ **Model.Meta**: Table name, ordering, constraints configuration

### v0.3.6
- 🏗️ **Multi-app architecture**: `apps` configuration in settings
- 🔍 **Auto-discovery**: Automatic ViewSet registration
- 🛠️ **startapp CLI**: Scaffold new apps with models, views, serializers

### v0.3.5
- ✨ **New fields**: `Email`, `URL`, `Text`, `Decimal`, `EnumField`
- 🔗 **OneToOne & ManyToMany**: Full relationship support

[View all releases →](https://github.com/nagarjuna-tella/vidyut/releases)

---

## 🤝 Contributing

Contributions welcome! Please read our contributing guidelines.

```bash
git clone https://github.com/nagarjuna-tella/vidyut.git
cd vidyut
pip install -e ".[dev]"
pytest
```

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<p align="center">
  <strong>⚡ Vidyut</strong> — The Async Python Web Framework<br>
  <a href="https://github.com/nagarjuna-tella/vidyut">GitHub</a> •
  <a href="https://github.com/nagarjuna-tella/vidyut/issues">Issues</a> •
  <a href="https://github.com/nagarjuna-tella/vidyut/discussions">Discussions</a>
</p>
