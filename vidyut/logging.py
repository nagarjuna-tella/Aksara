"""
Vidyut Logging

Structured logging for Vidyut ORM with debug mode support.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

# Create Vidyut logger
logger = logging.getLogger("vidyut")

# Default format for Vidyut logs
DEFAULT_FORMAT = "[VIDYUT] %(message)s"


def setup_logging(level: int = logging.DEBUG, format_string: Optional[str] = None) -> None:
    """
    Set up logging for Vidyut.
    
    Call this if you want Vidyut to configure its own handler.
    Otherwise, logging follows your application's configuration.
    
    Args:
        level: Logging level (default: DEBUG)
        format_string: Custom format string
    """
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(format_string or DEFAULT_FORMAT))
    logger.addHandler(handler)
    logger.setLevel(level)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a Vidyut logger.
    
    Args:
        name: Optional sub-logger name (e.g., "vidyut.db", "vidyut.query")
        
    Returns:
        Logger instance
    """
    if name:
        return logging.getLogger(f"vidyut.{name}")
    return logger


class QueryLogger:
    """
    Context manager for logging SQL queries with timing.
    
    Usage:
        with QueryLogger(query, params) as ql:
            result = await db.fetch(query, *params)
        # Logs: QUERY (12.3ms): SELECT ... ; params: [...]
    """
    
    def __init__(
        self,
        query: str,
        params: Optional[tuple] = None,
        *,
        enabled: Optional[bool] = None,
    ):
        self.query = query
        self.params = params
        self.start_time: Optional[float] = None
        self.duration_ms: Optional[float] = None
        
        # Check if logging is enabled
        if enabled is None:
            from vidyut.conf import settings
            self.enabled = settings.DEBUG
        else:
            self.enabled = enabled
    
    def __enter__(self) -> "QueryLogger":
        if self.enabled:
            self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if not self.enabled:
            return
        
        if self.start_time is not None:
            self.duration_ms = (time.perf_counter() - self.start_time) * 1000
        
        self._log_query(exc_val)
    
    def _log_query(self, error: Optional[Exception] = None) -> None:
        """Log the query with timing information."""
        # Truncate long queries
        query_display = self.query.strip().replace("\n", " ")
        if len(query_display) > 200:
            query_display = query_display[:200] + "..."
        
        # Format params
        params_display = ""
        if self.params:
            params_list = list(self.params)
            # Truncate long param values
            truncated = []
            for p in params_list[:5]:  # Show max 5 params
                p_str = repr(p)
                if len(p_str) > 50:
                    p_str = p_str[:50] + "..."
                truncated.append(p_str)
            if len(params_list) > 5:
                truncated.append(f"... ({len(params_list)} total)")
            params_display = f"; params: [{', '.join(truncated)}]"
        
        # Format timing
        timing = ""
        if self.duration_ms is not None:
            timing = f"({self.duration_ms:.1f}ms) "
        
        if error:
            logger.error(f"QUERY FAILED {timing}{query_display}{params_display} | Error: {error}")
        else:
            logger.debug(f"QUERY {timing}{query_display}{params_display}")


@contextmanager
def log_query(query: str, params: Optional[tuple] = None, *, enabled: Optional[bool] = None):
    """
    Context manager for logging queries.
    
    Usage:
        with log_query("SELECT * FROM users WHERE id = $1", (user_id,)):
            result = await db.fetch(...)
    """
    ql = QueryLogger(query, params, enabled=enabled)
    with ql:
        yield ql


def log_operation(operation: str) -> Callable:
    """
    Decorator for logging database operations.
    
    Usage:
        @log_operation("create")
        async def create(self, **kwargs):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            from vidyut.conf import settings
            
            if settings.DEBUG:
                start = time.perf_counter()
                try:
                    result = await func(*args, **kwargs)
                    duration = (time.perf_counter() - start) * 1000
                    logger.debug(f"{operation.upper()} completed in {duration:.1f}ms")
                    return result
                except Exception as e:
                    duration = (time.perf_counter() - start) * 1000
                    logger.error(f"{operation.upper()} failed after {duration:.1f}ms: {e}")
                    raise
            else:
                return await func(*args, **kwargs)
        return wrapper
    return decorator


__all__ = [
    "logger",
    "get_logger",
    "setup_logging",
    "QueryLogger",
    "log_query",
    "log_operation",
]
