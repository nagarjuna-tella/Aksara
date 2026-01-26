# ⚡ Vidyut

> The Async Python Web Framework

**Vidyut** (meaning "electricity" in Sanskrit) is a batteries-included, async-native web framework for Python. Built on top of FastAPI and PostgreSQL, it combines Django's developer experience with modern async performance.

[![Tests](https://img.shields.io/badge/tests-1250%2B%20passing-brightgreen)]()
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
| **AI Mode** | Expose APIs as AI tools for MCP, OpenAI, LangChain |
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

## 🤖 AI Mode (v0.4.0)

Vidyut automatically exposes your ViewSets as structured AI tools:

```python
from vidyut import Vidyut, ModelViewSet, action
from vidyut.permissions import IsAuthenticated

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
| `GET /ai/tools/{name}` | Get a specific tool by name |
| `GET /ai/schema` | Model schemas for AI (existing) |
| `GET /ai/schema/{model}` | Specific model schema (existing) |

### Export Functions

```python
from vidyut.ai import export_tools_as_mcp, export_tools_as_generic

# Get tools filtered by permissions
tools = await get_ai_tools_for_request(request, app)

# Export for MCP servers
mcp_tools = export_tools_as_mcp(tools)

# Export for OpenAI Assistants
openai_funcs = export_tools_as_openai_functions(tools)

# Generic JSON export
generic = export_tools_as_generic(tools)
```

### Security

AI tools respect Vidyut's permission system:

```python
from vidyut.permissions import DenyAI

class SensitiveViewSet(ModelViewSet):
    model = Secret
    ai_exposed = False  # Hide entire ViewSet from AI

class PartialViewSet(ModelViewSet):
    model = User
    ai_exposed = True
    permission_classes = [DenyAI]  # Block AI access
    
    @action(detail=True, methods=["post"], ai_exposed=False)
    async def sensitive_action(self, pk, request):
        """This action won't appear in /ai/tools"""
        pass
```

---

## 🩺 AI Debug Assistant (v0.4.1)

When errors occur in debug mode, Vidyut provides AI-powered debugging assistance:

### Features

- **Smart Suggestions**: Rule-based suggestions for common error patterns
- **Error Classification**: Auto-detects validation, database, auth, timeout errors
- **LLM Integration**: Copy error context directly to AI assistants
- **Structured JSON**: Machine-readable context for programmatic analysis

### Using AI Debug

When an error occurs, the debug page shows an "🤖 AI Debug" tab with:

1. **Suggestions**: Actionable fixes based on error patterns
2. **Classification**: Tags showing error types (DB, Auth, Validation, etc.)
3. **Copy to LLM**: One-click copy of a formatted prompt
4. **JSON Export**: Full structured context for external tools

### Custom Advisors

Create custom debug advisors for domain-specific suggestions:

```python
from vidyut.ai import BaseAiDebugAdvisor, AiDebugSuggestion

class MyAdvisor(BaseAiDebugAdvisor):
    def analyze(self, context):
        suggestions = []
        if "MyCustomError" in context.exception.type:
            suggestions.append(AiDebugSuggestion(
                title="Custom Fix",
                description="Try checking X, Y, Z",
                confidence=0.9,
                category="custom",
            ))
        return suggestions
    
    def get_related_tools(self, context):
        return []

# Configure in settings
settings.ai_debug_advisor_class = "myapp.advisors.MyAdvisor"
```

---

## � AI Query Assistant (v0.4.2)

Execute structured query plans generated by LLMs without any LLM provider lock-in.

### Query Plans

```python
from vidyut.ai import AiQueryPlan, execute_ai_query_plan

# Define a query plan (typically from LLM output)
plan = AiQueryPlan(
    model="User",
    filters=[
        {"field": "is_active", "lookup": "exact", "value": True},
        {"field": "created_at", "lookup": "gte", "value": "2024-01-01"}
    ],
    sorting=[{"field": "email", "direction": "asc"}],
    pagination={"limit": 50, "offset": 0}
)

# Execute the plan
result = await execute_ai_query_plan(plan)
print(result.rows)   # Serialized instances
print(result.count)  # Total count
```

### Supported Lookups

| Lookup | Description | Example |
|--------|-------------|---------|
| `exact` | Exact match | `{"field": "status", "lookup": "exact", "value": "active"}` |
| `gt` / `gte` | Greater than | `{"field": "age", "lookup": "gte", "value": 18}` |
| `lt` / `lte` | Less than | `{"field": "price", "lookup": "lt", "value": 100}` |
| `in` | In list | `{"field": "role", "lookup": "in", "value": ["admin", "mod"]}` |
| `isnull` | Is null | `{"field": "deleted_at", "lookup": "isnull", "value": true}` |
| `icontains` | Case-insensitive contains | `{"field": "name", "lookup": "icontains", "value": "john"}` |
| `contains` | Case-sensitive contains | `{"field": "code", "lookup": "contains", "value": "ABC"}` |

### REST Endpoints

```bash
# Get the query plan schema (for LLMs)
POST /ai/query/plan/schema

# Execute a query plan
POST /ai/query/execute
{
  "model": "User",
  "filters": [{"field": "is_active", "lookup": "exact", "value": true}]
}

# List all queryable models
GET /ai/query/models
```

---

## 🏗️ AI CodeGen (v0.4.2)

Generate Vidyut-compatible code from structured specifications.

### Model Spec

```python
from vidyut.ai import AiModelSpec, AiFieldSpec, generate_code, AiCodegenRequest

spec = AiModelSpec(
    app_label="blog",
    name="Article",
    description="A blog article",
    fields=[
        AiFieldSpec(name="title", type="string", max_length=200),
        AiFieldSpec(name="body", type="text"),
        AiFieldSpec(name="author", type="fk", related_model="User", on_delete="CASCADE"),
        AiFieldSpec(name="tags", type="m2m", related_model="Tag"),
        AiFieldSpec(name="is_published", type="boolean", default=False),
    ],
    add_viewset=True,
    add_serializer=True,
)

# Generate full app skeleton
request = AiCodegenRequest(target="app", model_spec=spec)
result = generate_code(request)

for path, code in result.files.items():
    print(f"--- {path} ---")
    print(code)
```

### Supported Field Types

| Type | Vidyut Field | Notes |
|------|--------------|-------|
| `string` | `CharField` | Requires `max_length` |
| `text` | `TextField` | Unlimited text |
| `integer` | `IntegerField` | |
| `boolean` | `BooleanField` | |
| `datetime` | `DateTimeField` | Supports `auto_now`, `auto_now_add` |
| `uuid` | `UUIDField` | Can be `primary_key` |
| `decimal` | `DecimalField` | Requires `max_digits`, `decimal_places` |
| `email` | `EmailField` | |
| `url` | `URLField` | |
| `json` | `JSONField` | |
| `fk` | `ForeignKey` | Requires `related_model` |
| `m2m` | `ManyToManyField` | Requires `related_model` |

### Code Targets

| Target | Output |
|--------|--------|
| `model` | Single model class |
| `viewset` | ViewSet for the model |
| `serializer` | Serializer for the model |
| `admin` | Admin registration |
| `app` | Full app skeleton with all files |
| `migration` | Migration stub |

### REST Endpoints

```bash
# Get codegen schemas (for LLMs)
POST /ai/codegen/schema

# Preview generated code
POST /ai/codegen/preview
{
  "target": "app",
  "model_spec": {
    "app_label": "blog",
    "name": "Article",
    "fields": [{"name": "title", "type": "string", "max_length": 200}]
  }
}
```

---

## 🧠 AI Context Engine (v0.4.3)

The AI Context Engine is the single most important foundation for Vidyut as an AI-native framework. It exports your entire application state as structured JSON that LLMs can consume.

### Full Context Endpoint

```bash
GET /ai/context/full
```

Returns complete app state including:
- All models with fields, types, relationships
- All ViewSets with actions and permissions
- All API routes with methods and documentation
- Migration history
- Admin configuration
- Application settings (safe subset, no credentials)
- Middleware stack
- Available AI tools and schemas

### Response Structure

```json
{
  "framework": "vidyut",
  "framework_version": "0.4.3",
  "context_version": "1.0.0",
  "generated_at": "2024-01-15T10:30:00Z",
  "checksum": "abc123def456",
  "models": [
    {
      "name": "User",
      "table_name": "users",
      "ai_description": "Application user",
      "fields": [
        {"name": "email", "field_type": "Email", "nullable": false},
        {"name": "name", "field_type": "String", "max_length": 100}
      ],
      "relations": [...]
    }
  ],
  "model_count": 5,
  "viewsets": [...],
  "viewset_count": 3,
  "routes": [...],
  "route_count": 25,
  "settings": {...},
  "admin": {...},
  "ai_tools": [...],
  "ai_schemas": [...]
}
```

### Key Properties

| Property | Description |
|----------|-------------|
| **Deterministic** | Same app state = same output (except timestamp) |
| **Stable** | Fields sorted alphabetically for consistency |
| **Safe** | No credentials or secrets included |
| **Checksummed** | Hash for change detection |

### Focused Endpoints

For specific context subsets:

```bash
# Models and relationships only
GET /ai/context/models

# ViewSets and actions only  
GET /ai/context/viewsets

# Settings and middleware only
GET /ai/context/settings

# All API routes
GET /ai/context/routes

# Admin configuration
GET /ai/context/admin
```

### Python Usage

```python
from vidyut.ai import build_full_ai_context, AiFullContext

# Build context from app
context = await build_full_ai_context(app)

# Access structured data
for model in context.models:
    print(f"Model: {model.name}")
    for field in model.fields:
        print(f"  - {field.name}: {field.field_type}")

# Export as JSON
import json
json_context = json.dumps(context.model_dump())
```

### Use Cases

1. **LLM Code Generation**: Give AI complete app knowledge for accurate code
2. **Documentation Generation**: Auto-generate API docs from context
3. **Schema Validation**: Verify app structure against expectations
4. **Change Detection**: Compare checksums to detect schema changes
5. **AI Assistants**: Provide context for Claude, GPT, etc.
```

---

## �🔧 CLI Commands

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

### v0.4.2 (Latest) — AI Query Assistant & CodeGen
- 🔍 **AI Query Assistant**: Execute structured query plans generated by LLMs
- 🏗️ **AI CodeGen**: Deterministic code generation from AI-provided specs
- 🔌 **Provider-Agnostic**: Define contracts, let external adapters call LLMs
- 📝 **New Pydantic Models**: `AiQueryPlan`, `AiFilterCondition`, `AiModelSpec`, `AiFieldSpec`
- 🌐 **New Endpoints**: 
  - `POST /ai/query/plan/schema` - Get query plan JSON schema
  - `POST /ai/query/execute` - Execute a query plan
  - `GET /ai/query/models` - List queryable models
  - `POST /ai/codegen/schema` - Get codegen JSON schemas  
  - `POST /ai/codegen/preview` - Generate code from spec
- 🔧 **Query Lookups**: exact, gt, gte, lt, lte, in, isnull, icontains, contains
- 📦 **Code Targets**: model, viewset, serializer, admin, app skeleton, migration
- 🧪 **Comprehensive Tests**: Full coverage for query execution and code generation

**Example - Query Plan**:
```python
from vidyut.ai import AiQueryPlan, execute_ai_query_plan

plan = AiQueryPlan(
    model="User",
    filters=[
        {"field": "is_active", "lookup": "exact", "value": True},
        {"field": "email", "lookup": "icontains", "value": "example.com"}
    ],
    sorting=[{"field": "created_at", "direction": "desc"}],
    pagination={"limit": 20}
)
result = await execute_ai_query_plan(plan)
```

**Example - CodeGen**:
```python
from vidyut.ai import AiModelSpec, AiCodegenRequest, generate_code

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
# result.files contains generated Python code files
```

### v0.4.1 — AI Debug Assistant
- 🤖 **AI Debug Context**: Structured error context for LLM analysis
- 💡 **Smart Suggestions**: Rule-based suggestions for common errors
- 🏷️ **Error Classification**: Auto-classify validation, db, auth, connection errors
- 📋 **Copy to LLM**: One-click copy of error context for AI assistants
- 🖥️ **New Debug Tab**: "AI Debug" tab in error pages with suggestions and JSON
- 🔧 **Extensible Advisors**: Create custom `BaseAiDebugAdvisor` implementations
- ⚙️ **Settings**: `ai_debug_enabled`, `ai_debug_advisor_class` configuration

**Usage**: When an error occurs in debug mode, click the "AI Debug" tab to see:
- Auto-generated suggestions based on error patterns
- Exception classification (validation, database, auth, etc.)
- Copyable LLM prompt for asking AI assistants
- Full JSON context for programmatic analysis

### v0.4.0 — AI Mode
- 🤖 **AI Tool Registry**: Expose ViewSets and actions as structured AI tools
- 🔧 **Universal Export**: `export_tools_as_mcp()`, `export_tools_as_generic()`, `export_tools_as_openai_functions()`
- 🔐 **Secure by Default**: Permission-aware tool filtering with `ai_exposed`, `DenyAI`
- 🌐 **New Endpoints**: `/ai/tools`, `/ai/tools/mcp`, `/ai/tools/openai`
- 📦 **New Package**: `vidyut.ai` with `AiTool`, `AiToolRegistry`, exporters
- 🧪 **Comprehensive Tests**: Full coverage for AI tool discovery and endpoints

### v0.3.20
- 🔢 **QuerySet.order_by()**: Full ordering API for ORM queries
  - `order_by("field")` for ascending, `order_by("-field")` for descending
  - Multiple fields: `order_by("is_active", "-created_at")`
  - Chaining: `filter(is_active=True).order_by("email")`
  - FK fields: `order_by("author_id")` and `order_by("author")`
- 🧪 **44 New Tests**: Comprehensive ordering test coverage
- 🛠️ **ORM Polish**: Stable foundation before 0.4.0 AI features

### v0.3.19
- ✅ **Sanity Audit**: Comprehensive pre-0.4.0 hardening with 45 new edge-case tests
- 📦 **Export Fixes**: Added `ValidationError`, `ConfigurationError` to public API
- 🧪 **1092 Tests**: Full coverage across all 14+ subsystems
- 📋 **Verified**: CLI scaffolding, migrations, admin, auth, permissions, API layer

### v0.3.18
- 🛠️ **Dev Tools CLI**: `vidyut format`, `vidyut lint`, `vidyut typecheck`, `vidyut test`
- 🔗 **Pre-commit Integration**: `vidyut precommit init` and `vidyut precommit run`
- 📦 **Dev Extra**: `pip install vidyut[dev]` for black, ruff, mypy, pytest, pre-commit
- 🆕 **Enhanced Scaffolding**: `.pre-commit-config.yaml`, `.editorconfig`, tool configs in pyproject.toml
- 📊 **Improved DX**: Graceful error messages when dev tools are not installed

### v0.3.17
- 🌙 **Dark-Mode Debug Pages**: Beautiful dark-themed error pages in debug mode
- 📊 **Rich Error Context**: Stacktrace, request details, context variables (request_id, tenant_id, user_id)
- 🔒 **Production-Safe**: Clean JSON or minimal HTML in production mode
- 🎨 **Interactive UI**: Tabs for traceback, request, context, environment
- 🛡️ **XSS Safe**: Automatic HTML escaping of error messages
- 📝 **Sensitive Headers**: Automatic redaction of auth headers

### v0.3.16
- 🔀 **Migration Conflict Resolution**: Detect and resolve parallel migration branches
- 📊 **Migration Graph**: Track dependencies between migrations
- 🛠️ **`--merge` flag**: `vidyut makemigrations --merge app` creates merge migrations
- ⚡ **Improved UX**: Clear conflict messages and resolution hints

### v0.3.15
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
