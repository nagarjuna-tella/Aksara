"""
Vidyut Database Layer

Async database engine with connection pooling for PostgreSQL.
"""

from vidyut.db.engine import Database
from vidyut.db.session import get_session, session_context
from vidyut.db.debug import (
    QueryEvent,
    QueryLog,
    capture_queries,
    get_active_query_log,
    log_query,
)

__all__ = [
    "Database",
    "get_session",
    "session_context",
    # Debug utilities
    "QueryEvent",
    "QueryLog",
    "capture_queries",
    "get_active_query_log",
    "log_query",
]
