# ViewSets

Handle API requests for your models with minimal code.

---

## What is a ViewSet?

A **ViewSet** is a class that handles all API requests for a specific type of data. Instead of writing separate functions for list, create, update, and delete, you write one class that handles everything.

**Without ViewSets (manual approach):**
```python
# You'd have to write these separately:
async def list_tasks(request): ...
async def create_task(request): ...
async def get_task(request, id): ...
async def update_task(request, id): ...
async def delete_task(request, id): ...
```

**With ViewSets:**
```python
class TaskViewSet(ModelViewSet):
    model = Task
# Done! The default CRUD routes and stream endpoint are created automatically.
```

---

## Creating a ViewSet

### Basic ViewSet

```python
from aksara.api import ModelViewSet
from myapp.models import Task

class TaskViewSet(ModelViewSet):
    """API for managing tasks."""
    model = Task
```

**What you get:**

| Endpoint | Method | What It Does |
|----------|--------|--------------|
| `/tasks/` | GET | List all tasks |
| `/tasks/` | POST | Create a new task |
| `/tasks/stream/` | GET | Stream task lifecycle events via SSE |
| `/tasks/{id}/` | GET | Get one task |
| `/tasks/{id}/` | PATCH | Update some fields |
| `/tasks/{id}/` | DELETE | Delete a task |

### Real-Time Streams

Every `ModelViewSet` includes `GET /<prefix>/stream/` by default. The endpoint uses server-sent events and emits model lifecycle payloads for `INSERT`, `UPDATE`, and `DELETE` operations. Set `stream_enabled = False` on a ViewSet if you do not want the built-in stream route.

### With Options

```python
from aksara.api import ModelViewSet
from aksara.permissions import IsAuthenticated
from myapp.models import Task
from myapp.serializers import TaskSerializer

class TaskViewSet(ModelViewSet):
    """API for managing tasks."""
    
    # Required
    model = Task
    
    # Serialization (how data is converted)
    serializer_class = TaskSerializer
    
    # Security (who can access)
    permission_classes = [IsAuthenticated]
    
    # Pagination (how many items per page)
    page_size = 20
    
    # Filtering (which fields can be filtered)
    filterset_fields = ["completed", "priority"]
    
    # Searching (which fields are searchable)
    search_fields = ["title", "description"]
    
    # Ordering (default sort order)
    ordering = ["-created_at"]  # Newest first
```

---

## ViewSet Options Reference

### Data Options

| Option | What It Does | Example |
|--------|--------------|---------|
| `model` | Which model this ViewSet handles | `model = Task` |
| `queryset` | Custom base query | `queryset = Task.objects.filter(active=True)` |
| `serializer_class` | How to convert data | `serializer_class = TaskSerializer` |
| `list_serializer_class` | Different serializer for lists | `list_serializer_class = TaskListSerializer` |

### Security Options

| Option | What It Does | Example |
|--------|--------------|---------|
| `permission_classes` | Who can access | `[IsAuthenticated]` |
| `authentication_classes` | How to identify users | `[TokenAuthentication]` |

### Filtering Options

| Option | What It Does | Example |
|--------|--------------|---------|
| `filterset_fields` | Fields users can filter by | `["status", "priority"]` |
| `search_fields` | Fields users can search | `["title", "description"]` |
| `ordering_fields` | Fields users can sort by | `["created_at", "title"]` |
| `ordering` | Default sort order | `["-created_at"]` |

### Pagination Options

| Option | What It Does | Example |
|--------|--------------|---------|
| `page_size` | Items per page | `20` |
| `max_page_size` | Maximum items per page | `100` |

### Query Optimization

| Option | What It Does | Example |
|--------|--------------|---------|
| `select_related` | Load related objects in same query | `["author"]` |
| `prefetch_related` | Load many-to-many efficiently | `["tags"]` |

---

## Controlling Which Actions Are Available

### Only Allow Certain Actions

```python
class TaskViewSet(ModelViewSet):
    model = Task
    
    # Only allow reading, not creating/updating/deleting
    allowed_actions = ["list", "retrieve"]
```

**Available actions:**

| Action | Endpoint | Method |
|--------|----------|--------|
| `"list"` | `/tasks/` | GET |
| `"create"` | `/tasks/` | POST |
| `"retrieve"` | `/tasks/{id}/` | GET |
| `"update"` | `/tasks/{id}/` | PUT |
| `"partial_update"` | `/tasks/{id}/` | PATCH |
| `"destroy"` | `/tasks/{id}/` | DELETE |

### Exclude Certain Actions

```python
class TaskViewSet(ModelViewSet):
    model = Task
    
    # Allow everything except delete
    excluded_actions = ["destroy"]
```

---

## Customizing Actions

### Custom List Action

Control what gets returned when listing items.

```python
class TaskViewSet(ModelViewSet):
    model = Task
    
    async def list(self, request):
        """
        List tasks for the current user only.
        
        GET /tasks/
        """
        # Get tasks for this user only
        queryset = Task.objects.filter(user_id=request.user.id)
        
        # Apply any filters from the URL
        queryset = self.filter_queryset(queryset)
        
        # Paginate
        page = self.paginate_queryset(queryset)
        
        # Convert to JSON
        data = [self.serialize(task) for task in page]
        
        return self.get_paginated_response(data)
```

### Custom Create Action

Control how new items are created.

```python
class TaskViewSet(ModelViewSet):
    model = Task
    
    async def create(self, request):
        """
        Create a task and assign it to the current user.
        
        POST /tasks/
        """
        # Get data from request
        data = await self.get_request_data(request)
        
        # Automatically set the owner
        data["user_id"] = str(request.user.id)
        
        # Validate the data
        self.validate_data(data)
        
        # Create the task
        task = await Task.objects.create(**data)
        
        # Return the created task
        return self.serialize(task), 201  # 201 = Created
```

### Custom Retrieve Action

Control what happens when getting a single item.

```python
class TaskViewSet(ModelViewSet):
    model = Task
    
    async def retrieve(self, request, id: str):
        """
        Get a task and increment its view count.
        
        GET /tasks/{id}/
        """
        # Get the task
        task = await self.get_object(id)
        
        # Increment view count
        task.view_count += 1
        await task.save()
        
        # Return the task
        return self.serialize(task)
```

### Custom Update Action

Control how items are updated.

```python
class TaskViewSet(ModelViewSet):
    model = Task
    
    async def update(self, request, id: str):
        """
        Update a task, but only if user owns it.
        
        PUT /tasks/{id}/
        """
        task = await self.get_object(id)
        
        # Check ownership
        if task.user_id != request.user.id:
            raise PermissionDenied("You can only edit your own tasks")
        
        # Get and validate data
        data = await self.get_request_data(request)
        self.validate_data(data)
        
        # Update fields
        for key, value in data.items():
            setattr(task, key, value)
        
        await task.save()
        return self.serialize(task)
```

### Custom Delete Action

Control how items are deleted.

```python
class TaskViewSet(ModelViewSet):
    model = Task
    
    async def destroy(self, request, id: str):
        """
        Soft-delete a task instead of actually removing it.
        
        DELETE /tasks/{id}/
        """
        task = await self.get_object(id)
        
        # Soft delete (mark as deleted instead of removing)
        task.deleted = True
        task.deleted_at = datetime.now()
        await task.save()
        
        return None, 204  # 204 = No Content
```

---

## Custom Actions

Add endpoints beyond CRUD using the `@action` decorator.

### Detail Actions (One Item)

Operate on a specific item.

```python
from aksara.api import ModelViewSet, action

class TaskViewSet(ModelViewSet):
    model = Task
    
    @action(detail=True, methods=["POST"])
    async def complete(self, request, id: str):
        """
        Mark a task as complete.
        
        POST /tasks/{id}/complete/
        """
        task = await self.get_object(id)
        task.completed = True
        task.completed_at = datetime.now()
        await task.save()
        return {"status": "completed", "completed_at": task.completed_at}
    
    @action(detail=True, methods=["POST"])
    async def assign(self, request, id: str):
        """
        Assign this task to someone.
        
        POST /tasks/{id}/assign/
        Body: {"user_id": "abc123"}
        """
        task = await self.get_object(id)
        data = await self.get_request_data(request)
        
        task.assigned_to_id = data["user_id"]
        await task.save()
        
        return {"assigned_to": task.assigned_to_id}
```

### Collection Actions (All Items)

Operate on the collection as a whole.

```python
class TaskViewSet(ModelViewSet):
    model = Task
    
    @action(detail=False, methods=["POST"])
    async def complete_all(self, request):
        """
        Mark all tasks as complete.
        
        POST /tasks/complete_all/
        """
        count = await Task.objects.filter(
            user_id=request.user.id,
            completed=False
        ).update(completed=True)
        
        return {"completed_count": count}
    
    @action(detail=False, methods=["GET"])
    async def stats(self, request):
        """
        Get task statistics.
        
        GET /tasks/stats/
        """
        total = await Task.objects.filter(user_id=request.user.id).count()
        completed = await Task.objects.filter(
            user_id=request.user.id,
            completed=True
        ).count()
        
        return {
            "total": total,
            "completed": completed,
            "remaining": total - completed,
            "completion_rate": completed / total if total > 0 else 0
        }
```

### Action Options

```python
@action(
    detail=True,           # True = one item, False = collection
    methods=["POST"],      # HTTP methods allowed
    url_path="my-action",  # Custom URL (default: action name)
    url_name="task-action", # Name for URL reversal
    permission_classes=[IsAdminUser],  # Override ViewSet permissions
)
async def my_action(self, request, id: str):
    ...
```

---

## Filtering

Allow users to filter results with query parameters.

### Basic Filtering

```python
class TaskViewSet(ModelViewSet):
    model = Task
    filterset_fields = ["completed", "priority", "category"]
```

**Users can now filter:**

```
GET /tasks/?completed=true
GET /tasks/?priority=high
GET /tasks/?completed=true&priority=high
```

### Search

```python
class TaskViewSet(ModelViewSet):
    model = Task
    search_fields = ["title", "description"]
```

**Users can search:**

```
GET /tasks/?search=meeting
GET /tasks/?search=important deadline
```

### Ordering

```python
class TaskViewSet(ModelViewSet):
    model = Task
    ordering_fields = ["created_at", "title", "priority"]
    ordering = ["-created_at"]  # Default: newest first
```

**Users can sort:**

```
GET /tasks/?ordering=title           # A to Z
GET /tasks/?ordering=-title          # Z to A
GET /tasks/?ordering=-created_at     # Newest first
GET /tasks/?ordering=priority,-created_at  # By priority, then date
```

---

## Pagination

Control how many items are returned per request.

```python
class TaskViewSet(ModelViewSet):
    model = Task
    page_size = 20        # Items per page
    max_page_size = 100   # Maximum items user can request
```

**Response format:**

```json
{
  "count": 150,
  "next": "http://api.example.com/tasks/?page=2",
  "previous": null,
  "results": [
    {"id": "...", "title": "Task 1", ...},
    {"id": "...", "title": "Task 2", ...}
  ]
}
```

**Users can navigate:**

```
GET /tasks/?page=1
GET /tasks/?page=2
GET /tasks/?page=3&page_size=50
```

---

## Query Optimization

Avoid N+1 query problems when loading related data.

### The Problem

```python
# ❌ Bad: This makes 1 query for tasks + 1 query per task for the author
tasks = await Task.objects.all()
for task in tasks:
    print(task.author.name)  # Another database call!
```

### The Solution

```python
class TaskViewSet(ModelViewSet):
    model = Task
    
    # For ForeignKey relationships (one related object)
    select_related = ["author", "category"]
    
    # For ManyToMany relationships (multiple related objects)
    prefetch_related = ["tags", "comments"]
```

**Now one query fetches everything needed.**

---

## Helper Methods

Methods available inside your ViewSet:

| Method | What It Does |
|--------|--------------|
| `get_queryset()` | Get the base queryset |
| `get_object(id)` | Get one object by ID |
| `filter_queryset(qs)` | Apply filters to queryset |
| `paginate_queryset(qs)` | Apply pagination |
| `serialize(obj)` | Convert object to dict |
| `get_request_data(request)` | Get data from request body |
| `validate_data(data)` | Validate data with serializer |
| `check_permissions(request)` | Check if request is allowed |

---

## Complete Example

```python
from datetime import datetime
from aksara.api import ModelViewSet, action
from aksara.permissions import IsAuthenticated
from myapp.models import Task
from myapp.serializers import TaskSerializer, TaskListSerializer

class TaskViewSet(ModelViewSet):
    """
    API endpoint for managing tasks.
    
    Provides CRUD operations plus custom actions for
    task completion and statistics.
    """
    model = Task
    serializer_class = TaskSerializer
    list_serializer_class = TaskListSerializer
    permission_classes = [IsAuthenticated]
    
    # Filtering
    filterset_fields = ["completed", "priority", "category"]
    search_fields = ["title", "description"]
    ordering_fields = ["created_at", "due_date", "priority"]
    ordering = ["-created_at"]
    
    # Pagination
    page_size = 20
    max_page_size = 100
    
    # Optimization
    select_related = ["author", "category"]
    prefetch_related = ["tags"]
    
    def get_queryset(self):
        """Only show tasks belonging to the current user."""
        return Task.objects.filter(user_id=self.request.user.id)
    
    async def create(self, request):
        """Create a task for the current user."""
        data = await self.get_request_data(request)
        data["user_id"] = str(request.user.id)
        self.validate_data(data)
        task = await Task.objects.create(**data)
        return self.serialize(task), 201
    
    @action(detail=True, methods=["POST"])
    async def complete(self, request, id: str):
        """Mark a task as complete."""
        task = await self.get_object(id)
        task.completed = True
        task.completed_at = datetime.now()
        await task.save()
        return {"status": "completed"}
    
    @action(detail=False, methods=["GET"])
    async def stats(self, request):
        """Get task statistics for the current user."""
        qs = self.get_queryset()
        total = await qs.count()
        completed = await qs.filter(completed=True).count()
        
        return {
            "total": total,
            "completed": completed,
            "remaining": total - completed
        }
```

---

## Related Documentation

- [Serializers](serializers.md) — Data validation and transformation
- [Actions](actions.md) — Custom endpoints in detail
- [Permissions](permissions.md) — Access control
- [Routing](routing.md) — URL configuration
