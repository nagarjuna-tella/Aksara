# Tutorial: Building a Blog API

Build a complete REST API for a blog with user authentication, posts, comments, and tags.

---

## What You'll Build

By the end of this tutorial, you'll have a working blog API that can:

- ✅ Register and authenticate users
- ✅ Create, read, update, and delete blog posts
- ✅ Add comments to posts
- ✅ Tag posts for organization
- ✅ Search and filter posts

**Time:** ~30 minutes

**Difficulty:** Beginner (no prior Aksara experience needed)

---

## What You'll Learn

| Concept | What It Means |
|---------|---------------|
| **Models** | How to define your data structure |
| **Serializers** | How to convert data to/from JSON |
| **ViewSets** | How to create API endpoints |
| **Relationships** | How to connect models (like posts to authors) |
| **Authentication** | How to add user login |

---

## Prerequisites

Before starting, make sure you have:

- Python 3.11 or higher (`python --version`)
- PostgreSQL installed and running (`psql --version`)
- pip or uv for installing packages

---

## Step 1: Set Up the Project

### Create the Project

Open your terminal and run:

```bash
# Create a new Aksara project
aksara startproject blog_api
cd blog_api

# Install Aksara with all features
pip install aksara[all]
```

**What this does:** Creates a folder called `blog_api` with all the files you need.

### Configure the Database

Edit `blog_api/settings.py`:

```python
# blog_api/settings.py
import os

AKSARA = {
    "DEBUG": True,  # Enable debug mode for development
    "DATABASE_URL": os.getenv(
        "DATABASE_URL",
        "postgresql://localhost/blog_api"  # Your database connection
    ),
    "INSTALLED_APPS": ["blog"],  # Apps in your project
}
```

**What this does:** Tells Aksara where your database is and which apps to load.

### Create the Database

```bash
# Using psql
createdb blog_api
```

### Create the Blog App

```bash
aksara startapp blog
```

**What this does:** Creates a `blog` folder with files for your models, views, etc.

---

## Step 2: Define Your Data Models

Models define what your data looks like. Each model becomes a table in your database.

### Create the User Model

Open `blog/models.py` and add:

```python
# blog/models.py
from aksara import Model, fields

class User(Model):
    """
    A user who can write blog posts.
    
    This creates a database table with columns for:
    - email, username, password (for login)
    - name, bio (profile information)
    - is_active (can this user log in?)
    """
    
    # Login fields
    email = fields.Email(unique=True)  # unique=True means no duplicates
    username = fields.String(max_length=150, unique=True)
    password = fields.String(max_length=128)  # Will store hashed password
    
    # Profile fields
    name = fields.String(max_length=100, nullable=True)  # nullable=True means optional
    bio = fields.Text(nullable=True)
    
    # Status
    is_active = fields.Boolean(default=True)  # default=True means new users are active
    
    class Meta:
        table_name = "users"  # The database table name
```

**Understanding the code:**

| Line | What It Means |
|------|---------------|
| `fields.Email(unique=True)` | Email address, must be unique |
| `fields.String(max_length=150)` | Text up to 150 characters |
| `nullable=True` | This field is optional |
| `default=True` | Use this value if not provided |

### Create the Post Model

Add this to `blog/models.py`:

```python
# blog/models.py (continued)

class Post(Model):
    """
    A blog post.
    
    Each post:
    - Has a title and content
    - Belongs to an author (a User)
    - Can be published or a draft
    """
    
    # Content
    title = fields.String(max_length=200)
    slug = fields.String(max_length=200, unique=True)  # URL-friendly version of title
    content = fields.Text()
    excerpt = fields.Text(nullable=True)  # Short preview
    
    # Ownership - this connects Post to User
    author = fields.ForeignKey(
        User,                    # The related model
        on_delete="CASCADE",     # Delete posts if author is deleted
        related_name="posts"     # Access author's posts as author.posts
    )
    
    # Publishing
    is_published = fields.Boolean(default=False)
    published_at = fields.DateTime(nullable=True)
    
    # Stats
    view_count = fields.Integer(default=0)
    
    class Meta:
        table_name = "posts"
        ordering = ["-created_at"]  # Newest first
```

**What is a ForeignKey?**

A ForeignKey connects two models. Here, every Post has an `author` that points to a User:

```
Post                          User
┌──────────────────┐         ┌──────────────────┐
│ id: abc123       │         │ id: user456      │
│ title: "Hello"   │────────►│ name: "Alice"    │
│ author_id: user456│         │ email: "..."     │
└──────────────────┘         └──────────────────┘
```

### Create the Comment Model

```python
# blog/models.py (continued)

class Comment(Model):
    """
    A comment on a blog post.
    
    Comments can be nested (replies to other comments).
    """
    
    # What post is this comment on?
    post = fields.ForeignKey(
        Post, 
        on_delete="CASCADE",
        related_name="comments"
    )
    
    # Who wrote this comment?
    author = fields.ForeignKey(
        User,
        on_delete="CASCADE", 
        related_name="comments"
    )
    
    content = fields.Text()
    is_approved = fields.Boolean(default=True)
    
    # For nested comments (replies)
    parent = fields.ForeignKey(
        "self",              # Reference to the same model
        on_delete="CASCADE",
        nullable=True,       # Top-level comments have no parent
        related_name="replies"
    )
    
    class Meta:
        table_name = "comments"
        ordering = ["created_at"]  # Oldest first
```

### Create the Tag Model

```python
# blog/models.py (continued)

class Tag(Model):
    """
    A tag for categorizing posts.
    
    Example: "python", "tutorial", "news"
    """
    
    name = fields.String(max_length=50, unique=True)
    slug = fields.String(max_length=50, unique=True)
    
    class Meta:
        table_name = "tags"
```

### Add Tags to Posts (Many-to-Many)

Update the Post model to include tags:

```python
class Post(Model):
    # ... all the fields from before ...
    
    # A post can have many tags, and a tag can be on many posts
    tags = fields.ManyToMany(Tag, related_name="posts")
```

**What is ManyToMany?**

Many-to-Many means both sides can have multiple connections:

```
Post "Python Tips"  ─────┬───► Tag "python"
                         └───► Tag "tutorial"

Post "Django Guide" ─────┬───► Tag "python"
                         └───► Tag "django"
```

### Create the Database Tables

Now create the actual database tables:

```bash
# Generate migration files (instructions for the database)
aksara makemigrations

# Run the migrations (create the tables)
aksara migrate
```

---

## Step 3: Create Serializers

Serializers convert Python objects to JSON and validate incoming data.

Create `blog/serializers.py`:

```python
# blog/serializers.py
from aksara.api import ModelSerializer, SerializerMethodField
from .models import User, Post, Comment, Tag

class UserSerializer(ModelSerializer):
    """
    Converts User objects to JSON.
    
    Used when showing user information in responses.
    """
    class Meta:
        model = User
        fields = ["id", "username", "name", "bio", "created_at"]
        # Note: We don't include email or password for privacy


class UserCreateSerializer(ModelSerializer):
    """
    Validates data when creating a new user.
    
    Used for registration.
    """
    class Meta:
        model = User
        fields = ["email", "username", "password", "name"]
    
    async def create(self, validated_data):
        """Hash the password before saving."""
        from aksara.contrib.auth import hash_password
        validated_data["password"] = hash_password(validated_data["password"])
        return await super().create(validated_data)


class TagSerializer(ModelSerializer):
    """Converts Tag objects to JSON."""
    class Meta:
        model = Tag
        fields = ["id", "name", "slug"]


class CommentSerializer(ModelSerializer):
    """
    Converts Comment objects to JSON.
    
    Includes the author's info (nested).
    """
    author = UserSerializer(read_only=True)
    
    class Meta:
        model = Comment
        fields = ["id", "content", "author", "parent", "created_at"]


class PostListSerializer(ModelSerializer):
    """
    Serializer for listing posts (brief info).
    
    Doesn't include full content or comments.
    """
    author = UserSerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    comment_count = SerializerMethodField()
    
    class Meta:
        model = Post
        fields = [
            "id", "title", "slug", "excerpt", "author",
            "tags", "comment_count", "is_published", "published_at"
        ]
    
    async def get_comment_count(self, obj):
        """Count comments for this post."""
        return await obj.comments.count()


class PostDetailSerializer(PostListSerializer):
    """
    Serializer for a single post (full info).
    
    Includes full content and all comments.
    """
    comments = CommentSerializer(many=True, read_only=True)
    
    class Meta(PostListSerializer.Meta):
        fields = PostListSerializer.Meta.fields + ["content", "comments"]
```

---

## Step 4: Create ViewSets (API Endpoints)

ViewSets handle API requests. Each ViewSet creates multiple endpoints.

Create `blog/views.py`:

```python
# blog/views.py
from datetime import datetime
from aksara.api import ModelViewSet, ViewSet, action
from aksara.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from aksara.contrib.auth import create_token, verify_password, hash_password

from .models import User, Post, Comment, Tag
from .serializers import (
    UserSerializer, UserCreateSerializer,
    PostListSerializer, PostDetailSerializer,
    CommentSerializer, TagSerializer
)


class AuthViewSet(ViewSet):
    """
    Authentication endpoints.
    
    Handles user registration and login.
    """
    
    @action(detail=False, methods=["POST"])
    async def register(self, request):
        """
        Register a new user.
        
        POST /api/auth/register/
        Body: {"email": "...", "username": "...", "password": "...", "name": "..."}
        """
        serializer = UserCreateSerializer(data=request.data)
        await serializer.is_valid(raise_exception=True)
        user = await serializer.save()
        
        # Create a login token
        token = create_token(user)
        
        return {
            "user": UserSerializer(user).data,
            "token": token,
        }
    
    @action(detail=False, methods=["POST"])
    async def login(self, request):
        """
        Login and get a token.
        
        POST /api/auth/login/
        Body: {"email": "...", "password": "..."}
        """
        email = request.data.get("email")
        password = request.data.get("password")
        
        # Find the user
        user = await User.objects.filter(email=email).first()
        
        # Check password
        if not user or not verify_password(password, user.password):
            return {"error": "Invalid email or password"}, 401
        
        # Create token
        token = create_token(user)
        
        return {
            "user": UserSerializer(user).data,
            "token": token,
        }
    
    @action(detail=False, methods=["GET"], permission_classes=[IsAuthenticated])
    async def me(self, request):
        """
        Get the current logged-in user.
        
        GET /api/auth/me/
        Headers: Authorization: Bearer <token>
        """
        return UserSerializer(request.user).data


class UserViewSet(ModelViewSet):
    """
    User management endpoints.
    
    GET /api/users/ - List all users
    GET /api/users/{id}/ - Get one user
    """
    model = User
    serializer_class = UserSerializer
    
    @action(detail=True, methods=["GET"])
    async def posts(self, request, id=None):
        """
        Get all published posts by this user.
        
        GET /api/users/{id}/posts/
        """
        user = await self.get_object(id)
        posts = await Post.objects.filter(
            author_id=user.id,
            is_published=True
        ).all()
        return PostListSerializer(posts, many=True).data


class PostViewSet(ModelViewSet):
    """
    Blog post endpoints.
    
    GET /api/posts/ - List posts
    POST /api/posts/ - Create post (authenticated)
    GET /api/posts/{id}/ - Get post detail
    PUT /api/posts/{id}/ - Update post (author only)
    DELETE /api/posts/{id}/ - Delete post (author only)
    """
    model = Post
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    # Enable searching and filtering
    search_fields = ["title", "content"]
    filterset_fields = ["is_published", "author_id"]
    ordering = ["-created_at"]
    
    # Optimize queries
    select_related = ["author"]
    prefetch_related = ["tags"]
    
    def get_serializer_class(self):
        """Use different serializers for list vs detail."""
        if self.action == "retrieve":
            return PostDetailSerializer
        return PostListSerializer
    
    def get_queryset(self):
        """Show drafts only to authenticated users."""
        qs = Post.objects.select_related("author").prefetch_related("tags")
        if not self.request.user.is_authenticated:
            qs = qs.filter(is_published=True)
        return qs
    
    async def create(self, request):
        """Create a post for the current user."""
        data = await self.get_request_data(request)
        data["author_id"] = str(request.user.id)
        
        self.validate_data(data)
        post = await Post.objects.create(**data)
        
        return PostDetailSerializer(post).data, 201
    
    @action(detail=True, methods=["POST"], permission_classes=[IsAuthenticated])
    async def publish(self, request, id=None):
        """
        Publish a draft post.
        
        POST /api/posts/{id}/publish/
        """
        post = await self.get_object(id)
        
        # Only the author can publish
        if str(post.author_id) != str(request.user.id):
            return {"error": "Only the author can publish this post"}, 403
        
        post.is_published = True
        post.published_at = datetime.now()
        await post.save()
        
        return PostDetailSerializer(post).data
    
    @action(detail=True, methods=["POST"], permission_classes=[IsAuthenticated])
    async def add_comment(self, request, id=None):
        """
        Add a comment to this post.
        
        POST /api/posts/{id}/add_comment/
        Body: {"content": "Great post!"}
        """
        post = await self.get_object(id)
        
        comment = await Comment.objects.create(
            post_id=post.id,
            author_id=request.user.id,
            content=request.data.get("content"),
            parent_id=request.data.get("parent_id"),
        )
        
        return CommentSerializer(comment).data, 201


class CommentViewSet(ModelViewSet):
    """Comment management endpoints."""
    model = Comment
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    async def create(self, request):
        """Create a comment for the current user."""
        data = await self.get_request_data(request)
        data["author_id"] = str(request.user.id)
        
        self.validate_data(data)
        comment = await Comment.objects.create(**data)
        
        return CommentSerializer(comment).data, 201


class TagViewSet(ModelViewSet):
    """Tag management endpoints."""
    model = Tag
    serializer_class = TagSerializer
    search_fields = ["name"]
```

---

## Step 5: Configure Routes

Connect your ViewSets to URLs.

Create `blog/urls.py`:

```python
# blog/urls.py
from aksara.api import Router
from .views import AuthViewSet, UserViewSet, PostViewSet, CommentViewSet, TagViewSet

router = Router()

# Register all ViewSets
router.register("auth", AuthViewSet, basename="auth")
router.register("users", UserViewSet)
router.register("posts", PostViewSet)
router.register("comments", CommentViewSet)
router.register("tags", TagViewSet)
```

Update your main app:

```python
# blog_api/app.py
from aksara import Aksara
from blog.urls import router

app = Aksara(
    database_url="postgresql://localhost/blog_api",
    title="Blog API",
    debug=True,
)

# Register all routes under /api/
app.include_router(router, prefix="/api")
```

---

## Step 6: Test Your API

### Start the Server

```bash
aksara run
```

You should see:

```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Started reloader process
```

### Register a User

```bash
curl -X POST http://localhost:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "alice@example.com",
    "username": "alice",
    "password": "secret123",
    "name": "Alice Smith"
  }'
```

**Response:**
```json
{
  "user": {
    "id": "abc123...",
    "username": "alice",
    "name": "Alice Smith"
  },
  "token": "eyJ..."
}
```

Save the token! You'll need it for authenticated requests.

### Login

```bash
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "alice@example.com",
    "password": "secret123"
  }'
```

### Create a Post

```bash
curl -X POST http://localhost:8000/api/posts/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -d '{
    "title": "My First Blog Post",
    "slug": "my-first-post",
    "content": "Hello, world! This is my first blog post.",
    "excerpt": "A brief introduction"
  }'
```

### List All Posts

```bash
curl http://localhost:8000/api/posts/
```

### Search Posts

```bash
curl "http://localhost:8000/api/posts/?search=first"
```

### Publish a Post

```bash
curl -X POST http://localhost:8000/api/posts/POST_ID/publish/ \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

### Add a Comment

```bash
curl -X POST http://localhost:8000/api/posts/POST_ID/add_comment/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -d '{"content": "Great post!"}'
```

### View Interactive Docs

Open http://localhost:8000/docs in your browser to see and test all endpoints.

---

## Step 7: Add Tests (Optional)

Create `blog/tests/test_api.py`:

```python
# blog/tests/test_api.py
import pytest
from aksara.testing import AksaraTestCase
from aksara.contrib.auth import hash_password, create_token
from blog.models import User, Post

class TestBlogAPI(AksaraTestCase):
    
    async def asyncSetUp(self):
        """Set up test data."""
        self.user = await User.objects.create(
            email="test@example.com",
            username="testuser",
            password=hash_password("password123"),
            name="Test User"
        )
        self.token = create_token(self.user)
    
    async def test_list_posts(self):
        """Anyone can list posts."""
        response = await self.client.get("/api/posts/")
        assert response.status_code == 200
    
    async def test_create_post_authenticated(self):
        """Authenticated users can create posts."""
        response = await self.client.post(
            "/api/posts/",
            json={
                "title": "Test Post",
                "slug": "test-post",
                "content": "Test content here",
            },
            headers={"Authorization": f"Bearer {self.token}"}
        )
        assert response.status_code == 201
        assert response.json()["title"] == "Test Post"
    
    async def test_create_post_unauthenticated(self):
        """Unauthenticated users cannot create posts."""
        response = await self.client.post(
            "/api/posts/",
            json={
                "title": "Test Post",
                "slug": "test-post",
                "content": "Test content",
            }
        )
        assert response.status_code == 401
```

Run tests:

```bash
pytest blog/tests/
```

---

## What You Built

Congratulations! You built a complete blog API with:

| Feature | Endpoint |
|---------|----------|
| User registration | `POST /api/auth/register/` |
| User login | `POST /api/auth/login/` |
| List posts | `GET /api/posts/` |
| Create post | `POST /api/posts/` |
| Get post detail | `GET /api/posts/{id}/` |
| Publish post | `POST /api/posts/{id}/publish/` |
| Add comment | `POST /api/posts/{id}/add_comment/` |
| Search posts | `GET /api/posts/?search=...` |
| List tags | `GET /api/tags/` |

---

## Next Steps

Ideas for extending your blog:

1. **Add pagination** — Don't load all posts at once
2. **Add image uploads** — Cover images for posts
3. **Add categories** — Organize posts hierarchically
4. **Add likes** — Let users like posts
5. **Add email notifications** — Notify on new comments

---

## Related Documentation

- [Models](../orm/models.md) — Learn more about defining data
- [ViewSets](../api/viewsets.md) — Customize your API endpoints
- [Serializers](../api/serializers.md) — Advanced data validation
- [Authentication](../api/authentication.md) — More auth options
- [Permissions](../api/permissions.md) — Fine-grained access control
