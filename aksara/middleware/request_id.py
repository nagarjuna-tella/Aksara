"""
Request ID Middleware

Ensures every request has a correlation ID for tracing and debugging.

Usage:
    from aksara import Aksara
    from aksara.middleware import RequestIDMiddleware
    
    app = Aksara(
        middlewares=[
            (RequestIDMiddleware, {}),
        ],
    )
    
    # Or with custom header name
    app = Aksara(
        middlewares=[
            (RequestIDMiddleware, {"header_name": "X-Correlation-ID"}),
        ],
    )

The middleware:
1. Reads the request ID from the specified header (default: X-Request-ID)
2. If not present, generates a new UUID4
3. Stores the ID in request.state.request_id and request_id_var
4. Adds the ID to the response headers
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .context import request_id_var

if TYPE_CHECKING:
    from starlette.types import ASGIApp


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware that ensures every request has a correlation ID.
    
    - Reads from header if present (e.g., from upstream proxy/gateway)
    - Otherwise generates a UUID4
    - Stores in request.state.request_id and contextvar
    - Adds header to response for client correlation
    
    Args:
        app: The ASGI application to wrap
        header_name: The header name to read/write (default: X-Request-ID)
    
    Example:
        # Access in endpoint
        @app.get("/")
        async def root(request: Request):
            return {"request_id": request.state.request_id}
        
        # Access anywhere via contextvar
        from aksara.middleware import request_id_var
        logger.info(f"Processing request {request_id_var.get()}")
    """
    
    def __init__(self, app: "ASGIApp", header_name: str = "X-Request-ID"):
        super().__init__(app)
        self.header_name = header_name
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Process the request and add request ID tracking."""
        # Get existing request ID or generate new one
        req_id = request.headers.get(self.header_name)
        if not req_id:
            req_id = str(uuid.uuid4())
        
        # Store in request state for endpoint access
        request.state.request_id = req_id
        
        # Store in contextvar for access anywhere in the call stack
        token = request_id_var.set(req_id)
        
        try:
            response: Response = await call_next(request)
        finally:
            # Reset contextvar to prevent leaking to other requests
            request_id_var.reset(token)
        
        # Add to response headers for client correlation
        response.headers[self.header_name] = req_id
        return response


__all__ = ["RequestIDMiddleware"]
