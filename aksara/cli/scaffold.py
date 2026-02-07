"""
Aksara Project Scaffold Templates

Templates for the `aksara startproject` command.
These generate a clean Aksara-first project structure.
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
{project_name} - Aksara Application (v0.5.13)

A modern async API with Admin, Studio, and AI Mode built-in.

Quick Start:
    aksara makemigrations --app app.models
    aksara migrate
    aksara createsuperuser  # Optional: create admin user
    aksara dev main:app

Endpoints:
    Welcome:   http://localhost:8000/
    API Docs:  http://localhost:8000/docs
    Admin:     http://localhost:8000/admin (debug mode)
    Studio:    http://localhost:8000/studio/ui
    AI Tools:  http://localhost:8000/ai/tools
"""

import importlib
from aksara import Aksara, __version__ as aksara_version
from aksara.middleware.request_id import RequestIdMiddleware
from aksara.middleware.logging import LoggingMiddleware
from fastapi.responses import HTMLResponse
from settings import settings, INSTALLED_APPS


def load_installed_apps():
    """
    Load all installed apps from INSTALLED_APPS.
    
    This imports each app module, which triggers:
    - Model registration (from models.py)
    - Admin registration (from admin.py)
    - ViewSet discovery (from views.py)
    """
    for app_path in INSTALLED_APPS:
        try:
            importlib.import_module(app_path)
            for submodule in ["models", "admin", "views"]:
                try:
                    importlib.import_module(f"{{app_path}}.{{submodule}}")
                except ImportError:
                    pass
        except ImportError as e:
            if not app_path.startswith("aksara."):
                print(f"Warning: Could not load app '{{app_path}}': {{e}}")


# Load all installed apps
load_installed_apps()

# Import URL configuration
from app.urls import register_routes


# Create the Aksara app
# Aksara automatically mounts:
#   - /admin (when debug=True or enable_admin=True)
#   - /studio/* (Studio endpoints for IDE/UI integration)
#   - /ai/* (AI tools, context, schemas)
app = Aksara(
    database_url=settings.database_url,
    title=settings.app_title or "{project_name}",
    description="A modern Aksara-powered async API",
    version="0.1.0",
    debug=settings.debug,
    enable_admin=settings.enable_admin,
    # Middlewares (request ID, logging)
    middlewares=[
        (RequestIdMiddleware, {{}}),
        (LoggingMiddleware, {{"log_request_body": False}}),
    ],
)


# Register routes from app/urls.py
register_routes(app)


# =============================================================================
# Welcome Page (v0.5.13)
# =============================================================================

WELCOME_HTML = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{project_name} - Aksara</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #e4e4e7;
        }}
        .container {{
            text-align: center;
            padding: 2rem;
            max-width: 600px;
        }}
        .logo {{ font-size: 3rem; margin-bottom: 1rem; }}
        h1 {{ font-size: 2rem; margin-bottom: 0.5rem; color: #fbbf24; }}
        .version {{ color: #9ca3af; font-size: 0.9rem; margin-bottom: 1.5rem; }}
        .success {{ color: #4ade80; font-size: 1.1rem; margin-bottom: 2rem; }}
        .links {{
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
            margin-bottom: 2rem;
        }}
        .links a {{
            background: rgba(255,255,255,0.1);
            padding: 0.75rem 1.5rem;
            border-radius: 8px;
            color: #e4e4e7;
            text-decoration: none;
            transition: background 0.2s;
        }}
        .links a:hover {{ background: rgba(255,255,255,0.2); }}
        .links a span {{ color: #9ca3af; font-size: 0.85rem; }}
        .note {{
            color: #6b7280;
            font-size: 0.85rem;
            padding-top: 1rem;
            border-top: 1px solid rgba(255,255,255,0.1);
        }}
        .note code {{
            background: rgba(255,255,255,0.1);
            padding: 0.1rem 0.3rem;
            border-radius: 3px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">⚡</div>
        <h1>{project_name}</h1>
        <p class="version">Powered by Aksara {{aksara_version}}</p>
        <p class="success">Your Aksara project is running 🚀</p>
        <div class="links">
            <a href="/admin/">Admin Panel <span>→ Manage your data</span></a>
            <a href="/studio/ui">Studio <span>→ Interactive dashboard</span></a>
            <a href="/api/posts/">API <span>→ /api/posts/</span></a>
            <a href="/docs">API Docs <span>→ OpenAPI / Swagger</span></a>
            <a href="/ai/tools">AI Tools <span>→ LLM integration</span></a>
        </div>
        <p class="note">
            Edit <code>main.py</code> to customize this page.
        </p>
    </div>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def welcome():
    """Welcome page - shows project status and links."""
    return WELCOME_HTML


# Health check endpoint
@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint."""
    if app.db:
        await app.db.fetchval("SELECT 1")
        return {{
            "status": "healthy",
            "database": "connected",
            "studio": "/studio/ui",
            "admin": "/admin",
            "ai_tools": "/ai/tools",
        }}
    return {{"status": "unhealthy", "database": "not configured"}}
'''


def get_settings_py_template(project_name: str) -> str:
    """Generate settings.py content."""
    return f'''"""
{project_name} - Settings (v0.5.13)

Aksara settings with environment variable support.
Configure via .env file or environment variables.
"""

import os
from dotenv import load_dotenv
load_dotenv()

from aksara.conf import Settings as AksaraSettings


# =============================================================================
# AKSARA Configuration
# =============================================================================
# Central configuration dict for Aksara features.
# These settings control Admin, Studio, AI Mode, and more.

AKSARA = {{
    "APP_NAME": "{project_name}",
    
    # Admin Interface
    "ENABLE_ADMIN": True,  # Mount /admin (requires auth contrib)
    
    # Studio Integration (v0.5.0+)
    "ENABLE_STUDIO": True,  # Mount /studio/* endpoints
    "STUDIO_UI_ENABLED": True,  # Enable /studio/ui dashboard
    "STUDIO_ALLOWED_ORIGINS": [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    
    # AI Mode (v0.4.0+)
    "AI_MODE_ENABLED": True,  # Enable /ai/* endpoints
    "AI_DEBUG_ENABLED": True,  # AI debug assistant in debug mode
}}


# =============================================================================
# Installed Apps
# =============================================================================
# List of app modules to load. Each app can contain:
#   - models.py: Database models
#   - views.py: ViewSets and API endpoints
#   - admin.py: Admin interface registrations

INSTALLED_APPS = [
    # Aksara built-in apps
    "aksara.contrib.auth",      # User authentication & sessions
    "aksara.contrib.admin",     # Admin interface
    
    # Your apps
    "app",                      # Default app created by startproject
]


# =============================================================================
# Settings Class
# =============================================================================

class Settings(AksaraSettings):
    """
    Project settings for {project_name}.

    Inherits from AksaraSettings which loads from environment:
      - DATABASE_URL: PostgreSQL connection string
      - AKSARA_DEBUG: Enable debug mode (default: false)
      - AKSARA_LOG_LEVEL: Logging level (default: INFO)
      - AKSARA_APP_TITLE: Application title
      - AKSARA_MIGRATIONS_DIR: Migrations directory (default: migrations)
    
    Add custom settings here as needed.
    """
    
    # Reference to installed apps
    installed_apps: list = INSTALLED_APPS
    
    # Admin & Studio (from AKSARA dict)
    enable_admin: bool = AKSARA.get("ENABLE_ADMIN", True)
    enable_studio: bool = AKSARA.get("ENABLE_STUDIO", True)
    studio_ui_enabled: bool = AKSARA.get("STUDIO_UI_ENABLED", True)
    studio_allowed_origins: list = AKSARA.get("STUDIO_ALLOWED_ORIGINS", [])
    
    # AI Mode
    ai_enabled: bool = AKSARA.get("AI_MODE_ENABLED", True)
    ai_debug_enabled: bool = AKSARA.get("AI_DEBUG_ENABLED", True)


# Global settings instance
settings = Settings()
'''


def get_env_template(project_name: str) -> str:
    """Generate .env content."""
    return f'''# {project_name} - Environment Configuration

# Database (PostgreSQL)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/{project_name}

# Debug mode - enables admin interface and detailed errors
AKSARA_DEBUG=true

# Logging level (DEBUG, INFO, WARNING, ERROR)
AKSARA_LOG_LEVEL=INFO

# App metadata
AKSARA_APP_TITLE={project_name}

# Migrations directory
AKSARA_MIGRATIONS_DIR=migrations
'''


def get_app_init_template() -> str:
    """Generate app/__init__.py content."""
    return '''"""
Application package.
"""
'''


def get_admin_template(project_name: str) -> str:
    """Generate app/admin.py content."""
    return f'''"""
{project_name} - Admin Configuration

Register your models with the admin interface here.
Admin is available at /admin when debug=True or enable_admin=True.
"""

from aksara.contrib.admin import site, ModelAdmin
from .models import Post


# =============================================================================
# Post Admin
# =============================================================================

class PostAdmin(ModelAdmin):
    """Admin configuration for Post model."""
    list_display = ["title", "is_published", "created_at"]
    list_filter = ["is_published"]
    search_fields = ["title", "content"]


# Register models with admin
site.register(Post, PostAdmin)


# =============================================================================
# Add more model registrations here:
#
# from .models import User
#
# class UserAdmin(ModelAdmin):
#     list_display = ["email", "name", "is_active"]
#
# site.register(User, UserAdmin)
# =============================================================================
'''


def get_models_template(project_name: str) -> str:
    """Generate app/models.py content."""
    return f'''"""
{project_name} - Models

Define your Aksara ORM models here.
Models are auto-discovered from INSTALLED_APPS.
"""

from aksara import Model, fields


# =============================================================================
# Post Model - Example model showcasing Aksara features
# =============================================================================

class Post(Model):
    """
    Blog post model.
    
    Demonstrates different field types and AI metadata.
    This model is registered in admin.py and exposed via API in views.py.
    
    AI tools can discover this model at /ai/tools.
    """
    
    title = fields.String(
        max_length=200,
        ai_description="Post title",
    )
    content = fields.Text(
        nullable=True,
        ai_description="Post body content (Markdown supported)",
    )
    is_published = fields.Boolean(
        default=False,
        ai_description="Whether the post is publicly visible",
    )
    view_count = fields.Integer(
        default=0,
        ai_description="Number of times the post has been viewed",
        ai_agent_writable=False,  # AI shouldn't modify view counts
    )
    tags = fields.JSON(
        nullable=True,
        ai_description="List of tags for categorization",
    )
    created_at = fields.DateTime(
        auto_now_add=True,
        ai_description="When the post was created",
    )
    updated_at = fields.DateTime(
        auto_now=True,
        ai_description="When the post was last updated",
    )
    
    class Meta:
        table_name = "posts"
        ai_name = "Post"
        ai_description = "Blog posts for the {project_name} application"
        ai_agent_exposed = True
        ai_permissions = ["read", "write"]


# =============================================================================
# Add more models here:
#
# class User(Model):
#     email = fields.Email(unique=True)
#     name = fields.String(max_length=100)
#     is_active = fields.Boolean(default=True)
#
#     class Meta:
#         table_name = "users"
#
#
# class Comment(Model):
#     post = fields.ForeignKey(Post, on_delete="CASCADE")
#     author = fields.String(max_length=100)
#     body = fields.Text()
#
#     class Meta:
#         table_name = "comments"
# =============================================================================
'''


def get_serializers_template(project_name: str) -> str:
    """Generate app/serializers.py content."""
    return f'''"""
{project_name} - Serializers

Define your ModelSerializer classes for validation and response shaping.
"""

from aksara import ModelSerializer
from .models import Post


# =============================================================================
# Post Serializer
# =============================================================================

class PostSerializer(ModelSerializer):
    """
    Serializer for Post model.
    
    Handles validation and JSON conversion for the Post API.
    """
    
    class Meta:
        model = Post
        fields = [
            "id",
            "title",
            "content",
            "is_published",
            "view_count",
            "tags",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "view_count", "created_at", "updated_at"]


# =============================================================================
# Add more serializers here:
#
# from .models import User
#
# class UserSerializer(ModelSerializer):
#     class Meta:
#         model = User
#         fields = ["id", "email", "name", "is_active", "created_at"]
#         read_only_fields = ["id", "created_at"]
# =============================================================================
'''


def get_views_template(project_name: str) -> str:
    """Generate app/views.py content."""
    return f'''"""
{project_name} - Views

Define your ViewSets and custom actions here.
ViewSets are auto-discovered and exposed as AI tools at /ai/tools.
"""

from aksara import ModelViewSet, action, Request
from aksara.permissions import IsAuthenticated, IsAdminUser
from .models import Post
from .serializers import PostSerializer


# =============================================================================
# Post ViewSet
# =============================================================================

class PostViewSet(ModelViewSet):
    """
    API ViewSet for Post model.
    
    Auto-generates these endpoints:
        GET    /api/posts/          - List all posts
        POST   /api/posts/          - Create a post
        GET    /api/posts/{{id}}/     - Get a post
        PUT    /api/posts/{{id}}/     - Update a post
        DELETE /api/posts/{{id}}/     - Delete a post
        POST   /api/posts/{{id}}/publish/  - Custom action
    
    This ViewSet is also exposed as an AI tool at /ai/tools.
    """
    
    model = Post
    serializer_class = PostSerializer
    prefix = "/api/posts"
    tags = ["Posts"]
    
    # AI exposure (default: True for ModelViewSet)
    ai_exposed = True
    
    @action(detail=True, methods=["POST"])
    async def publish(self, pk: str, request: Request):
        """Publish a post (custom action example)."""
        post = await self.model.objects.get(id=pk)
        post.is_published = True
        await post.save()
        return {{"status": "published", "id": str(post.id)}}
    
    @action(detail=True, methods=["POST"])
    async def increment_views(self, pk: str, request: Request):
        """Increment view count (custom action example)."""
        post = await self.model.objects.get(id=pk)
        post.view_count += 1
        await post.save()
        return {{"view_count": post.view_count}}


# =============================================================================
# Add more ViewSets here:
#
# class UserViewSet(ModelViewSet):
#     model = User
#     serializer_class = UserSerializer
#     prefix = "/api/users"
#     tags = ["Users"]
#     permission_classes = [IsAuthenticated]
# =============================================================================
'''


def get_urls_template(project_name: str) -> str:
    """Generate app/urls.py content."""
    return f'''"""
{project_name} - URL Configuration

Register your ViewSets here.
"""

from aksara import include_viewset
from .views import PostViewSet


# URL Patterns - list your ViewSets here
urlpatterns = [
    PostViewSet,
]


def register_routes(app):
    """Register all routes with the Aksara app."""
    for viewset in urlpatterns:
        include_viewset(app, viewset)
'''


def get_migrations_init_template() -> str:
    """Generate migrations/__init__.py content."""
    return '''"""
Migrations package.

Migration files are stored here and applied with:
    aksara migrate
"""
'''


def get_readme_template(project_name: str) -> str:
    """Generate README.md content."""
    return f'''# {project_name}

A modern Aksara-powered async API with Admin, Studio, and AI Mode built-in.

## Quick Start

```bash
# 1. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\\Scripts\\activate

# 2. Install dependencies
pip install -e ".[dev]"

# 3. Configure environment (edit .env with your database URL)
cp .env.example .env

# 4. Create database
createdb {project_name}

# 5. Run migrations (Post model is already defined)
aksara makemigrations --app app.models
aksara migrate

# 6. Create admin user (optional)
aksara createsuperuser

# 7. Start the server
aksara run main:app --reload
```

## URLs

| URL | Description |
|-----|-------------|
| http://localhost:8000/docs | API Documentation (Swagger UI) |
| http://localhost:8000/redoc | API Documentation (ReDoc) |
| http://localhost:8000/admin | Admin Interface (debug mode) |
| http://localhost:8000/studio/ui | Studio Dashboard |
| http://localhost:8000/api/posts | Posts API |
| http://localhost:8000/ai/tools | AI Tools Discovery |
| http://localhost:8000/health | Health Check |

## What's Included

This project comes pre-configured with:

- **Post model** - Example model with various field types
- **PostViewSet** - Full CRUD API for posts
- **Admin** - Post registered in admin interface
- **Studio** - Dashboard at /studio/ui
- **AI Mode** - Post ViewSet exposed as AI tools
- **Middleware** - Request ID & logging
- **Pre-commit** - Code formatting hooks

## Project Structure

```
{project_name}/
├── app/
│   ├── models.py        # Post model (and your models)
│   ├── views.py         # PostViewSet (and your ViewSets)
│   ├── serializers.py   # PostSerializer (and your serializers)
│   ├── urls.py          # Route registration
│   └── admin.py         # Post admin (and your admin classes)
├── migrations/          # Database migrations
├── settings.py          # Configuration (AKSARA dict)
├── main.py              # App entry point
├── .env                 # Environment variables
└── .pre-commit-config.yaml  # Pre-commit hooks
```

## CLI Commands

```bash
# Development
aksara run main:app --reload   # Start dev server
aksara shell                   # Interactive Python shell

# Database
aksara makemigrations --app app.models
aksara migrate
aksara createsuperuser

# Code Quality
aksara format                  # Format with black
aksara lint                    # Lint with ruff

# Studio
aksara studio open             # Open Studio UI in browser
aksara studio ai-context       # Export AI context (JSON)
```

## Configuration

Edit `settings.py` to customize:

```python
AKSARA = {{
    "ENABLE_ADMIN": True,       # /admin
    "ENABLE_STUDIO": True,      # /studio/*
    "AI_MODE_ENABLED": True,    # /ai/*
}}
```

## Built with ⚡ Aksara

https://github.com/nagarjuna-tella/aksara
'''


def get_requirements_template() -> str:
    """Generate requirements.txt content."""
    return '''# Core
-e .

# Server
uvicorn[standard]>=0.24.0
'''


def get_pyproject_template(project_name: str) -> str:
    """Generate pyproject.toml content."""
    return f'''[project]
name = "{project_name}"
version = "0.1.0"
description = "A modern Aksara-powered async API with Admin, Studio, and AI Mode"
requires-python = ">=3.11"
dependencies = [
    "aksara>=0.5.13",
    "uvicorn[standard]>=0.24.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.21.0",
    "httpx>=0.24.0",
    "black>=24.0.0",
    "ruff>=0.5.0",
    "mypy>=1.8.0",
    "pre-commit>=3.6.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.black]
line-length = 88
target-version = ["py311"]

[tool.ruff]
line-length = 88
select = ["E", "F", "I"]
ignore = []
src = ["."]

[tool.mypy]
python_version = "3.11"
strict = false
warn_return_any = true
warn_unused_ignores = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
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

# mypy
.mypy_cache/
'''


def get_precommit_config_template() -> str:
    """Generate .pre-commit-config.yaml content."""
    return '''# Aksara Pre-commit Configuration
# Install hooks: pre-commit install
# Run all hooks: aksara precommit run

repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.5.0
    hooks:
      - id: ruff
        args: ["--fix"]

  - repo: https://github.com/psf/black
    rev: 24.4.2
    hooks:
      - id: black

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: []

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: check-added-large-files
      - id: check-merge-conflict
      - id: check-yaml
'''


def get_editorconfig_template() -> str:
    """Generate .editorconfig content."""
    return '''# EditorConfig - https://editorconfig.org
root = true

[*]
indent_style = space
indent_size = 4
end_of_line = lf
charset = utf-8
trim_trailing_whitespace = true
insert_final_newline = true

[*.py]
indent_size = 4

[*.{yaml,yml,json,toml}]
indent_size = 2

[*.md]
trim_trailing_whitespace = false

[Makefile]
indent_style = tab
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
        project_path / "app" / "urls.py": get_urls_template(project_name),
        project_path / "app" / "admin.py": get_admin_template(project_name),
        project_path / "migrations" / "__init__.py": get_migrations_init_template(),
        project_path / "README.md": get_readme_template(project_name),
        project_path / "requirements.txt": get_requirements_template(),
        project_path / "pyproject.toml": get_pyproject_template(project_name),
        project_path / ".gitignore": get_gitignore_template(),
        project_path / ".pre-commit-config.yaml": get_precommit_config_template(),
        project_path / ".editorconfig": get_editorconfig_template(),
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


# =============================================================================
# App Scaffold Templates (for startapp command)
# =============================================================================


def get_app_models_template(app_name: str) -> str:
    """Generate models.py content for a new app."""
    return f'''"""
Define Aksara ORM models for the '{app_name}' app here.

Example:
    from aksara import Model, fields

    class Item(Model):
        name = fields.String(max_length=100)
        description = fields.Text(nullable=True)
        is_active = fields.Boolean(default=True)

        class Meta:
            table_name = "{app_name}_items"
"""

from aksara import Model, fields


# Define your models here
'''


def get_app_views_template(app_name: str) -> str:
    """Generate views.py content for a new app."""
    return f'''"""
Define ModelViewSet classes and any manual routes for the '{app_name}' app here.

Example:
    from aksara import ModelViewSet, action, Request
    from .models import Item

    class ItemViewSet(ModelViewSet):
        model = Item
        prefix = "/api/{app_name}/items"
        tags = ["Items"]

        @action(detail=True, methods=["post"])
        async def activate(self, pk: str, request: Request):
            item = await self.model.objects.get(id=pk)
            item.is_active = True
            await item.save()
            return {{"status": "activated"}}
"""

from aksara import ModelViewSet, action, Request

# Import your models
# from .models import Item


# Define your ViewSets here
'''


def get_app_serializers_template(app_name: str) -> str:
    """Generate serializers.py content for a new app."""
    return f'''"""
Define ModelSerializer classes for the '{app_name}' app here.

Example:
    from aksara import ModelSerializer
    from .models import Item

    class ItemSerializer(ModelSerializer):
        class Meta:
            model = Item
            fields = ["id", "name", "description", "is_active", "created_at"]
            read_only_fields = ["id", "created_at"]
"""

from aksara import ModelSerializer

# Import your models
# from .models import Item


# Define your serializers here
'''


def get_app_api_template(app_name: str) -> str:
    """Generate api.py content for a new app (for auto-registration)."""
    return f'''"""
ViewSets for '{app_name}' app - Auto-registration supported.

ViewSets defined here can be auto-registered using:
    from aksara.api import include_all_app_viewsets
    include_all_app_viewsets(app)  # Auto-registers all ViewSets from app.api modules

Or use include_app_viewsets for a single app:
    from aksara.api import include_app_viewsets
    include_app_viewsets(app, "{app_name}")

Example:
    from aksara import ModelViewSet, action, Request
    from .models import Item

    class ItemViewSet(ModelViewSet):
        model = Item
        prefix = "/api/{app_name}/items"
        tags = ["Items"]

        @action(detail=True, methods=["post"])
        async def activate(self, pk: str, request: Request):
            item = await self.model.objects.get(id=pk)
            item.is_active = True
            await item.save()
            return {{"status": "activated"}}
"""

from aksara import ModelViewSet, action, Request

# Import your models
# from .models import Item


# Define your ViewSets here - they will be auto-discovered
'''


def get_app_init_template_for_startapp(app_name: str) -> str:
    """Generate __init__.py content for a new app."""
    return f'''"""
{app_name} - Aksara App

This app contains models, views, and serializers for {app_name} functionality.
"""
'''


def create_app_scaffold(app_name: str, base_path: Path) -> Dict[Path, str]:
    """
    Create the app scaffold directory structure and files.
    
    Args:
        app_name: Name of the app
        base_path: Base path where the app will be created (usually cwd)
        
    Returns:
        Dict mapping file paths to their content
    """
    app_path = base_path / app_name
    
    # Define all files to create
    files = {
        app_path / "__init__.py": get_app_init_template_for_startapp(app_name),
        app_path / "models.py": get_app_models_template(app_name),
        app_path / "views.py": get_app_views_template(app_name),
        app_path / "api.py": get_app_api_template(app_name),
        app_path / "serializers.py": get_app_serializers_template(app_name),
    }
    
    return files
