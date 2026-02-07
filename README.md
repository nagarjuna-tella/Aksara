# ⚡ Aksara

> The AI-Native Async Python Web Framework

**Aksara** (meaning "letter/script" in Sanskrit — the building blocks of written language) is a batteries-included, async-native web framework for Python. Built on FastAPI and PostgreSQL, it gives you everything you need to build production APIs in minutes, not days.

[![Tests](https://img.shields.io/badge/tests-2493%2B%20passing-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.11+-blue)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()

> **Note**: Aksara was previously developed internally under the codename "Vidyut" but was never publicly released under that name. This is the first official public identity.

## Why Aksara?

**Stop writing boilerplate. Start building features.**

Most Python web frameworks make you choose: either simple but limited, or powerful but complex. Aksara gives you both — a clean, intuitive API with enterprise-grade features built in.

### What You Get Out of the Box

| Feature | What It Means For You |
|---------|----------------------|
| 🗄️ **Database ORM** | Define your data in Python, we handle the SQL |
| 🔄 **Auto CRUD APIs** | One class = complete REST API with 5 endpoints |
| 🔐 **Authentication** | Session & token auth, ready to use |
| 🛡️ **Permissions** | Control who can do what with simple rules |
| 📊 **Admin Panel** | Manage your data through a web interface |
| 🤖 **AI Integration** | Expose your APIs as AI tools automatically |
| 🚀 **Async Performance** | Handle thousands of concurrent requests |
| 🧪 **Built-in Testing** | Test utilities included |

### The Aksara Difference

```python
# Define your data
class Post(Model):
    title = fields.String(max_length=200)
    content = fields.Text()
    published = fields.Boolean(default=False)

# Get a complete REST API
class PostViewSet(ModelViewSet):
    model = Post
```

**That's it.** You now have:
- `GET /posts/` — List all posts (paginated)
- `POST /posts/` — Create a post
- `GET /posts/{id}/` — Get one post
- `PATCH /posts/{id}/` — Update a post
- `DELETE /posts/{id}/` — Delete a post

No routing code. No serialization logic. No boilerplate.

---

## Features

| Feature | Description |
|---------|-------------|
| **ORM** | Python classes become database tables with relationships and validation |
| **Migrations** | Change your models, run a command, database updates automatically |
| **ViewSets** | One class generates a complete REST API |
| **Serializers** | Control exactly what data goes in and out |
| **Auth** | User authentication with sessions or tokens |
| **Permissions** | Fine-grained access control |
| **Admin Interface** | Web-based data management panel |
| **AI Mode** | Your APIs become AI tools (OpenAI, LangChain, MCP compatible) |
| **AI Context** | Export your entire app as structured data for LLMs |
| **AI CodeGen** | Generate code from natural language descriptions |
| **CLI** | Commands for every common task |
| **Multi-App** | Organize large projects into modules |

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

## ⚡ How Aksara Compares

| Task | Raw FastAPI + SQLAlchemy | Aksara |
|------|--------------------------|--------|
| Define a model | ~30 lines (model + schema + CRUD) | 5 lines |
| Create REST API | ~100 lines (routes + logic) | 4 lines |
| Add authentication | Manual JWT/session setup | `permission_classes = [IsAuthenticated]` |
| Database migrations | Alembic setup + manual scripts | `aksara makemigrations` |
| Admin interface | Build from scratch | `site.register(Model)` |
| AI tool integration | Custom implementation | `ai_exposed = True` |

**Aksara is built on FastAPI** — you get all of FastAPI's features (OpenAPI docs, dependency injection, Pydantic validation) plus a complete application framework on top.

---

## 📖 Core Concepts

### Models — Your Data, Defined in Python

A **Model** is a Python class that represents a database table. Each attribute is a column:

```python
from aksara import Model, fields

class User(Model):
    email = fields.Email(unique=True)      # Must be unique across all users
    name = fields.String(max_length=100)   # Text up to 100 characters
    is_active = fields.Boolean(default=True)  # True/False, defaults to True
    
class Post(Model):
    title = fields.String(max_length=200)
    content = fields.Text()                 # Unlimited text
    author = fields.ForeignKey(User, on_delete=fields.CASCADE)  # Links to User
    tags = fields.ManyToMany("Tag", related_name="posts")  # Many posts ↔ many tags
    status = fields.Enum(PostStatus, default=PostStatus.DRAFT)
```

Aksara automatically creates `id`, `created_at`, and `updated_at` for every model.

#### Working with Data

```python
# Create a new record
user = await User.objects.create(email="hello@example.com", name="Alice")

# Find a record
user = await User.objects.get(id=user_id)           # Raises error if not found
user = await User.objects.get_or_none(email="...")  # Returns None if not found

# Query multiple records
active_users = await User.objects.filter(is_active=True).all()
recent_posts = await Post.objects.filter(status="published").order_by("-created_at").all()

# Update
user.name = "New Name"
await user.save()

# Delete
await user.delete()

# Counting and checking existence
count = await User.objects.filter(is_active=True).count()
exists = await User.objects.filter(email="test@example.com").exists()

# Get or create (won't duplicate)
user, created = await User.objects.get_or_create(
    email="hello@example.com",
    defaults={"name": "Default Name"}
)
```

### ViewSets — Instant REST APIs

A **ViewSet** turns your model into a complete REST API:

```python
from aksara.api import ModelViewSet, ModelSerializer

class UserSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "name", "is_active"]  # What to expose

class UserViewSet(ModelViewSet):
    model = User
    serializer_class = UserSerializer
```

This single class creates 5 API endpoints:

| Method | URL | What It Does |
|--------|-----|--------------|
| GET | `/users/` | List all users (paginated) |
| POST | `/users/` | Create a new user |
| GET | `/users/{id}/` | Get one user by ID |
| PATCH | `/users/{id}/` | Update a user |
| DELETE | `/users/{id}/` | Delete a user |

### Permissions — Control Access

Protect your endpoints with permission classes:

```python
from aksara.permissions import IsAuthenticated, IsAdminUser, IsOwnerOrReadOnly, AND, OR

class PostViewSet(ModelViewSet):
    model = Post
    permission_classes = [IsAuthenticated]  # Must be logged in
    
class AdminViewSet(ModelViewSet):
    model = Settings
    permission_classes = [IsAdminUser]  # Must be admin

# Combine permissions with AND/OR
class ArticleViewSet(ModelViewSet):
    permission_classes = [OR(IsAdminUser, IsOwnerOrReadOnly)]
    # Admin can do anything, others can only read or edit their own
```

| Permission | Who Can Access |
|------------|----------------|
| `AllowAny` | Everyone |
| `IsAuthenticated` | Logged-in users |
| `IsAdminUser` | Admin users only |
| `IsOwnerOrReadOnly` | Owner can edit, others can only read |

### Admin Interface — Manage Data Visually

Register your models to get a web-based admin panel:

```python
from aksara.contrib.admin import site

site.register(User)
site.register(Post)
```

Create an admin account:
```bash
aksara createsuperuser --email admin@example.com
```

Access at `http://localhost:8000/admin/` — view, create, edit, and delete records through a clean web interface.

---

## 🤖 AI Mode — Your APIs as AI Tools

Aksara is built for the AI era. With one flag, your APIs become tools that AI assistants can use:

```python
class PostViewSet(ModelViewSet):
    model = Post
    ai_exposed = True  # ← That's it. AI can now use this API.
```

### What AI Gets

| Endpoint | What It Returns |
|----------|-----------------|
| `GET /ai/tools` | All available tools for the current user |
| `GET /ai/tools/mcp` | Tools in Model Context Protocol format |
| `GET /ai/tools/openai` | Tools in OpenAI function calling format |
| `GET /ai/context/full` | Your entire app as structured JSON |

### Custom AI Actions

```python
from aksara.api import action

class PostViewSet(ModelViewSet):
    model = Post
    ai_exposed = True
    
    @action(detail=True, methods=["post"], ai_exposed=True)
    async def publish(self, pk, request):
        """AI can call this to publish a draft post."""
        post = await Post.objects.get(id=pk)
        post.status = "published"
        await post.save()
        return {"status": "published"}
```

### AI Code Generation

Generate Aksara code from descriptions:

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

result = generate_code(AiCodegenRequest(target="app", model_spec=spec))
# Returns complete, working Aksara code
```

---

## 🔧 CLI Commands

Aksara includes a powerful command-line interface:

```bash
# Create a new project
aksara startproject myapi

# Create a new app module
aksara startapp blog

# Database commands
aksara makemigrations --app app.models  # Generate migrations from model changes
aksara migrate --app app.models         # Apply migrations to database
aksara status --app app.models          # Check what's pending

# Run your app
aksara run main:app --reload   # Development server with auto-reload

# Interactive shell
aksara shell                   # Python shell with your models loaded

# Admin
aksara createsuperuser         # Create admin user

# Development tools
aksara format                  # Format code with black
aksara lint                    # Check code with ruff
aksara typecheck               # Type check with mypy
aksara test                    # Run tests with pytest
```

---

## 📋 Field Types

Every field maps to a PostgreSQL column type:

| Field | Database Type | Example Use |
|-------|--------------|-------------|
| `String` | `VARCHAR(n)` | Names, titles, short text |
| `Text` | `TEXT` | Articles, descriptions, long content |
| `Integer` | `INTEGER` | Counts, quantities |
| `Boolean` | `BOOLEAN` | Flags, yes/no values |
| `DateTime` | `TIMESTAMPTZ` | Timestamps with timezone |
| `Date` | `DATE` | Dates without time |
| `UUID` | `UUID` | Unique identifiers |
| `JSON` | `JSONB` | Structured data, settings |
| `Decimal` | `NUMERIC` | Money, precise numbers |
| `Email` | `VARCHAR(254)` | Email addresses (validated) |
| `URL` | `TEXT` | Web URLs (validated) |
| `Enum` | `TEXT` | Fixed choices (Python Enum) |
| `ForeignKey` | `UUID` | Link to another model (many-to-one) |
| `OneToOne` | `UUID` | Exclusive link (one-to-one) |
| `ManyToMany` | Junction table | Multiple links (many-to-many) |

**Note:** Every model automatically gets `id` (UUID), `created_at`, and `updated_at` fields.

---

## 📦 Imports

Everything you need from one package:

```python
from aksara import (
    # Core
    Aksara, Model, fields, Database,
    
    # API Layer
    ModelViewSet, ModelSerializer, action,
    
    # Permissions
    IsAuthenticated, IsAdminUser, IsOwnerOrReadOnly,
    
    # FastAPI (re-exported for convenience)
    FastAPI, APIRouter, Request, Response,
    HTTPException, Depends, Query, Path,
)
```

---

## 🏗️ Project Structure

Aksara projects are organized simply:

```
myapi/
├── app/
│   ├── models.py        # Your data models
│   ├── views.py         # Your API endpoints
│   ├── serializers.py   # Input/output formatting
│   └── urls.py          # Route configuration
├── migrations/          # Database migrations (auto-generated)
├── settings.py          # App configuration
├── main.py              # Entry point
└── .env                 # Environment variables (DATABASE_URL, etc.)
```

---

## 📋 Requirements

- Python 3.11+
- PostgreSQL 12+

---

## 📜 Changelog

### v0.4.11 — Admin UI/UX Overhaul
- 🎨 **Modern Admin UI**: Complete redesign with clean, professional interface
- 🧩 **Widget System**: New centralized widget architecture
- 📝 **JSON Widget**: Enhanced JSON editor with formatting, validation, syntax highlighting
- 📋 **Array Widget**: Dynamic repeater interface for array fields with add/remove functionality
- 🎨 **New CSS Framework**: 1200+ lines of modern, responsive styles
- 🌓 **Dark Mode**: Full dark mode support with auto-detection
- 📱 **Mobile Responsive**: Collapsible sidebar, optimized layouts
- ⚡ **No Dependencies**: Pure HTML/CSS/vanilla JS, no bloat
- 🎯 **Better UX**: Modern forms, improved tables, clear action buttons
- 📊 **Professional Design**: Inspired by Django Jet, Laravel Nova, Supabase
- 📚 **Documentation Overhaul**: Beginner-friendly docs with correct API references

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
