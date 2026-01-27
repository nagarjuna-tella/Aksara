# ⚡ Aksara

> The AI-Native Async Python Web Framework

**Aksara** (meaning "letter/script" in Sanskrit — the building blocks of written language) is a batteries-included, async-native web framework for Python. Built on top of FastAPI and PostgreSQL, it combines Django's developer experience with modern async performance and first-class AI integration.

[![Tests](https://img.shields.io/badge/tests-2000%2B%20passing-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.11+-blue)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()

> **Note**: Aksara was previously developed internally under the codename "Vidyut" but was never publicly released under that name. This is the first official public identity.

## Why Aksara?

Aksara gives you everything you need to build production-ready async APIs:

- 🚀 **Full Framework**: ORM, migrations, auth, permissions, admin — all included
- ⚡ **Async-Native**: Built from the ground up for async/await
- 🐘 **PostgreSQL-First**: Designed specifically for Postgres with asyncpg
- 🎯 **Django-Style DX**: Familiar APIs if you know Django/DRF
- 🔧 **Zero Boilerplate**: Auto-generated CRUD, schemas, and routing
- 🛡️ **Security Built-in**: Authentication, permissions, and rate limiting
- 🤖 **AI-Native**: Expose your APIs as AI tools, structured context export, codegen

---

## Features

| Feature | Description |
|---------|-------------|
| **ORM** | Django-like models with async queries, relationships, and validation |
| **Migrations** | `makemigrations` & `migrate` commands with SQL generation |
| **ViewSets** | Auto-generated CRUD APIs with `ModelViewSet` |
| **Serializers** | DRF-style `ModelSerializer` with nested relationships |
| **Auth** | Session & token auth with `AksaraUserProtocol` |
| **Permissions** | `IsAuthenticated`, `IsAdminUser`, `IsOwnerOrReadOnly`, composable |
| **Admin Interface** | Django-style server-rendered admin panel |
| **AI Mode** | Expose APIs as AI tools for MCP, OpenAI, LangChain |
| **AI Context** | Export full app context as structured JSON for LLMs |
| **AI CodeGen** | Generate models, viewsets, and apps from AI specs |
| **AI Query** | Execute LLM-generated query plans |
| **CLI** | Project scaffolding, migrations, shell, and more |
| **Multi-App** | Support for modular app architecture |

---

## 🚀 Quick Start

### Install

```bash
pip install aksara
```

### Create a Project

```bash
aksara startproject myapi
cd myapi
```

### Start Postgres

```bash
docker run --name postgres -e POSTGRES_PASSWORD=postgres -p 5432:5432 -d postgres
docker exec postgres psql -U postgres -c "CREATE DATABASE myapi;"
```

### Run Migrations & Start

```bash
aksara migrate --app app.models
aksara run main:app --reload
```

Visit:
- **API Docs**: http://localhost:8000/docs
- **Admin Panel**: http://localhost:8000/admin/ (debug mode)

---

## 📖 Core Concepts

### Models

```python
from aksara import Model, fields

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
from aksara import ModelViewSet, ModelSerializer

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
from aksara import (
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
from aksara.contrib.admin import site

# Register models
site.register(User)
site.register(Post)
```

Create a superuser:
```bash
aksara createsuperuser --email admin@example.com
```

Access at `/admin/` (auto-enabled in debug mode).

---

## 🤖 AI Mode

Aksara is designed from the ground up to work with AI. It automatically exposes your ViewSets as structured AI tools:

```python
from aksara import Aksara, ModelViewSet, action
from aksara.permissions import IsAuthenticated

class PostViewSet(ModelViewSet):
    model = Post
    prefix = "/api/posts"
    ai_exposed = True  # Enable AI tools for this ViewSet
    permission_classes = [IsAuthenticated]
    
    @action(detail=True, methods=["post"], ai_exposed=True)
    async def publish(self, pk, request):
        """Publish a draft post."""
        pass
```

### AI Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /ai/tools` | List all tools the current user can access |
| `GET /ai/tools/mcp` | Tools in MCP (Model Context Protocol) format |
| `GET /ai/tools/openai` | Tools in OpenAI function calling format |
| `GET /ai/context/full` | Complete app context as JSON for LLMs |
| `POST /ai/query/execute` | Execute LLM-generated query plans |
| `POST /ai/codegen/preview` | Generate code from AI specs |

### AI Context Engine

Export your entire application as structured JSON that LLMs can consume:

```bash
GET /ai/context/full
```

Returns models, viewsets, routes, settings, permissions — everything an AI needs to understand and work with your app.

### AI CodeGen

Generate Aksara-compatible code from specifications:

```python
from aksara.ai import AiModelSpec, AiCodegenRequest, generate_code

spec = AiModelSpec(
    app_label="blog",
    name="Article",
    fields=[
        {"name": "title", "type": "string", "max_length": 200},
        {"name": "body", "type": "text"},
        {"name": "author", "type": "fk", "related_model": "User"}
    ],
    add_viewset=True,
    add_serializer=True
)
request = AiCodegenRequest(target="app", model_spec=spec)
result = generate_code(request)
```

---

## 🔧 CLI Commands

```bash
# Project management
aksara startproject myapi      # Create new project
aksara startapp blog           # Create new app

# Database
aksara makemigrations --app app.models   # Generate migrations
aksara migrate --app app.models          # Apply migrations
aksara status --app app.models           # Check migration status

# Development
aksara run main:app --reload   # Run dev server
aksara shell                   # Async REPL
aksara models --app app.models # List models

# Admin
aksara createsuperuser         # Create admin user
aksara info                    # Show environment info

# Dev tools
aksara format                  # Format code with black
aksara lint                    # Lint with ruff
aksara typecheck               # Type check with mypy
aksara test                    # Run pytest
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

## 📦 Unified Imports

Everything from one package:

```python
from aksara import (
    # Framework
    Aksara, Model, fields, Database,
    
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
│   ├── models.py        # Aksara models
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

### v0.4.10 — Aksara (Rename Release)
- 🔄 **Renamed**: Framework renamed from Vidyut to Aksara
- 📦 **New Package**: `pip install aksara`
- 🔧 **New CLI**: `aksara` command (was `vidyut`)
- 📝 **Updated Docs**: All documentation updated to Aksara branding
- ✅ **Full Compatibility**: All existing features preserved

### Previous Versions (as Vidyut)

#### v0.4.3 — AI Context Engine
- 🧠 **Full Context Export**: Complete app state as structured JSON
- 📊 **Focused Endpoints**: Models, viewsets, routes, settings
- 🔐 **Safe Export**: No credentials or secrets included

#### v0.4.2 — AI Query & CodeGen
- 🔍 **AI Query Assistant**: Execute LLM-generated query plans
- 🏗️ **AI CodeGen**: Generate code from AI specifications

#### v0.4.1 — AI Debug Assistant
- 🤖 **AI Debug Context**: Structured error context for LLMs
- 💡 **Smart Suggestions**: Rule-based error suggestions

#### v0.4.0 — AI Mode
- 🤖 **AI Tool Registry**: Expose ViewSets as AI tools
- 🔧 **Universal Export**: MCP, OpenAI, generic formats

---

## 🤝 Contributing

Contributions welcome! Please read our contributing guidelines.

```bash
git clone https://github.com/aksara-framework/aksara.git
cd aksara
pip install -e ".[dev]"
pytest
```

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<p align="center">
  <strong>⚡ Aksara</strong> — The AI-Native Async Python Web Framework<br>
  <a href="https://github.com/aksara-framework/aksara">GitHub</a> •
  <a href="https://github.com/aksara-framework/aksara/issues">Issues</a> •
  <a href="https://github.com/aksara-framework/aksara/discussions">Discussions</a>
</p>
