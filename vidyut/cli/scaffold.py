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

Run with:
    vidyut makemigrations --app app.models
    vidyut migrate
    vidyut createsuperuser  # Optional: create admin user
    vidyut run main:app --reload
"""

from vidyut import Vidyut
from settings import settings

# Import models to register with Vidyut
from app import models  # noqa: F401

# Import admin configuration
from app import admin  # noqa: F401

# Import URL configuration
from app.urls import register_routes


# Create the Vidyut app
app = Vidyut(
    database_url=settings.database_url,
    title=settings.app_title or "{project_name}",
    description="A Vidyut-powered async API",
    version="0.1.0",
    debug=settings.debug,
    # Admin is auto-enabled in debug mode, or set explicitly:
    # enable_admin=True,
)


# Register routes from app/urls.py
register_routes(app)


# Health check endpoint
@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint."""
    if app.db:
        await app.db.fetchval("SELECT 1")
        return {{
            "status": "healthy",
            "database": "connected",
        }}
    return {{"status": "unhealthy", "database": "not configured"}}


# =============================================================================
# Quick Start:
#   1. Define models in app/models.py
#   2. Run: vidyut makemigrations --app app.models
#   3. Run: vidyut migrate
#   4. Run: vidyut createsuperuser (optional)
#   5. Run: vidyut run main:app --reload
#   6. Open: http://localhost:8000/docs (API)
#   7. Open: http://localhost:8000/admin (Admin - debug mode)
# =============================================================================
'''


def get_settings_py_template(project_name: str) -> str:
    """Generate settings.py content."""
    return f'''"""
{project_name} - Settings

Vidyut settings with environment variable support.
Configure via .env file or environment variables.
"""

from dotenv import load_dotenv
load_dotenv()

from vidyut.conf import Settings as VidyutSettings


class Settings(VidyutSettings):
    """
    Project settings for {project_name}.

    Inherits from VidyutSettings which loads from environment:
      - DATABASE_URL: PostgreSQL connection string
      - VIDYUT_DEBUG: Enable debug mode (default: false)
      - VIDYUT_LOG_LEVEL: Logging level (default: INFO)
      - VIDYUT_APP_TITLE: Application title
      - VIDYUT_MIGRATIONS_DIR: Migrations directory (default: migrations)
    
    Add custom settings here as needed.
    """
    pass


# Global settings instance
settings = Settings()
'''


def get_env_template(project_name: str) -> str:
    """Generate .env content."""
    return f'''# {project_name} - Environment Configuration

# Database (PostgreSQL)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/{project_name}

# Debug mode - enables admin interface and detailed errors
VIDYUT_DEBUG=true

# Logging level (DEBUG, INFO, WARNING, ERROR)
VIDYUT_LOG_LEVEL=INFO

# App metadata
VIDYUT_APP_TITLE={project_name}

# Migrations directory
VIDYUT_MIGRATIONS_DIR=migrations
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
"""

from vidyut.contrib.admin import site

# from .models import User, Post


# Register models with admin
# site.register(User)
# site.register(Post)
'''


def get_models_template(project_name: str) -> str:
    """Generate app/models.py content."""
    return f'''"""
{project_name} - Models

Define your Vidyut ORM models here.
"""

from vidyut import Model, fields


# Example model - uncomment and customize:
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
# class Post(Model):
#     title = fields.String(max_length=200)
#     content = fields.Text()
#     author = fields.ForeignKey(User, on_delete="CASCADE")
#     published = fields.Boolean(default=False)
#
#     class Meta:
#         table_name = "posts"
'''


def get_serializers_template(project_name: str) -> str:
    """Generate app/serializers.py content."""
    return f'''"""
{project_name} - Serializers

Define your ModelSerializer classes for validation and response shaping.
"""

from vidyut import ModelSerializer

# from .models import User, Post


# Example serializers - uncomment and customize:
#
# class UserSerializer(ModelSerializer):
#     class Meta:
#         model = User
#         fields = ["id", "email", "name", "is_active", "created_at"]
#         read_only_fields = ["id", "created_at"]
#
#
# class PostSerializer(ModelSerializer):
#     class Meta:
#         model = Post
#         fields = ["id", "title", "content", "author_id", "published", "created_at"]
#         read_only_fields = ["id", "created_at"]
'''


def get_views_template(project_name: str) -> str:
    """Generate app/views.py content."""
    return f'''"""
{project_name} - Views

Define your ViewSets and custom actions here.
"""

from vidyut import ModelViewSet, action, Request
from vidyut.permissions import IsAuthenticated, IsAdminUser

# from .models import User, Post
# from .serializers import UserSerializer, PostSerializer


# Example ViewSets - uncomment and customize:
#
# class UserViewSet(ModelViewSet):
#     model = User
#     serializer_class = UserSerializer
#     prefix = "/api/users"
#     tags = ["Users"]
#     permission_classes = [IsAuthenticated]
#
#
# class PostViewSet(ModelViewSet):
#     model = Post
#     serializer_class = PostSerializer
#     prefix = "/api/posts"
#     tags = ["Posts"]
#
#     @action(detail=True, methods=["POST"])
#     async def publish(self, pk: str, request: Request):
#         """Publish a post."""
#         post = await self.model.objects.get(id=pk)
#         post.published = True
#         await post.save()
#         return {{"status": "published", "id": str(post.id)}}
'''


def get_urls_template(project_name: str) -> str:
    """Generate app/urls.py content."""
    return f'''"""
{project_name} - URL Configuration

Register your ViewSets here.
"""

from vidyut import include_viewset

# from .views import UserViewSet, PostViewSet


# URL Patterns - list your ViewSets here
urlpatterns = [
    # UserViewSet,
    # PostViewSet,
]


def register_routes(app):
    """Register all routes with the Vidyut app."""
    for viewset in urlpatterns:
        include_viewset(app, viewset)
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

```bash
# 1. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\\Scripts\\activate

# 2. Install dependencies
pip install -e .

# 3. Configure environment (edit .env with your database URL)
cp .env.example .env

# 4. Create database
createdb {project_name}

# 5. Define your models in app/models.py, then:
vidyut makemigrations --app app.models
vidyut migrate

# 6. Create admin user (optional)
vidyut createsuperuser

# 7. Start the server
vidyut run main:app --reload
```

## URLs

- **API Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc  
- **Admin**: http://localhost:8000/admin/ (debug mode)

## Project Structure

```
{project_name}/
├── app/
│   ├── models.py        # ORM models
│   ├── views.py         # ViewSets
│   ├── serializers.py   # Serializers
│   ├── urls.py          # Route registration
│   └── admin.py         # Admin registration
├── migrations/          # Database migrations
├── settings.py          # Configuration
├── main.py              # App entry point
└── .env                 # Environment variables
```

## CLI Commands

```bash
vidyut makemigrations --app app.models  # Generate migrations
vidyut migrate                           # Apply migrations
vidyut createsuperuser                   # Create admin user
vidyut run main:app --reload            # Run dev server
vidyut shell                             # Interactive shell
vidyut format                            # Format code (black)
vidyut lint                              # Lint code (ruff)
```

## Built with ⚡ Vidyut

https://github.com/nagarjuna-tella/vidyut
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
description = "A Vidyut-powered async API application"
requires-python = ">=3.11"
dependencies = [
    "vidyut>=0.3.20",
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
    return '''# Vidyut Pre-commit Configuration
# Install hooks: pre-commit install
# Run all hooks: vidyut precommit run

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
Define Vidyut ORM models for the '{app_name}' app here.

Example:
    from vidyut import Model, fields

    class Item(Model):
        name = fields.String(max_length=100)
        description = fields.Text(nullable=True)
        is_active = fields.Boolean(default=True)

        class Meta:
            table_name = "{app_name}_items"
"""

from vidyut import Model, fields


# Define your models here
'''


def get_app_views_template(app_name: str) -> str:
    """Generate views.py content for a new app."""
    return f'''"""
Define ModelViewSet classes and any manual routes for the '{app_name}' app here.

Example:
    from vidyut import ModelViewSet, action, Request
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

from vidyut import ModelViewSet, action, Request

# Import your models
# from .models import Item


# Define your ViewSets here
'''


def get_app_serializers_template(app_name: str) -> str:
    """Generate serializers.py content for a new app."""
    return f'''"""
Define ModelSerializer classes for the '{app_name}' app here.

Example:
    from vidyut import ModelSerializer
    from .models import Item

    class ItemSerializer(ModelSerializer):
        class Meta:
            model = Item
            fields = ["id", "name", "description", "is_active", "created_at"]
            read_only_fields = ["id", "created_at"]
"""

from vidyut import ModelSerializer

# Import your models
# from .models import Item


# Define your serializers here
'''


def get_app_api_template(app_name: str) -> str:
    """Generate api.py content for a new app (for auto-registration)."""
    return f'''"""
ViewSets for '{app_name}' app - Auto-registration supported.

ViewSets defined here can be auto-registered using:
    from vidyut.api import include_all_app_viewsets
    include_all_app_viewsets(app)  # Auto-registers all ViewSets from app.api modules

Or use include_app_viewsets for a single app:
    from vidyut.api import include_app_viewsets
    include_app_viewsets(app, "{app_name}")

Example:
    from vidyut import ModelViewSet, action, Request
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

from vidyut import ModelViewSet, action, Request

# Import your models
# from .models import Item


# Define your ViewSets here - they will be auto-discovered
'''


def get_app_init_template_for_startapp(app_name: str) -> str:
    """Generate __init__.py content for a new app."""
    return f'''"""
{app_name} - Vidyut App

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
