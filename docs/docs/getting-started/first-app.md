# First App

Build your first Vidyut application from scratch.

---

## What We're Building

In this guide, you'll create a **Task Management API** with:

- A `Task` model with title, description, status, and priority
- Full CRUD API (Create, Read, Update, Delete)
- A custom action to mark tasks as complete
- Admin interface for data management

---

## Prerequisites

Before starting, ensure you have:

- Vidyut [installed](installation.md)
- PostgreSQL [set up](database-setup.md) and running
- A database created for your project

---

## Step 1: Create the Project

```bash
vidyut startproject taskapi
cd taskapi
```

You now have a complete project structure.

---

## Step 2: Configure the Database

Edit `.env` with your database connection:

```bash
DATABASE_URL=postgresql://postgres:password@localhost:5432/taskapi
VIDYUT_DEBUG=true
```

Create the database if it doesn't exist:

```bash
createdb taskapi
```

---

## Step 3: Define the Model

Open `app/models.py` and replace its contents:

```python
"""Task Management Models"""

from vidyut import Model, fields


class Task(Model):
    """
    A task in the task management system.
    
    Attributes:
        title: Short description of the task
        description: Detailed task description
        status: Current task status (pending, in_progress, completed)
        priority: Task priority (1=low, 2=medium, 3=high)
        due_date: Optional deadline
        created_at: When the task was created
        updated_at: When the task was last modified
    """
    
    # Core fields
    title = fields.String(
        max_length=200,
        ai_description="Short title describing the task"
    )
    description = fields.Text(
        nullable=True,
        ai_description="Detailed description of what needs to be done"
    )
    
    # Status tracking
    status = fields.String(
        max_length=20,
        default="pending",
        ai_description="Task status: pending, in_progress, or completed"
    )
    priority = fields.Integer(
        default=2,
        ai_description="Priority level: 1=low, 2=medium, 3=high"
    )
    
    # Dates
    due_date = fields.DateTime(
        nullable=True,
        ai_description="Optional deadline for the task"
    )
    created_at = fields.DateTime(auto_now_add=True)
    updated_at = fields.DateTime(auto_now=True)
    
    class Meta:
        app_label = "app"
    
    def __str__(self) -> str:
        return self.title
```

---

## Step 4: Create Migrations

Generate and apply the database schema:

```bash
# Generate migration file
vidyut makemigrations --app app.models

# Apply to database
vidyut migrate
```

You should see:

```
✓ Created migration: 0001_initial.py
✓ Applied migration: 0001_initial
```

---

## Step 5: Create the ViewSet

Open `app/views.py` and replace its contents:

```python
"""Task API ViewSets"""

from uuid import UUID
from fastapi import Request, HTTPException

from vidyut.api import ModelViewSet, action
from vidyut.permissions import IsAuthenticated, AllowAny

from app.models import Task


class TaskViewSet(ModelViewSet):
    """
    ViewSet for Task CRUD operations.
    
    Endpoints:
        GET    /tasks/         - List all tasks
        POST   /tasks/         - Create a task
        GET    /tasks/{id}     - Get a specific task
        PATCH  /tasks/{id}     - Update a task
        DELETE /tasks/{id}     - Delete a task
        POST   /tasks/{id}/complete - Mark task as complete
    """
    
    model = Task
    prefix = "/tasks"
    tags = ["Tasks"]
    
    # Allow anyone to read, authenticate to write
    permission_classes = [AllowAny]
    
    @action(detail=True, methods=["post"], summary="Mark task as complete")
    async def complete(self, pk: UUID, request: Request):
        """
        Mark a task as completed.
        
        Sets the status to 'completed' and returns the updated task.
        """
        task = await self.get_object(pk)
        
        if task.status == "completed":
            raise HTTPException(
                status_code=400,
                detail="Task is already completed"
            )
        
        task.status = "completed"
        await task.save()
        
        return {
            "message": "Task marked as complete",
            "task": {
                "id": str(task.id),
                "title": task.title,
                "status": task.status,
            }
        }
    
    @action(detail=False, methods=["get"], summary="Get pending tasks")
    async def pending(self, request: Request):
        """
        Get all pending tasks ordered by priority.
        """
        tasks = await Task.objects.filter(
            status="pending"
        ).order_by("-priority")
        
        return {
            "count": len(tasks),
            "tasks": [
                {
                    "id": str(t.id),
                    "title": t.title,
                    "priority": t.priority,
                }
                for t in tasks
            ]
        }
    
    @action(detail=False, methods=["get"], summary="Get task statistics")
    async def stats(self, request: Request):
        """
        Get task statistics by status.
        """
        all_tasks = await Task.objects.all()
        
        stats = {
            "total": len(all_tasks),
            "pending": 0,
            "in_progress": 0,
            "completed": 0,
        }
        
        for task in all_tasks:
            if task.status in stats:
                stats[task.status] += 1
        
        return stats
```

---

## Step 6: Register Routes

Open `app/urls.py`:

```python
"""URL Configuration"""

from fastapi import APIRouter
from vidyut.api import include_viewset

from app.views import TaskViewSet

router = APIRouter()
include_viewset(router, TaskViewSet)
```

---

## Step 7: Configure the App

Open `main.py` and update it:

```python
"""Task API Application"""

from vidyut import Vidyut
from app.urls import router

# Import settings to configure Vidyut
import settings

app = Vidyut(
    title="Task Management API",
    description="A simple task management API built with Vidyut",
    enable_admin=True,
    debug=True,
)

# Include the API router
app.include_router(router, prefix="/api")
```

Make sure `settings.py` exists and configures the database:

```python
"""Application Settings"""

import os
from vidyut import configure

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:password@localhost:5432/taskapi"
)

configure(
    database_url=DATABASE_URL,
    debug=os.getenv("VIDYUT_DEBUG", "true").lower() == "true",
    installed_apps=[
        "vidyut.contrib.auth",
        "vidyut.contrib.admin",
        "app",
    ],
)
```

---

## Step 8: Run the Application

```bash
vidyut run main:app --reload
```

You should see:

```
⚡ Vidyut v0.4.9
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
```

---

## Step 9: Test the API

### View API Documentation

Open **http://localhost:8000/docs** in your browser to see the interactive API documentation.

### Create a Task

```bash
curl -X POST http://localhost:8000/api/tasks/ \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Learn Vidyut",
    "description": "Complete the getting started guide",
    "priority": 3
  }'
```

Response:
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "title": "Learn Vidyut",
  "description": "Complete the getting started guide",
  "status": "pending",
  "priority": 3,
  "due_date": null,
  "created_at": "2026-01-26T10:00:00Z",
  "updated_at": "2026-01-26T10:00:00Z"
}
```

### List Tasks

```bash
curl http://localhost:8000/api/tasks/
```

### Get Pending Tasks

```bash
curl http://localhost:8000/api/tasks/pending
```

### Complete a Task

```bash
curl -X POST http://localhost:8000/api/tasks/{task_id}/complete
```

### Get Statistics

```bash
curl http://localhost:8000/api/tasks/stats
```

---

## Step 10: Explore the Admin

Visit **http://localhost:8000/admin** to manage tasks through the admin interface.

!!! note "Admin Login Required"
    Create a superuser to access admin:
    ```bash
    vidyut shell
    >>> from vidyut.contrib.auth import User
    >>> await User.objects.create(
    ...     email="admin@example.com",
    ...     hashed_password=User.hash_password("admin123"),
    ...     is_staff=True,
    ...     is_superuser=True
    ... )
    ```

---

## What You've Learned

In this guide, you:

1. ✅ Created a new Vidyut project
2. ✅ Defined a model with various field types
3. ✅ Generated and applied migrations
4. ✅ Created a ViewSet with custom actions
5. ✅ Registered routes and configured the app
6. ✅ Tested the API using curl
7. ✅ Explored the admin interface

---

## Next Steps

<div class="grid cards" markdown>

-   :material-database:{ .lg .middle } **Learn the ORM**

    ---

    Master models, fields, relations, and queries.

    [:octicons-arrow-right-24: ORM Guide](../orm/models.md)

-   :material-api:{ .lg .middle } **API Deep Dive**

    ---

    ViewSets, serializers, permissions, and more.

    [:octicons-arrow-right-24: API Guide](../api/viewsets.md)

-   :material-robot:{ .lg .middle } **AI Mode**

    ---

    Make your app AI-native.

    [:octicons-arrow-right-24: AI Overview](../ai/overview.md)

-   :material-book-open:{ .lg .middle } **Full Tutorial**

    ---

    Build a complete blog application.

    [:octicons-arrow-right-24: Blog Tutorial](../tutorials/build-a-blog.md)

</div>
