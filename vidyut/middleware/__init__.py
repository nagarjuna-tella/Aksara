"""
Vidyut Middleware

Production-ready middleware components for request handling,
observability, and multi-tenancy.

Usage:
    from vidyut import Vidyut
    from vidyut.middleware import (
        RequestIDMiddleware,
        TenantMiddleware,
        LoggingMiddleware,
    )
    
    app = Vidyut(
        database_url="postgresql://...",
        middlewares=[
            (RequestIDMiddleware, {}),
            (TenantMiddleware, {"header_name": "X-Tenant-Id"}),
            (LoggingMiddleware, {}),
        ],
    )

Context Variables:
    The middleware components use context variables to propagate
    request-scoped data throughout the application:
    
    - request_id_var: Correlation ID for the request
    - tenant_id_var: Multi-tenant identifier
    - user_id_var: Authenticated user ID
    
    These can be accessed anywhere in your code:
    
        from vidyut.middleware import request_id_var, tenant_id_var, user_id_var
        
        def get_context():
            return {
                "request_id": request_id_var.get(),
                "tenant_id": tenant_id_var.get(),
                "user_id": user_id_var.get(),
            }
"""

from __future__ import annotations

from .context import request_id_var, tenant_id_var, user_id_var
from .request_id import RequestIDMiddleware
from .tenant import TenantMiddleware
from .logging import LoggingMiddleware

__all__ = [
    # Context variables
    "request_id_var",
    "tenant_id_var",
    "user_id_var",
    # Middleware classes
    "RequestIDMiddleware",
    "TenantMiddleware",
    "LoggingMiddleware",
]
