# Serializers

Convert data between Python objects and JSON, and validate incoming requests.

---

## What is a Serializer?

A **Serializer** is like a translator between two languages:

- **Python** ↔ **JSON**

When your API receives data, the serializer:

1. **Validates** — Is this data correct?
2. **Converts** — Turn JSON into Python objects

When your API sends data, the serializer:

1. **Selects** — Which fields should be included?
2. **Converts** — Turn Python objects into JSON

```
                         SERIALIZER
                             │
    ┌──────────────┐         │         ┌──────────────┐
    │   JSON       │ ───────►│────────►│   Python     │
    │   Request    │         │         │   Object     │
    │              │         │         │              │
    │ {"title":    │  Input  │ Output  │ task.title   │
    │  "Buy milk"} │         │         │ = "Buy milk" │
    └──────────────┘         │         └──────────────┘
                             │
```

---

## Basic Usage

### Creating a Serializer

```python
from aksara.api import ModelSerializer
from myapp.models import Task

class TaskSerializer(ModelSerializer):
    """
    Converts Task objects to/from JSON.
    """
    class Meta:
        model = Task
        fields = ["id", "title", "description", "completed", "created_at"]
```

### Using a Serializer

```python
# Serialize: Python → JSON
task = await Task.objects.get(id=task_id)
serializer = TaskSerializer(task)
json_data = serializer.data
# {"id": "abc123", "title": "Buy milk", "completed": false, ...}

# Deserialize: JSON → Python
data = {"title": "Buy eggs", "description": "Get a dozen"}
serializer = TaskSerializer(data=data)
serializer.is_valid(raise_exception=True)  # Validates
task = await serializer.save()  # Creates the object
```

---

## Specifying Fields

### Include Specific Fields

```python
class TaskSerializer(ModelSerializer):
    class Meta:
        model = Task
        fields = ["id", "title", "completed"]  # Only these fields
```

**Result:**
```json
{"id": "abc123", "title": "Buy milk", "completed": false}
```

### Include All Fields

```python
class TaskSerializer(ModelSerializer):
    class Meta:
        model = Task
        fields = "__all__"  # Every field on the model
```

### Exclude Fields

```python
class TaskSerializer(ModelSerializer):
    class Meta:
        model = Task
        exclude = ["internal_notes", "deleted_at"]  # Everything except these
```

---

## Field Access Control

### Read-Only Fields

**What it means:** Users can see these fields but can't change them.

```python
class TaskSerializer(ModelSerializer):
    class Meta:
        model = Task
        fields = ["id", "title", "description", "completed", "created_at"]
        read_only_fields = ["id", "created_at"]  # Can't be set by user
```

**Use case:** IDs, timestamps, calculated values.

### Write-Only Fields

**What it means:** Users can send these fields but won't see them in responses.

```python
class UserSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "password", "name"]
        write_only_fields = ["password"]  # Hidden in responses
```

**Use case:** Passwords, secrets, internal codes.

---

## Validation

### Automatic Validation

Serializers automatically validate:

| Check | What It Does |
|-------|--------------|
| Required fields | Ensures all required fields are present |
| Data types | Ensures correct types (string, number, etc.) |
| Max length | Ensures strings don't exceed limits |
| Valid values | Ensures enum values are valid |

```python
# This will fail validation:
data = {"title": ""}  # Title is required and can't be empty
serializer = TaskSerializer(data=data)
serializer.is_valid()  # Returns False
print(serializer.errors)  # {"title": ["This field is required."]}
```

### Field-Level Validation

Add custom validation for a specific field.

```python
class TaskSerializer(ModelSerializer):
    class Meta:
        model = Task
        fields = ["id", "title", "description"]
    
    def validate_title(self, value):
        """
        Custom validation for the title field.
        
        This runs when someone tries to set the title.
        """
        # Check minimum length
        if len(value) < 3:
            raise ValidationError("Title must be at least 3 characters")
        
        # Check for banned words
        banned_words = ["spam", "test123"]
        if any(word in value.lower() for word in banned_words):
            raise ValidationError("Title contains banned words")
        
        return value  # Return the value (possibly modified)
```

### Object-Level Validation

Validate multiple fields together.

```python
class TaskSerializer(ModelSerializer):
    class Meta:
        model = Task
        fields = ["id", "title", "due_date", "reminder_date"]
    
    def validate(self, data):
        """
        Validate the entire object.
        
        Use this when validation depends on multiple fields.
        """
        due_date = data.get("due_date")
        reminder_date = data.get("reminder_date")
        
        if reminder_date and due_date and reminder_date > due_date:
            raise ValidationError({
                "reminder_date": "Reminder must be before the due date"
            })
        
        return data
```

---

## Custom Fields

### Computed Fields

Add fields that don't exist on the model.

**Conceptual or legacy pseudocode (not an installed-package API):**

```text title="Conceptual or legacy pseudocode"
from aksara.api import ModelSerializer, SerializerMethodField

class TaskSerializer(ModelSerializer):
    # Field computed from a method
    summary = SerializerMethodField()
    is_overdue = SerializerMethodField()
    
    class Meta:
        model = Task
        fields = ["id", "title", "description", "summary", "is_overdue", "due_date"]
    
    def get_summary(self, obj):
        """
        Create a short summary from the description.
        
        Method name must be `get_<field_name>`.
        """
        if not obj.description:
            return ""
        return obj.description[:100] + "..." if len(obj.description) > 100 else obj.description
    
    def get_is_overdue(self, obj):
        """Check if task is past due date."""
        if not obj.due_date:
            return False
        return obj.due_date < datetime.now() and not obj.completed
```

**Result:**
```json
{
  "id": "abc123",
  "title": "Buy milk",
  "description": "Get 2% milk from the store on Main Street...",
  "summary": "Get 2% milk from the store on Main Street...",
  "is_overdue": true,
  "due_date": "2024-01-01T10:00:00Z"
}
```

### Renamed Fields

Expose a field with a different name.

**Conceptual or legacy pseudocode (not an installed-package API):**

```text title="Conceptual or legacy pseudocode"
from aksara.api import ModelSerializer, Field

class TaskSerializer(ModelSerializer):
    # Expose "created_at" as "createdAt" for JavaScript
    createdAt = Field(source="created_at", read_only=True)
    
    class Meta:
        model = Task
        fields = ["id", "title", "createdAt"]
```

---

## Nested Serializers

Include related objects in your response.

### Basic Nesting

```python
class AuthorSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "name", "email"]

class PostSerializer(ModelSerializer):
    # Nest the author object
    author = AuthorSerializer(read_only=True)
    
    class Meta:
        model = Post
        fields = ["id", "title", "content", "author"]
```

**Result:**
```json
{
  "id": "post-123",
  "title": "Hello World",
  "content": "This is my first post...",
  "author": {
    "id": "user-456",
    "name": "Alice",
    "email": "alice@example.com"
  }
}
```

### Many Nested Objects

For lists of related objects (like tags on a post).

```python
class TagSerializer(ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name"]

class PostSerializer(ModelSerializer):
    # many=True for lists
    tags = TagSerializer(many=True, read_only=True)
    
    class Meta:
        model = Post
        fields = ["id", "title", "tags"]
```

**Result:**
```json
{
  "id": "post-123",
  "title": "Python Tips",
  "tags": [
    {"id": "tag-1", "name": "python"},
    {"id": "tag-2", "name": "programming"}
  ]
}
```

---

## Different Serializers for Different Actions

Use simple serializers for lists, detailed for single items.

```python
# Simple serializer for list view (less data = faster)
class TaskListSerializer(ModelSerializer):
    class Meta:
        model = Task
        fields = ["id", "title", "completed"]

# Detailed serializer for detail view (all the info)
class TaskDetailSerializer(ModelSerializer):
    author = UserSerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    
    class Meta:
        model = Task
        fields = ["id", "title", "description", "completed", 
                  "author", "tags", "created_at", "updated_at"]
```

**Use in ViewSet:**
```python
class TaskViewSet(ModelViewSet):
    model = Task
    serializer_class = TaskDetailSerializer      # For single item
    list_serializer_class = TaskListSerializer   # For list view
```

---

## Context

Pass extra information to the serializer.

```python
# In ViewSet
class TaskViewSet(ModelViewSet):
    model = Task
    
    def get_serializer_context(self):
        """Add the current user to serializer context."""
        return {
            "user": self.request.user,
            "request": self.request,
        }

# In Serializer
class TaskSerializer(ModelSerializer):
    is_owner = SerializerMethodField()
    
    class Meta:
        model = Task
        fields = ["id", "title", "is_owner"]
    
    def get_is_owner(self, obj):
        """Check if current user owns this task."""
        user = self.context.get("user")
        return user and obj.user_id == user.id
```

---

## Creating and Updating

### Creating Objects

```python
# Data from request
data = {"title": "New Task", "description": "Do something"}

# Validate
serializer = TaskSerializer(data=data)
serializer.is_valid(raise_exception=True)

# Create
task = await serializer.save()
```

### Updating Objects

```python
# Get existing object
task = await Task.objects.get(id=task_id)

# Partial update (PATCH) - only provided fields
data = {"completed": True}
serializer = TaskSerializer(task, data=data, partial=True)
serializer.is_valid(raise_exception=True)
updated_task = await serializer.save()

# Full update (PUT) - all fields required
data = {"title": "Updated Task", "description": "New description", "completed": True}
serializer = TaskSerializer(task, data=data)
serializer.is_valid(raise_exception=True)
updated_task = await serializer.save()
```

### Custom Create/Update Logic

```python
class TaskSerializer(ModelSerializer):
    class Meta:
        model = Task
        fields = ["id", "title", "description"]
    
    async def create(self, validated_data):
        """Custom create logic."""
        # Add extra data
        validated_data["user_id"] = self.context["user"].id
        
        # Create the object
        return await Task.objects.create(**validated_data)
    
    async def update(self, instance, validated_data):
        """Custom update logic."""
        # Track what changed
        old_title = instance.title
        
        # Update fields
        for key, value in validated_data.items():
            setattr(instance, key, value)
        
        await instance.save()
        
        # Log if title changed
        if old_title != instance.title:
            print(f"Task renamed: {old_title} → {instance.title}")
        
        return instance
```

---

## Quick Reference

### Meta Options

| Option | What It Does | Example |
|--------|--------------|---------|
| `model` | The model to serialize | `model = Task` |
| `fields` | Which fields to include | `["id", "title"]` or `"__all__"` |
| `exclude` | Which fields to exclude | `["internal_notes"]` |
| `read_only_fields` | Can read, can't write | `["id", "created_at"]` |
| `write_only_fields` | Can write, can't read | `["password"]` |

### Field Types

| Type | Use Case |
|------|----------|
| `Field()` | Basic field with options |
| `SerializerMethodField()` | Computed from a method |
| `PrimaryKeyRelatedField()` | Return ID of related object |
| `StringRelatedField()` | Return str() of related object |
| `NestedSerializer()` | Full nested object |

### Validation Methods

| Method | When It Runs |
|--------|--------------|
| `validate_<field>(value)` | For one field |
| `validate(data)` | For entire object |

---

## Complete Example

**Conceptual or legacy pseudocode (not an installed-package API):**

```text title="Conceptual or legacy pseudocode"
from datetime import datetime
from aksara.api import ModelSerializer, SerializerMethodField
from aksara.api.validators import ValidationError
from myapp.models import Task, User, Tag

class UserBriefSerializer(ModelSerializer):
    """Minimal user info for nesting."""
    class Meta:
        model = User
        fields = ["id", "name"]

class TagSerializer(ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name"]

class TaskSerializer(ModelSerializer):
    """
    Full task serializer with related objects and computed fields.
    """
    # Nested objects
    assigned_to = UserBriefSerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    
    # Computed fields
    is_overdue = SerializerMethodField()
    summary = SerializerMethodField()
    
    class Meta:
        model = Task
        fields = [
            "id", "title", "description", "summary",
            "completed", "is_overdue",
            "due_date", "assigned_to", "tags",
            "created_at", "updated_at"
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
    
    def get_is_overdue(self, obj):
        if not obj.due_date or obj.completed:
            return False
        return obj.due_date < datetime.now()
    
    def get_summary(self, obj):
        if not obj.description:
            return ""
        return obj.description[:100] + "..." if len(obj.description) > 100 else obj.description
    
    def validate_title(self, value):
        if len(value) < 3:
            raise ValidationError("Title must be at least 3 characters")
        return value
    
    def validate(self, data):
        due_date = data.get("due_date")
        if due_date and due_date < datetime.now():
            raise ValidationError({"due_date": "Due date cannot be in the past"})
        return data
```

---

## Related Documentation

- [ViewSets](viewsets.md) — Use serializers in API endpoints
- [Validation](../advanced/validation.md) — Advanced validation techniques
- [Fields](../orm/fields.md) — Model field types
