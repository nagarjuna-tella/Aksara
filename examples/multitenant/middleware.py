"""
Multitenant Example - Middleware

TenantMiddleware for automatic tenant resolution from request headers.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Optional, TYPE_CHECKING
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

if TYPE_CHECKING:
    from .models import Tenant

# Context variable to store current tenant
current_tenant: ContextVar[Optional[Tenant]] = ContextVar("current_tenant", default=None)


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Middleware to resolve tenant from request.
    
    Resolution order:
    1. X-Tenant-ID header (UUID)
    2. X-Tenant-Slug header (slug string)
    3. Host header (domain-based)
    
    Usage:
        app.add_middleware(TenantMiddleware)
        
        # In your views:
        from examples.multitenant.middleware import get_current_tenant
        tenant = get_current_tenant()
    """
    
    # Paths that don't require tenant context
    EXEMPT_PATHS = [
        "/",
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/admin",
        "/studio",
        "/api/tenants",  # Tenant management doesn't need tenant context
    ]
    
    async def dispatch(self, request: Request, call_next):
        # Skip tenant resolution for exempt paths
        path = request.url.path
        if any(path.startswith(exempt) for exempt in self.EXEMPT_PATHS):
            return await call_next(request)
        
        # Try to resolve tenant
        tenant = await self._resolve_tenant(request)
        
        if tenant is None:
            # Check if tenant is required for this path
            if self._requires_tenant(path):
                return JSONResponse(
                    {"error": "Tenant not found", "detail": "Provide X-Tenant-ID or X-Tenant-Slug header"},
                    status_code=403
                )
        
        # Set tenant in context
        token = current_tenant.set(tenant)
        try:
            response = await call_next(request)
            return response
        finally:
            current_tenant.reset(token)
    
    async def _resolve_tenant(self, request: Request):
        """Resolve tenant from request headers or domain."""
        from .models import Tenant
        
        # 1. Try X-Tenant-ID header
        tenant_id = request.headers.get("X-Tenant-ID")
        if tenant_id:
            try:
                return await Tenant.objects.get(id=tenant_id)
            except Exception:
                pass
        
        # 2. Try X-Tenant-Slug header
        tenant_slug = request.headers.get("X-Tenant-Slug")
        if tenant_slug:
            try:
                return await Tenant.objects.get(slug=tenant_slug)
            except Exception:
                pass
        
        # 3. Try domain from Host header
        host = request.headers.get("Host", "").split(":")[0]
        if host and host not in ["localhost", "127.0.0.1"]:
            try:
                return await Tenant.objects.get(domain=host)
            except Exception:
                pass
        
        return None
    
    def _requires_tenant(self, path: str) -> bool:
        """Check if path requires tenant context."""
        # Users and projects require tenant context
        return path.startswith("/api/users") or path.startswith("/api/projects")


def get_current_tenant():
    """Get the current tenant from context."""
    return current_tenant.get()


def require_tenant():
    """
    Decorator to require tenant context.
    
    Usage:
        @require_tenant()
        async def my_view(request: Request):
            tenant = get_current_tenant()
            ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            tenant = get_current_tenant()
            if tenant is None:
                return JSONResponse(
                    {"error": "Tenant required"},
                    status_code=403
                )
            return await func(*args, **kwargs)
        return wrapper
    return decorator
