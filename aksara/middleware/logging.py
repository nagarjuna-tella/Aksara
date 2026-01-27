"""
Logging Middleware

Structured request logging with timing and context correlation.

Usage:
    from aksara import Aksara
    from aksara.middleware import RequestIDMiddleware, LoggingMiddleware
    
    app = Aksara(
        middlewares=[
            (RequestIDMiddleware, {}),  # Add request ID first
            (LoggingMiddleware, {}),
        ],
    )

Configuration via aksara.conf.settings:
    - log_requests: bool = True  (enable/disable logging)
    - log_json: bool = False     (JSON format vs human-readable)

Log output includes:
    - HTTP method and path
    - Response status code
    - Request duration in milliseconds
    - Request ID (from RequestIDMiddleware)
    - Tenant ID (from TenantMiddleware)
    - User ID (from auth integration)
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .context import request_id_var, tenant_id_var, user_id_var

if TYPE_CHECKING:
    from starlette.types import ASGIApp

# Logger for request logs - can be configured by users
logger = logging.getLogger("aksara.request")


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs one structured line per request.
    
    Includes timing, context variables (request_id, tenant_id, user_id),
    and request/response metadata.
    
    Args:
        app: The ASGI application to wrap
        log_body: Reserved for future use (request/response body logging)
    
    Configuration:
        Control via aksara.conf.settings:
        - log_requests: Enable/disable logging (default: True)
        - log_json: Use JSON format (default: False, human-readable)
    
    Example output (text mode):
        HTTP GET /api/users -> 200 in 12.34ms [request_id=abc-123 tenant=acme user=42]
    
    Example output (JSON mode):
        {"event": "http_request", "method": "GET", "path": "/api/users", ...}
    """
    
    def __init__(self, app: "ASGIApp", log_body: bool = False):
        super().__init__(app)
        self.log_body = log_body  # Reserved for future extended logging
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Process the request and log timing/context."""
        # Check if logging is enabled
        from aksara.conf import settings
        
        if not getattr(settings, "log_requests", True):
            return await call_next(request)
        
        start = time.perf_counter()
        response: Optional[Response] = None
        status_code: Optional[int] = None
        
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            status_code = 500
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000.0
            self._log_request(request, status_code, duration_ms)
    
    def _log_request(
        self,
        request: Request,
        status_code: Optional[int],
        duration_ms: float,
    ) -> None:
        """Emit the log entry for this request."""
        from aksara.conf import settings
        
        # Gather context data
        data = {
            "event": "http_request",
            "method": request.method,
            "path": request.url.path,
            "status_code": status_code,
            "duration_ms": round(duration_ms, 2),
            "request_id": request_id_var.get(),
            "tenant_id": tenant_id_var.get(),
            "user_id": user_id_var.get(),
        }
        
        # Determine log level based on status code
        if status_code is None or status_code >= 500:
            log_level = logging.ERROR
        elif status_code >= 400:
            log_level = logging.WARNING
        else:
            log_level = logging.INFO
        
        # Format based on settings
        if getattr(settings, "log_json", False):
            # Structured JSON logging
            logger.log(log_level, data)
        else:
            # Human-readable format
            logger.log(
                log_level,
                "HTTP %s %s -> %s in %.2fms [request_id=%s tenant=%s user=%s]",
                data["method"],
                data["path"],
                data["status_code"],
                data["duration_ms"],
                data["request_id"],
                data["tenant_id"],
                data["user_id"],
            )


__all__ = ["LoggingMiddleware"]
