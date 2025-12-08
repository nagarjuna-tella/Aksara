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


def quote_identifier(name: str) -> str:
    """
    Quote a SQL identifier (table name, column name) to handle reserved words.
    
    PostgreSQL uses double quotes for identifiers. Any embedded double quotes
    are escaped by doubling them.
    
    Args:
        name: The identifier to quote
        
    Returns:
        Quoted identifier safe for use in SQL
    """
    # Escape any embedded double quotes by doubling them
    escaped = name.replace('"', '""')
    return f'"{escaped}"'


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
    # SQL utilities
    "quote_identifier",
]
