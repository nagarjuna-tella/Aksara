"""
FastAPI Integration

Aksara integration with FastAPI for database lifecycle and session management.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional, Callable, TYPE_CHECKING

from fastapi import FastAPI, Request

from aksara.db import Database, session_context

if TYPE_CHECKING:
    import asyncpg


def init_aksara(
    app: FastAPI,
    database_url: str,
    *,
    min_pool_size: int = 5,
    max_pool_size: int = 20,
) -> Database:
    """
    Initialize Aksara with a FastAPI application.
    
    This sets up the database connection pool and registers startup/shutdown
    handlers for proper lifecycle management.
    
    Args:
        app: FastAPI application instance
        database_url: PostgreSQL connection URL
        min_pool_size: Minimum connections in the pool
        max_pool_size: Maximum connections in the pool
        
    Returns:
        The Database instance
        
    Usage:
        app = FastAPI()
        init_aksara(app, "postgresql://user:pass@localhost/db")
    """
    db = Database(
        database_url=database_url,
        min_size=min_pool_size,
        max_size=max_pool_size,
    )
    
    @app.on_event("startup")
    async def startup():
        await db.connect()
    
    @app.on_event("shutdown")
    async def shutdown():
        await db.disconnect()
    
    return db


def create_lifespan(database_url: str, **db_kwargs) -> Callable:
    """
    Create a lifespan context manager for FastAPI.
    
    This is the recommended approach for FastAPI 0.109+.
    
    Args:
        database_url: PostgreSQL connection URL
        **db_kwargs: Additional arguments for Database
        
    Returns:
        Lifespan context manager function
        
    Usage:
        lifespan = create_lifespan("postgresql://user:pass@localhost/db")
        app = FastAPI(lifespan=lifespan)
    """
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        db = Database(database_url=database_url, **db_kwargs)
        await db.connect()
        try:
            yield
        finally:
            await db.disconnect()
    
    return lifespan


async def get_db_session() -> AsyncGenerator["asyncpg.Connection", None]:
    """
    FastAPI dependency for database session.
    
    Provides a database connection from the pool for the duration of the request.
    The connection is automatically returned to the pool after the request.
    
    Usage:
        from fastapi import Depends
        from aksara.fastapi import get_db_session
        
        @app.get("/users")
        async def list_users(session = Depends(get_db_session)):
            # Session is available here
            pass
    """
    db = Database.get_instance()
    async with session_context(db) as session:
        yield session


class AksaraMiddleware:
    """
    ASGI middleware for automatic session management.
    
    Wraps each request in a database session context, making the
    session available via get_session() throughout the request.
    
    Usage:
        app = FastAPI()
        app.add_middleware(AksaraMiddleware)
    """
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        
        try:
            db = Database.get_instance()
            async with session_context(db):
                await self.app(scope, receive, send)
        except RuntimeError:
            # Database not initialized, proceed without session
            await self.app(scope, receive, send)
