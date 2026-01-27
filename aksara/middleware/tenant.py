"""
Tenant Middleware

Extracts tenant identifier for multi-tenant applications.

Usage:
    from aksara import Aksara
    from aksara.middleware import TenantMiddleware
    
    # From header (default)
    app = Aksara(
        middlewares=[
            (TenantMiddleware, {}),  # Uses X-Tenant-Id header
        ],
    )
    
    # Custom header name
    app = Aksara(
        middlewares=[
            (TenantMiddleware, {"header_name": "X-Tenant"}),
        ],
    )
    
    # From subdomain (e.g., acme.example.com -> tenant_id="acme")
    app = Aksara(
        middlewares=[
            (TenantMiddleware, {"use_subdomain": True}),
        ],
    )

The middleware:
1. Extracts tenant ID from header or subdomain
2. Stores in request.state.tenant_id and tenant_id_var
3. Available throughout the request lifecycle

Future enhancements can add:
- Automatic query filtering by tenant
- Tenant validation against database
- Tenant-specific configuration loading
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .context import tenant_id_var

if TYPE_CHECKING:
    from starlette.types import ASGIApp


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Middleware that extracts tenant ID from header or subdomain.
    
    Useful for multi-tenant SaaS applications where each tenant
    has isolated data.
    
    Args:
        app: The ASGI application to wrap
        header_name: The header name to read tenant from (default: X-Tenant-Id)
        use_subdomain: If True, also try to extract tenant from subdomain
    
    Example:
        # Access in endpoint
        @app.get("/data")
        async def get_data(request: Request):
            tenant_id = request.state.tenant_id
            return await Data.objects.filter(tenant_id=tenant_id).all()
        
        # Access anywhere via contextvar
        from aksara.middleware import tenant_id_var
        tenant = tenant_id_var.get()
    """
    
    def __init__(
        self,
        app: "ASGIApp",
        header_name: str = "X-Tenant-Id",
        use_subdomain: bool = False,
    ):
        super().__init__(app)
        self.header_name = header_name
        self.use_subdomain = use_subdomain
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Process the request and extract tenant ID."""
        # Try header first
        tenant_id: Optional[str] = request.headers.get(self.header_name)
        
        # Fall back to subdomain if enabled and no header found
        if not tenant_id and self.use_subdomain:
            tenant_id = self._extract_subdomain(request)
        
        # Store in request state for endpoint access
        request.state.tenant_id = tenant_id
        
        # Store in contextvar for access anywhere in the call stack
        token = tenant_id_var.set(tenant_id)
        
        try:
            response = await call_next(request)
        finally:
            # Reset contextvar to prevent leaking to other requests
            tenant_id_var.reset(token)
        
        return response
    
    def _extract_subdomain(self, request: Request) -> Optional[str]:
        """
        Extract tenant from subdomain.
        
        Assumes format: <tenant>.domain.tld
        Returns None for hosts without subdomain (e.g., localhost, domain.tld)
        """
        host = request.headers.get("host", "")
        
        # Remove port if present
        if ":" in host:
            host = host.split(":")[0]
        
        # Split into parts
        parts = host.split(".")
        
        # Need at least 3 parts for subdomain (tenant.domain.tld)
        # Skip common patterns like "www" or "api"
        if len(parts) >= 3:
            subdomain = parts[0]
            # Don't treat www/api as tenant
            if subdomain.lower() not in ("www", "api", "app"):
                return subdomain
        
        return None


__all__ = ["TenantMiddleware"]
