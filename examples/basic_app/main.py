"""
Basic Aksara Example Application (v0.3.4)

A simple FastAPI application demonstrating Aksara ORM usage.
All imports come from aksara - clean and unified!

New in v0.3.4:
- aksara startproject <name> for scaffolded project creation
- Clean project structure: app/, settings.py, migrations/
- No more manual get_create_table_sql - use migrations!

New in v0.3.3:
- Operation-based Python migrations (CreateTable, AddField, etc.)
- RunSQL escape hatch for raw SQL with safety controls
- aksara makemigrations generates Python migration files
- aksara migrate runs operations, not raw SQL

New in v0.3.2:
- ModelSerializer for DRF-style validation and serialization
- Serializer-based ViewSets with validation hooks
- Nested FK expansion via serializers

New in v0.3.1:
- @action decorator for custom ViewSet endpoints
- Full Swagger/OpenAPI support for custom actions

New in v0.3:
- ModelViewSet for auto-generated CRUD APIs
- Auto-generated Pydantic schemas from models
- include_viewset() to wire ViewSets to routers

Retained from v0.2:
- Centralized settings with env var support
- ForeignKey relationships
- AI metadata on models and fields
- Query lookups (__gt, __gte, __lt, __lte, __in, __isnull, __icontains)
- Custom exceptions with proper error mapping
"""

from contextlib import asynccontextmanager
from typing import Optional

from pydantic import BaseModel

# Import settings module first - this configures Aksara!
from . import settings as app_settings  # noqa: F401 - import for side effects

# Import models from models.py (single source of truth)
from .models import User, Post, Article

# Everything imported from aksara - clean and unified!
from aksara import (
    Aksara,
    Database,
    Request,
    HTTPException,
    # v0.2: Settings (configured by app_settings import above)
    settings,
    # v0.2: Custom exceptions
    UniqueConstraintError,
    # v0.2: AI metadata helpers
    get_models,
    get_model_schema_for_ai,
    get_all_schemas_for_ai,
    # v0.3: API layer
    ModelViewSet,
    include_viewset,
    # v0.3.1: Action decorator
    action,
    # v0.3.2: Serializer
    ModelSerializer,
)


# =============================================================================
# v0.3.2: ModelSerializer - Django/DRF-style Validation
# =============================================================================
# Serializers provide a thin layer on top of Pydantic for:
# - Field selection and exclusion
# - Validation hooks (validate_<field>, validate)
# - Async save/create/update
# - Nested FK expansion
# =============================================================================

class UserSerializer(ModelSerializer):
    """
    Serializer for User model with validation hooks.
    
    Demonstrates:
        - Field selection with fields/exclude
        - read_only_fields for output-only fields
        - validate_<field>() hooks for field-level validation
        - validate() for cross-field validation
    """
    
    class Meta:
        model = User
        fields = ["id", "email", "name", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]
    
    def validate_email(self, value):
        """Validate and normalize email."""
        if not value or "@" not in value:
            raise ValueError("Invalid email format")
        return value.lower().strip()
    
    def validate(self, data):
        """Cross-field validation."""
        # Example: ensure name is provided for active users
        if data.get("is_active") and not data.get("name"):
            # Just a warning - we'll allow it
            pass
        return data


class PostSerializer(ModelSerializer):
    """
    Serializer for Post model with FK expansion.
    
    Demonstrates:
        - ForeignKey handling (author → author_id)
        - expand for nested serializer data
    """
    
    class Meta:
        model = Post
        fields = ["id", "title", "content", "is_published", "view_count", "author", "created_at"]
        read_only_fields = ["id", "view_count", "created_at"]
        expand = {"author": UserSerializer}  # Nested serializer for FK


# =============================================================================
# v0.3: ModelViewSets - Auto-generated CRUD APIs!
# =============================================================================
# Instead of manually writing endpoints, ViewSets generate them automatically.
# Pydantic schemas are also auto-generated from the model fields.
#
# v0.3.1: @action decorator for custom endpoints with full Swagger support!
# v0.3.2: Use serializers for validation and response shaping!
# =============================================================================

class UserViewSet(ModelViewSet):
    """
    ViewSet for User model.
    
    Auto-generates:
        - GET /api/users/ → list (with pagination)
        - GET /api/users/{id} → retrieve
        - POST /api/users/ → create
        - PATCH /api/users/{id} → update
        - DELETE /api/users/{id} → delete
    
    v0.3.1 Custom Actions:
        - POST /api/users/{pk}/deactivate → deactivate user
        - POST /api/users/{pk}/activate → activate user
        - GET /api/users/active → list active users only
        - GET /api/users/stats → get user statistics
    
    v0.3.2: Uses UserSerializer for validation and response shaping.
    """
    model = User
    prefix = "/api/users"
    tags = ["Users"]
    
    # Customize pagination
    default_limit = 20
    max_limit = 100
    
    # -------------------------------------------------------------------------
    # v0.3.1: Custom Actions with @action decorator
    # -------------------------------------------------------------------------
    
    @action(detail=True, methods=["post"], summary="Deactivate user")
    async def deactivate(self, pk: str, request: Request):
        """
        Deactivate a user account.
        
        Sets is_active to False for the specified user.
        """
        user = await self.model.objects.get(id=pk)
        user.is_active = False
        await user.save()
        return {"status": "deactivated", "id": str(user.id), "email": user.email}
    
    @action(detail=True, methods=["post"], summary="Activate user")
    async def activate(self, pk: str, request: Request):
        """
        Activate a user account.
        
        Sets is_active to True for the specified user.
        """
        user = await self.model.objects.get(id=pk)
        user.is_active = True
        await user.save()
        return {"status": "activated", "id": str(user.id), "email": user.email}
    
    @action(detail=False, methods=["get"], summary="List active users")
    async def active(self, request: Request):
        """
        Get all active users.
        
        Returns only users with is_active=True.
        """
        users = await self.model.objects.filter(is_active=True).all()
        return [
            {"id": str(u.id), "email": u.email, "name": u.name}
            for u in users
        ]
    
    @action(detail=False, methods=["get"], summary="Get user statistics")
    async def stats(self, request: Request):
        """
        Get user statistics.
        
        Returns counts of total, active, and inactive users.
        """
        total = await self.model.objects.filter().count()
        active = await self.model.objects.filter(is_active=True).count()
        inactive = await self.model.objects.filter(is_active=False).count()
        return {
            "total": total,
            "active": active,
            "inactive": inactive,
        }


class PostViewSet(ModelViewSet):
    """
    ViewSet for Post model.
    
    Auto-generates full CRUD API at /api/posts/
    
    v0.3.1 Custom Actions:
        - POST /api/posts/{pk}/publish → publish a post
        - POST /api/posts/{pk}/unpublish → unpublish a post
        - GET /api/posts/published → list published posts only
        - GET /api/posts/by-author/{author_id} → list posts by author
    """
    model = Post
    prefix = "/api/posts"
    tags = ["Posts"]
    
    # -------------------------------------------------------------------------
    # v0.3.1: Custom Actions
    # -------------------------------------------------------------------------
    
    @action(detail=True, methods=["post"], summary="Publish post")
    async def publish(self, pk: str, request: Request):
        """
        Publish a post.
        
        Sets is_published to True for the specified post.
        """
        post = await self.model.objects.get(id=pk)
        post.is_published = True
        await post.save()
        return {"status": "published", "id": str(post.id), "title": post.title}
    
    @action(detail=True, methods=["post"], summary="Unpublish post")
    async def unpublish(self, pk: str, request: Request):
        """
        Unpublish a post.
        
        Sets is_published to False for the specified post.
        """
        post = await self.model.objects.get(id=pk)
        post.is_published = False
        await post.save()
        return {"status": "unpublished", "id": str(post.id), "title": post.title}
    
    @action(detail=False, methods=["get"], summary="List published posts")
    async def published(self, request: Request):
        """
        Get all published posts.
        
        Returns only posts with is_published=True.
        """
        posts = await self.model.objects.filter(is_published=True).all()
        return [
            {
                "id": str(p.id),
                "title": p.title,
                "view_count": p.view_count,
                "author_id": str(p.author_id) if p.author_id else None,
            }
            for p in posts
        ]
    
    @action(detail=True, methods=["post"], summary="Increment view count")
    async def view(self, pk: str, request: Request):
        """
        Increment the view count for a post.
        
        Call this when a post is viewed to track analytics.
        """
        post = await self.model.objects.get(id=pk)
        post.view_count = (post.view_count or 0) + 1
        await post.save()
        return {"id": str(post.id), "view_count": post.view_count}


# =============================================================================
# Legacy Pydantic Schemas (for manual endpoints below)
# =============================================================================
# These are kept for the manual endpoints, but for ViewSets,
# schemas are auto-generated from the model!

class UserCreate(BaseModel):
    email: str
    name: Optional[str] = None
    is_active: bool = True
    metadata: Optional[dict] = None


class UserUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    metadata: Optional[dict] = None


class UserResponse(BaseModel):
    id: str
    email: str
    name: Optional[str]
    is_active: bool
    metadata: Optional[dict]
    created_at: str
    updated_at: str


class PostCreate(BaseModel):
    title: str
    content: Optional[str] = None
    is_published: bool = False
    author_id: Optional[str] = None  # v0.2: FK reference


class PostResponse(BaseModel):
    id: str
    title: str
    content: Optional[str]
    is_published: bool
    view_count: int
    author_id: Optional[str]  # v0.2: FK reference
    created_at: str
    updated_at: str


# =============================================================================
# Application Setup
# =============================================================================

# Custom lifespan to create tables on startup
@asynccontextmanager
async def lifespan(app):
    # Tables will be created after DB connects
    db = Database.get_instance()
    # Create User first (referenced by Post)
    for model in [User, Post]:
        sql = model.get_create_table_sql()
        try:
            await db.execute(sql)
        except Exception:
            pass  # Table might already exist
    yield


# Create the Aksara app - database connection is automatic!
# Uses settings.database_url by default, or pass explicit URL
app = Aksara(
    database_url=settings.database_url,
    title="Aksara Example App",
    description="Demo application using Aksara async ORM (v0.3.4)",
    version="0.3.4",
    lifespan=lifespan,
)


# =============================================================================
# v0.3: Register ViewSets with the app
# =============================================================================
# One line per model - that's all you need for full CRUD APIs!
# =============================================================================

include_viewset(app, UserViewSet)
include_viewset(app, PostViewSet)


# =============================================================================
# Manual User Endpoints (legacy - for comparison with ViewSets)
# =============================================================================
# These endpoints show the old way of doing things.
# Compare with the auto-generated /api/users/ endpoints above!

@app.post("/users", response_model=UserResponse)
async def create_user(data: UserCreate):
    """Create a new user. (Legacy - see POST /api/users/ for v0.3 way)"""
    try:
        user = await User.objects.create(
            email=data.email,
            name=data.name,
            is_active=data.is_active,
            metadata=data.metadata,
        )
        return _user_to_response(user)
    except UniqueConstraintError:
        # v0.2: Proper exception handling
        raise HTTPException(status_code=400, detail="Email already exists")


@app.get("/users", response_model=list[UserResponse])
async def list_users(
    is_active: Optional[bool] = None,
    name_contains: Optional[str] = None,  # v0.2: icontains lookup
):
    """List all users with optional filters. (Legacy - see GET /api/users/ for v0.3 way)"""
    queryset = User.objects.filter()
    
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    
    # v0.2: Use __icontains lookup for case-insensitive search
    if name_contains:
        queryset = queryset.filter(name__icontains=name_contains)
    
    users = await queryset.all()
    return [_user_to_response(u) for u in users]


@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: str):
    """Get a user by ID. (Legacy - see GET /api/users/{id} for v0.3 way)"""
    # With Aksara app, DoesNotExist automatically returns 404!
    user = await User.objects.get(id=user_id)
    return _user_to_response(user)


@app.put("/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: str, data: UserUpdate):
    """Update a user. (Legacy - see PATCH /api/users/{id} for v0.3 way)"""
    user = await User.objects.get(id=user_id)
    
    if data.name is not None:
        user.name = data.name
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.metadata is not None:
        user.metadata = data.metadata
    
    await user.save()
    return _user_to_response(user)


@app.delete("/users/{user_id}")
async def delete_user(user_id: str):
    """Delete a user. (Legacy - see DELETE /api/users/{id} for v0.3 way)"""
    user = await User.objects.get(id=user_id)
    await user.delete()
    return {"deleted": True, "id": user_id}


def _user_to_response(user: User) -> UserResponse:
    """Convert User model to response schema."""
    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        is_active=user.is_active,
        metadata=user.metadata,
        created_at=user.created_at.isoformat() if user.created_at else "",
        updated_at=user.updated_at.isoformat() if user.updated_at else "",
    )


# =============================================================================
# Manual Post Endpoints (legacy - for comparison with ViewSets)
# =============================================================================

@app.post("/posts", response_model=PostResponse)
async def create_post(data: PostCreate):
    """Create a new post. (Legacy - see POST /api/posts/ for v0.3 way)"""
    post = await Post.objects.create(
        title=data.title,
        content=data.content,
        is_published=data.is_published,
        author_id=data.author_id,  # v0.2: FK value
    )
    return _post_to_response(post)


@app.get("/posts", response_model=list[PostResponse])
async def list_posts(
    is_published: Optional[bool] = None,
    min_views: Optional[int] = None,  # v0.2: __gte lookup
    author_id: Optional[str] = None,  # v0.2: FK filter
):
    """List all posts with optional filters. (Legacy - see GET /api/posts/ for v0.3 way)"""
    queryset = Post.objects.filter()
    
    if is_published is not None:
        queryset = queryset.filter(is_published=is_published)
    
    # v0.2: Use __gte lookup for minimum view count
    if min_views is not None:
        queryset = queryset.filter(view_count__gte=min_views)
    
    # v0.2: Filter by author FK
    if author_id is not None:
        queryset = queryset.filter(author_id=author_id)
    
    posts = await queryset.all()
    return [_post_to_response(p) for p in posts]


@app.get("/posts/{post_id}", response_model=PostResponse)
async def get_post(post_id: str):
    """Get a post by ID and increment view count. (Legacy - see GET /api/posts/{id} for v0.3 way)"""
    post = await Post.objects.get(id=post_id)
    post.view_count = (post.view_count or 0) + 1
    await post.save()
    return _post_to_response(post)


def _post_to_response(post: Post) -> PostResponse:
    """Convert Post model to response schema."""
    return PostResponse(
        id=str(post.id),
        title=post.title,
        content=post.content,
        is_published=post.is_published,
        view_count=post.view_count or 0,
        author_id=str(post.author_id) if post.author_id else None,
        created_at=post.created_at.isoformat() if post.created_at else "",
        updated_at=post.updated_at.isoformat() if post.updated_at else "",
    )


# =============================================================================
# v0.2: AI Schema Endpoints (for MCP/AI agent integration)
# =============================================================================

@app.get("/ai/schema")
async def get_ai_schemas():
    """
    Get AI-friendly schemas for all exposed models.
    
    This endpoint is useful for AI agents to understand the data model.
    Only returns models with ai_agent_exposed=True.
    """
    return {
        "schemas": get_all_schemas_for_ai(),
        "version": "0.3.4",
    }


@app.get("/ai/schema/{model_name}")
async def get_model_ai_schema(model_name: str):
    """Get AI schema for a specific model."""
    models = get_models()
    for model in models:
        if model.__name__.lower() == model_name.lower():
            return get_model_schema_for_ai(model)
    raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found")


# =============================================================================
# Health Check
# =============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    if app.db:
        await app.db.fetchval("SELECT 1")
        return {
            "status": "healthy", 
            "database": "connected",
            "version": "0.3.4",
            "debug": settings.debug,
        }
    return {"status": "unhealthy", "database": "not configured"}


# =============================================================================
# Run with: aksara run main:app --reload
# Or: DATABASE_URL="postgresql://..." uvicorn main:app --reload
# =============================================================================
