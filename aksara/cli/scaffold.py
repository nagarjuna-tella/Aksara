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
{project_name} - Aksara Application (v0.5.49)

A modern async API with Admin, Studio, and AI Mode built-in.

Quick Start:
    aksara dbsetup                       # Configure PostgreSQL
    aksara makemigrations --app app.models
    aksara migrate
    aksara createsuperuser  # Optional: create admin user
    aksara dev              # Uses main:app by default

Endpoints:
    Welcome:   http://localhost:8000/
    API Docs:  http://localhost:8000/docs
    Admin:     http://localhost:8000/admin (debug mode)
    Studio:    http://localhost:8000/studio/ui
    AI Tools:  http://localhost:8000/ai/tools
"""

import importlib
from pathlib import Path
from aksara import Aksara, __version__ as aksara_version
from aksara.middleware.request_id import RequestIDMiddleware
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
    description="AI-native backend — REST API, MCP tools, Studio",
    version="0.1.0",
    debug=settings.debug,
    enable_admin=settings.enable_admin,
    # Middlewares (request ID, logging)
    middlewares=[
        (RequestIDMiddleware, {{}}),
        (LoggingMiddleware, {{}}),
    ],
)


# Register routes from app/urls.py
register_routes(app)


# =============================================================================
# Welcome Page (loaded from static/welcome.html)
# =============================================================================

_WELCOME_HTML_PATH = Path(__file__).parent / "static" / "welcome.html"


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def welcome():
    """Welcome page — serves static/welcome.html."""
    if _WELCOME_HTML_PATH.exists():
        return _WELCOME_HTML_PATH.read_text()
    return HTMLResponse(f"<h1>{project_name} is running on Aksara {{aksara_version}}</h1>")


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


def get_welcome_html_template(project_name: str) -> str:
    """Generate static/welcome.html content."""
    return f'''<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{project_name} — Aksara</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        :root {{
            --primary: #6366F1;
            --primary-hover: #4F46E5;
            --background: #FAFAFA;
            --foreground: #09090B;
            --card: #FFFFFF;
            --muted: #F4F4F5;
            --muted-foreground: #71717A;
            --border: #E4E4E7;
            --radius: 0.5rem;
            --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
            --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
            --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
        }}

        [data-theme="dark"] {{
            --background: #09090B;
            --foreground: #FAFAFA;
            --card: #18181B;
            --muted: #27272A;
            --muted-foreground: #A1A1AA;
            --border: #27272A;
            --primary: #818CF8;
            --primary-hover: #6366F1;
        }}

        body {{
            font-family: var(--font-sans);
            background: var(--background);
            color: var(--foreground);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            line-height: 1.5;
            -webkit-font-smoothing: antialiased;
        }}

        .container {{
            text-align: center;
            padding: 2rem;
            max-width: 480px;
            width: 100%;
        }}

        .logo-wrap {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 72px;
            height: 72px;
            border-radius: 1rem;
            background: var(--muted);
            margin-bottom: 1.5rem;
        }}
        .logo-wrap svg {{
            width: 36px;
            height: 36px;
            color: var(--primary);
        }}

        h1 {{
            font-size: 1.875rem;
            font-weight: 700;
            letter-spacing: -0.03em;
            margin-bottom: 0.25rem;
            color: var(--foreground);
        }}
        .version {{ color: var(--muted-foreground); font-size: 0.875rem; margin-bottom: 0.25rem; }}
        .success {{ color: #10B981; font-size: 0.9375rem; margin-bottom: 2rem; font-weight: 500; }}

        .links {{
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
            margin-bottom: 2rem;
        }}
        .links a {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
            background: var(--card);
            padding: 0.75rem 1rem;
            border-radius: var(--radius);
            color: var(--foreground);
            text-decoration: none;
            border: 1px solid var(--border);
            box-shadow: var(--shadow-sm);
            font-weight: 500;
            font-size: 0.875rem;
            transition: all 0.15s ease;
        }}
        .links a:hover {{ border-color: var(--primary); box-shadow: var(--shadow-md); }}
        .links a span {{ color: var(--muted-foreground); font-size: 0.8125rem; font-weight: 400; margin-left: auto; }}

        .note {{
            color: var(--muted-foreground);
            font-size: 0.8125rem;
            padding-top: 1rem;
            border-top: 1px solid var(--border);
        }}
        .note code {{
            background: var(--muted);
            padding: 0.125rem 0.375rem;
            border-radius: 0.25rem;
            font-size: 0.8125rem;
        }}

        .theme-toggle {{
            position: fixed;
            top: 1rem;
            right: 1rem;
            width: 36px;
            height: 36px;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 1px solid var(--border);
            border-radius: 0.375rem;
            background: var(--card);
            color: var(--muted-foreground);
            cursor: pointer;
            transition: all 0.15s ease;
        }}
        .theme-toggle:hover {{ background: var(--muted); color: var(--foreground); }}
        .theme-toggle svg {{ width: 16px; height: 16px; }}
        [data-theme="dark"] .icon-sun {{ display: none; }}
        [data-theme="light"] .icon-moon {{ display: none; }}
    </style>
    <script>
        (function() {{
            var t = localStorage.getItem('aksara-theme');
            if (t === 'dark' || (!t && window.matchMedia('(prefers-color-scheme: dark)').matches)) {{
                document.documentElement.setAttribute('data-theme', 'dark');
            }}
        }})();
    </script>
</head>
<body>
    <button class="theme-toggle" onclick="var d=document.documentElement,n=d.getAttribute('data-theme')==='dark'?'light':'dark';d.setAttribute('data-theme',n);localStorage.setItem('aksara-theme',n)">
        <svg class="icon-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>
        <svg class="icon-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
    </button>

    <div class="container">
        <div class="logo-wrap">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
            </svg>
        </div>
        <h1>{project_name}</h1>
        <p class="version">Powered by Aksara</p>
        <p class="success">Your project is running</p>
        <div class="links">
            <a href="/admin/">Admin Panel <span>/admin/</span></a>
            <a href="/studio/ui">Studio <span>/studio/ui</span></a>
            <a href="/api/posts/">API <span>/api/posts/</span></a>
            <a href="/docs">API Docs <span>/docs</span></a>
            <a href="/ai/tools">AI Tools <span>/ai/tools</span></a>
        </div>
        <p class="note">
            Edit <code>static/welcome.html</code> to customize this page.
        </p>
    </div>
</body>
</html>
'''


def get_settings_py_template(project_name: str) -> str:
    """Generate settings.py content."""
    return f'''"""
{project_name} - Settings (v0.5.49)

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
    # NOTE: Set AKSARA_STUDIO_SECRET_TOKEN in .env before enabling
    "ENABLE_STUDIO": False,  # Mount /studio/* endpoints (requires AKSARA_STUDIO_SECRET_TOKEN)
    "STUDIO_UI_ENABLED": True,  # Enable /studio/ui dashboard
    "STUDIO_ALLOWED_ORIGINS": [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    
    # Security (v0.5.38+)
    "COOKIE_SECURE": True,         # Secure flag on session cookies
    "ADMIN_CSRF_ENABLED": True,    # CSRF protection for admin forms
    "ADMIN_RATE_LIMIT_ENABLED": True,  # Rate limiting on admin login
    
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
    enable_studio: bool = AKSARA.get("ENABLE_STUDIO", False)
    studio_ui_enabled: bool = AKSARA.get("STUDIO_UI_ENABLED", True)
    studio_allowed_origins: list = AKSARA.get("STUDIO_ALLOWED_ORIGINS", [])
    # v0.5.38+: Studio requires a secret token when enabled
    # Set AKSARA_STUDIO_SECRET_TOKEN in .env or provide via AKSARA dict
    studio_secret_token: str | None = AKSARA.get("STUDIO_SECRET_TOKEN", None)
    
    # Security (v0.5.38+)
    cookie_secure: bool = AKSARA.get("COOKIE_SECURE", True)
    admin_csrf_enabled: bool = AKSARA.get("ADMIN_CSRF_ENABLED", True)
    admin_rate_limit_enabled: bool = AKSARA.get("ADMIN_RATE_LIMIT_ENABLED", True)
    
    # AI Mode
    ai_enabled: bool = AKSARA.get("AI_MODE_ENABLED", True)
    ai_debug_enabled: bool = AKSARA.get("AI_DEBUG_ENABLED", True)


# Global settings instance
settings = Settings()
'''


def get_env_template(project_name: str, studio_token: str | None = None) -> str:
    """Generate .env content. Pass studio_token to reuse a pre-generated token."""
    import secrets
    if studio_token is None:
        studio_token = secrets.token_urlsafe(32)

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

# Studio (disabled by default — set to true and configure a secret token to enable)
AKSARA_ENABLE_STUDIO=false
AKSARA_STUDIO_SECRET_TOKEN={studio_token}
# Disable studio auth requirement in development (set to true in production)
AKSARA_STUDIO_REQUIRE_AUTH=false

# Security Settings (v0.5.38+)
# Uncomment to override defaults:
# AKSARA_COOKIE_SECURE=true
# AKSARA_ADMIN_CSRF_ENABLED=true
# AKSARA_ADMIN_RATE_LIMIT_ENABLED=true
# AKSARA_ADMIN_RATE_LIMIT_REQUESTS=20
# AKSARA_ADMIN_RATE_LIMIT_WINDOW_SECONDS=60
# AKSARA_AI_AGENT_TOKEN=your-token-here
'''


def get_env_example_template(project_name: str) -> str:
    """Generate .env.example content with placeholder token (safe to commit)."""
    return f'''# {project_name} - Environment Configuration (example — copy to .env and fill in values)

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

# Studio (disabled by default — set to true and configure a secret token to enable)
AKSARA_ENABLE_STUDIO=false
AKSARA_STUDIO_SECRET_TOKEN=your-secret-token-here
# Disable studio auth requirement in development (set to true in production)
AKSARA_STUDIO_REQUIRE_AUTH=false

# Security Settings (v0.5.38+)
# Uncomment to override defaults:
# AKSARA_COOKIE_SECURE=true
# AKSARA_ADMIN_CSRF_ENABLED=true
# AKSARA_ADMIN_RATE_LIMIT_ENABLED=true
# AKSARA_ADMIN_RATE_LIMIT_REQUESTS=20
# AKSARA_ADMIN_RATE_LIMIT_WINDOW_SECONDS=60
# AKSARA_AI_AGENT_TOKEN=your-token-here
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

# Add admin registrations here.
#
# Example:
#
# from aksara.contrib.admin import site, ModelAdmin
# from .models import Post
#
# class PostAdmin(ModelAdmin):
#     list_display = ["title", "is_published", "created_at"]
#     list_filter = ["is_published"]
#     search_fields = ["title", "content"]
#
# site.register(Post, PostAdmin)
'''


def get_models_template(project_name: str) -> str:
    """Generate app/models.py content."""
    return f'''"""
{project_name} - Models

Define your Aksara ORM models here.
Models are auto-discovered from INSTALLED_APPS.
"""

# Define your domain models here.
#
# Built-in authentication already provides a concrete user model via
# `aksara.contrib.auth.User` (table: `aksara_users`), so you do not need to
# create a local `User` model just to get started.
#
# Example model (uncomment and adapt to create your first model):
#
# from aksara import Model, fields
#
# class Post(Model):
#     title = fields.String(max_length=200, ai_description="Post title")
#     content = fields.Text(nullable=True)
#     is_published = fields.Boolean(default=False)
#     view_count = fields.Integer(default=0)
#     tags = fields.JSON(default=list)
#     created_at = fields.DateTime(auto_now_add=True)
#     updated_at = fields.DateTime(auto_now=True)
#     ai_agent_exposed = True
#
#     class Meta:
#         table_name = "posts"
#         ai_name = "Post"
'''


def get_serializers_template(project_name: str) -> str:
    """Generate app/serializers.py content."""
    return f'''"""
{project_name} - Serializers

Define your ModelSerializer classes for validation and response shaping.
"""

# Define your serializers here.
#
# Example:
#
# from aksara import ModelSerializer
# from .models import Post
#
# class PostSerializer(ModelSerializer):
#     class Meta:
#         model = Post
#         fields = ["id", "title", "content", "is_published", "created_at", "updated_at"]
#         read_only_fields = ["id", "created_at", "updated_at"]
'''


def get_views_template(project_name: str) -> str:
    """Generate app/views.py content."""
    return f'''"""
{project_name} - Views

Define your ViewSets and custom actions here.
ViewSets are auto-discovered and exposed as AI tools at /ai/tools.
"""

# Define your ViewSets here.
#
# Example (uncomment and adapt to create your first ViewSet):
#
# from aksara import ModelViewSet, action, Request
# from .models import Post
# from .serializers import PostSerializer
#
# class PostViewSet(ModelViewSet):
#     model = Post
#     prefix = "/api/posts"
#     tags = ["Posts"]
#     ai_exposed = True
#     list_serializer_class = PostSerializer
#     retrieve_serializer_class = PostSerializer
#     create_serializer_class = PostSerializer
#     update_serializer_class = PostSerializer
#
#     @action(detail=True, methods=["POST"], ai_exposed=True)
#     async def publish(self, request: Request, id: str):
#         post = await self.model.objects.get(id=id)
#         post.is_published = True
#         await post.save()
#         return {{"status": "published"}}
#
#     @action(detail=True, methods=["POST"])
#     async def increment_views(self, request: Request, id: str):
#         post = await self.model.objects.get(id=id)
#         post.view_count = (post.view_count or 0) + 1
#         await post.save()
#         return {{"view_count": post.view_count}}
'''


def get_urls_template(project_name: str) -> str:
    """Generate app/urls.py content."""
    return f'''"""
{project_name} - URL Configuration

Register your ViewSets here.
"""

from aksara import include_viewset


# Import your ViewSets here, then add them to urlpatterns.
#
# Example:
#
# from .views import PostViewSet


urlpatterns = [
    # PostViewSet,
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

# 5. Define your models in app/models.py, then run migrations
aksara makemigrations --app app.models
aksara migrate

# 6. Create admin user (optional)
aksara createsuperuser

# 7. Start the server
aksara dev
```

> **Tip:** If you get "uvicorn not installed" errors, run `python -m aksara dev` instead of `aksara dev` to ensure you're using your virtual environment's Python.

## URLs

| URL | Description |
|-----|-------------|
| http://localhost:8000/docs | API Documentation (Swagger UI) |
| http://localhost:8000/redoc | API Documentation (ReDoc) |
| http://localhost:8000/admin | Admin Interface (debug mode) |
| http://localhost:8000/studio/ui | Studio Dashboard (disabled by default — see below) |
| http://localhost:8000/api/posts | Posts API |
| http://localhost:8000/ai/tools | AI Tools Discovery |
| http://localhost:8000/health | Health Check |

## What's Included

This project comes pre-configured with:

- **Post model stub** - Commented example in `app/models.py` (uncomment to activate)
- **PostViewSet stub** - Commented example in `app/views.py` with `@action` examples
- **Admin stub** - Commented example in `app/admin.py`
- **Studio** - Dashboard at /studio/ui (disabled by default — see below)
- **AI Mode** - ViewSets exposed as AI tools at /ai/tools
- **Middleware** - Request ID & logging
- **Pre-commit** - Code formatting hooks

## Project Structure

```
{project_name}/
├── app/
│   ├── models.py        # Define your models here (Post example in comments)
│   ├── views.py         # Define your ViewSets here (PostViewSet example in comments)
│   ├── serializers.py   # Define your serializers here (PostSerializer example in comments)
│   ├── urls.py          # Route registration
│   └── admin.py         # Admin registrations (Post example in comments)
├── migrations/          # Database migrations
├── settings.py          # Configuration (AKSARA dict)
├── main.py              # App entry point
├── .env                 # Environment variables
└── .pre-commit-config.yaml  # Pre-commit hooks
```

## CLI Commands

```bash
# Development
aksara dev                     # Start dev server (uses main:app by default)
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

## Enabling Studio

Studio is disabled by default to avoid accidental exposure. A secret token was
already generated for you when you ran `aksara startproject` — it's in your `.env`:

```
AKSARA_STUDIO_SECRET_TOKEN=<already set>
```

To turn Studio on, open `settings.py` and change:

```python
"ENABLE_STUDIO": True,   # was False
```

Then restart the server. Studio will be available at http://localhost:8000/studio/ui.

Need a fresh token? Generate one with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Paste the output into `.env` as `AKSARA_STUDIO_SECRET_TOKEN=<value>`.

## Configuration

Edit `settings.py` to customize:

```python
AKSARA = {{
    "ENABLE_ADMIN": True,       # /admin
    "ENABLE_STUDIO": False,     # /studio/* (see Enabling Studio above)
    "AI_MODE_ENABLED": True,    # /ai/*
}}
```

## Built with ⚡ Aksara

https://github.com/nagarjuna-tella/Aksara
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
description = "AI-native backend — REST API, MCP tools, Studio"
requires-python = ">=3.11"
dependencies = [
    "aksara>=0.5.49",
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
    import secrets as _secrets
    project_path = base_path / project_name
    studio_token = _secrets.token_urlsafe(32)

    # Define all files to create
    files = {
        project_path / "main.py": get_main_py_template(project_name),
        project_path / "settings.py": get_settings_py_template(project_name),
        project_path / ".env": get_env_template(project_name, studio_token=studio_token),
        project_path / ".env.example": get_env_example_template(project_name),
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
        project_path / "static" / "welcome.html": get_welcome_html_template(project_name),
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


def get_app_admin_template(app_name: str) -> str:
    """Generate admin.py content for a new app."""
    capitalized = app_name.capitalize()
    return f'''"""
{capitalized} - Admin Configuration

Register your models with the admin interface here.
Admin is available at /admin when debug=True or enable_admin=True.
"""

from aksara.contrib.admin import site, ModelAdmin

# Import your models
# from .models import MyModel


# =============================================================================
# Example admin registration:
#
# class MyModelAdmin(ModelAdmin):
#     list_display = ["name", "created_at"]
#     list_filter = ["is_active"]
#     search_fields = ["name"]
#
# site.register(MyModel, MyModelAdmin)
# =============================================================================
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
        app_path / "serializers.py": get_app_serializers_template(app_name),
        app_path / "admin.py": get_app_admin_template(app_name),
    }
    
    return files
