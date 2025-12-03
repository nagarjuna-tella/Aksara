"""
Vidyut Context Variables

Context variables for propagating request-scoped data throughout
the application. These are set by middleware and can be accessed
anywhere in your code.

Usage:
    from vidyut.middleware.context import request_id_var, tenant_id_var, user_id_var
    
    # Get current values (returns None if not set)
    request_id = request_id_var.get()
    tenant_id = tenant_id_var.get()
    user_id = user_id_var.get()
    
    # Set values (typically done by middleware)
    token = request_id_var.set("abc-123")
    try:
        # ... handle request ...
    finally:
        request_id_var.reset(token)
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Optional

# Request correlation ID - set by RequestIDMiddleware
# Used for tracing requests across services and in logs
request_id_var: ContextVar[Optional[str]] = ContextVar(
    "vidyut_request_id",
    default=None,
)

# Tenant identifier - set by TenantMiddleware
# Used for multi-tenant applications to scope data access
tenant_id_var: ContextVar[Optional[str]] = ContextVar(
    "vidyut_tenant_id",
    default=None,
)

# Authenticated user ID - set by auth dependencies
# Used for audit logging and user context
user_id_var: ContextVar[Optional[str]] = ContextVar(
    "vidyut_user_id",
    default=None,
)


__all__ = [
    "request_id_var",
    "tenant_id_var",
    "user_id_var",
]
