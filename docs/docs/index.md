# Vidyut Framework

## The AI-Native Async Backend Framework for Python

<div class="hero-section" markdown>

**Vidyut** is a modern, async-first backend framework built on FastAPI and PostgreSQL. It combines the developer experience of Django with the performance of async Python — and adds first-class AI integration that makes your application intelligible to LLMs.

[Get Started](quickstart.md){ .md-button .md-button--primary }
[View on GitHub](https://github.com/vidyut-orm/vidyut){ .md-button }

</div>

---

## Why Vidyut?

### ⚡ Async-Native from Day One

Vidyut is built entirely on async Python. Every database query, every API endpoint, every middleware — all async. No thread pools, no blocking calls, just pure `asyncio` performance.

```python
from vidyut import Model, fields

class Article(Model):
    title = fields.String(max_length=200)
    content = fields.Text()
    published = fields.Boolean(default=False)
    created_at = fields.DateTime(auto_now_add=True)

# Fully async queries
articles = await Article.objects.filter(published=True).order_by("-created_at")
```

### 🧠 AI-Native Architecture

Vidyut is the first backend framework designed for AI agents. Every model, every endpoint, every action is automatically exposed as structured AI tools with full type information.

```python
from vidyut.ai import build_full_ai_context

# Export your entire app as structured JSON for LLMs
context = await build_full_ai_context(app)

# Or let AI agents query your data directly
from vidyut.ai import execute_ai_query_plan
result = await execute_ai_query_plan(query_plan)
```

### 🎯 Django-like Developer Experience

If you've used Django, you'll feel right at home. Models, migrations, admin, viewsets — all the patterns you love, reimagined for async.

```python
from vidyut.api import ModelViewSet, action
from vidyut.permissions import IsAuthenticated

class ArticleViewSet(ModelViewSet):
    model = Article
    prefix = "/articles"
    permission_classes = [IsAuthenticated]
    
    @action(detail=True, methods=["post"])
    async def publish(self, pk: UUID, request: Request):
        article = await self.get_object(pk)
        article.published = True
        await article.save()
        return {"status": "published"}
```

### 🔒 Production-Ready

Built-in authentication, permissions, middleware, request tracing, multi-tenancy support, and beautiful debug pages. Everything you need to ship to production.

---

## Feature Highlights

<div class="grid cards" markdown>

-   :material-database:{ .lg .middle } **Async ORM**

    ---

    PostgreSQL-native ORM with relations, migrations, and Django-style QuerySet API — all fully async.

    [:octicons-arrow-right-24: Learn about Models](orm/models.md)

-   :material-api:{ .lg .middle } **REST API Layer**

    ---

    Auto-generated CRUD endpoints, custom actions, serializers, and permissions — built on FastAPI.

    [:octicons-arrow-right-24: Explore ViewSets](api/viewsets.md)

-   :material-robot:{ .lg .middle } **AI Mode**

    ---

    First-class AI integration: tools, context engine, query engine, patch engine, and agent runtime.

    [:octicons-arrow-right-24: Discover AI Mode](ai/overview.md)

-   :material-cog:{ .lg .middle } **Admin Interface**

    ---

    Django-style admin for managing your data with customizable list views and permissions.

    [:octicons-arrow-right-24: Configure Admin](admin/admin-site.md)

-   :material-bug:{ .lg .middle } **Debug Tools**

    ---

    Beautiful dark-mode error pages with AI-powered debugging suggestions.

    [:octicons-arrow-right-24: Debug Your App](debugging/error-pages.md)

-   :material-console:{ .lg .middle } **CLI Tools**

    ---

    Project scaffolding, migrations, development tools, and AI commands.

    [:octicons-arrow-right-24: CLI Reference](cli/overview.md)

</div>

---

## Quick Example

Create a complete blog API in under 50 lines:

```python
# main.py
from vidyut import Vidyut, Model, fields
from vidyut.api import ModelViewSet, include_viewset
from vidyut.permissions import IsAuthenticated

# Define your models
class Author(Model):
    name = fields.String(max_length=100)
    email = fields.Email(unique=True)

class Post(Model):
    title = fields.String(max_length=200)
    content = fields.Text()
    author = fields.ForeignKey(Author, on_delete=fields.CASCADE)
    published = fields.Boolean(default=False)
    created_at = fields.DateTime(auto_now_add=True)

# Create ViewSets
class AuthorViewSet(ModelViewSet):
    model = Author
    prefix = "/authors"

class PostViewSet(ModelViewSet):
    model = Post
    prefix = "/posts"
    permission_classes = [IsAuthenticated]

# Initialize app
app = Vidyut(
    database_url="postgresql://localhost/myapp",
    title="Blog API",
    enable_admin=True,
)

# Register routes
include_viewset(app, AuthorViewSet)
include_viewset(app, PostViewSet)
```

Run it:

```bash
vidyut makemigrations --app main
vidyut migrate
vidyut run main:app --reload
```

Visit `http://localhost:8000/docs` to see your auto-generated API documentation.

---

## What's New in v0.4.9

The latest release focuses on stability and AI capabilities:

- **AI Schema Doctor** — Detect schema drift and health issues
- **AI Agent Runtime** — Mini agent loop for external AI coordination
- **AI Planner** — Multi-step execution plans for complex operations
- **Enhanced Debug Pages** — AI-powered debugging suggestions
- **2000+ Tests** — Comprehensive test coverage for production reliability

[View Full Changelog](changelog.md){ .md-button }

---

## Installation

```bash
pip install vidyut
```

Requires Python 3.11+ and PostgreSQL 13+.

[Full Installation Guide](getting-started/installation.md){ .md-button }

---

## Community & Support

- **GitHub**: [vidyut-orm/vidyut](https://github.com/vidyut-orm/vidyut)
- **Issues**: [Report bugs or request features](https://github.com/vidyut-orm/vidyut/issues)
- **Discussions**: [Ask questions and share ideas](https://github.com/vidyut-orm/vidyut/discussions)

---

<div class="footer-tagline" markdown>

**Vidyut** — *Lightning-fast async backends, AI-ready from the start.*

</div>
