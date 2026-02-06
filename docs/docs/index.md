# Aksara Framework

## Build Web APIs in Python — Fast, Simple, AI-Ready

<div class="hero-section" markdown>

**Aksara** is a Python framework for building web APIs that connect to databases. If you want to create a backend for a mobile app, website, or any application that stores data, Aksara helps you do it quickly.

[Get Started →](quickstart.md){ .md-button .md-button--primary }
[View on GitHub](https://github.com/aksara-orm/aksara){ .md-button }

</div>

---

## What is Aksara?

**Aksara is a backend framework.** It helps you:

| What You Need | How Aksara Helps |
|---------------|------------------|
| Store data | Define **Models** that create database tables |
| Retrieve data | Use **QuerySets** to search without writing SQL |
| Build an API | Create **ViewSets** that auto-generate REST endpoints |
| Secure access | Set up **Permissions** to control who can do what |
| Manage data | Use the **Admin** dashboard to view and edit data |
| Work with AI | Use **AI Mode** so AI agents can interact with your data |

---

## Who is Aksara For?

**Aksara is for Python developers who:**

- ✅ Want to build APIs without writing repetitive code
- ✅ Need a database but don't want to write raw SQL
- ✅ Want modern async Python (not slow threads)
- ✅ Like Django's patterns but want FastAPI's speed
- ✅ Want their app to work with AI agents

**You don't need:**

- ❌ Previous Django experience
- ❌ Deep database knowledge
- ❌ To understand async internals

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
    title = fields.String(max_length=200)
    completed = fields.Boolean(default=False)
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
aksara migrate    # Create the database table
aksara run        # Start the server
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

## What's New in v0.4.11

The latest release includes:

- **Admin UI Overhaul** — New modern widget system with JSON and Array field widgets
- **AI Schema Doctor** — Detect schema drift and health issues
- **AI Agent Runtime** — Mini agent loop for external AI coordination
- **Enhanced Debug Pages** — AI-powered debugging suggestions
- **1920+ Tests** — Comprehensive test coverage

[View Full Changelog](changelog.md){ .md-button }

---

## Getting Help

- **Documentation** — You're reading it!
- **GitHub Issues** — [Report bugs or request features](https://github.com/aksara-orm/aksara/issues)
- **Discussions** — [Ask questions](https://github.com/aksara-orm/aksara/discussions)

---

<div class="footer-tagline" markdown>

**Aksara** — *Simple, fast, AI-ready backends for Python.*

</div>
