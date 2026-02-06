# API Layer

Build REST APIs that let other applications (websites, mobile apps, AI agents) interact with your data.

---

## What is an API?

An **API** (Application Programming Interface) is how different programs talk to each other. When a mobile app shows you your tasks, it's calling an API to get that data.

```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│   Mobile App    │  ────►  │    Your API     │  ────►  │    Database     │
│                 │         │   (Aksara)      │         │                 │
│  "Show my       │  ◄────  │                 │  ◄────  │   [Tasks...]    │
│   tasks"        │         │                 │         │                 │
└─────────────────┘         └─────────────────┘         └─────────────────┘
     Request                   Process                      Fetch
```

**A REST API uses HTTP requests:**

| HTTP Method | What It Does | Example |
|-------------|--------------|---------|
| `GET` | Read data | Get all tasks |
| `POST` | Create data | Create a new task |
| `PUT` | Replace data | Update a whole task |
| `PATCH` | Modify data | Update part of a task |
| `DELETE` | Remove data | Delete a task |

---

## What Aksara Gives You

Aksara creates a complete REST API automatically. You define your data (Models), and Aksara creates the endpoints.

```python
from aksara.api import ModelViewSet
from myapp.models import Task

class TaskViewSet(ModelViewSet):
    model = Task
```

**That's 4 lines. You get 6 endpoints:**

| Method | URL | What It Does |
|--------|-----|--------------|
| `GET` | `/tasks/` | List all tasks |
| `POST` | `/tasks/` | Create a task |
| `GET` | `/tasks/{id}/` | Get one task |
| `PUT` | `/tasks/{id}/` | Update a task |
| `PATCH` | `/tasks/{id}/` | Partial update |
| `DELETE` | `/tasks/{id}/` | Delete a task |

---

## Key Concepts

### ViewSets

**What they are:** Classes that handle API requests for a model.

**What they do:** When someone calls `GET /tasks/`, the ViewSet decides what to return.

```python
class TaskViewSet(ModelViewSet):
    model = Task  # Which model to expose
    
    # Optional: customize which fields are returned
    serializer_class = TaskSerializer
    
    # Optional: who can access this?
    permission_classes = [IsAuthenticated]
```

👉 **Learn more:** [ViewSets](viewsets.md)

---

### Serializers

**What they are:** Classes that convert between Python objects and JSON.

**What they do:** 

- When receiving data: Validate it and convert JSON to Python
- When sending data: Convert Python to JSON

```python
class TaskSerializer(ModelSerializer):
    class Meta:
        model = Task
        fields = ["id", "title", "completed"]
        read_only_fields = ["id"]  # Can't be set by user
```

**The serializer automatically:**

- Validates required fields are present
- Checks data types (string, number, boolean)
- Rejects extra fields
- Formats the response

👉 **Learn more:** [Serializers](serializers.md)

---

### Permissions

**What they are:** Rules about who can do what.

**What they do:** Check each request and allow or deny access.

```python
from aksara.permissions import IsAuthenticated, IsAdminUser

class TaskViewSet(ModelViewSet):
    model = Task
    
    # Only logged-in users can access
    permission_classes = [IsAuthenticated]
```

**Common permission classes:**

| Permission | Who Can Access |
|------------|----------------|
| `AllowAny` | Everyone (even anonymous) |
| `IsAuthenticated` | Only logged-in users |
| `IsAdminUser` | Only admin users |
| `IsOwner` | Only the object's owner |

👉 **Learn more:** [Permissions](permissions.md)

---

### Actions

**What they are:** Custom endpoints beyond basic CRUD.

**When to use:** When you need operations that aren't create/read/update/delete.

```python
from aksara.api import ModelViewSet, action

class TaskViewSet(ModelViewSet):
    model = Task
    
    @action(detail=True, methods=["POST"])
    async def complete(self, request, id: str):
        """
        Mark a task as complete.
        
        URL: POST /tasks/{id}/complete/
        """
        task = await self.get_object(id)
        task.completed = True
        await task.save()
        return {"status": "completed"}
```

**Action options:**

| Option | Meaning |
|--------|---------|
| `detail=True` | Operates on one item (`/tasks/{id}/complete/`) |
| `detail=False` | Operates on the collection (`/tasks/complete_all/`) |
| `methods=["POST"]` | Which HTTP methods to accept |

👉 **Learn more:** [Actions](actions.md)

---

### Routers

**What they are:** Tools that connect URLs to ViewSets.

**What they do:** Automatically create all the URL patterns.

```python
from aksara.api import Router
from myapp.views import TaskViewSet, ProjectViewSet

router = Router()
router.register("tasks", TaskViewSet)      # → /api/tasks/
router.register("projects", ProjectViewSet)  # → /api/projects/
```

👉 **Learn more:** [Routing](routing.md)

---

## Quick Example

Here's a complete API for a Task model:

```python
# models.py
from aksara import Model, fields

class Task(Model):
    title = fields.String(max_length=200)
    description = fields.Text(nullable=True)
    completed = fields.Boolean(default=False)
    created_at = fields.DateTime(auto_now_add=True)
```

```python
# serializers.py
from aksara.api import ModelSerializer
from myapp.models import Task

class TaskSerializer(ModelSerializer):
    class Meta:
        model = Task
        fields = ["id", "title", "description", "completed", "created_at"]
        read_only_fields = ["id", "created_at"]
```

```python
# views.py
from aksara.api import ModelViewSet, action
from aksara.permissions import IsAuthenticated
from myapp.models import Task
from myapp.serializers import TaskSerializer

class TaskViewSet(ModelViewSet):
    model = Task
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]
    
    # Filter options
    filterset_fields = ["completed"]
    search_fields = ["title", "description"]
    ordering = ["-created_at"]
    
    @action(detail=True, methods=["POST"])
    async def toggle(self, request, id: str):
        """Toggle task completion status."""
        task = await self.get_object(id)
        task.completed = not task.completed
        await task.save()
        return {"completed": task.completed}
```

```python
# urls.py
from aksara.api import Router
from myapp.views import TaskViewSet

router = Router()
router.register("tasks", TaskViewSet)
```

**This creates:**

| Endpoint | What It Does |
|----------|--------------|
| `GET /api/tasks/` | List all tasks |
| `GET /api/tasks/?completed=true` | List completed tasks |
| `GET /api/tasks/?search=groceries` | Search tasks |
| `POST /api/tasks/` | Create a task |
| `GET /api/tasks/{id}/` | Get one task |
| `PUT /api/tasks/{id}/` | Update a task |
| `DELETE /api/tasks/{id}/` | Delete a task |
| `POST /api/tasks/{id}/toggle/` | Toggle completion |

---

## Testing Your API

### Interactive Documentation

Aksara automatically generates interactive docs at `/docs`:

```
http://localhost:8000/docs
```

You can try out every endpoint directly in the browser!

### Using curl

```bash
# List tasks
curl http://localhost:8000/api/tasks/

# Create a task
curl -X POST http://localhost:8000/api/tasks/ \
  -H "Content-Type: application/json" \
  -d '{"title": "Buy milk"}'

# Get one task
curl http://localhost:8000/api/tasks/abc123/

# Update a task
curl -X PUT http://localhost:8000/api/tasks/abc123/ \
  -H "Content-Type: application/json" \
  -d '{"title": "Buy milk", "completed": true}'

# Delete a task
curl -X DELETE http://localhost:8000/api/tasks/abc123/
```

### Using Python

```python
import httpx

# Create a client
client = httpx.Client(base_url="http://localhost:8000")

# List tasks
tasks = client.get("/api/tasks/").json()

# Create a task
new_task = client.post(
    "/api/tasks/",
    json={"title": "Learn Aksara"}
).json()

# Update a task
client.put(
    f"/api/tasks/{new_task['id']}/",
    json={"title": "Learn Aksara", "completed": True}
)
```

---

## What's Next?

| Guide | What You'll Learn |
|-------|-------------------|
| [ViewSets](viewsets.md) | All ViewSet options and customization |
| [Serializers](serializers.md) | Data validation and transformation |
| [Actions](actions.md) | Custom endpoints beyond CRUD |
| [Permissions](permissions.md) | Access control and security |
| [Authentication](authentication.md) | User login and tokens |
| [Routing](routing.md) | URL configuration |
| [Throttling](throttling.md) | Rate limiting requests |
