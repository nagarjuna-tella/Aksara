"""
Admin Mount Helper

Helper function to mount admin routes on a FastAPI/Vidyut app.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

if TYPE_CHECKING:
    from fastapi import FastAPI


class AdminSessionMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle session-based authentication for admin.
    
    Reads session_token cookie and populates request.state.user.
    """
    
    async def dispatch(self, request: Request, call_next):
        # Initialize user as None
        if not hasattr(request.state, "user"):
            request.state.user = None
        
        # Try to get user from session cookie
        token = request.cookies.get("session_token")
        if token and request.state.user is None:
            try:
                from vidyut.contrib.auth import get_user_from_session_token
                
                db = getattr(request.app, "db", None)
                if db:
                    user = await get_user_from_session_token(db, token)
                    if user:
                        request.state.user = user
            except Exception:
                pass  # Session lookup failed, continue without user
        
        return await call_next(request)


def include_admin(app: "FastAPI", prefix: str = "/admin") -> None:
    """
    Mount the admin interface on a FastAPI/Vidyut application.
    
    Args:
        app: The FastAPI/Vidyut application instance
        prefix: URL prefix for admin (default: "/admin")
        
    Example:
        from vidyut import Vidyut
        from vidyut.contrib.admin import include_admin
        
        app = Vidyut(database_url="...")
        include_admin(app)  # Mounts at /admin/
        
        # Or with custom prefix
        include_admin(app, prefix="/dashboard")
    """
    from vidyut.contrib.admin.urls import router as admin_router
    
    # Add session middleware for admin authentication
    app.add_middleware(AdminSessionMiddleware)
    
    app.include_router(admin_router, prefix=prefix)
