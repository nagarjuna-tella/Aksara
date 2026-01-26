# Quickstart

Get Vidyut running in under 5 minutes.

---

## Prerequisites

Before you begin, ensure you have:

- **Python 3.11+** installed
- **PostgreSQL 13+** running locally or remotely
- **pip** or **uv** for package management

---

## Step 1: Install Vidyut

=== "pip"

    ```bash
    pip install vidyut
    ```

=== "uv"

    ```bash
    uv pip install vidyut
    ```

=== "poetry"

    ```bash
    poetry add vidyut
    ```

---

## Step 2: Create a New Project

Use the CLI to scaffold a new project:

```bash
vidyut startproject myproject
cd myproject
```

This creates the following structure:

```
myproject/
├── main.py           # Application entry point
├── settings.py       # Configuration
├── app/
│   ├── models.py     # Your models
│   ├── views.py      # ViewSets
│   ├── urls.py       # Route registration
│   └── serializers.py
├── migrations/       # Database migrations
├── .env              # Environment variables
├── pyproject.toml    # Project metadata
└── README.md
```

---

## Step 3: Configure Your Database

Edit the `.env` file with your PostgreSQL connection:

```bash
DATABASE_URL=postgresql://postgres:password@localhost:5432/myproject
VIDYUT_DEBUG=true
```

Or set it directly in `settings.py`:

```python
from vidyut import configure

configure(
    database_url="postgresql://postgres:password@localhost:5432/myproject",
    debug=True,
)
```

---

## Step 4: Define Your First Model

Open `app/models.py` and add a model:

```python
from vidyut import Model, fields

class Task(Model):
    """A simple task model."""
    title = fields.String(max_length=200)
    description = fields.Text(nullable=True)
    completed = fields.Boolean(default=False)
    priority = fields.Integer(default=1)
    created_at = fields.DateTime(auto_now_add=True)
    updated_at = fields.DateTime(auto_now=True)
```

---

## Step 5: Create and Run Migrations

Generate and apply migrations:

```bash
# Generate migration files
vidyut makemigrations --app app.models

# Apply migrations to the database
vidyut migrate
```

---

## Step 6: Create a ViewSet

Open `app/views.py`:

```python
from vidyut.api import ModelViewSet, action
from fastapi import Request
from uuid import UUID

from app.models import Task

class TaskViewSet(ModelViewSet):
    model = Task
    prefix = "/tasks"
    tags = ["Tasks"]
    
    @action(detail=True, methods=["post"], summary="Mark task complete")
    async def complete(self, pk: UUID, request: Request):
        task = await self.get_object(pk)
        task.completed = True
        await task.save()
        return {"status": "completed", "task_id": str(pk)}
```

---

## Step 7: Register Routes

Open `app/urls.py`:

```python
from vidyut.api import include_viewset
from fastapi import APIRouter

from app.views import TaskViewSet

router = APIRouter()
include_viewset(router, TaskViewSet)
```

Then in `main.py`, include the router:

```python
from vidyut import Vidyut
from app.urls import router

app = Vidyut(
    database_url="postgresql://postgres:password@localhost:5432/myproject",
    title="My Task API",
    enable_admin=True,
)

app.include_router(router, prefix="/api")
```

---

## Step 8: Run the Application

```bash
vidyut run main:app --reload
```

Your API is now running at `http://localhost:8000`.

---

## Step 9: Explore

### API Documentation

Visit **http://localhost:8000/docs** for interactive Swagger UI.

### Admin Interface

Visit **http://localhost:8000/admin** to manage your data.

!!! note "Admin Login"
    Create a superuser first:
    ```bash
    vidyut shell
    >>> from vidyut.contrib.auth import User
    >>> await User.objects.create(
    ...     email="admin@example.com",
    ...     hashed_password=User.hash_password("secret"),
    ...     is_staff=True,
    ...     is_superuser=True
    ... )
    ```

### Test the API

```bash
# Create a task
curl -X POST http://localhost:8000/api/tasks/ \
  -H "Content-Type: application/json" \
  -d '{"title": "Learn Vidyut", "priority": 1}'

# List tasks
curl http://localhost:8000/api/tasks/

# Complete a task
curl -X POST http://localhost:8000/api/tasks/{task_id}/complete
```

---

## What's Next?

<div class="grid cards" markdown>

-   :material-book-open-variant:{ .lg .middle } **Full Tutorial**

    ---

    Build a complete blog application step by step.

    [:octicons-arrow-right-24: Build a Blog](tutorials/build-a-blog.md)

-   :material-database:{ .lg .middle } **Learn the ORM**

    ---

    Master models, fields, relations, and queries.

    [:octicons-arrow-right-24: ORM Guide](orm/models.md)

-   :material-robot:{ .lg .middle } **Explore AI Mode**

    ---

    Make your app AI-native with tools and agents.

    [:octicons-arrow-right-24: AI Overview](ai/overview.md)

-   :material-cog:{ .lg .middle } **Configuration**

    ---

    Learn all available settings and options.

    [:octicons-arrow-right-24: Settings Reference](reference/settings-reference.md)

</div>

---

## Need Help?

- Check the [Glossary](glossary.md) for terminology
- Browse the [API Reference](reference/model-api-reference.md)
- Open an issue on [GitHub](https://github.com/vidyut-orm/vidyut/issues)
