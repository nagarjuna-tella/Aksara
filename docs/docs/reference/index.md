# Reference

Complete API reference for Vidyut.

---

## Overview

| Reference | Description |
|-----------|-------------|
| [Settings Reference](settings-reference.md) | All configuration options |
| [API Reference](api-reference.md) | ViewSets, serializers, permissions |
| [ORM Reference](orm-reference.md) | Models, fields, queries |
| [CLI Reference](cli-reference.md) | All CLI commands |
| [Exceptions](exceptions.md) | Error types |
| [Types](types.md) | Type definitions |

---

## Quick Links

### Settings

```python
VIDYUT = {
    "DEBUG": True,
    "DATABASE_URL": "postgresql://localhost/myapp",
    "SECRET_KEY": "...",
    "INSTALLED_APPS": ["myapp"],
}
```

→ [Full Settings Reference](settings-reference.md)

### Models

```python
from vidyut import Model, fields

class User(Model):
    email = fields.EmailField(unique=True)
    name = fields.StringField(max_length=100)
```

→ [ORM Reference](orm-reference.md)

### ViewSets

```python
from vidyut.api import ModelViewSet

class UserViewSet(ModelViewSet):
    model = User
    serializer_class = UserSerializer
```

→ [API Reference](api-reference.md)

### CLI

```bash
vidyut startproject myproject
vidyut makemigrations
vidyut migrate
vidyut runserver
```

→ [CLI Reference](cli-reference.md)

---

## Version Information

Current version: **0.4.9**

```python
import vidyut
print(vidyut.__version__)  # 0.4.9
```

---

## Related Documentation

- [Getting Started](../getting-started/index.md)
- [Tutorials](../tutorials/index.md)
- [Changelog](../changelog.md)
