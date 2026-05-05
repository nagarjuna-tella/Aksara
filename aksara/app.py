"""
Aksara Application

Re-exports FastAPI with Aksara branding and auto-DB integration.
Core FastAPI functionality remains untouched.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import os
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Type, Union

# Re-export everything from FastAPI as-is
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    UploadFile,
    WebSocket,
    status,
)
from fastapi.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from aksara.db import Database
from aksara.apps import load_app_models
from aksara._version import __version__


# Aksara SVG logo (blue lightning bolt with gradient)
AKSARA_LOGO_SVG = '''data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%236366F1' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolygon points='13 2 3 14 12 14 11 22 21 10 12 10 13 2'/%3E%3C/svg%3E'''


class Aksara(FastAPI):
    """
    Aksara-enhanced FastAPI application.
    
    This is a thin wrapper that adds:
    - Automatic database lifecycle management
    - Auto-discovery of ModelViewSet classes
    - Aksara branding on startup
    - Pre-configured exception handlers for ORM errors
    - Optional admin interface (v0.3.15)
    
    All FastAPI functionality works exactly the same.
    
    Usage:
        from aksara import Aksara
        
        app = Aksara(database_url="postgresql://...")
        
        # Everything else is standard FastAPI
        @app.get("/")
        async def root():
            return {"hello": "world"}
        
    Auto-Discovery:
        # Automatically discovers and registers all ModelViewSet classes
        # from settings.apps (default: ["app"])
        
        app = Aksara(
            database_url="...",
            auto_discover_views=True,  # Default: True
        )
        
        # Or specify a single module
        app = Aksara(
            database_url="...",
            views_module="myapp.views",
        )
    
    Admin Interface (v0.3.15):
        # enable_admin=None (default): Auto-enable in debug mode if auth available
        # enable_admin=True: Always enable (requires auth contrib)
        # enable_admin=False: Never enable
        
        app = Aksara(
            database_url="...",
            enable_admin=True,  # Explicitly enable admin
        )
    """
    
    def __init__(
        self,
        database_url: Optional[str] = None,
        *,
        min_pool_size: int = 5,
        max_pool_size: int = 20,
        # Auto-discovery args
        auto_discover_views: bool = True,
        views_module: Optional[str] = None,
        # v0.3.13: Aksara middleware configuration
        middlewares: Optional[List[Tuple[Type[BaseHTTPMiddleware], Dict[str, Any]]]] = None,
        # v0.3.15: Admin interface
        enable_admin: Optional[bool] = None,
        # Standard FastAPI args
        debug: bool = False,
        title: str = "Aksara API",
        summary: Optional[str] = None,
        description: str = "",
        version: str = __version__,
        openapi_url: Optional[str] = "/openapi.json",
        openapi_tags: Optional[list[dict[str, Any]]] = None,
        docs_url: Optional[str] = "/docs",
        redoc_url: Optional[str] = "/redoc",
        swagger_ui_oauth2_redirect_url: Optional[str] = "/docs/oauth2-redirect",
        middleware: Optional[Sequence[Middleware]] = None,
        exception_handlers: Optional[dict[Any, Callable]] = None,
        on_startup: Optional[Sequence[Callable]] = None,
        on_shutdown: Optional[Sequence[Callable]] = None,
        lifespan: Optional[Callable] = None,
        **extra: Any,
    ):
        # Store database config
        self._database_url = database_url
        self._min_pool_size = min_pool_size
        self._max_pool_size = max_pool_size
        self._db: Optional[Database] = None
        
        # Store auto-discovery config
        self._auto_discover_views = auto_discover_views
        self._views_module = views_module
        
        # v0.3.15: Store admin config
        self.enable_admin = enable_admin
        self._debug = debug
        
        # v0.4.0: AI registry (initialized later)
        self.ai_registry = None
        self._task_worker = None
        
        # Store docs URLs for custom handlers
        self._docs_url = docs_url
        self._redoc_url = redoc_url
        self._openapi_url = openapi_url
        self._swagger_ui_oauth2_redirect_url = swagger_ui_oauth2_redirect_url
        
        # If user provides custom lifespan, wrap it with our DB lifecycle
        if lifespan is not None:
            wrapped_lifespan = self._wrap_lifespan(lifespan)
        elif database_url is not None:
            wrapped_lifespan = self._default_lifespan
        else:
            wrapped_lifespan = None
        
        # Initialize FastAPI with docs disabled (we'll add custom ones)
        super().__init__(
            debug=debug,
            title=title,
            summary=summary,
            description=description,
            version=version,
            openapi_url=openapi_url,
            openapi_tags=openapi_tags,
            docs_url=None,  # Disable default, we'll add custom
            redoc_url=None,  # Disable default, we'll add custom
            swagger_ui_oauth2_redirect_url=swagger_ui_oauth2_redirect_url,
            middleware=middleware,
            exception_handlers=exception_handlers,
            on_startup=on_startup,
            on_shutdown=on_shutdown,
            lifespan=wrapped_lifespan,
            **extra,
        )
        
        # v0.3.13: Register Aksara middlewares
        # Note: Middlewares are registered in reverse order because Starlette
        # wraps them like onion layers - last added is first executed
        if middlewares:
            for mw_class, options in reversed(middlewares):
                self.add_middleware(mw_class, **(options or {}))
        
        # v0.3.14: Auto-load models from configured apps
        # This ensures models are registered before any routes or migrations
        load_app_models()
        
        # Add custom Aksara-branded docs
        self._setup_custom_docs(docs_url, redoc_url, title)
        
        # Add welcome page at root
        self._setup_welcome_page(title, version)
        
        # Register ORM exception handlers
        self._register_orm_exceptions()
        
        # v0.3.17: Register debug-aware exception handlers
        self._register_debug_exception_handlers()
        
        # v0.3.15: Maybe mount admin interface
        self._maybe_mount_admin()

        # v0.5.45: Mount local media files automatically in debug mode
        self._maybe_mount_media()
        
        # v0.4.0: Initialize AI registry and endpoints
        self._setup_ai_registry()
        
        # Auto-discover and register ViewSets
        if self._auto_discover_views:
            self._auto_register_viewsets()
    
    @property
    def db(self) -> Optional[Database]:
        """Get the database instance."""
        return self._db

    @property
    def task_worker(self):
        """Get the background task worker, if enabled."""
        return self._task_worker

    async def _startup_runtime(self) -> None:
        """Start database-backed runtime services."""
        if not self._database_url:
            return

        self._db = Database(
            self._database_url,
            min_size=self._min_pool_size,
            max_size=self._max_pool_size,
        )
        await self._db.connect()

        from aksara.conf import settings
        if "aksara.contrib.auth" in settings.installed_apps:
            from aksara.contrib.auth.session import _ensure_sessions_table
            await _ensure_sessions_table(self._db)

        from aksara.model.base import finalize_relations
        finalize_relations()

        from aksara.contenttypes import clear_content_type_cache, sync_content_types
        clear_content_type_cache()
        await sync_content_types(self._db, prune_stale=True)

        if settings.tasks_enabled:
            from aksara.tasks import TaskWorker

            self._task_worker = TaskWorker(self._db)
            await self._task_worker.start()

        self._print_startup()

    async def _shutdown_runtime(self) -> None:
        """Stop database-backed runtime services."""
        if self._task_worker is not None:
            await self._task_worker.stop()
            self._task_worker = None

        if self._db is not None:
            await self._db.disconnect()
            self._db = None
            self._print_shutdown()
    
    def _maybe_mount_admin(self) -> None:
        """
        Mount admin interface based on enable_admin setting.
        
        v0.3.15: Admin mounting rules:
        - enable_admin=None (default):
          - If settings.debug == True and auth is available → mount /admin
          - Else → no admin
        - enable_admin=True:
          - Always mount /admin, requires auth contrib → or RuntimeError
        - enable_admin=False:
          - Never mount admin
        """
        from aksara.conf import settings
        
        # Check if auth contrib is available (including bcrypt dependency)
        auth_available = False
        auth_error = None
        try:
            from aksara.contrib.auth import User  # noqa: F401
            # Also verify bcrypt is available
            from aksara.contrib.auth.hashing import hash_password  # noqa: F401
            auth_available = True
        except ImportError as e:
            auth_error = str(e)
        
        if self.enable_admin is True:
            # Explicit enable: require auth
            if not auth_available:
                if auth_error and "bcrypt" in auth_error.lower():
                    raise RuntimeError(
                        "Aksara Admin requires bcrypt for password hashing. "
                        "Install with: pip install aksara[auth]"
                    )
                raise RuntimeError(
                    "Aksara Admin requires 'aksara.contrib.auth'. "
                    "Install with: pip install aksara[auth]"
                )
            from aksara.contrib.admin import include_admin
            include_admin(self)
        
        elif self.enable_admin is None:
            # Default: auto-enable in debug mode only if auth is available
            is_debug = self._debug or getattr(settings, "debug", False)
            if is_debug and auth_available:
                from aksara.contrib.admin import include_admin
                include_admin(self)
        
        # else: enable_admin is False → never mount admin

    def _maybe_mount_media(self) -> None:
        """Mount MEDIA_URL when filesystem storage is active in debug mode."""
        from aksara.conf import settings
        from aksara.storage import FileSystemStorage, get_default_storage

        is_debug = self._debug or getattr(settings, "debug", False)
        if not is_debug:
            return

        storage = get_default_storage()
        if not isinstance(storage, FileSystemStorage):
            return

        media_url = getattr(settings, "media_url", "/media/")
        mount_path = media_url.rstrip("/") or "/media"
        if mount_path == "/":
            return

        route_paths = {getattr(route, "path", None) for route in self.routes}
        if mount_path in route_paths:
            return

        self.mount(mount_path, StaticFiles(directory=str(storage.location)), name="aksara-media")
    
    def _setup_custom_docs(
        self,
        docs_url: Optional[str],
        redoc_url: Optional[str],
        title: str,
    ) -> None:
        """Setup custom Swagger UI and ReDoc with Aksara branding."""
        if docs_url:
            @self.get(docs_url, include_in_schema=False)
            async def custom_swagger_ui_html():
                return get_swagger_ui_html(
                    openapi_url=self._openapi_url or "/openapi.json",
                    title=f"{title} - Swagger UI",
                    oauth2_redirect_url=self._swagger_ui_oauth2_redirect_url,
                    swagger_favicon_url=AKSARA_LOGO_SVG,
                    swagger_ui_parameters={
                        "docExpansion": "list",
                        "defaultModelsExpandDepth": 1,
                        "deepLinking": True,
                        "displayRequestDuration": True,
                    },
                )
        
        if redoc_url:
            @self.get(redoc_url, include_in_schema=False)
            async def custom_redoc_html():
                return get_redoc_html(
                    openapi_url=self._openapi_url or "/openapi.json",
                    title=f"{title} - ReDoc",
                    redoc_favicon_url=AKSARA_LOGO_SVG,
                )
    
    def _setup_welcome_page(self, title: str, version: str) -> None:
        """Setup a welcome page at the root URL."""
        @self.get("/", include_in_schema=False)
        async def welcome_page():
            html_content = f"""
<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="icon" href="{AKSARA_LOGO_SVG}">
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
            --ring: #6366F1;
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
            flex-direction: column;
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
        .tagline {{
            font-size: 0.9375rem;
            color: var(--muted-foreground);
            margin-bottom: 0.25rem;
        }}
        .version {{
            font-size: 0.8125rem;
            color: var(--muted-foreground);
            margin-bottom: 2rem;
        }}

        .links {{
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
            margin-bottom: 2rem;
        }}
        .link {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
            padding: 0.75rem 1rem;
            border-radius: var(--radius);
            text-decoration: none;
            font-weight: 500;
            font-size: 0.875rem;
            background: var(--card);
            color: var(--foreground);
            border: 1px solid var(--border);
            box-shadow: var(--shadow-sm);
            transition: all 0.15s ease;
        }}
        .link:hover {{
            border-color: var(--primary);
            box-shadow: var(--shadow-md);
        }}
        .link svg {{
            width: 20px;
            height: 20px;
            color: var(--primary);
            flex-shrink: 0;
        }}
        .link span {{
            color: var(--muted-foreground);
            font-size: 0.8125rem;
            font-weight: 400;
            margin-left: auto;
        }}

        .footer {{
            font-size: 0.8125rem;
            color: var(--muted-foreground);
        }}
        .footer a {{
            color: var(--primary);
            text-decoration: none;
            font-weight: 500;
        }}
        .footer a:hover {{ text-decoration: underline; }}

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
        .theme-toggle:hover {{
            background: var(--muted);
            color: var(--foreground);
        }}
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
        <h1>{title}</h1>
        <p class="tagline">Async Postgres ORM for FastAPI</p>
        <p class="version">v{version}</p>
        <div class="links">
            <a href="/docs" class="link">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>
                API Documentation <span>/docs</span>
            </a>
            <a href="/redoc" class="link">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M16 13H8"/><path d="M16 17H8"/><path d="M10 9H8"/></svg>
                ReDoc <span>/redoc</span>
            </a>
        </div>
        <p class="footer">
            Powered by <a href="https://github.com/nagarjuna-tella/Aksara" target="_blank">Aksara</a>
        </p>
    </div>
</body>
</html>
"""
            return HTMLResponse(content=html_content)
    
    def _wrap_lifespan(self, user_lifespan: Callable):
        """Wrap user's lifespan with DB lifecycle."""
        @asynccontextmanager
        async def wrapped_lifespan(app: FastAPI):
            await self._startup_runtime()
            
            # Run user's lifespan
            async with user_lifespan(app):
                yield
            
            await self._shutdown_runtime()
        
        return wrapped_lifespan
    
    @asynccontextmanager
    async def _default_lifespan(self, app: FastAPI):
        """Default lifespan with DB management."""
        await self._startup_runtime()
        
        yield
        
        await self._shutdown_runtime()
    
    def _print_startup(self) -> None:
        """Print Aksara startup banner."""
        suppress_brand = os.environ.get("AKSARA_SUPPRESS_RUNTIME_BRAND") == "1"
        print()
        if not suppress_brand:
            print("  \033[33m⚡\033[0m \033[1mAksara\033[0m - Async Postgres ORM")
        print(f"  \033[32m✓\033[0m Database connected")
        print()
    
    def _print_shutdown(self) -> None:
        """Print shutdown message."""
        suppress_brand = os.environ.get("AKSARA_SUPPRESS_RUNTIME_BRAND") == "1"
        print()
        if not suppress_brand:
            print("  \033[33m⚡\033[0m \033[1mAksara\033[0m - Shutting down")
        print(f"  \033[32m✓\033[0m Database disconnected")
        print()
    
    def _register_orm_exceptions(self) -> None:
        """Register exception handlers for Aksara ORM errors."""
        from aksara.manager import DoesNotExist, MultipleObjectsReturned
        from aksara.exceptions import ValidationError, UniqueConstraintError, RestrictedError
        
        @self.exception_handler(DoesNotExist)
        async def handle_does_not_exist(request: Request, exc: DoesNotExist):
            return JSONResponse(
                status_code=404,
                content={"detail": str(exc)},
            )
        
        @self.exception_handler(MultipleObjectsReturned)
        async def handle_multiple_objects(request: Request, exc: MultipleObjectsReturned):
            return JSONResponse(
                status_code=500,
                content={"detail": str(exc)},
            )
        
        @self.exception_handler(UniqueConstraintError)
        async def handle_unique_constraint(request: Request, exc: UniqueConstraintError):
            return JSONResponse(
                status_code=409,
                content={
                    "detail": str(exc),
                    "field": exc.field_name,
                    "code": "unique_constraint_violated",
                },
            )
        
        @self.exception_handler(ValidationError)
        async def handle_validation_error(request: Request, exc: ValidationError):
            return JSONResponse(
                status_code=422,
                content={
                    "detail": str(exc),
                    "errors": exc.errors,
                    "code": "validation_error",
                },
            )
        
        @self.exception_handler(RestrictedError)
        async def handle_restricted_error(request: Request, exc: RestrictedError):
            return JSONResponse(
                status_code=409,
                content={
                    "detail": str(exc),
                    "model": exc.model_name,
                    "related_model": exc.related_model,
                    "related_count": exc.related_count,
                    "code": "delete_restricted",
                },
            )
    
    def _register_debug_exception_handlers(self) -> None:
        """
        Register debug-aware exception handlers.
        
        v0.3.17: Provides beautiful dark-mode error pages in debug mode
        with rich context including stacktrace, request details, and more.
        In production, shows clean JSON or minimal HTML.
        """
        from aksara.debug import register_debug_exception_handlers
        register_debug_exception_handlers(self)
    
    def _setup_ai_registry(self) -> None:
        """
        Initialize AI tool registry and mount AI endpoints.
        
        v0.4.0: AI Mode - exposes models and ViewSets as AI tools.
        v0.5.0: Also mounts Studio endpoints for IDE integration.
        """
        from aksara.ai import AiToolRegistry
        from aksara.ai.fastapi import router as ai_router
        from aksara.conf import settings
        
        # Initialize the registry
        self.ai_registry = AiToolRegistry()
        
        # Include AI endpoints (hidden from public OpenAPI docs)
        self.include_router(ai_router, include_in_schema=False)
        
        # v0.5.0: Include Studio endpoints
        if self._should_enable_studio():
            from aksara.studio.fastapi import router as studio_router
            self.include_router(studio_router, include_in_schema=False)
    
    def _should_enable_studio(self) -> bool:
        """
        Determine whether to enable Studio endpoints.
        
        v0.5.0: Studio endpoint rules:
        - If settings.enable_studio is False → never enable
        - If in production (debug=False):
          - Only enable if settings.studio_expose_in_production is True
        - Otherwise → enable
        """
        from aksara.conf import settings
        
        # Respect explicit disable
        if not settings.enable_studio:
            return False
        
        # In production, require explicit flag
        is_debug = self._debug or settings.debug
        if not is_debug and not settings.studio_expose_in_production:
            return False
        
        return True
    
    def _discover_ai_tools_from_viewsets(self, viewsets: list) -> None:
        """
        Discover AI tools from a list of ViewSet classes.
        
        Called after ViewSets are registered to populate the AI registry.
        
        Args:
            viewsets: List of ModelViewSet classes
        """
        if self.ai_registry is None:
            return
        
        from aksara.ai.registry import discover_tools_from_viewset
        
        for viewset_cls in viewsets:
            tools = discover_tools_from_viewset(viewset_cls)
            for tool in tools:
                self.ai_registry.register_tool(tool)
    
    def _auto_register_viewsets(self) -> None:
        """
        Auto-discover and register all ModelViewSet classes.
        
        Discovers ViewSets from:
        - views_module parameter (if specified)
        - settings.apps (if no views_module specified)
        """
        from aksara.core.discovery import auto_discover_viewsets
        from aksara.api.router import include_viewset
        
        # Discover all ViewSets
        viewsets = auto_discover_viewsets(views_module=self._views_module)
        
        if viewsets:
            # Create a router for discovered viewsets
            router = APIRouter()
            
            for viewset_cls in viewsets:
                include_viewset(router, viewset_cls)
            
            # Include the router in the app
            self.include_router(router)
            
            # v0.4.0: Discover AI tools from registered ViewSets
            self._discover_ai_tools_from_viewsets(viewsets)
    
    def discover_viewsets(self, views_module: Optional[str] = None) -> list:
        """
        Manually discover ViewSets from a module.
        
        Args:
            views_module: Optional module path to discover from.
                         If not provided, uses settings.apps.
        
        Returns:
            List of discovered ViewSet classes.
        """
        from aksara.core.discovery import auto_discover_viewsets
        return auto_discover_viewsets(views_module=views_module)
    
    def register_viewsets(self, viewsets: list, prefix: str = "") -> None:
        """
        Manually register a list of ViewSet classes.
        
        Args:
            viewsets: List of ModelViewSet classes to register.
            prefix: Optional URL prefix for all viewsets.
        """
        from aksara.api.router import include_viewset
        
        router = APIRouter(prefix=prefix)
        
        for viewset_cls in viewsets:
            include_viewset(router, viewset_cls)
        
        self.include_router(router)
        
        # v0.4.0: Discover AI tools from registered ViewSets
        self._discover_ai_tools_from_viewsets(viewsets)


# Re-export for convenience
__all__ = [
    # Aksara's enhanced FastAPI
    "Aksara",
    # Standard FastAPI exports (unchanged)
    "FastAPI",
    "APIRouter",
    "Request",
    "Response",
    "HTTPException",
    "Depends",
    "Query",
    "Path",
    "Header",
    "File",
    "Form",
    "UploadFile",
    "BackgroundTasks",
    "WebSocket",
    "status",
    # Responses
    "JSONResponse",
    "HTMLResponse",
    "PlainTextResponse",
    "RedirectResponse",
    "FileResponse",
    "StreamingResponse",
    # Extras
    "StaticFiles",
    "Jinja2Templates",
    "Middleware",
]
