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
from vidyut.api import include_all_app_viewsets
from settings import settings

# Import models to register with Vidyut
from app import models  # noqa: F401

# Import URL configuration (Django-style)
from app.urls import register_routes


# Create the Vidyut app - database connection is automatic!
app = Vidyut(
    database_url=settings.database_url,
    title=settings.app_title or "{project_name}",
    description="Vidyut async API for {project_name}",
    version=settings.app_version or "0.3.15",
    # enable_admin=True,  # Uncomment to enable admin in production
)


# Register all routes from app/urls.py (explicit registration)
register_routes(app)

# Alternative: Auto-register all ViewSets from configured apps (v0.3.15)
# include_all_app_viewsets(app)  # Registers ViewSets from all apps in settings.apps


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    if app.db:
        await app.db.fetchval("SELECT 1")
        return {{
            "status": "healthy",
            "database": "connected",
            "version": settings.app_version or "0.3.15",
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

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, use environment variables directly

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

Define your Vidyut ORM models here.

Example:
    from vidyut import Model, fields

    class User(Model):
        email = fields.String(max_length=255, unique=True)
        name = fields.String(max_length=100, nullable=True)
        is_active = fields.Boolean(default=True)

        class Meta:
            table_name = "users"

Documentation: https://github.com/nagarjuna-tella/vidyut
"""

from vidyut import Model, fields


# Define your models here
'''


def get_serializers_template(project_name: str) -> str:
    """Generate app/serializers.py content."""
    return f'''"""
{project_name} - Serializers

Define your ModelSerializer classes here for validation and response shaping.

Example:
    from vidyut import ModelSerializer
    from .models import User

    class UserSerializer(ModelSerializer):
        class Meta:
            model = User
            fields = ["id", "email", "name", "is_active", "created_at"]
            read_only_fields = ["id", "created_at"]

Documentation: https://github.com/nagarjuna-tella/vidyut
"""

from vidyut import ModelSerializer

# Import your models
# from .models import User


# Define your serializers here
'''


def get_views_template(project_name: str) -> str:
    """Generate app/views.py content."""
    return f'''"""
{project_name} - Views

Define your ViewSets and custom actions here.
Route registration is in urls.py (Django-style).

Alternative: Use include_all_app_viewsets(app) in main.py to auto-register
all ViewSets defined in app/api.py modules.

Example:
    from vidyut import ModelViewSet, action, Request
    from .models import User

    class UserViewSet(ModelViewSet):
        model = User
        prefix = "/api/users"
        tags = ["Users"]

        @action(detail=True, methods=["post"])
        async def deactivate(self, pk: str, request: Request):
            user = await self.model.objects.get(id=pk)
            user.is_active = False
            await user.save()
            return {{"status": "deactivated"}}

Documentation: https://github.com/nagarjuna-tella/vidyut
"""

from vidyut import (
    Request,
    ModelViewSet,
    action,
)

# Import your models
# from .models import User


# Define your ViewSets here
'''


def get_urls_template(project_name: str) -> str:
    """Generate app/urls.py content."""
    return f'''"""
{project_name} - URL Configuration

Define your URL patterns here (Django-style).
ViewSets are registered via the `urlpatterns` list.

Example:
    from .views import UserViewSet, PostViewSet

    urlpatterns = [
        UserViewSet,
        PostViewSet,
    ]

Documentation: https://github.com/nagarjuna-tella/vidyut
"""

from vidyut import include_viewset

# Import your ViewSets
# from .views import UserViewSet


# URL Patterns - Add your ViewSets here
urlpatterns = [
    # Add your ViewSets here, e.g.:
    # UserViewSet,
]


def register_routes(app):
    """
    Register all routes with the Vidyut app.
    
    This is called from main.py to wire up all endpoints.
    """
    # Register ViewSets from urlpatterns
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

4. **Create models in `app/models.py`:**
   ```python
   from vidyut import Model, fields

   class User(Model):
       email = fields.String(max_length=255, unique=True)
       name = fields.String(max_length=100, nullable=True)
       is_active = fields.Boolean(default=True)

       class Meta:
           table_name = "users"
   ```

5. **Run migrations:**
   ```bash
   vidyut makemigrations --app app.models
   vidyut migrate
   ```

6. **Create admin superuser (optional):**
   ```bash
   vidyut createsuperuser
   ```

7. **Start the server:**
   ```bash
   vidyut run main:app --reload
   ```

8. **Open the API docs:**
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc
   - Admin (debug mode): http://localhost:8000/admin/

## Project Structure

```
{project_name}/
├── app/
│   ├── __init__.py
│   ├── models.py        # Vidyut ORM models
│   ├── views.py         # ViewSets with custom actions
│   ├── urls.py          # URL patterns (Django-style)
│   └── serializers.py   # ModelSerializer classes
├── migrations/          # Database migrations
├── settings.py          # VidyutSettings configuration
├── main.py              # Vidyut app entry point
├── .env                 # Environment variables
└── requirements.txt     # Python dependencies
```

## Admin Interface

Vidyut includes a Django-style admin interface (v0.3.15+).

**Enable admin:**
- Auto-enabled in debug mode (`VIDYUT_DEBUG=true`)
- Or set `enable_admin=True` in `Vidyut()` constructor

**Register models:**
```python
from vidyut.contrib.admin import site
from app.models import User

site.register(User)
```

**Create superuser:**
```bash
vidyut createsuperuser --email admin@example.com
```

## Example Endpoints

Once you define your models and ViewSets:

### Users API (example)
- `GET /api/users/` - List users (paginated)
- `POST /api/users/` - Create user
- `GET /api/users/{{id}}` - Get user
- `PATCH /api/users/{{id}}` - Update user
- `DELETE /api/users/{{id}}` - Delete user

### Health Check
- `GET /health` - Health check endpoint

## Built with Vidyut

⚡ [Vidyut](https://github.com/nagarjuna-tella/vidyut) - Async Postgres ORM for FastAPI
'''


def get_requirements_template() -> str:
    """Generate requirements.txt content."""
    return '''# Vidyut ORM (includes FastAPI, asyncpg, pydantic)
vidyut>=0.3.15

# Server
uvicorn[standard]>=0.24.0

# Environment variables
python-dotenv>=1.0.0

# Admin interface templates
jinja2>=3.0.0
'''


def get_pyproject_template(project_name: str) -> str:
    """Generate pyproject.toml content."""
    return f'''[project]
name = "{project_name}"
version = "0.1.0"
description = "A Vidyut-powered async API application"
requires-python = ">=3.11"
dependencies = [
    "vidyut>=0.3.18",
    "uvicorn[standard]>=0.24.0",
    "python-dotenv>=1.0.0",
    "jinja2>=3.0.0",
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
        project_path / "migrations" / "__init__.py": get_migrations_init_template(),
        project_path / "README.md": get_readme_template(project_name),
        project_path / "requirements.txt": get_requirements_template(),
        project_path / "pyproject.toml": get_pyproject_template(project_name),
        project_path / ".gitignore": get_gitignore_template(),
        # v0.3.18: Dev workflow files
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
