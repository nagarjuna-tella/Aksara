# Your First 10 Minutes with Aksara

This guide walks you from **zero to a running Aksara app** with:

- ✅ A model
- ✅ An API
- ✅ Admin panel
- ✅ Studio inspector

By the end, you'll have a working Book API you can extend.

---

## Prerequisites

| Requirement | Version | Check Command |
|-------------|---------|---------------|
| Python | 3.11+ | `python --version` |
| PostgreSQL | 13+ | `psql --version` |
| pip | Latest | `pip --version` |

**Don't have PostgreSQL?** Use Docker:

```bash
docker run -d --name postgres \
  -e POSTGRES_PASSWORD=postgres \
  -p 5432:5432 \
  postgres:15

docker exec postgres psql -U postgres -c "CREATE DATABASE myapp;"
```

---

## Step 1: Install & Create a Project

Install Aksara:

```bash
pip install aksara
```

Create a new project:

```bash
aksara startproject myapp
cd myapp
```

Your project structure:

```
myapp/
├── main.py           # App entry point
├── settings.py       # Configuration
├── .env              # Environment variables
├── app/
│   ├── models.py     # Your models
│   ├── views.py      # Your ViewSets
│   ├── serializers.py
│   ├── urls.py       # Route registration
│   └── admin.py      # Admin registrations
└── migrations/       # Database migrations
```

---

## Step 2: Add a Model

Open `app/models.py` and add a `Book` model:

```python
# app/models.py
from aksara import Model, fields

class Book(Model):
    title = fields.String(
        max_length=200,
        ai_description="Title of the book"
    )
    author = fields.String(
        max_length=200,
        ai_description="Author's full name"
    )
    published = fields.Boolean(
        default=False,
        ai_description="Whether the book is published",
        ai_agent_writable=False
    )
    pages = fields.Integer(
        nullable=True,
        ai_description="Total number of pages"
    )

    class Meta:
        table_name = "books"
```

**What's happening:**

- `fields.String` creates a `VARCHAR` column
- `fields.Boolean` creates a boolean with a default
- `fields.Integer(nullable=True)` allows NULL values
- `Meta.table_name` sets the database table name

---

## Step 3: Register in Admin

Open `app/admin.py` and register the Book model:

```python
# app/admin.py
from aksara.contrib.admin import admin_site
from .models import Book

admin_site.register(Book)
```

This gives you a web UI to create, edit, and delete books—no extra code needed.

---

## Step 4: Add a ViewSet

Open `app/views.py` and add a ViewSet:

```python
# app/views.py
from aksara.api import ModelViewSet
from .models import Book

class BookViewSet(ModelViewSet):
    model = Book
    prefix = "/api/books"
    tags = ["Books"]
```

**What this gives you:**

| Method | Path | Action |
|--------|------|--------|
| GET | `/api/books/` | List all books |
| POST | `/api/books/` | Create a book |
| GET | `/api/books/{id}/` | Get one book |
| PATCH | `/api/books/{id}/` | Update a book |
| DELETE | `/api/books/{id}/` | Delete a book |

---

## Step 5: Register the ViewSet

Open `app/urls.py` and register the ViewSet:

```python
# app/urls.py
from aksara.api import include_viewset
from .views import BookViewSet

def register_routes(app):
    """Register all routes for this app."""
    include_viewset(app, BookViewSet)
```

---

## Step 6: Configure Database

Run the interactive database setup:

```bash
aksara dbsetup
```

This checks for PostgreSQL, prompts for credentials, creates the database, and writes `DATABASE_URL` to `.env`.

!!! tip "Manual alternative"
    You can also edit `.env` directly:
    ```bash
    DATABASE_URL=postgresql://postgres:postgres@localhost:5432/myapp
    ```

---

## Step 7: Migrate & Run

Generate and apply migrations:

```bash
aksara makemigrations
aksara migrate
```

Start the development server:

```bash
aksara dev
```

You should see:

```
⚡ Aksara v0.5.43

  Running development server...
  
  App:    http://127.0.0.1:8000/
  Admin:  http://127.0.0.1:8000/admin/
  Studio: http://127.0.0.1:8000/studio/ui
  Docs:   http://127.0.0.1:8000/docs
```

---

## Step 8: Explore Your App

### 8.1 API Endpoints

Test your API:

```bash
# Create a book
curl -X POST http://127.0.0.1:8000/api/books/ \
  -H "Content-Type: application/json" \
  -d '{"title": "The Pragmatic Programmer", "author": "Hunt & Thomas", "pages": 352}'

# List all books
curl http://127.0.0.1:8000/api/books/
```

Or visit the interactive API docs at **http://127.0.0.1:8000/docs**.

### 8.2 Admin Panel

Visit **http://127.0.0.1:8000/admin/**:

1. You'll see "Books" in the sidebar
2. Click to view, create, or edit books
3. No authentication required in debug mode

### 8.3 Studio Inspector

Visit **http://127.0.0.1:8000/studio/ui**:

| Tab | What It Shows |
|-----|---------------|
| **Models** | All your models, fields, and relationships |
| **Routes** | All registered API endpoints |
| **Migrations** | Migration history and pending changes |
| **Runtime** | Settings and configuration |
| **DB Queries** | SQL query inspector |
| **AI Context** | AI-ready context export |

---

## What's Next?

You've built a working Aksara app! Here's where to go next:

### Learn More

- **[Quickstart](../quickstart.md)** – Build a Task Manager with more features
- **[ORM Guide](../orm/index.md)** – Deep dive into models, fields, and queries
- **[API Guide](../api/index.md)** – ViewSets, actions, permissions, and serializers

### Try a Pattern

- **[Blog Pattern](../patterns/blog.md)** – Posts, comments, publishing workflow
- **[CRM Pattern](../patterns/crm.md)** – Customers, deals, pipelines
- **[Multitenant Pattern](../patterns/multitenant.md)** – Tenant-aware SaaS apps

### Explore Features

- **[Admin Guide](../admin/index.md)** – Customize your admin panel
- **[Studio Guide](../studio/index.md)** – Use the visual inspector
- **[AI Mode](../ai-mode/index.md)** – Expose your API as AI tools

---

## Common Questions

**Q: How do I add authentication?**  
See [Authentication](../api/authentication.md) for session and token auth.

**Q: How do I add custom endpoints?**  
Use the `@action` decorator. See [Actions](../api/actions.md).

**Q: How do I add relationships between models?**  
See [Relations](../orm/relations.md) for ForeignKey and ManyToMany.

**Q: How do I deploy to production?**  
See [Running Your App](running-your-app.md) for production configuration.

---

🎉 **Congratulations!** You've completed your first 10 minutes with Aksara.
