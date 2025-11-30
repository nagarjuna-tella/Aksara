"""
Vidyut Project Scaffold Templates

Templates for the `vidyut startproject` command.
These generate a clean Vidyut-first project structure.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict

# =============================================================================
# Template Files
# =============================================================================


def get_main_py_template(project_name: str) -> str:
    """Generate main.py content."""
    return f'''"""
{project_name} - Vidyut Application

This is a Vidyut app (powered by FastAPI under the hood), showcasing:

- Async Postgres ORM
- ModelViewSet CRUD APIs
- ModelSerializer-based validation
- Operation-based migrations
- AI schema endpoints

Run with:
    vidyut makemigrations --app app.models
    vidyut migrate
    vidyut run main:app --reload
"""

from vidyut import Vidyut
from settings import settings

# Import models & views to register with Vidyut
from app import models, views  # noqa: F401


# Create the Vidyut app - database connection is automatic!
app = Vidyut(
    database_url=settings.database_url,
    title=settings.app_title or "{project_name}",
    description="Vidyut async API for {project_name}",
    version=settings.app_version or "0.3.4",
)


# Register all routes (ViewSets, AI endpoints, etc.)
views.register_routes(app)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    if app.db:
        await app.db.fetchval("SELECT 1")
        return {{
            "status": "healthy",
            "database": "connected",
            "version": settings.app_version or "0.3.4",
            "debug": settings.debug,
        }}
    return {{"status": "unhealthy", "database": "not configured"}}


# =============================================================================
# Run with:
#   vidyut makemigrations --app app.models
#   vidyut migrate
#   vidyut run main:app --reload
# =============================================================================
'''


def get_settings_py_template(project_name: str) -> str:
    """Generate settings.py content."""
    return f'''"""
{project_name} - Settings

Vidyut settings with environment variable support.
Configure via .env file or environment variables.
"""

from vidyut.conf import Settings as VidyutSettings


class Settings(VidyutSettings):
    """
    Project settings for {project_name}.

    Inherits defaults from VidyutSettings:
      - database_url (from env: DATABASE_URL)
      - debug (from env: VIDYUT_DEBUG)
      - log_level (from env: VIDYUT_LOG_LEVEL)
      - app_title (from env: VIDYUT_APP_TITLE)
      - app_version (from env: VIDYUT_APP_VERSION)
      - migrations_dir (from env: VIDYUT_MIGRATIONS_DIR)
    
    You can override or extend settings here.
    """
    pass


# Global settings instance - loads from environment automatically
settings = Settings()
'''


def get_env_template(project_name: str) -> str:
    """Generate .env content."""
    return f'''# {project_name} - Environment Configuration
# Copy this to .env and customize for your environment

# Database connection URL (PostgreSQL via asyncpg)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/{project_name}

# Debug mode (enables detailed error messages)
VIDYUT_DEBUG=true

# Logging level (DEBUG, INFO, WARNING, ERROR)
VIDYUT_LOG_LEVEL=INFO

# App metadata
VIDYUT_APP_TITLE={project_name}
VIDYUT_APP_VERSION=0.3.4

# Migrations directory (relative to project root)
VIDYUT_MIGRATIONS_DIR=migrations
'''


def get_app_init_template() -> str:
    """Generate app/__init__.py content."""
    return '''"""
Application package.

Contains models, views, and serializers.
"""
'''


def get_models_template(project_name: str) -> str:
    """Generate app/models.py content."""
    return f'''"""
{project_name} - Models

Vidyut ORM models for the application.
"""

from vidyut import Model, fields


class User(Model):
    """
    User model for authentication and profiles.
    
    Demonstrates:
    - String fields with unique constraint
    - Boolean fields with defaults
    - JSON fields for flexible metadata
    - AI metadata for agent integration
    """
    
    email = fields.String(
        max_length=255,
        unique=True,
        ai_description="User's email address",
        ai_sensitive=True,
    )
    name = fields.String(
        max_length=100,
        nullable=True,
        ai_description="User's display name",
    )
    is_active = fields.Boolean(
        default=True,
        ai_description="Whether the user account is active",
    )
    metadata = fields.JSON(
        nullable=True,
        ai_description="Arbitrary user metadata",
    )
    
    class Meta:
        table_name = "users"
        ai_name = "User"
        ai_description = "Application users for authentication"
        ai_agent_exposed = True
        ai_permissions = ["read", "write"]


class Post(Model):
    """
    Blog post model with author relationship.
    
    Demonstrates:
    - ForeignKey relationship to User
    - Integer fields with defaults
    - String fields with large max_length
    """
    
    title = fields.String(
        max_length=200,
        ai_description="Post title",
    )
    content = fields.String(
        max_length=10000,
        nullable=True,
        ai_description="Post body content",
    )
    is_published = fields.Boolean(
        default=False,
        ai_description="Whether the post is publicly visible",
    )
    view_count = fields.Integer(
        default=0,
        ai_description="Number of times the post has been viewed",
        ai_agent_writable=False,
    )
    author = fields.ForeignKey(
        User,
        on_delete="CASCADE",
        nullable=True,
        ai_description="The user who authored this post",
    )
    
    class Meta:
        table_name = "posts"
        ai_name = "Post"
        ai_description = "Blog posts created by users"
        ai_agent_exposed = True
        ai_permissions = ["read", "write"]
'''


def get_serializers_template(project_name: str) -> str:
    """Generate app/serializers.py content."""
    return f'''"""
{project_name} - Serializers

ModelSerializer classes for validation and response shaping.
"""

from vidyut import ModelSerializer
from .models import User, Post


class UserSerializer(ModelSerializer):
    """
    Serializer for User model.
    
    Provides:
    - Field selection via `fields`
    - Read-only fields via `read_only_fields`
    - Field validation via `validate_<field>` methods
    - Cross-field validation via `validate` method
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
            # Allow it but could add a warning
            pass
        return data


class PostSerializer(ModelSerializer):
    """
    Serializer for Post model.
    
    Demonstrates ForeignKey expansion with nested serializer.
    """
    
    class Meta:
        model = Post
        fields = ["id", "title", "content", "is_published", "view_count", "author", "created_at"]
        read_only_fields = ["id", "view_count", "created_at"]
        expand = {{"author": UserSerializer}}
'''


def get_views_template(project_name: str) -> str:
    """Generate app/views.py content."""
    return f'''"""
{project_name} - Views

ViewSets, custom actions, and route registration.
"""

from vidyut import (
    Request,
    HTTPException,
    ModelViewSet,
    include_viewset,
    action,
    get_models,
    get_model_schema_for_ai,
    get_all_schemas_for_ai,
)
from .models import User, Post
from .serializers import UserSerializer, PostSerializer


class UserViewSet(ModelViewSet):
    """
    ViewSet for User model.
    
    Auto-generates:
        - GET /api/users/ → list (with pagination)
        - GET /api/users/{{id}} → retrieve
        - POST /api/users/ → create
        - PATCH /api/users/{{id}} → update
        - DELETE /api/users/{{id}} → delete
    
    Custom Actions:
        - POST /api/users/{{pk}}/deactivate → deactivate user
        - POST /api/users/{{pk}}/activate → activate user
        - GET /api/users/active → list active users only
        - GET /api/users/stats → get user statistics
    """
    
    model = User
    prefix = "/api/users"
    tags = ["Users"]
    
    default_limit = 20
    max_limit = 100
    
    @action(detail=True, methods=["post"], summary="Deactivate user")
    async def deactivate(self, pk: str, request: Request):
        """Deactivate a user account."""
        user = await self.model.objects.get(id=pk)
        user.is_active = False
        await user.save()
        return {{"status": "deactivated", "id": str(user.id), "email": user.email}}
    
    @action(detail=True, methods=["post"], summary="Activate user")
    async def activate(self, pk: str, request: Request):
        """Activate a user account."""
        user = await self.model.objects.get(id=pk)
        user.is_active = True
        await user.save()
        return {{"status": "activated", "id": str(user.id), "email": user.email}}
    
    @action(detail=False, methods=["get"], summary="List active users")
    async def active(self, request: Request):
        """Get all active users."""
        users = await self.model.objects.filter(is_active=True).all()
        return [
            {{"id": str(u.id), "email": u.email, "name": u.name}}
            for u in users
        ]
    
    @action(detail=False, methods=["get"], summary="Get user statistics")
    async def stats(self, request: Request):
        """Get user statistics."""
        total = await self.model.objects.filter().count()
        active = await self.model.objects.filter(is_active=True).count()
        inactive = await self.model.objects.filter(is_active=False).count()
        return {{
            "total": total,
            "active": active,
            "inactive": inactive,
        }}


class PostViewSet(ModelViewSet):
    """
    ViewSet for Post model.
    
    Auto-generates full CRUD API at /api/posts/
    
    Custom Actions:
        - POST /api/posts/{{pk}}/publish → publish a post
        - POST /api/posts/{{pk}}/unpublish → unpublish a post
        - GET /api/posts/published → list published posts only
        - POST /api/posts/{{pk}}/view → increment view count
    """
    
    model = Post
    prefix = "/api/posts"
    tags = ["Posts"]
    
    @action(detail=True, methods=["post"], summary="Publish post")
    async def publish(self, pk: str, request: Request):
        """Publish a post."""
        post = await self.model.objects.get(id=pk)
        post.is_published = True
        await post.save()
        return {{"status": "published", "id": str(post.id), "title": post.title}}
    
    @action(detail=True, methods=["post"], summary="Unpublish post")
    async def unpublish(self, pk: str, request: Request):
        """Unpublish a post."""
        post = await self.model.objects.get(id=pk)
        post.is_published = False
        await post.save()
        return {{"status": "unpublished", "id": str(post.id), "title": post.title}}
    
    @action(detail=False, methods=["get"], summary="List published posts")
    async def published(self, request: Request):
        """Get all published posts."""
        posts = await self.model.objects.filter(is_published=True).all()
        return [
            {{
                "id": str(p.id),
                "title": p.title,
                "view_count": p.view_count,
                "author_id": str(p.author_id) if p.author_id else None,
            }}
            for p in posts
        ]
    
    @action(detail=True, methods=["post"], summary="Increment view count")
    async def view(self, pk: str, request: Request):
        """Increment the view count for a post."""
        post = await self.model.objects.get(id=pk)
        post.view_count = (post.view_count or 0) + 1
        await post.save()
        return {{"id": str(post.id), "view_count": post.view_count}}


def register_routes(app):
    """
    Register all ViewSets and routes with the Vidyut app.
    
    This is called from main.py to wire up all endpoints.
    """
    # Register ViewSets
    include_viewset(app, UserViewSet)
    include_viewset(app, PostViewSet)
    
    # AI Schema endpoints
    @app.get("/ai/schema", tags=["AI"])
    async def get_ai_schemas():
        """Get AI-friendly schemas for all exposed models."""
        return {{
            "schemas": get_all_schemas_for_ai(),
            "version": "0.3.4",
        }}
    
    @app.get("/ai/schema/{{model_name}}", tags=["AI"])
    async def get_model_ai_schema(model_name: str):
        """Get AI schema for a specific model."""
        models = get_models()
        for model in models:
            if model.__name__.lower() == model_name.lower():
                return get_model_schema_for_ai(model)
        raise HTTPException(status_code=404, detail=f"Model '{{model_name}}' not found")
'''


def get_migrations_init_template() -> str:
    """Generate migrations/__init__.py content."""
    return '''"""
Migrations package.

Migration files are stored here and applied with:
    vidyut migrate
"""
'''


def get_readme_template(project_name: str) -> str:
    """Generate README.md content."""
    return f'''# {project_name}

A Vidyut-powered async API application.

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your database credentials
   ```

3. **Create database:**
   ```bash
   createdb {project_name}
   ```

4. **Run migrations:**
   ```bash
   vidyut makemigrations --app app.models
   vidyut migrate
   ```

5. **Start the server:**
   ```bash
   vidyut run main:app --reload
   ```

6. **Open the API docs:**
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

## Project Structure

```
{project_name}/
├── app/
│   ├── __init__.py
│   ├── models.py        # Vidyut ORM models
│   ├── views.py         # ViewSets and route registration
│   └── serializers.py   # ModelSerializer classes
├── migrations/          # Database migrations
├── settings.py          # VidyutSettings configuration
├── main.py              # Vidyut app entry point
├── .env                 # Environment variables
└── requirements.txt     # Python dependencies
```

## API Endpoints

### Users (`/api/users/`)
- `GET /api/users/` - List users (paginated)
- `POST /api/users/` - Create user
- `GET /api/users/{{id}}` - Get user
- `PATCH /api/users/{{id}}` - Update user
- `DELETE /api/users/{{id}}` - Delete user
- `POST /api/users/{{id}}/activate` - Activate user
- `POST /api/users/{{id}}/deactivate` - Deactivate user
- `GET /api/users/active` - List active users
- `GET /api/users/stats` - User statistics

### Posts (`/api/posts/`)
- `GET /api/posts/` - List posts (paginated)
- `POST /api/posts/` - Create post
- `GET /api/posts/{{id}}` - Get post
- `PATCH /api/posts/{{id}}` - Update post
- `DELETE /api/posts/{{id}}` - Delete post
- `POST /api/posts/{{id}}/publish` - Publish post
- `POST /api/posts/{{id}}/unpublish` - Unpublish post
- `GET /api/posts/published` - List published posts

### AI Schema (`/ai/schema`)
- `GET /ai/schema` - Get all model schemas for AI agents
- `GET /ai/schema/{{model_name}}` - Get specific model schema

### Health (`/health`)
- `GET /health` - Health check endpoint

## Built with Vidyut

⚡ [Vidyut](https://github.com/nagarjuna-tella/vidyut) - Async Postgres ORM for FastAPI
'''


def get_requirements_template() -> str:
    """Generate requirements.txt content."""
    return '''# Vidyut ORM (includes FastAPI, asyncpg, pydantic)
vidyut>=0.3.4

# Server
uvicorn[standard]>=0.24.0

# Environment variables
python-dotenv>=1.0.0
'''


def get_pyproject_template(project_name: str) -> str:
    """Generate pyproject.toml content."""
    return f'''[project]
name = "{project_name}"
version = "0.1.0"
description = "A Vidyut-powered async API application"
requires-python = ">=3.10"
dependencies = [
    "vidyut>=0.3.4",
    "uvicorn[standard]>=0.24.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "httpx>=0.24.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
'''


def get_gitignore_template() -> str:
    """Generate .gitignore content."""
    return '''# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
*.egg
*.egg-info/
dist/
build/
eggs/
*.manifest
*.spec
pip-log.txt

# Virtual environments
.venv/
venv/
ENV/

# Environment variables (keep .env.example)
.env
.env.local
.env.*.local

# IDE
.idea/
.vscode/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Testing
.pytest_cache/
.coverage
htmlcov/

# Logs
*.log
'''


# =============================================================================
# Scaffold Creation
# =============================================================================


def create_project_scaffold(project_name: str, base_path: Path) -> Dict[str, str]:
    """
    Create the project scaffold directory structure and files.
    
    Args:
        project_name: Name of the project
        base_path: Base path where the project will be created
        
    Returns:
        Dict mapping file paths to their content
    """
    project_path = base_path / project_name
    
    # Define all files to create
    files = {
        project_path / "main.py": get_main_py_template(project_name),
        project_path / "settings.py": get_settings_py_template(project_name),
        project_path / ".env": get_env_template(project_name),
        project_path / ".env.example": get_env_template(project_name),
        project_path / "app" / "__init__.py": get_app_init_template(),
        project_path / "app" / "models.py": get_models_template(project_name),
        project_path / "app" / "serializers.py": get_serializers_template(project_name),
        project_path / "app" / "views.py": get_views_template(project_name),
        project_path / "migrations" / "__init__.py": get_migrations_init_template(),
        project_path / "README.md": get_readme_template(project_name),
        project_path / "requirements.txt": get_requirements_template(),
        project_path / "pyproject.toml": get_pyproject_template(project_name),
        project_path / ".gitignore": get_gitignore_template(),
    }
    
    return files


def write_scaffold_files(files: Dict[Path, str]) -> None:
    """
    Write all scaffold files to disk.
    
    Args:
        files: Dict mapping file paths to their content
    """
    for file_path, content in files.items():
        # Create parent directories
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write file
        with open(file_path, 'w') as f:
            f.write(content)
