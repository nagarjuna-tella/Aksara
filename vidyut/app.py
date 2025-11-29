"""
Vidyut Application

Re-exports FastAPI with Vidyut branding and auto-DB integration.
Core FastAPI functionality remains untouched.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, Callable, Optional, Sequence, Union

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

from vidyut.db import Database


class Vidyut(FastAPI):
    """
    Vidyut-enhanced FastAPI application.
    
    This is a thin wrapper that adds:
    - Automatic database lifecycle management
    - Vidyut branding on startup
    - Pre-configured exception handlers for ORM errors
    
    All FastAPI functionality works exactly the same.
    
    Usage:
        from vidyut import Vidyut
        
        app = Vidyut(database_url="postgresql://...")
        
        # Everything else is standard FastAPI
        @app.get("/")
        async def root():
            return {"hello": "world"}
    """
    
    def __init__(
        self,
        database_url: Optional[str] = None,
        *,
        min_pool_size: int = 5,
        max_pool_size: int = 20,
        # Standard FastAPI args
        debug: bool = False,
        title: str = "Vidyut API",
        summary: Optional[str] = None,
        description: str = "",
        version: str = "0.3.1",
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
        
        # If user provides custom lifespan, wrap it with our DB lifecycle
        if lifespan is not None:
            wrapped_lifespan = self._wrap_lifespan(lifespan)
        elif database_url is not None:
            wrapped_lifespan = self._default_lifespan
        else:
            wrapped_lifespan = None
        
        # Initialize FastAPI with all standard args
        super().__init__(
            debug=debug,
            title=title,
            summary=summary,
            description=description,
            version=version,
            openapi_url=openapi_url,
            openapi_tags=openapi_tags,
            docs_url=docs_url,
            redoc_url=redoc_url,
            swagger_ui_oauth2_redirect_url=swagger_ui_oauth2_redirect_url,
            middleware=middleware,
            exception_handlers=exception_handlers,
            on_startup=on_startup,
            on_shutdown=on_shutdown,
            lifespan=wrapped_lifespan,
            **extra,
        )
        
        # Register ORM exception handlers
        self._register_orm_exceptions()
    
    @property
    def db(self) -> Optional[Database]:
        """Get the database instance."""
        return self._db
    
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
            self._print_startup()
        
        yield
        
        if self._db:
            await self._db.disconnect()
            self._print_shutdown()
    
    def _print_startup(self) -> None:
        """Print Vidyut startup banner."""
        print()
        print("  \033[33m⚡\033[0m \033[1mVidyut\033[0m - Async Postgres ORM")
        print(f"  \033[32m✓\033[0m Database connected")
        print()
    
    def _print_shutdown(self) -> None:
        """Print shutdown message."""
        print()
        print("  \033[33m⚡\033[0m \033[1mVidyut\033[0m - Shutting down")
        print(f"  \033[32m✓\033[0m Database disconnected")
        print()
    
    def _register_orm_exceptions(self) -> None:
        """Register exception handlers for Vidyut ORM errors."""
        from vidyut.manager import DoesNotExist, MultipleObjectsReturned
        
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


# Re-export for convenience
__all__ = [
    # Vidyut's enhanced FastAPI
    "Vidyut",
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
