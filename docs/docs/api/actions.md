# Actions

Add custom endpoints to ViewSets with the `@action` decorator.

---

## Overview

While ModelViewSet provides standard CRUD operations, the `@action` decorator lets you add custom endpoints:

```python
from aksara.api import ModelViewSet, action

class PostViewSet(ModelViewSet):
    model = Post
    
    @action(detail=True, methods=["POST"])
    async def publish(self, request, id: str):
        post = await self.get_object(id)
        post.is_published = True
        await post.save()
        return {"status": "published"}
```

This creates: `POST /posts/{id}/publish/`

---

## Action Types

### Detail Actions

Operate on a single object (`detail=True`):

```python
@action(detail=True, methods=["POST"])
async def publish(self, request, id: str):
    """POST /posts/{id}/publish/"""
    post = await self.get_object(id)
    ...
```

### List Actions

Operate on the collection (`detail=False`):

```python
@action(detail=False, methods=["GET"])
async def featured(self, request):
    """GET /posts/featured/"""
    posts = await self.get_queryset().filter(is_featured=True)
    ...
```

---

## @action Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `detail` | `bool` | Required | True for single object, False for collection |
| `methods` | `list[str]` | `["GET"]` | Allowed HTTP methods |
| `url_path` | `str` | Method name | Custom URL segment |
| `url_name` | `str` | Method name | Route name for reverse lookups |
| `permission_classes` | `list` | ViewSet's | Override permissions |
| `ai_exposed` | `bool` | `True` | Expose this endpoint to AI tools and MCP exports |

---

## AI & MCP Integration

Any action decorated with `@action` is automatically discovered by the `AiToolRegistry` and exposed to AI agents, provided `ai_exposed` is true (which is the default). 

This means that if you enable the Model Context Protocol (MCP) in your app, your
custom actions are automatically serialized as MCP tools that clients discover
and invoke over Streamable HTTP at `/mcp/`. The permission-filtered inspection
catalog remains available at `/ai/tools/mcp`. Tool descriptions and JSON input
schemas use the action's docstring and type hints.

```python
@action(detail=True, methods=["POST"], ai_exposed=True)
async def submit_for_review(self, request, id: str):
    """
    Submit a draft for editorial review.
    This description becomes the MCP tool description.
    """
    ...
```

If an endpoint is internal or sensitive, you can hide it from AI agents and MCP exports by setting `ai_exposed=False`:

```python
@action(detail=False, methods=["GET"], ai_exposed=False)
async def internal_metrics(self, request):
    """This will not be exported to MCP."""
    ...
```

---

## HTTP Methods

### Single Method

```python
@action(detail=True, methods=["POST"])
async def publish(self, request, id: str):
    ...
```

### Multiple Methods

```python
@action(detail=True, methods=["GET", "POST"])
async def comments(self, request, id: str):
    if request.method == "GET":
        # List comments
        ...
    else:
        # Create comment
        ...
```

### Method-Specific Handlers

```python
@action(detail=True, methods=["GET", "POST"])
async def comments(self, request, id: str):
    ...

@comments.mapping.get
async def list_comments(self, request, id: str):
    """Handle GET /posts/{id}/comments/"""
    post = await self.get_object(id)
    comments = await post.comments.all()
    return [self.serialize_comment(c) for c in comments]

@comments.mapping.post
async def add_comment(self, request, id: str):
    """Handle POST /posts/{id}/comments/"""
    post = await self.get_object(id)
    data = await self.get_request_data(request)
    comment = await Comment.objects.create(post=post, **data)
    return self.serialize_comment(comment), 201
```

---

## Custom URL Paths

### url_path

Customize the URL segment:

```python
@action(detail=True, methods=["POST"], url_path="mark-published")
async def publish(self, request, id: str):
    """POST /posts/{id}/mark-published/"""
    ...
```

### url_name

Set the route name for reverse lookups:

```python
@action(detail=True, methods=["GET"], url_name="post-stats")
async def statistics(self, request, id: str):
    ...

# Usage
url = app.url_path_for("post-stats", id=post_id)
```

---

## Permissions

### Override ViewSet Permissions

```python
from aksara.permissions import IsAdminUser

class PostViewSet(ModelViewSet):
    model = Post
    permission_classes = [IsAuthenticated]  # Default
    
    @action(detail=True, methods=["POST"], permission_classes=[IsAdminUser])
    async def feature(self, request, id: str):
        """Only admins can feature posts."""
        ...
```

### Action-Specific Permission Check

```python
@action(detail=True, methods=["POST"])
async def edit(self, request, id: str):
    post = await self.get_object(id)
    
    # Custom permission check
    if post.author_id != request.user.id and not request.user.is_staff:
        raise PermissionDenied("You can only edit your own posts")
    
    ...
```

---

## Response Formats

### Dict Response

```python
@action(detail=True, methods=["POST"])
async def publish(self, request, id: str):
    post = await self.get_object(id)
    post.is_published = True
    await post.save()
    
    return {"status": "published", "id": str(post.id)}
```

### List Response

```python
@action(detail=False, methods=["GET"])
async def featured(self, request):
    posts = await self.get_queryset().filter(is_featured=True)[:5]
    return [self.serialize(p) for p in posts]
```

### Status Code with Response

```python
@action(detail=True, methods=["POST"])
async def archive(self, request, id: str):
    post = await self.get_object(id)
    post.is_archived = True
    await post.save()
    
    return {"status": "archived"}, 200  # Explicit status

@action(detail=False, methods=["POST"])
async def bulk_create(self, request):
    data = await self.get_request_data(request)
    posts = [await self.model.objects.create(**d) for d in data]
    
    return [self.serialize(p) for p in posts], 201
```

### No Content Response

```python
@action(detail=True, methods=["DELETE"])
async def clear_comments(self, request, id: str):
    post = await self.get_object(id)
    await post.comments.all().delete()
    
    return None, 204  # No Content
```

---

## Common Patterns

### Toggle Actions

```python
@action(detail=True, methods=["POST"])
async def toggle_published(self, request, id: str):
    """Toggle publish state."""
    post = await self.get_object(id)
    post.is_published = not post.is_published
    await post.save()
    
    return {
        "id": str(post.id),
        "is_published": post.is_published,
    }
```

### State Transitions

```python
@action(detail=True, methods=["POST"])
async def submit_for_review(self, request, id: str):
    """Submit draft for editorial review."""
    post = await self.get_object(id)
    
    if post.status != "draft":
        raise ValidationError("Only drafts can be submitted")
    
    post.status = "pending_review"
    post.submitted_at = datetime.now()
    await post.save()
    
    # Notify editors
    await notify_editors(post)
    
    return {"status": post.status}

@action(detail=True, methods=["POST"], permission_classes=[IsEditor])
async def approve(self, request, id: str):
    """Approve and publish post."""
    post = await self.get_object(id)
    
    if post.status != "pending_review":
        raise ValidationError("Only pending posts can be approved")
    
    post.status = "published"
    post.is_published = True
    post.published_at = datetime.now()
    post.approved_by_id = str(request.user.id)
    await post.save()
    
    return self.serialize(post)
```

### Bulk Operations

```python
@action(detail=False, methods=["POST"])
async def bulk_publish(self, request):
    """Publish multiple posts at once."""
    data = await self.get_request_data(request)
    post_ids = data.get("ids", [])
    
    if not post_ids:
        raise ValidationError("No post IDs provided")
    
    count = await (
        self.get_queryset()
        .filter(id__in=post_ids)
        .update(is_published=True, published_at=datetime.now())
    )
    
    return {"published": count}

@action(detail=False, methods=["DELETE"])
async def bulk_delete(self, request):
    """Delete multiple posts."""
    data = await self.get_request_data(request)
    post_ids = data.get("ids", [])
    
    count = await (
        self.get_queryset()
        .filter(id__in=post_ids)
        .delete()
    )
    
    return {"deleted": count}
```

### Related Objects

```python
@action(detail=True, methods=["GET"])
async def comments(self, request, id: str):
    """Get all comments for a post."""
    post = await self.get_object(id)
    comments = await post.comments.all()
    
    return [{
        "id": str(c.id),
        "content": c.content,
        "author_id": str(c.author_id),
        "created_at": c.created_at.isoformat(),
    } for c in comments]

@action(detail=True, methods=["GET", "POST"])
async def tags(self, request, id: str):
    """Get or add tags for a post."""
    post = await self.get_object(id)
    
    if request.method == "GET":
        tags = await post.tags.all()
        return [{"id": str(t.id), "name": t.name} for t in tags]
    
    # POST: Add tags
    data = await self.get_request_data(request)
    tag_ids = data.get("tag_ids", [])
    tags = await Tag.objects.filter(id__in=tag_ids).all()
    await post.tags.add(*tags)
    
    return {"added": len(tags)}
```

### Statistics and Aggregations

```python
@action(detail=True, methods=["GET"])
async def statistics(self, request, id: str):
    """Get post statistics."""
    post = await self.get_object(id)
    
    comments_count = await post.comments.count()
    likes_count = await post.likes.count()
    
    return {
        "id": str(post.id),
        "view_count": post.view_count,
        "comments_count": comments_count,
        "likes_count": likes_count,
        "shares_count": post.shares_count,
    }

@action(detail=False, methods=["GET"])
async def summary(self, request):
    """Get collection summary statistics."""
    qs = self.get_queryset()
    
    total = await qs.count()
    published = await qs.filter(is_published=True).count()
    featured = await qs.filter(is_featured=True).count()
    
    return {
        "total": total,
        "published": published,
        "drafts": total - published,
        "featured": featured,
    }
```

### Current User Actions

```python
@action(detail=False, methods=["GET"])
async def mine(self, request):
    """Get current user's posts."""
    posts = await self.get_queryset().filter(
        author_id=str(request.user.id)
    ).all()
    
    return [self.serialize(p) for p in posts]

@action(detail=True, methods=["POST"])
async def like(self, request, id: str):
    """Like a post."""
    post = await self.get_object(id)
    
    # Check if already liked
    existing = await Like.objects.filter(
        post=post,
        user_id=str(request.user.id),
    ).first()
    
    if existing:
        return {"status": "already_liked"}
    
    await Like.objects.create(
        post=post,
        user_id=str(request.user.id),
    )
    
    return {"status": "liked"}
```

---

## Documentation

Actions automatically appear in OpenAPI docs:

```python
@action(detail=True, methods=["POST"])
async def publish(self, request, id: str):
    """
    Publish a draft post.
    
    Marks the post as published and sets the publication date.
    Only the post author or admin users can publish.
    
    Returns:
        status: "published" on success
    """
    ...
```

---

## Complete Example

```python
from aksara.api import ModelViewSet, action
from aksara.permissions import IsAuthenticated, IsAdminUser
from myapp.models import Post, Comment, Like


class PostViewSet(ModelViewSet):
    """Blog post API with custom actions."""
    
    model = Post
    permission_classes = [IsAuthenticated]
    
    # === Detail Actions ===
    
    @action(detail=True, methods=["POST"])
    async def publish(self, request, id: str):
        """Publish a draft post."""
        post = await self.get_object(id)
        
        if post.author_id != str(request.user.id):
            raise PermissionDenied("You can only publish your own posts")
        
        post.is_published = True
        post.published_at = datetime.now()
        await post.save()
        
        return {"status": "published", "id": str(post.id)}
    
    @action(detail=True, methods=["POST"])
    async def unpublish(self, request, id: str):
        """Unpublish a post (make draft)."""
        post = await self.get_object(id)
        post.is_published = False
        await post.save()
        
        return {"status": "unpublished", "id": str(post.id)}
    
    @action(detail=True, methods=["POST"], permission_classes=[IsAdminUser])
    async def feature(self, request, id: str):
        """Mark post as featured (admin only)."""
        post = await self.get_object(id)
        post.is_featured = True
        await post.save()
        
        return {"status": "featured", "id": str(post.id)}
    
    @action(detail=True, methods=["GET"])
    async def stats(self, request, id: str):
        """Get post statistics."""
        post = await self.get_object(id)
        
        return {
            "id": str(post.id),
            "views": post.view_count,
            "comments": await post.comments.count(),
            "likes": await post.likes.count(),
        }
    
    @action(detail=True, methods=["GET", "POST"])
    async def comments(self, request, id: str):
        """List or add comments."""
        post = await self.get_object(id)
        
        if request.method == "GET":
            comments = await post.comments.order_by("-created_at").all()
            return [{
                "id": str(c.id),
                "content": c.content,
                "author_id": str(c.author_id),
                "created_at": c.created_at.isoformat(),
            } for c in comments]
        
        # POST: Add comment
        data = await self.get_request_data(request)
        comment = await Comment.objects.create(
            post=post,
            content=data["content"],
            author_id=str(request.user.id),
        )
        
        return {
            "id": str(comment.id),
            "content": comment.content,
        }, 201
    
    @action(detail=True, methods=["POST"])
    async def like(self, request, id: str):
        """Like or unlike a post."""
        post = await self.get_object(id)
        user_id = str(request.user.id)
        
        existing = await Like.objects.filter(
            post=post, user_id=user_id
        ).first()
        
        if existing:
            await existing.delete()
            return {"status": "unliked"}
        
        await Like.objects.create(post=post, user_id=user_id)
        return {"status": "liked"}
    
    # === List Actions ===
    
    @action(detail=False, methods=["GET"])
    async def mine(self, request):
        """Get current user's posts."""
        posts = await self.get_queryset().filter(
            author_id=str(request.user.id)
        ).order_by("-created_at").all()
        
        return [self.serialize(p) for p in posts]
    
    @action(detail=False, methods=["GET"])
    async def featured(self, request):
        """Get featured posts."""
        posts = await self.get_queryset().filter(
            is_featured=True,
            is_published=True,
        ).order_by("-published_at")[:10]
        
        return [self.serialize(p) for p in posts]
    
    @action(detail=False, methods=["GET"])
    async def popular(self, request):
        """Get most viewed posts."""
        posts = await self.get_queryset().filter(
            is_published=True,
        ).order_by("-view_count")[:10]
        
        return [self.serialize(p) for p in posts]
    
    @action(detail=False, methods=["POST"], permission_classes=[IsAdminUser])
    async def bulk_publish(self, request):
        """Bulk publish posts (admin only)."""
        data = await self.get_request_data(request)
        ids = data.get("ids", [])
        
        count = await self.get_queryset().filter(
            id__in=ids,
            is_published=False,
        ).update(is_published=True, published_at=datetime.now())
        
        return {"published": count}
```

---

## Related Documentation

- [ViewSets](viewsets.md) — ViewSet configuration
- [Permissions](permissions.md) — Access control
- [Routing](routing.md) — URL configuration
