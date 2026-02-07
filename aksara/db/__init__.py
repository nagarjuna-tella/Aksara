"""
Aksara Database Layer

Async database engine with connection pooling for PostgreSQL.
"""

from aksara.db.engine import Database
from aksara.db.session import get_session, session_context
from aksara.db.debug import (
    QueryEvent,
    QueryLog,
    capture_queries,
    get_active_query_log,
    log_query,
)
from aksara.db.tracing import (
    DbQueryTrace,
    DbQueryBatch,
    start_trace_session,
    stop_trace_session,
    record_query,
    get_current_trace_session,
    get_recent_traces,
    get_trace_by_request_id,
    get_trace_stats,
    get_top_slow_queries,
    clear_traces,
    is_tracing_enabled,
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
    # v0.5.10: Query tracing
    "DbQueryTrace",
    "DbQueryBatch",
    "start_trace_session",
    "stop_trace_session",
    "record_query",
    "get_current_trace_session",
    "get_recent_traces",
    "get_trace_by_request_id",
    "get_trace_stats",
    "get_top_slow_queries",
    "clear_traces",
    "is_tracing_enabled",
]
