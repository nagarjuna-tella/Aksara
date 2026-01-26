# Tutorial: Blog API

Build a complete blog REST API with authentication, posts, comments, and tags.

---

## What You'll Build

A fully-featured blog API with:

- User registration and authentication
- CRUD operations for posts
- Nested comments
- Tags with many-to-many relationships
- Search and filtering
- Pagination

**Time:** ~30 minutes

---

## Setup

### Create Project

```bash
# Create project
vidyut startproject blog_api
cd blog_api

# Install dependencies
pip install vidyut[all]
```

### Configure Database

```python
# blog_api/settings.py
import os

VIDYUT = {
    "DEBUG": True,
    "DATABASE_URL": os.getenv(
        "DATABASE_URL",
        "postgresql://localhost/blog_api"
    ),
    "INSTALLED_APPS": ["blog"],
}
```

### Create App

```bash
vidyut startapp blog
```

---

## Step 1: Define Models

### User Model

```python
# blog/models.py
from vidyut import Model, fields

class User(Model):
    """Blog user."""
    
    email = fields.EmailField(unique=True)
    username = fields.StringField(max_length=150, unique=True)
    password = fields.StringField(max_length=128)
    name = fields.StringField(max_length=100, null=True)
    bio = fields.TextField(null=True)
    is_active = fields.BooleanField(default=True)
    
    class Meta:
        table_name = "users"
```

### Post Model

```python
# blog/models.py (continued)
class Post(Model):
    """Blog post."""
    
    title = fields.StringField(max_length=200)
    slug = fields.StringField(max_length=200, unique=True)
    content = fields.TextField()
    excerpt = fields.TextField(null=True)
    author = fields.ForeignKey(User, on_delete="CASCADE", related_name="posts")
    is_published = fields.BooleanField(default=False)
    published_at = fields.DateTimeField(null=True)
    view_count = fields.IntegerField(default=0)
    
    class Meta:
        table_name = "posts"
        ordering = ["-created_at"]
```

### Comment Model

```python
# blog/models.py (continued)
class Comment(Model):
    """Comment on a post."""
    
    post = fields.ForeignKey(Post, on_delete="CASCADE", related_name="comments")
    author = fields.ForeignKey(User, on_delete="CASCADE", related_name="comments")
    content = fields.TextField()
    is_approved = fields.BooleanField(default=True)
    parent = fields.ForeignKey(
        "self",
        on_delete="CASCADE",
        null=True,
        related_name="replies"
    )
    
    class Meta:
        table_name = "comments"
        ordering = ["created_at"]
```

### Tag Model

```python
# blog/models.py (continued)
class Tag(Model):
    """Post tag."""
    
    name = fields.StringField(max_length=50, unique=True)
    slug = fields.StringField(max_length=50, unique=True)
    
    class Meta:
        table_name = "tags"

# Add tags to Post model
class Post(Model):
    # ... existing fields ...
    tags = fields.ManyToManyField(Tag, related_name="posts")
```

### Create Migrations

```bash
vidyut makemigrations
vidyut migrate
```

---

## Step 2: Create Serializers

```python
# blog/serializers.py
from vidyut.api import ModelSerializer
from .models import User, Post, Comment, Tag

class UserSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "name", "bio", "created_at"]

class UserCreateSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ["email", "username", "password", "name"]
        extra_kwargs = {"password": {"write_only": True}}
    
    async def create(self, validated_data):
        from vidyut.contrib.auth import hash_password
        validated_data["password"] = hash_password(validated_data["password"])
        return await super().create(validated_data)

class TagSerializer(ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "slug"]

class CommentSerializer(ModelSerializer):
    author = UserSerializer(read_only=True)
    
    class Meta:
        model = Comment
        fields = ["id", "content", "author", "parent", "created_at"]

class PostListSerializer(ModelSerializer):
    author = UserSerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    comment_count = SerializerMethodField()
    
    class Meta:
        model = Post
        fields = [
            "id", "title", "slug", "excerpt", "author",
            "tags", "comment_count", "published_at"
        ]
    
    async def get_comment_count(self, obj):
        return await obj.comments.count()

class PostDetailSerializer(PostListSerializer):
    comments = CommentSerializer(many=True, read_only=True)
    
    class Meta(PostListSerializer.Meta):
        fields = PostListSerializer.Meta.fields + ["content", "comments"]
```

---

## Step 3: Create ViewSets

```python
# blog/viewsets.py
from vidyut.api import ModelViewSet, action
from vidyut.api.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from .models import User, Post, Comment, Tag
from .serializers import (
    UserSerializer, UserCreateSerializer,
    PostListSerializer, PostDetailSerializer,
    CommentSerializer, TagSerializer
)

class UserViewSet(ModelViewSet):
    model = User
    serializer_class = UserSerializer
    
    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        return UserSerializer
    
    @action(detail=True)
    async def posts(self, request, pk=None):
        """Get posts by this user."""
        user = await self.get_object()
        posts = await Post.objects.filter(
            author=user,
            is_published=True
        ).all()
        return PostListSerializer(posts, many=True).data

class PostViewSet(ModelViewSet):
    model = Post
    permission_classes = [IsAuthenticatedOrReadOnly]
    search_fields = ["title", "content"]
    filterset_fields = ["author", "is_published", "tags"]
    
    def get_serializer_class(self):
        if self.action == "retrieve":
            return PostDetailSerializer
        return PostListSerializer
    
    def get_queryset(self):
        qs = Post.objects.select_related("author").prefetch_related("tags")
        if not self.request.user.is_authenticated:
            qs = qs.filter(is_published=True)
        return qs
    
    async def perform_create(self, serializer):
        await serializer.save(author=self.request.user)
    
    @action(detail=True, methods=["post"])
    async def publish(self, request, pk=None):
        """Publish a post."""
        from datetime import datetime
        
        post = await self.get_object()
        if post.author.id != request.user.id:
            return {"error": "Not authorized"}, 403
        
        post.is_published = True
        post.published_at = datetime.now()
        await post.save()
        
        return PostDetailSerializer(post).data
    
    @action(detail=True, methods=["post"])
    async def add_comment(self, request, pk=None):
        """Add a comment to this post."""
        post = await self.get_object()
        
        comment = await Comment.objects.create(
            post=post,
            author=request.user,
            content=request.data.get("content"),
            parent_id=request.data.get("parent_id"),
        )
        
        return CommentSerializer(comment).data

class CommentViewSet(ModelViewSet):
    model = Comment
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    async def perform_create(self, serializer):
        await serializer.save(author=self.request.user)

class TagViewSet(ModelViewSet):
    model = Tag
    serializer_class = TagSerializer
    search_fields = ["name"]
```

---

## Step 4: Configure Routes

```python
# blog/urls.py
from vidyut.api import include_viewset
from .viewsets import UserViewSet, PostViewSet, CommentViewSet, TagViewSet

routes = [
    include_viewset("/users", UserViewSet),
    include_viewset("/posts", PostViewSet),
    include_viewset("/comments", CommentViewSet),
    include_viewset("/tags", TagViewSet),
]
```

```python
# blog_api/app.py
from vidyut import Vidyut
from blog.urls import routes

app = Vidyut()

# Register routes
for route in routes:
    app.include_router(route, prefix="/api")
```

---

## Step 5: Add Authentication

```python
# blog/viewsets.py (add auth endpoints)
from vidyut.api import ViewSet, action
from vidyut.contrib.auth import (
    authenticate, create_token, hash_password, verify_password
)

class AuthViewSet(ViewSet):
    """Authentication endpoints."""
    
    @action(detail=False, methods=["post"])
    async def register(self, request):
        """Register a new user."""
        serializer = UserCreateSerializer(data=request.data)
        await serializer.is_valid(raise_exception=True)
        user = await serializer.save()
        
        token = create_token(user)
        return {
            "user": UserSerializer(user).data,
            "token": token,
        }
    
    @action(detail=False, methods=["post"])
    async def login(self, request):
        """Login and get token."""
        email = request.data.get("email")
        password = request.data.get("password")
        
        user = await User.objects.filter(email=email).first()
        if not user or not verify_password(password, user.password):
            return {"error": "Invalid credentials"}, 401
        
        token = create_token(user)
        return {
            "user": UserSerializer(user).data,
            "token": token,
        }
    
    @action(detail=False, methods=["get"])
    async def me(self, request):
        """Get current user."""
        if not request.user.is_authenticated:
            return {"error": "Not authenticated"}, 401
        return UserSerializer(request.user).data
```

```python
# blog/urls.py (add auth routes)
from .viewsets import AuthViewSet

routes = [
    # ... existing routes ...
    include_viewset("/auth", AuthViewSet),
]
```

---

## Step 6: Test the API

### Start Server

```bash
vidyut runserver
```

### Create User

```bash
curl -X POST http://localhost:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com",
    "username": "john",
    "password": "secret123",
    "name": "John Doe"
  }'
```

### Login

```bash
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com",
    "password": "secret123"
  }'
```

### Create Post

```bash
curl -X POST http://localhost:8000/api/posts/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "title": "My First Post",
    "slug": "my-first-post",
    "content": "Hello, world!",
    "excerpt": "A brief intro"
  }'
```

### List Posts

```bash
curl http://localhost:8000/api/posts/
```

### Search Posts

```bash
curl "http://localhost:8000/api/posts/?search=hello"
```

### Add Comment

```bash
curl -X POST http://localhost:8000/api/posts/POST_ID/add_comment/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"content": "Great post!"}'
```

---

## Step 7: Add Tests

```python
# blog/tests/test_api.py
import pytest
from vidyut.testing import VidyutTestCase

class TestBlogAPI(VidyutTestCase):
    async def asyncSetUp(self):
        self.user = await User.objects.create(
            email="test@example.com",
            username="testuser",
            password=hash_password("password"),
        )
        self.token = create_token(self.user)
    
    async def test_list_posts(self):
        response = await self.client.get("/api/posts/")
        assert response.status_code == 200
    
    async def test_create_post_authenticated(self):
        response = await self.client.post(
            "/api/posts/",
            json={
                "title": "Test Post",
                "slug": "test-post",
                "content": "Test content",
            },
            headers={"Authorization": f"Bearer {self.token}"}
        )
        assert response.status_code == 201
        assert response.json()["title"] == "Test Post"
    
    async def test_create_post_unauthenticated(self):
        response = await self.client.post(
            "/api/posts/",
            json={"title": "Test", "slug": "test", "content": "Test"}
        )
        assert response.status_code == 401
```

Run tests:

```bash
vidyut test
```

---

## Next Steps

You've built a complete blog API! Here's what you can add:

1. **Pagination** — Add page-based pagination
2. **Image uploads** — Post cover images
3. **Categories** — Organize posts by category
4. **Likes** — Let users like posts
5. **Email notifications** — Notify on new comments

---

## Complete Code

See the complete code on GitHub:
[github.com/vidyut/examples/blog-api](https://github.com/vidyut/examples/blog-api)

---

## Related Documentation

- [Models](../orm/models.md)
- [ViewSets](../api/viewsets.md)
- [Authentication](../api/authentication.md)
- [Serializers](../api/serializers.md)
