"""
aksara.debug - Dark-Mode Debug & Error Experience

v0.3.17: Provides beautiful dark-themed error pages in debug mode
with rich context including stacktrace, request details, user info,
tenant context, and database queries.

In production mode, shows clean JSON responses or minimal HTML.
"""
from aksara.debug.handlers import (
    collect_debug_context,
    render_debug_page,
    render_minimal_error_page,
    render_json_error,
    register_debug_exception_handlers,
    AksaraDebugMiddleware,
    DebugContext,
)

__all__ = [
    "collect_debug_context",
    "render_debug_page",
    "render_minimal_error_page",
    "render_json_error",
    "register_debug_exception_handlers",
    "AksaraDebugMiddleware",
    "DebugContext",
]
