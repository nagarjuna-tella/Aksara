# Blog Pattern

A complete blog backend with posts, comments, moderation, and publish workflow.

## Quick Start

```bash
aksara startproject myblog --template blog
cd myblog
pip install -e ".[dev]"
aksara makemigrations --app app.models
aksara migrate
aksara run main:app --reload
```

## Models

### Post

```python
class Post(Model):
    """Blog post with publish workflow."""
    
    title = fields.String(max_length=200, ai_description="Post title")
    slug = fields.String(
        max_length=200,
        unique=True,
        ai_description="URL-friendly slug",
    )
    content = fields.Text(nullable=True, ai_description="Post body (Markdown)")
    tags = fields.JSON(nullable=True, ai_description="List of tags")
    is_published = fields.Boolean(default=False, ai_description="Publication status")
    view_count = fields.Integer(default=0, ai_agent_writable=False)
    author_email = fields.Email(nullable=True)
    created_at = fields.DateTime(auto_now_add=True)
    updated_at = fields.DateTime(auto_now=True)
    
    class Meta:
        table_name = "posts"
        ai_name = "Post"
        ai_agent_exposed = True
```

### Comment

```python
class Comment(Model):
    """Comment with moderation."""
    
    post = fields.ForeignKey(Post, on_delete="CASCADE", related_name="comments")
    author_name = fields.String(max_length=100)
    author_email = fields.Email()
    body = fields.Text(ai_description="Comment body")
    is_approved = fields.Boolean(default=False, ai_description="Moderation status")
    created_at = fields.DateTime(auto_now_add=True)
    
    class Meta:
        table_name = "comments"
        ai_name = "Comment"
```

## API Endpoints

### Posts

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/posts/` | List posts (with filtering) |
| POST | `/api/posts/` | Create a post |
| GET | `/api/posts/{id}/` | Get post details |
| PUT | `/api/posts/{id}/` | Update a post |
| DELETE | `/api/posts/{id}/` | Delete a post |
| POST | `/api/posts/{id}/publish/` | Publish a post |
| POST | `/api/posts/{id}/unpublish/` | Unpublish a post |
| POST | `/api/posts/{id}/view/` | Increment view count |

### Comments

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/comments/` | List comments |
| POST | `/api/comments/` | Create a comment |
| GET | `/api/comments/{id}/` | Get comment details |
| DELETE | `/api/comments/{id}/` | Delete a comment |
| POST | `/api/comments/{id}/approve/` | Approve a comment |
| POST | `/api/comments/{id}/reject/` | Reject a comment |

## Custom Actions

### Publish Workflow

```python
class PostViewSet(ModelViewSet):
    @action(detail=True, methods=["POST"])
    async def publish(self, pk: str, request: Request):
        """Publish a post (make it visible)."""
        post = await self.model.objects.get(id=pk)
        if not post.content:
            return {"error": "Cannot publish post without content"}
        post.is_published = True
        await post.save()
        return {"status": "published", "id": str(post.id)}
    
    @action(detail=True, methods=["POST"])
    async def unpublish(self, pk: str, request: Request):
        """Unpublish a post (hide from public)."""
        post = await self.model.objects.get(id=pk)
        post.is_published = False
        await post.save()
        return {"status": "unpublished", "id": str(post.id)}
```

### Comment Moderation

```python
class CommentViewSet(ModelViewSet):
    @action(detail=True, methods=["POST"])
    async def approve(self, pk: str, request: Request):
        """Approve a comment for display."""
        comment = await self.model.objects.get(id=pk)
        comment.is_approved = True
        await comment.save()
        return {"status": "approved", "id": str(comment.id)}
    
    @action(detail=True, methods=["POST"])
    async def reject(self, pk: str, request: Request):
        """Reject/hide a comment."""
        comment = await self.model.objects.get(id=pk)
        comment.is_approved = False
        await comment.save()
        return {"status": "rejected", "id": str(comment.id)}
```

## Example Requests

### Create a Post

```bash
curl -X POST http://localhost:8000/api/posts/ \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Hello World",
    "slug": "hello-world",
    "content": "# Welcome\n\nThis is my first post.",
    "tags": ["welcome", "intro"]
  }'
```

### Publish the Post

```bash
curl -X POST http://localhost:8000/api/posts/1/publish/
```

### Add a Comment

```bash
curl -X POST http://localhost:8000/api/comments/ \
  -H "Content-Type: application/json" \
  -d '{
    "post_id": 1,
    "author_name": "Jane",
    "author_email": "jane@example.com",
    "body": "Great post!"
  }'
```

### Approve the Comment

```bash
curl -X POST http://localhost:8000/api/comments/1/approve/
```

## Serializers

### PostSerializer (Full)

```python
class PostSerializer(ModelSerializer):
    class Meta:
        model = Post
        fields = [
            "id", "title", "slug", "content", "tags",
            "is_published", "view_count", "author_email",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "view_count", "created_at", "updated_at"]
```

### PostListSerializer (Compact)

```python
class PostListSerializer(ModelSerializer):
    """Compact serializer for list views."""
    
    class Meta:
        model = Post
        fields = ["id", "title", "slug", "is_published", "created_at"]
```

## Admin Configuration

```python
class PostAdmin(ModelAdmin):
    list_display = ["title", "slug", "is_published", "view_count", "created_at"]
    list_filter = ["is_published"]
    search_fields = ["title", "content"]

class CommentAdmin(ModelAdmin):
    list_display = ["post", "author_name", "is_approved", "created_at"]
    list_filter = ["is_approved"]
    search_fields = ["author_name", "body"]
```

## Extending the Pattern

### Add Categories

```python
class Category(Model):
    name = fields.String(max_length=100)
    slug = fields.String(max_length=100, unique=True)
    
    class Meta:
        table_name = "categories"

class Post(Model):
    # ... existing fields ...
    category = fields.ForeignKey(Category, nullable=True, on_delete="SET_NULL")
```

### Add Featured Images

```python
class Post(Model):
    # ... existing fields ...
    featured_image_url = fields.String(max_length=500, nullable=True)
    featured_image_alt = fields.String(max_length=200, nullable=True)
```

### Add SEO Fields

```python
class Post(Model):
    # ... existing fields ...
    meta_title = fields.String(max_length=60, nullable=True)
    meta_description = fields.String(max_length=160, nullable=True)
```

## Next Steps

- [CRM Pattern](crm.md) - Sales pipeline
- [Multitenant Pattern](multitenant.md) - SaaS backend
- [ViewSet Actions](../api/viewsets.md) - Custom actions
