"""
Query Trace Middleware

Per-request database query tracing for profiling and debugging.

v0.5.10: Introduces automatic query tracing per request.

Usage:
    from aksara import Aksara
    from aksara.middleware import QueryTraceMiddleware
    from aksara.conf import configure, Settings
    
    # Enable tracing in settings
    configure(Settings(db_trace_enabled=True))
    
    # Add middleware
    app = Aksara(
        middlewares=[
            (QueryTraceMiddleware, {}),
        ],
    )

The middleware:
1. Starts a trace session at the beginning of each request
2. Captures all database queries executed during the request
3. Stops the trace session, storing results in memory
4. Query batches can be viewed via Studio or CLI

Note: This middleware should be registered AFTER RequestIDMiddleware
to ensure request IDs are available for correlation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from aksara.middleware.context import request_id_var

if TYPE_CHECKING:
    from starlette.types import ASGIApp


class QueryTraceMiddleware(BaseHTTPMiddleware):
    """
    Middleware that traces database queries for each request.
    
    When db_trace_enabled is True in settings:
    - Starts a trace session when request begins
    - Automatically records all database queries
    - Stops session on response, storing results for analysis
    
    Query batches are stored in a ring buffer and can be accessed via:
    - Studio: GET /studio/db/queries
    - CLI: aksara db stats, aksara db profile
    - Programmatically: aksara.db.get_recent_traces()
    
    Example:
        # View traces in code
        from aksara.db import get_recent_traces
        
        for batch in get_recent_traces(10):
            print(f"{batch.method} {batch.path}: {batch.total_queries} queries")
            for q in batch.queries:
                if q.is_slow:
                    print(f"  SLOW: {q.duration_ms}ms - {q.sql[:80]}")
    """
    
    def __init__(self, app: "ASGIApp"):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Process the request with query tracing."""
        from aksara.db.tracing import (
            is_tracing_enabled,
            start_trace_session,
            stop_trace_session,
        )
        
        if not is_tracing_enabled():
            return await call_next(request)
        
        # Get request ID from contextvar (set by RequestIDMiddleware)
        # or from request.state as fallback
        request_id = request_id_var.get(None)
        if request_id is None:
            request_id = getattr(request.state, "request_id", None)
        
        # Start trace session with request metadata
        start_trace_session(
            request_id=request_id,
            path=request.url.path,
            method=request.method,
        )
        
        try:
            # Process the request
            response = await call_next(request)
            
            # Stop trace session, recording status code
            stop_trace_session(status_code=response.status_code)
            
            return response
        except Exception:
            # Stop trace session even on error (record as 500)
            stop_trace_session(status_code=500)
            raise


__all__ = ["QueryTraceMiddleware"]
