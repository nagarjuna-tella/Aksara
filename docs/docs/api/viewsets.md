# ViewSets

Create full CRUD APIs with ModelViewSet.

---

## Overview

A ViewSet is a class-based view that provides CRUD operations for a model:

```python
from aksara.api import ModelViewSet
from myapp.models import Post

class PostViewSet(ModelViewSet):
    model = Post
```

This single class creates 6 endpoints automatically.

---

## Basic Configuration

### Required Attributes

```python
class PostViewSet(ModelViewSet):
    model = Post  # Required: the model to expose
```

### Optional Attributes

```python
class PostViewSet(ModelViewSet):
    model = Post
    
    # Serialization
    serializer_class = PostSerializer      # Custom serializer
    list_serializer_class = PostListSerializer  # For list action
    
    # Permissions
    permission_classes = [IsAuthenticated]
    
    # Pagination
    page_size = 20
    max_page_size = 100
    
    # Filtering
    filterset_fields = ["is_published", "author_id", "category"]
    search_fields = ["title", "content"]
    ordering_fields = ["created_at", "title"]
    ordering = ["-created_at"]
    
    # Query optimization
    select_related = ["author", "category"]
    prefetch_related = ["tags"]
```

---

## Generated Endpoints

### Default Actions

| Action | Method | Path | Handler |
|--------|--------|------|---------|
| List | GET | `/posts/` | `list()` |
| Create | POST | `/posts/` | `create()` |
| Retrieve | GET | `/posts/{id}/` | `retrieve()` |
| Update | PUT | `/posts/{id}/` | `update()` |
| Partial Update | PATCH | `/posts/{id}/` | `partial_update()` |
| Delete | DELETE | `/posts/{id}/` | `destroy()` |

### Disabling Actions

```python
class PostViewSet(ModelViewSet):
    model = Post
    
    # Only allow read operations
    allowed_actions = ["list", "retrieve"]
```

Or exclude specific actions:

```python
class PostViewSet(ModelViewSet):
    model = Post
    
    # Disable delete
    excluded_actions = ["destroy"]
```

---

## Customizing Actions

### Overriding List

```python
class PostViewSet(ModelViewSet):
    model = Post
    
    async def list(self, request):
        """Custom list with additional data."""
        queryset = self.get_queryset()
        
        # Apply filters
        queryset = self.filter_queryset(queryset)
        
        # Paginate
        page = self.paginate_queryset(queryset)
        
        # Serialize
        data = [self.serialize(obj) for obj in page]
        
        return self.get_paginated_response(data)
```

### Overriding Create

```python
class PostViewSet(ModelViewSet):
    model = Post
    
    async def create(self, request):
        """Create with automatic author assignment."""
        data = await self.get_request_data(request)
        
        # Auto-set author
        data["author_id"] = str(request.user.id)
        
        # Validate
        self.validate_data(data)
        
        # Create
        obj = await self.model.objects.create(**data)
        
        return self.serialize(obj), 201
```

### Overriding Retrieve

```python
class PostViewSet(ModelViewSet):
    model = Post
    
    async def retrieve(self, request, id: str):
        """Retrieve with view count increment."""
        obj = await self.get_object(id)
        
        # Increment view count
        obj.view_count += 1
        await obj.save()
        
        return self.serialize(obj)
```

### Overriding Update

```python
class PostViewSet(ModelViewSet):
    model = Post
    
    async def update(self, request, id: str):
        """Update with audit logging."""
        obj = await self.get_object(id)
        data = await self.get_request_data(request)
        
        # Log changes
        self.log_changes(obj, data)
        
        # Apply updates
        for key, value in data.items():
            setattr(obj, key, value)
        
        await obj.save()
        return self.serialize(obj)
```

### Overriding Destroy

```python
class PostViewSet(ModelViewSet):
    model = Post
    
    async def destroy(self, request, id: str):
        """Soft delete instead of hard delete."""
        obj = await self.get_object(id)
        
        # Soft delete
        obj.is_deleted = True
        obj.deleted_at = datetime.now()
        await obj.save()
        
        return None, 204
```

---

## QuerySet Customization

### get_queryset()

Control the base queryset for all operations:

```python
class PostViewSet(ModelViewSet):
    model = Post
    
    def get_queryset(self):
        """Base queryset with eager loading."""
        return (
            self.model.objects
            .select_related("author", "category")
            .prefetch_related("tags")
        )
```

### Dynamic QuerySet

```python
class PostViewSet(ModelViewSet):
    model = Post
    
    def get_queryset(self):
        """Filter based on user permissions."""
        qs = super().get_queryset()
        
        if self.request.user.is_anonymous:
            # Anonymous users see only published
            return qs.filter(is_published=True)
        
        if not self.request.user.is_staff:
            # Regular users see published + their own
            return qs.filter(
                Q(is_published=True) | Q(author=self.request.user)
            )
        
        # Staff see everything
        return qs
```

### Action-Specific QuerySet

```python
class PostViewSet(ModelViewSet):
    model = Post
    
    def get_queryset(self):
        """Different querysets per action."""
        qs = super().get_queryset()
        
        if self.action == "list":
            # List only shows published
            return qs.filter(is_published=True)
        
        # Other actions see all (with permission checks)
        return qs
```

---

## Serialization

### Default Serialization

By default, ModelViewSet serializes all model fields:

```python
# GET /posts/1/
{
    "id": "uuid-string",
    "title": "My Post",
    "content": "...",
    "author_id": "author-uuid",
    "created_at": "2024-01-15T10:30:00Z"
}
```

### Custom Serializer

```python
from aksara.api import ModelSerializer

class PostSerializer(ModelSerializer):
    model = Post
    fields = ["id", "title", "content", "author", "created_at"]
    read_only_fields = ["id", "created_at"]

class PostViewSet(ModelViewSet):
    model = Post
    serializer_class = PostSerializer
```

### Different Serializers per Action

```python
class PostListSerializer(ModelSerializer):
    model = Post
    fields = ["id", "title", "created_at"]  # Minimal for list

class PostDetailSerializer(ModelSerializer):
    model = Post
    fields = "__all__"  # Full detail

class PostViewSet(ModelViewSet):
    model = Post
    serializer_class = PostDetailSerializer
    list_serializer_class = PostListSerializer
    
    def get_serializer_class(self):
        """Dynamic serializer selection."""
        if self.action == "list":
            return self.list_serializer_class
        return self.serializer_class
```

---

## Filtering

### Simple Field Filtering

```python
class PostViewSet(ModelViewSet):
    model = Post
    filterset_fields = ["is_published", "author_id", "category_id"]

# Usage:
# GET /posts/?is_published=true
# GET /posts/?author_id=abc&category_id=xyz
```

### Custom Filter Method

```python
class PostViewSet(ModelViewSet):
    model = Post
    
    def filter_queryset(self, queryset):
        """Custom filtering logic."""
        qs = super().filter_queryset(queryset)
        
        # Date range filter
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        
        if date_from:
            qs = qs.filter(created_at__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__lte=date_to)
        
        return qs
```

### Search

```python
class PostViewSet(ModelViewSet):
    model = Post
    search_fields = ["title", "content"]

# GET /posts/?search=python
# Searches title and content for "python"
```

---

## Ordering

### Default Ordering

```python
class PostViewSet(ModelViewSet):
    model = Post
    ordering = ["-created_at"]  # Newest first by default
```

### Client-Controlled Ordering

```python
class PostViewSet(ModelViewSet):
    model = Post
    ordering_fields = ["created_at", "title", "view_count"]
    ordering = ["-created_at"]

# GET /posts/?ordering=title          # A-Z
# GET /posts/?ordering=-title         # Z-A
# GET /posts/?ordering=-view_count    # Most viewed first
```

---

## Pagination

### Configuration

```python
class PostViewSet(ModelViewSet):
    model = Post
    page_size = 20          # Default items per page
    max_page_size = 100     # Maximum allowed
```

### Response Format

```python
# GET /posts/?page=2&page_size=10
{
    "count": 156,
    "page": 2,
    "page_size": 10,
    "total_pages": 16,
    "next": "/posts/?page=3&page_size=10",
    "previous": "/posts/?page=1&page_size=10",
    "results": [...]
}
```

### Disable Pagination

```python
class PostViewSet(ModelViewSet):
    model = Post
    pagination_class = None  # No pagination
```

---

## Permissions

### ViewSet-Level Permissions

```python
from aksara.permissions import IsAuthenticated, IsAdminUser

class PostViewSet(ModelViewSet):
    model = Post
    permission_classes = [IsAuthenticated]
```

### Action-Specific Permissions

```python
class PostViewSet(ModelViewSet):
    model = Post
    permission_classes = [IsAuthenticated]
    
    def get_permissions(self):
        """Different permissions per action."""
        if self.action in ["list", "retrieve"]:
            # Anyone can read
            return []
        
        if self.action == "destroy":
            # Only admins can delete
            return [IsAdminUser()]
        
        # Default: authenticated
        return [IsAuthenticated()]
```

---

## Request Helpers

### get_object(id)

Get a single object with permission check:

```python
async def my_action(self, request, id: str):
    obj = await self.get_object(id)  # Raises 404 if not found
    ...
```

### get_request_data(request)

Parse and validate request body:

```python
async def create(self, request):
    data = await self.get_request_data(request)
    # data is validated dict
    ...
```

### serialize(obj)

Serialize an object using the configured serializer:

```python
obj = await self.get_object(id)
return self.serialize(obj)
```

---

## Complete Example

```python
from aksara.api import ModelViewSet, ModelSerializer, action
from aksara.permissions import IsAuthenticated, IsAdminUser
from myapp.models import Post, Comment


class PostListSerializer(ModelSerializer):
    model = Post
    fields = ["id", "title", "author_id", "is_published", "created_at"]


class PostDetailSerializer(ModelSerializer):
    model = Post
    fields = "__all__"
    read_only_fields = ["id", "created_at", "updated_at"]


class PostViewSet(ModelViewSet):
    """
    API for managing blog posts.
    
    Provides full CRUD operations plus custom actions for
    publishing and featuring posts.
    """
    model = Post
    serializer_class = PostDetailSerializer
    list_serializer_class = PostListSerializer
    
    # Filtering
    filterset_fields = ["is_published", "is_featured", "author_id"]
    search_fields = ["title", "content"]
    ordering_fields = ["created_at", "title", "view_count"]
    ordering = ["-created_at"]
    
    # Pagination
    page_size = 20
    max_page_size = 100
    
    # Query optimization
    select_related = ["author", "category"]
    prefetch_related = ["tags"]
    
    def get_queryset(self):
        """Filter queryset based on user."""
        qs = super().get_queryset()
        
        if self.request.user.is_anonymous:
            return qs.filter(is_published=True)
        
        if not self.request.user.is_staff:
            return qs.filter(
                Q(is_published=True) | Q(author=self.request.user)
            )
        
        return qs
    
    def get_permissions(self):
        """Action-specific permissions."""
        if self.action in ["list", "retrieve"]:
            return []  # Public
        if self.action == "destroy":
            return [IsAdminUser()]
        return [IsAuthenticated()]
    
    async def create(self, request):
        """Create post with author auto-assignment."""
        data = await self.get_request_data(request)
        data["author_id"] = str(request.user.id)
        
        obj = await self.model.objects.create(**data)
        return self.serialize(obj), 201
    
    @action(detail=True, methods=["POST"])
    async def publish(self, request, id: str):
        """Publish a draft post."""
        post = await self.get_object(id)
        post.is_published = True
        post.published_at = datetime.now()
        await post.save()
        return {"status": "published", "id": str(post.id)}
    
    @action(detail=True, methods=["POST"], permission_classes=[IsAdminUser])
    async def feature(self, request, id: str):
        """Mark post as featured (admin only)."""
        post = await self.get_object(id)
        post.is_featured = True
        await post.save()
        return {"status": "featured", "id": str(post.id)}
    
    @action(detail=False, methods=["GET"])
    async def popular(self, request):
        """Get most viewed posts."""
        posts = await self.get_queryset().filter(
            is_published=True
        ).order_by("-view_count")[:10]
        
        return [self.serialize(p) for p in posts]
```

---

## Related Documentation

- [Actions](actions.md) — Custom endpoints
- [Serializers](serializers.md) — Data transformation
- [Permissions](permissions.md) — Access control
- [Routing](routing.md) — URL configuration
