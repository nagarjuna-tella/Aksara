"""
Aksara Application

Re-exports FastAPI with Aksara branding and auto-DB integration.
Core FastAPI functionality remains untouched.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
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
AKSARA_LOGO_SVG = '''data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Cdefs%3E%3ClinearGradient id='g' x1='0%25' y1='0%25' x2='0%25' y2='100%25'%3E%3Cstop offset='0%25' style='stop-color:%234DA8FF'/%3E%3Cstop offset='100%25' style='stop-color:%231E90FF'/%3E%3C/linearGradient%3E%3C/defs%3E%3Cpolygon points='55,5 25,45 45,45 20,95 75,40 50,40 70,5' fill='url(%23g)'/%3E%3C/svg%3E'''


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
        
        # v0.4.0: Initialize AI registry and endpoints
        self._setup_ai_registry()
        
        # Auto-discover and register ViewSets
        if self._auto_discover_views:
            self._auto_register_viewsets()
    
    @property
    def db(self) -> Optional[Database]:
        """Get the database instance."""
        return self._db
    
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
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="icon" href="{AKSARA_LOGO_SVG}">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #0f0f23 0%, #1a1a2e 50%, #16213e 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #fff;
        }}
        .container {{
            text-align: center;
            padding: 2rem;
        }}
        .logo {{
            width: 120px;
            height: 120px;
            margin-bottom: 1.5rem;
            filter: drop-shadow(0 0 30px rgba(77, 168, 255, 0.5));
            animation: pulse 2s ease-in-out infinite;
        }}
        @keyframes pulse {{
            0%, 100% {{ transform: scale(1); }}
            50% {{ transform: scale(1.05); }}
        }}
        h1 {{
            font-size: 3rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
            background: linear-gradient(90deg, #4DA8FF, #1E90FF);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        .tagline {{
            font-size: 1.2rem;
            color: #888;
            margin-bottom: 2rem;
        }}
        .version {{
            font-size: 0.9rem;
            color: #666;
            margin-bottom: 2rem;
        }}
        .links {{
            display: flex;
            gap: 1rem;
            justify-content: center;
            flex-wrap: wrap;
        }}
        .link {{
            display: inline-block;
            padding: 0.75rem 1.5rem;
            border-radius: 8px;
            text-decoration: none;
            font-weight: 500;
            transition: all 0.3s ease;
        }}
        .link-primary {{
            background: linear-gradient(90deg, #4DA8FF, #1E90FF);
            color: #fff;
        }}
        .link-primary:hover {{
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(77, 168, 255, 0.3);
        }}
        .link-secondary {{
            background: rgba(255, 255, 255, 0.1);
            color: #fff;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }}
        .link-secondary:hover {{
            background: rgba(255, 255, 255, 0.15);
            transform: translateY(-2px);
        }}
        .footer {{
            margin-top: 3rem;
            font-size: 0.85rem;
            color: #555;
        }}
        .footer a {{
            color: #4DA8FF;
            text-decoration: none;
        }}
    </style>
</head>
<body>
    <div class="container">
        <svg class="logo" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
            <defs>
                <linearGradient id="bolt-gradient" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" style="stop-color:#4DA8FF"/>
                    <stop offset="100%" style="stop-color:#1E90FF"/>
                </linearGradient>
            </defs>
            <polygon points="55,5 25,45 45,45 20,95 75,40 50,40 70,5" fill="url(#bolt-gradient)"/>
        </svg>
        <h1>{title}</h1>
        <p class="tagline">⚡ Async Postgres ORM for FastAPI</p>
        <p class="version">v{version}</p>
        <div class="links">
            <a href="/docs" class="link link-primary">📚 API Documentation</a>
            <a href="/redoc" class="link link-secondary">📖 ReDoc</a>
        </div>
        <p class="footer">
            Powered by <a href="https://github.com/nagarjuna-tella/aksara" target="_blank">Aksara</a>
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
            # Start DB
            if self._database_url:
                self._db = Database(
                    self._database_url,
                    min_size=self._min_pool_size,
                    max_size=self._max_pool_size,
                )
                await self._db.connect()
                
                # Finalize relations for reverse access
                from aksara.model.base import finalize_relations
                finalize_relations()
                
                self._print_startup()
            
            # Run user's lifespan
            async with user_lifespan(app):
                yield
            
            # Shutdown DB
            if self._db:
                await self._db.disconnect()
                self._print_shutdown()
        
        return wrapped_lifespan
    
    @asynccontextmanager
    async def _default_lifespan(self, app: FastAPI):
        """Default lifespan with DB management."""
        if self._database_url:
            self._db = Database(
                self._database_url,
                min_size=self._min_pool_size,
                max_size=self._max_pool_size,
            )
            await self._db.connect()
            
            # Finalize relations for reverse access
            from aksara.model.base import finalize_relations
            finalize_relations()
            
            self._print_startup()
        
        yield
        
        if self._db:
            await self._db.disconnect()
            self._print_shutdown()
    
    def _print_startup(self) -> None:
        """Print Aksara startup banner."""
        print()
        print("  \033[33m⚡\033[0m \033[1mAksara\033[0m - Async Postgres ORM")
        print(f"  \033[32m✓\033[0m Database connected")
        print()
    
    def _print_shutdown(self) -> None:
        """Print shutdown message."""
        print()
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
        """
        from aksara.ai import AiToolRegistry
        from aksara.ai.fastapi import router as ai_router
        
        # Initialize the registry
        self.ai_registry = AiToolRegistry()
        
        # Include AI endpoints
        self.include_router(ai_router)
    
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
