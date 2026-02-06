# Quickstart

Build a working API in 5 minutes. No prior framework experience needed.

---

## What We're Building

A simple **Task Manager API** that lets you:

- Create tasks
- List all tasks
- Mark tasks as complete
- Delete tasks

By the end, you'll have a real API you can call from any frontend or tool.

---

## Prerequisites

Before you start, make sure you have:

| Tool | How to Check | What It's For |
|------|--------------|---------------|
| Python 3.11+ | `python --version` | Running Aksara |
| PostgreSQL | `psql --version` | Storing your data |
| pip | `pip --version` | Installing packages |

**Don't have PostgreSQL?** You can use Docker:
```bash
docker run -d --name postgres -e POSTGRES_PASSWORD=password -p 5432:5432 postgres:15
```

---

## Step 1: Install Aksara

Open your terminal and run:

```bash
pip install aksara
```

**What this does:** Downloads Aksara and its dependencies (FastAPI, Pydantic, asyncpg, etc.).

Verify it worked:

```bash
aksara --version
# Output: aksara, version 0.4.11
```

---

## Step 2: Create Your Project

Run the scaffolding command:

```bash
aksara startproject taskmanager
cd taskmanager
```

**What this does:** Creates a folder with all the files you need to start.

You'll see this structure:

```
taskmanager/
├── main.py           ← Starts your application
├── settings.py       ← Configuration (database URL, etc.)
├── .env              ← Secret settings (not committed to git)
├── app/
│   ├── models.py     ← Define your data structure
│   ├── views.py      ← Handle API requests
│   ├── serializers.py ← Convert data to/from JSON
│   └── urls.py       ← Map URLs to views
└── migrations/       ← Database schema changes
```

---

## Step 3: Configure Your Database

### Option A: Using a `.env` File (Recommended)

Edit `.env`:

```bash
DATABASE_URL=postgresql://postgres:password@localhost:5432/taskmanager
AKSARA_DEBUG=true
```

### Option B: Environment Variables

Set them in your shell:

```bash
export DATABASE_URL=postgresql://postgres:password@localhost:5432/taskmanager
export AKSARA_DEBUG=true
```

### Create the Database

If the database doesn't exist yet:

```bash
# Using psql
createdb taskmanager

# Or connect to PostgreSQL and create it
psql -U postgres -c "CREATE DATABASE taskmanager;"
```

---

## Step 4: Define Your Data Model

Open `app/models.py` and add:

```python
from aksara import Model, fields

class Task(Model):
    """
    A task in our todo list.
    
    This creates a database table with these columns:
    - id: UUID (created automatically)
    - title: Text up to 200 characters
    - description: Optional longer text
    - completed: True or False
    - created_at: When the task was created (automatic)
    """
    title = fields.String(max_length=200)
    description = fields.Text(nullable=True)
    completed = fields.Boolean(default=False)
    created_at = fields.DateTime(auto_now_add=True)
```

**What this does:** Defines what a "Task" looks like. Aksara will create a database table matching this structure.

**Understanding the code:**

| Line | What It Means |
|------|---------------|
| `class Task(Model)` | "Task" is a type of data we store |
| `fields.String(max_length=200)` | Text that can't exceed 200 characters |
| `fields.Text(nullable=True)` | Optional long text (`nullable=True` means it can be empty) |
| `fields.Boolean(default=False)` | True/False value, starts as False |
| `fields.DateTime(auto_now_add=True)` | Timestamp, automatically set when created |

---

## Step 5: Create Your API

### Serializer (Data Converter)

Open `app/serializers.py`:

```python
from aksara.api import ModelSerializer
from app.models import Task

class TaskSerializer(ModelSerializer):
    """
    Converts Task objects to/from JSON.
    
    When someone sends JSON to your API, the serializer:
    1. Validates the data
    2. Converts it to a Task object
    
    When you return a Task, the serializer converts it to JSON.
    """
    class Meta:
        model = Task
        fields = ["id", "title", "description", "completed", "created_at"]
        read_only_fields = ["id", "created_at"]  # Users can't set these
```

**What this does:** Tells Aksara how to convert between Python objects and JSON.

### ViewSet (Request Handler)

Open `app/views.py`:

```python
from aksara.api import ModelViewSet
from app.models import Task
from app.serializers import TaskSerializer

class TaskViewSet(ModelViewSet):
    """
    Handles all API requests for tasks.
    
    ModelViewSet automatically creates these endpoints:
    - GET    /tasks/      → List all tasks
    - POST   /tasks/      → Create a task
    - GET    /tasks/{id}/ → Get one task
    - PUT    /tasks/{id}/ → Update a task
    - DELETE /tasks/{id}/ → Delete a task
    """
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
```

**What this does:** Creates a complete REST API for tasks with just 4 lines of code.

### URLs (Route Mapping)

Open `app/urls.py`:

```python
from aksara.api import Router
from app.views import TaskViewSet

router = Router()
router.register("tasks", TaskViewSet)

# This creates these URLs:
# - /api/tasks/
# - /api/tasks/{id}/
```

**What this does:** Maps URLs to your ViewSet.

---

## Step 6: Create the Database Table

Run migrations to create your table:

```bash
# Generate a migration file (like a recipe for changing the database)
aksara makemigrations

# Apply the migration (actually create the table)
aksara migrate
```

**What this does:**

1. `makemigrations` looks at your models and creates instructions for the database
2. `migrate` runs those instructions to create the actual tables

---

## Step 7: Start Your Server

```bash
aksara run
```

**What you'll see:**

```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
```

**Your API is now running!**

---

## Step 8: Test Your API

### Using the Interactive Docs

Open your browser to: **http://localhost:8000/docs**

You'll see Swagger UI with all your endpoints. Try them out!

### Using curl (Command Line)

**Create a task:**

```bash
curl -X POST http://localhost:8000/api/tasks/ \
  -H "Content-Type: application/json" \
  -d '{"title": "Buy groceries", "description": "Milk, eggs, bread"}'
```

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Buy groceries",
  "description": "Milk, eggs, bread",
  "completed": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**List all tasks:**

```bash
curl http://localhost:8000/api/tasks/
```

**Mark a task complete:**

```bash
curl -X PUT http://localhost:8000/api/tasks/{id}/ \
  -H "Content-Type: application/json" \
  -d '{"completed": true}'
```

**Delete a task:**

```bash
curl -X DELETE http://localhost:8000/api/tasks/{id}/
```

### Using Python

```python
import httpx

# Create a task
response = httpx.post(
    "http://localhost:8000/api/tasks/",
    json={"title": "Learn Aksara", "description": "Read the docs"}
)
task = response.json()
print(f"Created task: {task['id']}")

# List tasks
tasks = httpx.get("http://localhost:8000/api/tasks/").json()
print(f"You have {len(tasks)} tasks")
```

---

## What You Built

Congratulations! You created:

✅ A **database table** to store tasks  
✅ A **REST API** with full CRUD operations  
✅ **Interactive documentation** at `/docs`  
✅ **Automatic validation** of incoming data  

**In about 20 lines of code.**

---

## Next Steps

Now that you have a working app, learn more:

| Want to... | Read This |
|------------|-----------|
| Add more fields to your model | [Fields Reference](orm/fields.md) |
| Filter and search tasks | [Querying Data](orm/querying.md) |
| Add user authentication | [Authentication](api/authentication.md) |
| Protect your endpoints | [Permissions](api/permissions.md) |
| Add an admin dashboard | [Admin Guide](admin/index.md) |
| Use AI to query your data | [AI Mode](ai-mode/index.md) |

---

## Common Issues

### "Connection refused" when running migrate

**Problem:** PostgreSQL isn't running.

**Solution:**
```bash
# macOS
brew services start postgresql

# Linux  
sudo systemctl start postgresql

# Docker
docker start postgres
```

### "Database does not exist"

**Problem:** You need to create the database first.

**Solution:**
```bash
createdb taskmanager
```

### "Module not found" errors

**Problem:** Aksara isn't installed in your current environment.

**Solution:**
```bash
pip install aksara
# or if using a virtual environment, activate it first
source venv/bin/activate
pip install aksara
```

---

## Quick Reference Card

```bash
# Create a new project
aksara startproject <name>

# Create migrations
aksara makemigrations

# Apply migrations
aksara migrate

# Start development server
aksara run

# Start with specific port
aksara run --port 8080

# Start the admin panel
aksara admin
```

**API Endpoints (automatic with ModelViewSet):**

| Method | URL | Action |
|--------|-----|--------|
| GET | `/api/{resource}/` | List all |
| POST | `/api/{resource}/` | Create new |
| GET | `/api/{resource}/{id}/` | Get one |
| PUT | `/api/{resource}/{id}/` | Update |
| PATCH | `/api/{resource}/{id}/` | Partial update |
| DELETE | `/api/{resource}/{id}/` | Delete |
