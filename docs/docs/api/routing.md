# Routing

Configure URLs and auto-register ViewSets.

---

## Overview

Aksara provides multiple ways to register API routes:

- **include_viewset** — Register a single ViewSet
- **discover_viewsets** — Auto-discover ViewSets from modules
- **Manual registration** — Fine-grained control

```python
from aksara import include_viewset
from myapp.views import PostViewSet

# Register a ViewSet with the app
include_viewset(app, PostViewSet)
```

---

## include_viewset

Register a ViewSet with all its routes:

```python
from aksara import include_viewset
from myapp.views import PostViewSet

# Basic usage — registers all CRUD routes at PostViewSet.prefix
include_viewset(app, PostViewSet)
```

`include_viewset` reads the `prefix` and `tags` from the ViewSet class:

```python
class PostViewSet(ModelViewSet):
    model = Post
    prefix = "/api/posts"  # Routes registered here
    tags = ["Blog Posts"]   # OpenAPI grouping
```

### Generated Routes

For a ViewSet with default actions:

| Method | Path | Name | Action |
|--------|------|------|--------|
| GET | `/posts/` | `post-list` | list |
| POST | `/posts/` | `post-create` | create |
| GET | `/posts/stream` | `post-stream` | stream |
| GET | `/posts/{id}/` | `post-detail` | retrieve |
| PATCH | `/posts/{id}/` | `post-partial-update` | partial_update |
| DELETE | `/posts/{id}/` | `post-delete` | destroy |

Plus custom actions:
| Method | Path | Name | Action |
|--------|------|------|--------|
| POST | `/posts/{id}/publish/` | `post-publish` | publish |
| GET | `/posts/featured/` | `post-featured` | featured |

The built-in stream route is registered before `/{pk}` paths so `/posts/stream` is never captured by the detail route.

---

## discover_viewsets

Auto-discover and register all ViewSets from a module:

```python
from aksara.api import discover_viewsets

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
from aksara.api import ModelViewSet
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

## Registering ViewSets

### Direct Registration

```python
# main.py
from aksara import Aksara, include_viewset
from myapp.views import PostViewSet

app = Aksara()
include_viewset(app, PostViewSet)
```

### Using urlpatterns (Recommended)

```python
# app/urls.py
from aksara import include_viewset
from app.views import UserViewSet, PostViewSet, CommentViewSet

urlpatterns = [
    UserViewSet,
    PostViewSet,
    CommentViewSet,
]

def register_routes(app):
    """Register all routes with the Aksara app."""
    for viewset in urlpatterns:
        include_viewset(app, viewset)
```

```python
# main.py
from aksara import Aksara
from app.urls import register_routes

app = Aksara()
register_routes(app)
```

### With API Prefix

ViewSets define their own prefix via the `prefix` class attribute:

```python
class PostViewSet(ModelViewSet):
    model = Post
    prefix = "/api/v1/posts"  # Full prefix on the ViewSet
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
from aksara import Aksara
from starlette.routing import Route

async def list_posts(request):
    posts = await Post.objects.all()
    return JSONResponse([...])

async def get_post(request):
    post_id = request.path_params["id"]
    post = await Post.objects.get(id=post_id)
    return JSONResponse({...})

app = Aksara()
app.add_route("/posts/", list_posts, methods=["GET"])
app.add_route("/posts/{id}/", get_post, methods=["GET"])
```

### Using FastAPI APIRouter

For endpoints that don't fit into a ViewSet, you can use FastAPI's `APIRouter` directly:

```python
from fastapi import APIRouter

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
# app/urls.py
from aksara import include_viewset
from fastapi import APIRouter
from myapp.views import (
    PostViewSet,
    AuthorViewSet,
    CategoryViewSet,
    TagViewSet,
)

# Method 1: urlpatterns list (recommended)
urlpatterns = [
    PostViewSet,
    AuthorViewSet,
    CategoryViewSet,
    TagViewSet,
]

# Method 2: Manual FastAPI router for misc endpoints
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


def register_routes(app):
    """Register all routes with the Aksara app."""
    for viewset in urlpatterns:
        include_viewset(app, viewset)
    app.include_router(misc_router)


# main.py
from aksara import Aksara
from app.urls import register_routes

app = Aksara()
register_routes(app)
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
