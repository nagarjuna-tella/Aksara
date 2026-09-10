# AI Tools

AI-callable functions for interacting with your Aksara application.

---

## Overview

Aksara exposes a set of tools that AI models can call:

| Category | Tools |
|----------|-------|
| **Data** | `create_record`, `update_record`, `delete_record`, `query_records` |
| **Schema** | `list_models`, `describe_model`, `suggest_migration` |
| **Code** | `generate_model`, `generate_viewset`, `generate_test` |
| **System** | `run_migration`, `run_tests`, `get_settings` |

---

## Data Tools

### query_records

Query database records using filters.

```python
{
    "name": "query_records",
    "parameters": {
        "model": "User",
        "filters": {"is_active": True},
        "order_by": "-created_at",
        "limit": 10
    }
}
```

**Returns:**
```json
{
    "count": 10,
    "records": [
        {"id": "uuid-1", "email": "user1@example.com"},
        {"id": "uuid-2", "email": "user2@example.com"}
    ]
}
```

### create_record

Create a new database record.

```python
{
    "name": "create_record",
    "parameters": {
        "model": "User",
        "data": {
            "email": "new@example.com",
            "name": "New User"
        }
    }
}
```

**Returns:**
```json
{
    "success": true,
    "record": {"id": "uuid-new", "email": "new@example.com"}
}
```

### update_record

Update an existing record.

```python
{
    "name": "update_record",
    "parameters": {
        "model": "User",
        "id": "uuid-123",
        "data": {"is_active": False}
    }
}
```

### delete_record

Delete a record.

```python
{
    "name": "delete_record",
    "parameters": {
        "model": "User",
        "id": "uuid-123"
    }
}
```

**Safety:** Requires confirmation unless `AI_REQUIRE_CONFIRMATION=False`.

---

## Schema Tools

### list_models

Get all registered models.

```python
{
    "name": "list_models",
    "parameters": {}
}
```

**Returns:**
```python
{
    "models": [
        {
            "name": "User",
            "app": "myapp",
            "table": "users",
            "fields_count": 5
        },
        {
            "name": "Post",
            "app": "myapp",
            "table": "posts",
            "fields_count": 8
        }
    ]
}
```

### describe_model

Get detailed model information.

```python
{
    "name": "describe_model",
    "parameters": {
        "model": "User"
    }
}
```

**Returns:**
```python
{
    "name": "User",
    "table": "users",
    "fields": [
        {"name": "id", "type": "UUID", "primary_key": True},
        {"name": "email", "type": "Email", "unique": True},
        {"name": "name", "type": "String", "max_length": 100},
        {"name": "is_active", "type": "Boolean", "default": True},
        {"name": "created_at", "type": "DateTime", "auto_now_add": True}
    ],
    "relations": [
        {"name": "posts", "type": "reverse_fk", "related_model": "Post"}
    ],
    "indexes": [
        {"fields": ["email"], "unique": True}
    ]
}
```

### suggest_migration

Suggest a migration for a schema change.

```python
{
    "name": "suggest_migration",
    "parameters": {
        "description": "Add phone_number field to User"
    }
}
```

**Returns:**
```python
{
    "migration_code": "...",
    "operations": [
        "AddField(User, phone_number, fields.String(max_length=20, null=True))"
    ],
    "preview": "ALTER TABLE users ADD COLUMN phone_number VARCHAR(20);"
}
```

---

## Code Generation Tools

### generate_model

Generate a model class.

```python
{
    "name": "generate_model",
    "parameters": {
        "name": "BlogPost",
        "description": "Blog post with title, content, author FK, tags M2M"
    }
}
```

**Returns:**
```python
{
    "code": '''
from aksara import Model, fields

class BlogPost(Model):
    """A blog post."""
    
    title = fields.String(max_length=200)
    content = fields.Text()
    author = fields.ForeignKey("User", on_delete=fields.CASCADE)
    tags = fields.ManyToMany("Tag")
    
    class Meta:
        table_name = "blog_posts"
''',
    "file_path": "models.py"
}
```

### generate_viewset

Generate a ViewSet class.

```python
{
    "name": "generate_viewset",
    "parameters": {
        "model": "BlogPost",
        "features": ["pagination", "search", "filter_by_author"]
    }
}
```

**Returns:**
```python
{
    "code": '''
from aksara.api import ModelViewSet, action
from .models import BlogPost
from .serializers import BlogPostSerializer

class BlogPostViewSet(ModelViewSet):
    """API endpoints for blog posts."""
    
    model = BlogPost
    serializer_class = BlogPostSerializer
    pagination_class = PageNumberPagination
    search_fields = ["title", "content"]
    filterset_fields = ["author_id"]
''',
    "file_path": "viewsets.py"
}
```

### generate_test

Generate test cases.

```python
{
    "name": "generate_test",
    "parameters": {
        "model": "BlogPost",
        "test_types": ["crud", "validation", "permissions"]
    }
}
```

**Returns:**
```python
{
    "code": '''
import pytest
from aksara.testing import AksaraTestCase
from .models import BlogPost

class TestBlogPost(AksaraTestCase):
    async def test_create_blog_post(self):
        post = await BlogPost.objects.create(
            title="Test Post",
            content="Test content",
            author=self.user,
        )
        assert post.id is not None
        assert post.title == "Test Post"
    
    async def test_title_required(self):
        with pytest.raises(ValidationError):
            await BlogPost.objects.create(content="No title")
''',
    "file_path": "tests/test_blog_post.py"
}
```

---

## System Tools

### run_migration

Execute database migrations.

```python
{
    "name": "run_migration",
    "parameters": {
        "app": "myapp",
        "migration": "0005_add_phone_number"  # Optional: specific migration
    }
}
```

**Returns:**
```python
{
    "success": True,
    "applied": ["0005_add_phone_number"],
    "message": "Applied 1 migration"
}
```

### run_tests

Run test suite.

```python
{
    "name": "run_tests",
    "parameters": {
        "path": "tests/test_blog_post.py",  # Optional
        "verbose": True
    }
}
```

**Returns:**
```python
{
    "success": True,
    "passed": 15,
    "failed": 0,
    "errors": 0,
    "output": "..."
}
```

### get_settings

Get application settings.

```python
{
    "name": "get_settings",
    "parameters": {
        "keys": ["DATABASE_URL", "DEBUG"]  # Optional: specific keys
    }
}
```

**Returns:**
```python
{
    "settings": {
        "DATABASE_URL": "postgresql://...",
        "DEBUG": True
    }
}
```

**Safety:** Sensitive settings are masked.

---

## Using Tools with LLMs

### OpenAI Function Calling

**Conceptual or legacy pseudocode (not an installed-package API):**

```text title="Conceptual or legacy pseudocode"
from aksara.ai.tools import get_openai_tools

tools = get_openai_tools()
# Returns OpenAI-formatted function definitions

response = await openai.chat.completions.create(
    model="gpt-4",
    messages=messages,
    tools=tools,
)
```

### Anthropic Tool Use

**Conceptual or legacy pseudocode (not an installed-package API):**

```text title="Conceptual or legacy pseudocode"
from aksara.ai.tools import get_anthropic_tools

tools = get_anthropic_tools()
# Returns Anthropic-formatted tool definitions

response = await anthropic.messages.create(
    model="claude-3-opus-20240229",
    messages=messages,
    tools=tools,
)
```

### Executing Tool Calls

**Conceptual or legacy pseudocode (not an installed-package API):**

```text title="Conceptual or legacy pseudocode"
from aksara.ai.tools import execute_tool

# Parse tool call from LLM response
tool_call = response.tool_calls[0]

# Execute it
result = await execute_tool(
    name=tool_call.function.name,
    parameters=json.loads(tool_call.function.arguments),
)
```

---

## Custom Tools

### Register Custom Tools

**Conceptual or legacy pseudocode (not an installed-package API):**

```text title="Conceptual or legacy pseudocode"
from aksara.ai.tools import register_tool, Tool

@register_tool
class SendNotificationTool(Tool):
    """Send a notification to a user."""
    
    name = "send_notification"
    
    parameters = {
        "user_id": {"type": "string", "description": "User ID"},
        "message": {"type": "string", "description": "Notification message"},
    }
    
    async def execute(self, user_id: str, message: str):
        user = await User.objects.get(id=user_id)
        await send_push_notification(user, message)
        return {"success": True}
```

### Tool Categories

Organize tools by category:

```python
@register_tool(category="notifications")
class SendEmailTool(Tool):
    ...

@register_tool(category="notifications")  
class SendSMSTool(Tool):
    ...
```

### Tool Permissions

Restrict tool access:

```python
@register_tool(permissions=["admin"])
class DeleteAllDataTool(Tool):
    """Dangerous tool requiring admin permission."""
    ...
```

---

## Tool Configuration

**Conceptual legacy configuration (the runtime does not read an `AKSARA` dictionary):**

```text title="Conceptual legacy configuration"
# settings.py
AKSARA = {
    "AI_TOOLS": {
        # Enable/disable built-in tools
        "data_tools": True,
        "schema_tools": True,
        "code_tools": True,
        "system_tools": True,
        
        # Tool-specific settings
        "query_records_max_limit": 100,
        "delete_record_require_confirmation": True,
        "run_migration_allowed": False,  # Disable in production
    },
}
```

---

## Related Documentation

- [AI Mode Overview](index.md)
- [Context Engine](context-engine.md)
- [Agent Runtime](agent-runtime.md)
- [Safety](safety.md)
