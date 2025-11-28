"""
Basic Vidyut Example Application

A simple FastAPI application demonstrating Vidyut ORM usage.
All imports come from vidyut - clean and unified!
"""

import os
from contextlib import asynccontextmanager
from typing import Optional

from pydantic import BaseModel

# Everything imported from vidyut - clean and unified!
from vidyut import (
    Model,
    fields,
    Vidyut,
    Database,
    HTTPException,
    DoesNotExist,
)


# =============================================================================
# Models
# =============================================================================

class User(Model):
    """User model with email, name, and active status."""
    
    email = fields.String(max_length=255, unique=True)
    name = fields.String(max_length=100, nullable=True)
    is_active = fields.Boolean(default=True)
    metadata = fields.JSON(nullable=True)


class Post(Model):
    """Blog post model."""
    
    title = fields.String(max_length=200)
    content = fields.String(max_length=10000, nullable=True)
    is_published = fields.Boolean(default=False)
    view_count = fields.Integer(default=0)


# =============================================================================
# Pydantic Schemas
# =============================================================================

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


class PostResponse(BaseModel):
    id: str
    title: str
    content: Optional[str]
    is_published: bool
    view_count: int
    created_at: str
    updated_at: str


# =============================================================================
# Application Setup
# =============================================================================

# Get database URL from environment or use default
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:qwertyuiop@localhost:5432/vidyut_example"
)


# Custom lifespan to create tables on startup
@asynccontextmanager
async def lifespan(app):
    # Tables will be created after DB connects
    db = Database.get_instance()
    for model in [User, Post]:
        sql = model.get_create_table_sql()
        try:
            await db.execute(sql)
        except Exception:
            pass  # Table might already exist
    yield


# Create the Vidyut app - database connection is automatic!
app = Vidyut(
    database_url=DATABASE_URL,
    title="Vidyut Example App",
    description="Demo application using Vidyut async ORM",
    version="0.1.0",
    lifespan=lifespan,
)


# =============================================================================
# User Endpoints
# =============================================================================

@app.post("/users", response_model=UserResponse)
async def create_user(data: UserCreate):
    """Create a new user."""
    user = await User.objects.create(
        email=data.email,
        name=data.name,
        is_active=data.is_active,
        metadata=data.metadata,
    )
    return _user_to_response(user)


@app.get("/users", response_model=list[UserResponse])
async def list_users(is_active: Optional[bool] = None):
    """List all users, optionally filtered by active status."""
    if is_active is not None:
        users = await User.objects.filter(is_active=is_active).all()
    else:
        users = await User.objects.all()
    return [_user_to_response(u) for u in users]


@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: str):
    """Get a user by ID."""
    # With Vidyut app, DoesNotExist automatically returns 404!
    user = await User.objects.get(id=user_id)
    return _user_to_response(user)


@app.put("/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: str, data: UserUpdate):
    """Update a user."""
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
    """Delete a user."""
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
# Post Endpoints
# =============================================================================

@app.post("/posts", response_model=PostResponse)
async def create_post(data: PostCreate):
    """Create a new post."""
    post = await Post.objects.create(
        title=data.title,
        content=data.content,
        is_published=data.is_published,
    )
    return _post_to_response(post)


@app.get("/posts", response_model=list[PostResponse])
async def list_posts(is_published: Optional[bool] = None):
    """List all posts, optionally filtered by published status."""
    if is_published is not None:
        posts = await Post.objects.filter(is_published=is_published).all()
    else:
        posts = await Post.objects.all()
    return [_post_to_response(p) for p in posts]


@app.get("/posts/{post_id}", response_model=PostResponse)
async def get_post(post_id: str):
    """Get a post by ID and increment view count."""
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
        created_at=post.created_at.isoformat() if post.created_at else "",
        updated_at=post.updated_at.isoformat() if post.updated_at else "",
    )


# =============================================================================
# Health Check
# =============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    if app.db:
        await app.db.fetchval("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    return {"status": "unhealthy", "database": "not configured"}


# =============================================================================
# Run with: vidyut run main:app --reload
# =============================================================================
