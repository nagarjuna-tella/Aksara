"""
Admin Mount Helper

Helper function to mount admin routes on a FastAPI/Aksara app.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

if TYPE_CHECKING:
    from fastapi import FastAPI


def _get_settings():
    """Get Aksara settings lazily to avoid circular imports."""
    from aksara.conf import settings
    return settings


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
                from aksara.contrib.auth import get_user_from_session_token
                
                db = getattr(request.app, "db", None)
                if db:
                    user = await get_user_from_session_token(db, token)
                    if user:
                        request.state.user = user
            except Exception:
                pass  # Session lookup failed, continue without user
        
        return await call_next(request)


class AdminRateLimitMiddleware(BaseHTTPMiddleware):
    """Apply a best-effort rate limit to admin POST requests."""

    def __init__(self, app, prefix: str = "/admin"):
        super().__init__(app)
        self.prefix = prefix.rstrip("/") or "/admin"

    async def dispatch(self, request: Request, call_next):
        settings = _get_settings()
        if not settings.admin_rate_limit_enabled or request.method != "POST":
            return await call_next(request)

        if not request.url.path.startswith(f"{self.prefix}/"):
            return await call_next(request)

        client_host = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if not client_host and request.client:
            client_host = request.client.host
        if not client_host:
            client_host = "unknown"

        now = time.monotonic()
        window_seconds = max(settings.admin_rate_limit_window_seconds, 1)
        max_requests = max(settings.admin_rate_limit_requests, 1)
        cutoff = now - window_seconds
        bucket_key = f"{client_host}:{request.url.path}"

        store = getattr(request.app.state, "_aksara_admin_rate_limits", None)
        if store is None:
            store = {}
            request.app.state._aksara_admin_rate_limits = store

        timestamps = [ts for ts in store.get(bucket_key, []) if ts >= cutoff]
        if len(timestamps) >= max_requests:
            retry_after = max(1, int(window_seconds - (now - timestamps[0])))
            return Response(
                content="Too many admin requests.",
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )

        timestamps.append(now)
        store[bucket_key] = timestamps
        return await call_next(request)


def include_admin(app: "FastAPI", prefix: str = "/admin") -> None:
    """
    Mount the admin interface on a FastAPI/Aksara application.
    
    Args:
        app: The FastAPI/Aksara application instance
        prefix: URL prefix for admin (default: "/admin")
        
    Example:
        from aksara import Aksara
        from aksara.contrib.admin import include_admin
        
        app = Aksara(database_url="...")
        include_admin(app)  # Mounts at /admin/
        
        # Or with custom prefix
        include_admin(app, prefix="/dashboard")
    """
    import os
    from starlette.staticfiles import StaticFiles
    from aksara.contrib.admin.urls import router as admin_router
    
    # Add admin security middlewares
    app.add_middleware(AdminRateLimitMiddleware, prefix=prefix)
    app.add_middleware(AdminSessionMiddleware)
    
    # Mount admin static files at app level so templates can reference
    # /static/admin/css/admin.css regardless of admin prefix.
    # Directory layout: admin/static/admin/{css,js}/... 
    # We mount the inner static/admin/ dir at /static/admin/
    admin_dir = os.path.dirname(os.path.abspath(__file__))
    static_admin_dir = os.path.join(admin_dir, "static", "admin")
    if os.path.exists(static_admin_dir):
        app.mount(
            "/static/admin",
            StaticFiles(directory=static_admin_dir),
            name="admin_static",
        )
    
    app.include_router(admin_router, prefix=prefix, include_in_schema=False)
