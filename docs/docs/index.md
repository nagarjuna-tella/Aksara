# Aksara Framework

## Async Python Backend — ORM, Auto-REST, AI Console, and MCP Tools in One Framework

<div class="hero-section" markdown>

**Aksara** is a Python backend framework that ships with everything you need to go from an empty directory to a running, AI-ready API. Define your models, get a full REST API, an admin interface, a visual Studio dashboard, an interactive AI Console, and auto-generated MCP tools — all from the same codebase.

[Get Started →](quickstart.md){ .md-button .md-button--primary }
[View on GitHub](https://github.com/nagarjuna-tella/Aksara){ .md-button }

</div>

---

## What is Aksara?

**Aksara gives you everything out of the box:**

| What You Get | How |
|--------------|-----|
| **Async ORM** | Define Python models → Aksara creates database tables and handles all SQL |
| **Auto REST API** | One `ModelViewSet` class → full CRUD endpoints with pagination and validation |
| **Built-in Admin** | Browse and edit your data at `/admin` with zero configuration |
| **Studio UI** | Visual dashboard at `/studio/ui` — inspect models, routes, queries, and migrations |
| **AI Console** | Natural-language interface inside Studio — ask questions about your data, routes, and schema in plain English |
| **AI Review Tools** | Run AI Debugger, Architecture Review, and Performance Analyzer against the same live project context |
| **MCP Tools** | Your models become MCP tools automatically — connect any MCP-compatible AI agent |
| **Doctor & Fix Plans** | `aksara doctor` checks app health and `aksara doctor fix-plan` prints the remediation path |
| **Migration System** | Schema changes tracked and applied with `aksara migrate` |

---

## Who is Aksara For?

**Aksara is for Python developers who:**

- ✅ Want a complete backend stack, not just a web framework
- ✅ Need async PostgreSQL without writing raw SQL
- ✅ Like Django's ergonomics but want FastAPI's async performance
- ✅ Want their data instantly accessible to AI agents via MCP
- ✅ Value built-in tooling (Studio, AI Console, Doctor) over plugin sprawl

**You don't need:**

- ❌ Previous Django or FastAPI experience
- ❌ Deep database knowledge
- ❌ To configure AI integrations from scratch

---

## How Does It Work?

```
You write this:                    You get this:

┌──────────────────────┐           ┌──────────────────────┐
│ class Task(Model):   │           │ Database table       │
│   title = String()   │    ──►    │ with columns         │
│   completed = Bool() │           │                      │
└──────────────────────┘           └──────────────────────┘

┌──────────────────────┐           ┌──────────────────────┐
│ class TaskViewSet(   │           │ REST API endpoints:  │
│   ModelViewSet):     │    ──►    │ GET  /tasks/         │
│   model = Task       │           │ POST /tasks/         │
└──────────────────────┘           │ GET  /tasks/{id}/    │
                                   │ PUT  /tasks/{id}/    │
                                   │ DELETE /tasks/{id}/  │
                                   └──────────────────────┘
```

**In ~10 lines of code, you get:**

- A database table
- A complete REST API
- Input validation
- Interactive documentation
- Admin interface

---

## Quick Example

Here's a complete working API:

```python
# main.py
from aksara import Aksara, Model, fields
from aksara.api import ModelViewSet

# 1. Define your data structure
class Task(Model):
    """A task in a todo list."""
    title = fields.String(
        max_length=200,
        ai_description="Short title describing the task",
    )
    completed = fields.Boolean(
        default=False,
        ai_description="Whether the task has been finished",
    )
    created_at = fields.DateTime(auto_now_add=True)

# 2. Create the API
class TaskViewSet(ModelViewSet):
    model = Task

# 3. Start the app
app = Aksara(database_url="postgresql://localhost/myapp")
app.include_viewset(TaskViewSet, prefix="/tasks")
```

**Run it:**

```bash
aksara dbsetup    # Set up the database interactively
aksara migrate    # Create the database table
aksara dev        # Start the development server
```

**Test it:**

```bash
# Create a task
curl -X POST http://localhost:8000/tasks/ \
  -H "Content-Type: application/json" \
  -d '{"title": "Learn Aksara"}'

# List all tasks
curl http://localhost:8000/tasks/
```

Once running, open **http://localhost:8000/studio/ui** to explore your models and queries in the built-in Studio dashboard. The `ai_description` metadata you wrote above flows through to the AI Console and to the MCP tool catalog at `/ai/tools/mcp` — no second schema required.

---

## Key Features

### 🗄️ Database Without SQL

Define your data as Python classes. Aksara handles the SQL.

```python
class Article(Model):
    title = fields.String(max_length=200)
    content = fields.Text()
    published = fields.Boolean(default=False)
    created_at = fields.DateTime(auto_now_add=True)

# Query without SQL
articles = await Article.objects.filter(published=True).order_by("-created_at")
```

**What this means:** You work with Python objects, not database queries.

👉 [Learn about Models](orm/models.md)

---

### ⚡ Fast Async Performance

Every database call is non-blocking. Your app can handle many requests at once.

```python
# All database calls use await
article = await Article.objects.get(id=article_id)
articles = await Article.objects.filter(published=True)
```

**What this means:** Your server doesn't freeze while waiting for the database.

---

### 🔌 Automatic API Creation

One class creates a complete REST API with all standard operations.

```python
class ArticleViewSet(ModelViewSet):
    model = Article
    permission_classes = [IsAuthenticated]
```

**What you get automatically:**

| Method | URL | What It Does |
|--------|-----|--------------|
| GET | `/articles/` | List all articles |
| POST | `/articles/` | Create an article |
| GET | `/articles/{id}/` | Get one article |
| PUT | `/articles/{id}/` | Update an article |
| DELETE | `/articles/{id}/` | Delete an article |

👉 [Learn about ViewSets](api/viewsets.md)

---

### 🔒 Built-in Security

Control who can access what with simple permission classes.

```python
from aksara.permissions import IsAuthenticated, IsAdminUser

class ArticleViewSet(ModelViewSet):
    model = Article
    permission_classes = [IsAuthenticated]  # Must be logged in
```

**What this means:** Unauthorized requests are automatically rejected.

👉 [Learn about Permissions](api/permissions.md)

---

### 🤖 AI Agent Integration

Make your application accessible to AI assistants like ChatGPT.

```python
from aksara.ai import build_full_ai_context

# Export your entire app as structured data for AI
context = await build_full_ai_context(app)
```

**What this means:** AI agents can understand and interact with your data.

The same AI layer also powers the built-in Studio AI Console, the Architecture Review, and the Performance Analyzer, so you do not have to maintain separate schemas for internal tooling and external agents.

👉 [Learn about AI Mode](ai-mode/index.md)

---

### 🛠️ Admin Dashboard

A built-in interface to view and manage your data.

```python
app = Aksara(
    database_url="postgresql://localhost/myapp",
    enable_admin=True,  # Enable admin at /admin/
)
```

**What you get:** A web interface to browse, create, edit, and delete data.

👉 [Learn about Admin](admin/index.md)

---

## Installation

```bash
pip install aksara
```

**Requirements:**

| Tool | Minimum Version | What It's For |
|------|-----------------|---------------|
| Python | 3.11 | Running Aksara |
| PostgreSQL | 13 | Storing your data |

👉 [Full Installation Guide](getting-started/installation.md)

---

## Next Steps

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } **Quickstart**

    ---

    Build your first API in 5 minutes.

    [:octicons-arrow-right-24: Start Building](quickstart.md)

-   :material-school:{ .lg .middle } **Getting Started Guide**

    ---

    Detailed walkthrough for beginners.

    [:octicons-arrow-right-24: Learn Step by Step](getting-started/index.md)

-   :material-database:{ .lg .middle } **Models & ORM**

    ---

    Learn how to define and query data.

    [:octicons-arrow-right-24: Learn about Data](orm/index.md)

-   :material-api:{ .lg .middle } **API Layer**

    ---

    Build REST APIs with ViewSets.

    [:octicons-arrow-right-24: Learn about APIs](api/index.md)

</div>

---

## What's New in v0.5.45

The latest release includes:

- **`Q()` Objects** — Nested boolean filtering with explicit `AND`, `OR`, and `NOT`
- **`F()` Expressions** — Database-side arithmetic and field comparisons
- **Relation-Aware Aggregates** — One-hop aggregate joins for reverse FK/O2O and M2M paths
- **`transaction.atomic`** — Async context manager and decorator for safe multi-step writes
- **Expanded ORM Coverage** — New tests for expressions, aggregate joins, and transaction reuse

[View Full Changelog](changelog.md){ .md-button }

---

## Getting Help

- **Documentation** — You're reading it!
- **GitHub Issues** — [Report bugs or request features](https://github.com/nagarjuna-tella/Aksara/issues)
- **Discussions** — [Ask questions](https://github.com/nagarjuna-tella/Aksara/discussions)

---

<div class="footer-tagline" markdown>

**Aksara** — *Simple, fast, AI-ready backends for Python.*

Designed and built by [Nagarjuna Tella](https://github.com/nagarjuna-tella).

</div>
