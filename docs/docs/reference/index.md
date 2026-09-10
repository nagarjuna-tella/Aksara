# Reference

Complete API reference for Aksara — a quick lookup for all classes, methods, and options.

---

## What is This Section?

This is a **reference guide**, not a tutorial. Use it when you need to look up:

- What options a setting accepts
- What methods are available on a class
- What parameters a function takes

**New to Aksara?** Start with the [Getting Started Guide](../getting-started/index.md) or [Quickstart](../quickstart.md) instead.

---

## Reference Sections

| Reference | What It Covers |
|-----------|----------------|
| [Settings Reference](settings-reference.md) | All configuration options for your app |
| [API Reference](api-reference.md) | ViewSets, serializers, permissions, actions |
| [ORM Reference](orm-reference.md) | Models, fields, queries, managers |
| [CLI Reference](cli-reference.md) | All command-line commands |
| [Exceptions](exceptions.md) | Error types and how to handle them |
| [Types](types.md) | Type definitions for type hints |

---

## Quick Reference

### Settings

```python
# settings.py
from aksara import configure

configure(
    database_url="postgresql://localhost/myapp",
    debug=True,
    installed_apps=["myapp"],
)
```

👉 [Full Settings Reference](settings-reference.md)

---

### Models

```python
from aksara import Model, fields

class User(Model):
    email = fields.Email(unique=True)
    name = fields.String(max_length=100)
    is_active = fields.Boolean(default=True)
```

👉 [ORM Reference](orm-reference.md)

---

### ViewSets

```python
from aksara.api import ModelViewSet

class UserViewSet(ModelViewSet):
    model = User
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
```

👉 [API Reference](api-reference.md)

---

### CLI Commands

```bash
# Create a project
aksara startproject myproject

# Create database migrations
aksara makemigrations

# Apply migrations
aksara migrate

# Start the development server
aksara dev
```

👉 [CLI Reference](cli-reference.md)

---

## Version Information

Current version: **0.6.1**

```python
import aksara
print(aksara.__version__)  # 0.6.1
```

Check your installed version:

```bash
aksara --version
```

---

## How to Use This Reference

### Finding What You Need

1. **Know the setting name?** → [Settings Reference](settings-reference.md)
2. **Working with models?** → [ORM Reference](orm-reference.md)
3. **Building an API?** → [API Reference](api-reference.md)
4. **Running commands?** → [CLI Reference](cli-reference.md)
5. **Handling errors?** → [Exceptions](exceptions.md)

### Understanding the Format

Each reference page uses this format:

```text
# Class or Function Name
description of what it does

# Parameters/Options
parameter_name: type = default  # description

# Example
actual_code_example()
```

---

## Related Documentation

| Section | For |
|---------|-----|
| [Getting Started](../getting-started/index.md) | Learning Aksara from scratch |
| [Tutorials](../tutorials/index.md) | Building complete applications |
| [ORM Guide](../orm/index.md) | Understanding the ORM in depth |
| [API Guide](../api/index.md) | Understanding the API layer |
| [Changelog](../changelog.md) | What's new in each version |
