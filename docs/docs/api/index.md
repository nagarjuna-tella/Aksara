# API Layer

Build REST APIs rapidly with Vidyut's ModelViewSet and action system.

---

## Overview

Vidyut's API layer provides Django REST Framework-like patterns optimized for FastAPI:

- **ModelViewSet** — Full CRUD with minimal code
- **Actions** — Custom endpoints beyond CRUD
- **Serializers** — Automatic validation and transformation
- **Permissions** — Flexible access control
- **Routing** — Auto-registration and discovery

```python
from vidyut.api import ModelViewSet, action

class PostViewSet(ModelViewSet):
    model = Post
    
    @action(detail=True, methods=["POST"])
    async def publish(self, request, id: str):
        post = await self.get_object(id)
        post.is_published = True
        await post.save()
        return {"status": "published"}
```

---

## Quick Start

### 1. Define a ViewSet

```python
# myapp/viewsets.py
from vidyut.api import ModelViewSet
from myapp.models import Post

class PostViewSet(ModelViewSet):
    model = Post
```

This automatically creates:

| Method | Path | Action |
|--------|------|--------|
| GET | `/posts/` | List all posts |
| POST | `/posts/` | Create a post |
| GET | `/posts/{id}/` | Retrieve a post |
| PUT | `/posts/{id}/` | Update a post |
| PATCH | `/posts/{id}/` | Partial update |
| DELETE | `/posts/{id}/` | Delete a post |

### 2. Register Routes

```python
# myapp/routes.py
from vidyut.api import include_viewset
from myapp.viewsets import PostViewSet

routes = include_viewset(PostViewSet, prefix="/posts")
```

### 3. Include in App

```python
# main.py
from vidyut import Vidyut
from myapp.routes import routes

app = Vidyut()
app.include_router(routes)
```

---

## Key Features

### Type Safety

Automatic request/response validation:

```python
# POST /posts/ with invalid data
# Request: {"title": "Hi"} (content missing)
# Response: 422 Validation Error
```

### OpenAPI Docs

Auto-generated Swagger documentation at `/docs`:

```python
# ViewSet docstrings become API descriptions
class PostViewSet(ModelViewSet):
    """
    API for managing blog posts.
    
    Supports creating, reading, updating, and deleting posts.
    """
    model = Post
```

### Query Parameters

Built-in filtering and pagination:

```python
GET /posts/?is_published=true&author_id=abc&page=1&limit=20
```

---

## Section Contents

<div class="grid cards" markdown>

-   :material-view-dashboard: **[ViewSets](viewsets.md)**
    
    ModelViewSet configuration and customization

-   :material-gesture-tap: **[Actions](actions.md)**
    
    Custom endpoints with the @action decorator

-   :material-code-json: **[Serializers](serializers.md)**
    
    Data validation and transformation

-   :material-routes: **[Routing](routing.md)**
    
    URL configuration and auto-discovery

-   :material-shield-lock: **[Permissions](permissions.md)**
    
    Access control for endpoints

-   :material-key: **[Authentication](authentication.md)**
    
    User authentication methods

-   :material-speedometer: **[Throttling](throttling.md)**
    
    Rate limiting (future)

</div>

---

## Example: Complete API

```python
# models.py
from vidyut import Model, fields, CASCADE

class Author(Model):
    name = fields.String(max_length=100)
    email = fields.Email(unique=True)

class Post(Model):
    title = fields.String(max_length=200)
    content = fields.Text()
    is_published = fields.Boolean(default=False)
    author = fields.ForeignKey(Author, on_delete=CASCADE)
    created_at = fields.DateTime(auto_now_add=True)

# viewsets.py
from vidyut.api import ModelViewSet, action
from vidyut.permissions import IsAuthenticated, IsAdminUser

class AuthorViewSet(ModelViewSet):
    model = Author
    permission_classes = [IsAuthenticated]

class PostViewSet(ModelViewSet):
    model = Post
    
    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            # Non-staff only see published posts
            qs = qs.filter(is_published=True)
        return qs
    
    @action(detail=True, methods=["POST"])
    async def publish(self, request, id: str):
        """Publish a draft post."""
        post = await self.get_object(id)
        post.is_published = True
        await post.save()
        return {"id": str(post.id), "is_published": True}
    
    @action(detail=False, methods=["GET"])
    async def featured(self, request):
        """Get featured posts."""
        posts = await self.get_queryset().filter(is_featured=True)[:5]
        return [self.serialize(p) for p in posts]

# routes.py
from vidyut.api import include_viewset

author_routes = include_viewset(AuthorViewSet, prefix="/authors")
post_routes = include_viewset(PostViewSet, prefix="/posts")

# main.py
from vidyut import Vidyut

app = Vidyut()
app.include_router(author_routes)
app.include_router(post_routes)
```

---

## Related Documentation

- [ORM](../orm/index.md) — Model definitions
- [Permissions](permissions.md) — Access control
- [Authentication](authentication.md) — User auth
