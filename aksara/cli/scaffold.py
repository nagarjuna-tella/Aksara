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
{project_name} - Aksara Application (v0.7.0)

An async PostgreSQL API with generated REST and optional MCP.

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
    Studio:    http://localhost:8000/studio/ui (enable explicitly in settings)
    Tool catalog: http://localhost:8000/ai/tools/mcp
    MCP protocol: http://localhost:8000/mcp/ (when enabled)
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
    description="Async PostgreSQL API with generated REST and optional MCP",
    version="0.1.0",
    debug=settings.debug,
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
            "admin": "/admin",
            "tool_catalog": "/ai/tools/mcp",
            "mcp": "/mcp/" if settings.mcp_enabled else "disabled",
            "studio": "/studio/ui" if settings.enable_studio else "disabled",
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
            <a href="/docs">REST API docs <span>/docs</span></a>
            <a href="/ai/tools/mcp">Tool inspection catalog <span>/ai/tools/mcp</span></a>
            <a href="/redoc">REST API reference <span>/redoc</span></a>
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
{project_name} - Settings (v0.7.0)

Environment variables configure Aksara. Use ``configure()`` only for explicit
Python overrides such as the installed-app list below.
"""

from dotenv import load_dotenv

load_dotenv()

from aksara.conf import configure, settings


INSTALLED_APPS = [
    "aksara.contrib.auth",
    "aksara.contrib.admin",
    "app",
]

# Aksara's global settings object is the single runtime configuration source.
# Precedence is: explicit configure() values, AKSARA_* environment variables,
# compatibility environment aliases such as DATABASE_URL, then defaults.
configure(installed_apps=INSTALLED_APPS)
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

# Stable MCP protocol server (opt in after adding server-side authentication)
AKSARA_MCP_ENABLED=false
AKSARA_MCP_TOKEN_AUDIENCE={project_name}

# Experimental provider-backed AI and Studio are opt in
AKSARA_AI_ENABLED=false
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

# Stable MCP protocol server (opt in after adding server-side authentication)
AKSARA_MCP_ENABLED=false
AKSARA_MCP_TOKEN_AUDIENCE={project_name}

# Experimental provider-backed AI and Studio are opt in
AKSARA_AI_ENABLED=false
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
Registered AI-exposed ViewSets appear in the /ai/tools/mcp inspection catalog
and, when MCP is enabled, as protocol tools at /mcp/.
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

An Aksara async PostgreSQL API scaffold. Stable core features are ready to
configure; provider-backed AI and Studio stay disabled until you opt in.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install "aksara-framework>=0.7.0" "uvicorn[standard]>=0.24.0" "pytest>=8.0.0" "pytest-asyncio>=0.21.0"
# Edit DATABASE_URL in .env, or run the interactive helper:
aksara dbsetup
# Define a model and ViewSet from the stubs in app/, then:
aksara makemigrations --app app.models
aksara migrate
aksara doctor launch-check
aksara dev
```

Run from the generated project directory. These commands install the framework
and local test tools; they do not package this application. The generated
`pyproject.toml` does not yet configure Hatch file selection for its `app/`
directory, so `pip install -e ".[dev]"` fails for a fresh project. Configure your
application packaging explicitly before using editable installation or building
an application wheel. This limitation does not require changing runtime defaults.

The runtime reads one global `aksara.conf.settings` object. Environment values
are loaded first; explicit `configure(...)` calls take precedence. The generated
`settings.py` uses `configure()` only to register installed apps.

## Build your first resource

The generated `app/` files are stubs. Follow the
[first-project tutorial](https://nagarjuna-tella.github.io/Aksara/getting-started/first-project/)
to add a model in `app/models.py`, its ViewSet in `app/views.py`, and the route
registration in `app/urls.py`. Serializers shape and validate API data;
`app/admin.py` registers the management interface. Commit generated migrations
with the model change and apply them before starting an upgraded application.

## Add identity before exposing data

The starter is a local development scaffold, not a complete authentication
integration. Verify credentials on the server and resolve a `Principal` before
adding protected routes. Put business permission rules alongside the relevant
ViewSets or durable action authorizers. A client-provided tenant ID is not proof
of membership. See the
[application boundary guide](https://nagarjuna-tella.github.io/Aksara/concepts/application-boundaries/).

## Test and diagnose

Install the test tools as shown above, add application tests in `tests/`,
then run `python -m pytest`. The scaffold does not generate an application test
suite. Use a dedicated PostgreSQL test database and test allowed and denied
requests, validation errors, and cross-tenant access when tenancy is enabled.
Never run destructive test fixtures against the production database.

`aksara doctor launch-check` diagnoses local setup. For deployment, follow the
[production guide](https://nagarjuna-tella.github.io/Aksara/tutorials/deployment/)
for separate migration/application roles, RLS, configuration and
`aksara doctor production-check --release`. Do not enable optional AI or Studio
features solely to remove local development recommendations.

## Add background execution when needed

Ordinary tasks queue application jobs. Durable Operations additionally retain
accepted work, ownership and current reauthorization across retries and worker
loss. Both need explicit application registration and worker supervision;
creating this project does not start a durable worker. Start with the
[durable operations guide](https://nagarjuna-tella.github.io/Aksara/advanced/durable-operations/)
when that recovery contract is necessary. MCP is an optional consumer of the
backend and can be added later.

## Surfaces

| Surface | Purpose | Default |
| --- | --- | --- |
| `/docs` | Generated REST OpenAPI | enabled |
| `/admin/` | Admin interface in debug mode | enabled for local development |
| `/ai/tools/mcp` | HTTP JSON inspection catalog for generated tool metadata | enabled |
| `/mcp/` | MCP Streamable HTTP protocol endpoint for official clients | disabled |
| `/studio/ui` | Experimental Studio UI | disabled |

`/ai/tools/mcp` is not an MCP transport. Before enabling `/mcp/`, add trusted
server-side authentication that resolves each bearer credential to a
`Principal`, then set `AKSARA_MCP_ENABLED=true`. Follow the canonical
[MCP quickstart](https://nagarjuna-tella.github.io/Aksara/getting-started/mcp/).

Provider-backed AI and Studio are experimental. Enable them only after reading
their configuration and security guidance:

```dotenv
AKSARA_AI_ENABLED=true
AKSARA_ENABLE_STUDIO=true
```

Studio also requires a secret token and production exposure policy. See `.env`
for the generated local token and current defaults.

## Project structure

```text
{project_name}/
├── app/                 # model, serializer, ViewSet, route, and admin stubs
├── migrations/          # generated migration files
├── settings.py          # global Settings/configure path
├── main.py              # application entry point
├── .env                 # local environment values; do not commit
└── .env.example         # documented environment names
```

Built with [Aksara](https://github.com/nagarjuna-tella/Aksara).
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
description = "Async PostgreSQL API with generated REST and optional MCP"
requires-python = ">=3.11"
dependencies = [
    "aksara-framework>=0.7.0",
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
