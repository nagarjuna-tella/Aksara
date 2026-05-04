"""
Aksara Context Variables

Context variables for propagating request-scoped data throughout
the application. These are set by middleware and can be accessed
anywhere in your code.

Usage:
    from aksara.middleware.context import request_id_var, tenant_id_var, user_id_var
    
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

from aksara.context_state import (
    locale_var,
    request_id_var,
    tenant_id_var,
    timezone_var,
    user_id_var,
)


__all__ = [
    "request_id_var",
    "tenant_id_var",
    "user_id_var",
    "locale_var",
    "timezone_var",
]
