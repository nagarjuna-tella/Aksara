# Routing

Configure URLs and auto-register ViewSets.

---

## Overview

Vidyut provides multiple ways to register API routes:

- **include_viewset** — Register a single ViewSet
- **discover_viewsets** — Auto-discover ViewSets from modules
- **Manual registration** — Fine-grained control

```python
from vidyut.api import include_viewset
from myapp.viewsets import PostViewSet

routes = include_viewset(PostViewSet, prefix="/posts")
```

---

## include_viewset

Register a ViewSet with all its routes:

```python
from vidyut.api import include_viewset
from myapp.viewsets import PostViewSet

# Basic usage
routes = include_viewset(PostViewSet, prefix="/posts")

# With custom tags for OpenAPI
routes = include_viewset(
    PostViewSet,
    prefix="/posts",
    tags=["Blog Posts"],
)
```

### Generated Routes

For a ViewSet with default actions:

| Method | Path | Name | Action |
|--------|------|------|--------|
| GET | `/posts/` | `post-list` | list |
| POST | `/posts/` | `post-create` | create |
| GET | `/posts/{id}/` | `post-detail` | retrieve |
| PUT | `/posts/{id}/` | `post-update` | update |
| PATCH | `/posts/{id}/` | `post-partial-update` | partial_update |
| DELETE | `/posts/{id}/` | `post-delete` | destroy |

Plus custom actions:
| Method | Path | Name | Action |
|--------|------|------|--------|
| POST | `/posts/{id}/publish/` | `post-publish` | publish |
| GET | `/posts/featured/` | `post-featured` | featured |

---

## discover_viewsets

Auto-discover and register all ViewSets from a module:

```python
from vidyut.api import discover_viewsets

# Discover from a module
routes = discover_viewsets("myapp.viewsets")

# Or from the viewsets module in current app
routes = discover_viewsets("myapp")  # Looks in myapp.viewsets
```

### Discovery Rules

ViewSets are discovered if they:
1. Inherit from `ModelViewSet` or `ViewSet`
2. Are defined in the specified module
3. Have a `model` attribute (for ModelViewSet)

```python
# myapp/viewsets.py
from vidyut.api import ModelViewSet
from myapp.models import Post, Author

class PostViewSet(ModelViewSet):
    model = Post

class AuthorViewSet(ModelViewSet):
    model = Author

# Both will be discovered
```

### Custom Prefix

ViewSets use the model name (lowercased, pluralized) as the prefix by default:

- `PostViewSet` → `/posts/`
- `AuthorViewSet` → `/authors/`

Override with `url_prefix`:

```python
class PostViewSet(ModelViewSet):
    model = Post
    url_prefix = "/blog/posts"  # Custom prefix
```

---

## Including in App

### Single Router

```python
# main.py
from vidyut import Vidyut
from myapp.routes import routes

app = Vidyut()
app.include_router(routes)
```

### Multiple Routers

```python
# main.py
from vidyut import Vidyut
from vidyut.api import include_viewset
from users.viewsets import UserViewSet
from posts.viewsets import PostViewSet
from comments.viewsets import CommentViewSet

app = Vidyut()

# Add each router
app.include_router(include_viewset(UserViewSet, prefix="/users"))
app.include_router(include_viewset(PostViewSet, prefix="/posts"))
app.include_router(include_viewset(CommentViewSet, prefix="/comments"))
```

### With API Prefix

```python
from vidyut import Vidyut
from vidyut.api import include_viewset

app = Vidyut()

# All API routes under /api/v1/
api_v1 = include_viewset(PostViewSet, prefix="/posts")
app.include_router(api_v1, prefix="/api/v1")

# Results in: /api/v1/posts/
```

### Versioned APIs

```python
from vidyut import Vidyut
from vidyut.api import include_viewset
from myapp.viewsets.v1 import PostViewSetV1
from myapp.viewsets.v2 import PostViewSetV2

app = Vidyut()

# Version 1
v1_routes = include_viewset(PostViewSetV1, prefix="/posts")
app.include_router(v1_routes, prefix="/api/v1", tags=["v1"])

# Version 2
v2_routes = include_viewset(PostViewSetV2, prefix="/posts")
app.include_router(v2_routes, prefix="/api/v2", tags=["v2"])
```

---

## Route Names

Routes are automatically named based on the model and action:

```python
# Format: {model}-{action}
# post-list, post-create, post-detail, etc.
```

### Custom Route Names

```python
class PostViewSet(ModelViewSet):
    model = Post
    url_name_prefix = "blog"  # blog-list, blog-detail, etc.
```

### URL Reverse Lookup

```python
from starlette.routing import request

# In a view
url = request.url_for("post-detail", id=post_id)
# Returns: /posts/{post_id}/

# For actions
url = request.url_for("post-publish", id=post_id)
# Returns: /posts/{post_id}/publish/
```

---

## Manual Route Registration

For fine-grained control, bypass ViewSets entirely:

```python
from vidyut import Vidyut
from starlette.routing import Route

async def list_posts(request):
    posts = await Post.objects.all()
    return JSONResponse([...])

async def get_post(request):
    post_id = request.path_params["id"]
    post = await Post.objects.get(id=post_id)
    return JSONResponse({...})

app = Vidyut()
app.add_route("/posts/", list_posts, methods=["GET"])
app.add_route("/posts/{id}/", get_post, methods=["GET"])
```

### Using APIRouter

```python
from vidyut.api import APIRouter

router = APIRouter(prefix="/posts", tags=["Posts"])

@router.get("/")
async def list_posts():
    ...

@router.get("/{id}")
async def get_post(id: str):
    ...

@router.post("/")
async def create_post(request):
    ...

# Include in app
app.include_router(router)
```

---

## Route Ordering

Routes are registered in order. More specific routes should come before general ones:

```python
# Correct: specific route first
@router.get("/featured")  # Matches /posts/featured
async def featured():
    ...

@router.get("/{id}")  # Matches /posts/{any-id}
async def get_post(id: str):
    ...

# Wrong: {id} would match "featured" as an ID
```

ViewSets handle this automatically by registering actions before detail routes.

---

## OpenAPI Tags

Group endpoints in Swagger docs:

```python
# Single tag
routes = include_viewset(PostViewSet, prefix="/posts", tags=["Blog"])

# Multiple tags
routes = include_viewset(
    PostViewSet,
    prefix="/posts",
    tags=["Blog", "Content"],
)

# On ViewSet
class PostViewSet(ModelViewSet):
    model = Post
    tags = ["Blog Posts"]
```

---

## Nested Routes

For parent-child relationships:

```python
# posts/{post_id}/comments/
class CommentViewSet(ModelViewSet):
    model = Comment
    
    def get_queryset(self):
        post_id = self.kwargs.get("post_id")
        return Comment.objects.filter(post_id=post_id)

# Register nested
post_routes = include_viewset(PostViewSet, prefix="/posts")
comment_routes = include_viewset(CommentViewSet, prefix="/posts/{post_id}/comments")

app.include_router(post_routes)
app.include_router(comment_routes)
```

---

## Complete Example

```python
# routes.py
from vidyut.api import include_viewset, discover_viewsets, APIRouter
from myapp.viewsets import (
    PostViewSet,
    AuthorViewSet,
    CategoryViewSet,
    TagViewSet,
)

# Method 1: Individual ViewSets
post_routes = include_viewset(PostViewSet, prefix="/posts", tags=["Posts"])
author_routes = include_viewset(AuthorViewSet, prefix="/authors", tags=["Authors"])

# Method 2: Auto-discover
# content_routes = discover_viewsets("myapp.viewsets")

# Method 3: Custom router for misc endpoints
misc_router = APIRouter(prefix="/misc", tags=["Miscellaneous"])

@misc_router.get("/health")
async def health_check():
    return {"status": "healthy"}

@misc_router.get("/stats")
async def site_stats():
    return {
        "posts": await Post.objects.count(),
        "authors": await Author.objects.count(),
    }


# main.py
from vidyut import Vidyut
from myapp.routes import post_routes, author_routes, misc_router

app = Vidyut()

# Register all routes under /api/v1
app.include_router(post_routes, prefix="/api/v1")
app.include_router(author_routes, prefix="/api/v1")
app.include_router(misc_router, prefix="/api/v1")

# Or use discover_viewsets for automatic registration
# from vidyut.api import discover_viewsets
# app.include_router(discover_viewsets("myapp"), prefix="/api/v1")
```

### URLs Generated

```
GET    /api/v1/posts/                    post-list
POST   /api/v1/posts/                    post-create
GET    /api/v1/posts/{id}/               post-detail
PUT    /api/v1/posts/{id}/               post-update
PATCH  /api/v1/posts/{id}/               post-partial-update
DELETE /api/v1/posts/{id}/               post-delete
POST   /api/v1/posts/{id}/publish/       post-publish
GET    /api/v1/posts/featured/           post-featured

GET    /api/v1/authors/                  author-list
POST   /api/v1/authors/                  author-create
...

GET    /api/v1/misc/health               misc-health
GET    /api/v1/misc/stats                misc-stats
```

---

## Related Documentation

- [ViewSets](viewsets.md) — ViewSet configuration
- [Actions](actions.md) — Custom endpoints
- [Quick Start](../quickstart.md) — Getting started
