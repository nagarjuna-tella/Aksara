"""
Aksara Database Debugging Utilities

Query capture and profiling tools for tests and development.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple, Union


@dataclass
class QueryEvent:
    """
    Represents a single database query execution.
    
    Attributes:
        sql: The SQL query string
        params: Query parameters (tuple, list, or dict)
        duration_ms: Query execution time in milliseconds (if measured)
    """
    sql: str
    params: Optional[Union[Tuple, List, dict]] = None
    duration_ms: Optional[float] = None
    
    def __repr__(self) -> str:
        sql_preview = self.sql[:60] + "..." if len(self.sql) > 60 else self.sql
        return f"<QueryEvent: {sql_preview!r}>"


@dataclass
class QueryLog:
    """
    Accumulator for captured database queries.
    
    Usage:
        async with capture_queries() as log:
            await User.objects.all()
            await Post.objects.filter(author_id=user.id).all()
        
        print(f"Executed {log.count} queries")
        for q in log.queries:
            print(q.sql)
    """
    queries: List[QueryEvent] = field(default_factory=list)
    
    def add(self, sql: str, params: Optional[Union[Tuple, List, dict]] = None) -> None:
        """Record a query execution."""
        self.queries.append(QueryEvent(sql=sql, params=params))
    
    @property
    def count(self) -> int:
        """Number of queries captured."""
        return len(self.queries)
    
    def clear(self) -> None:
        """Clear all captured queries."""
        self.queries.clear()
    
    def filter_by_table(self, table_name: str) -> List[QueryEvent]:
        """Get queries that reference a specific table."""
        return [
            q for q in self.queries
            if table_name.lower() in q.sql.lower()
        ]
    
    def filter_selects(self) -> List[QueryEvent]:
        """Get only SELECT queries."""
        return [
            q for q in self.queries
            if q.sql.strip().upper().startswith("SELECT")
        ]
    
    def filter_inserts(self) -> List[QueryEvent]:
        """Get only INSERT queries."""
        return [
            q for q in self.queries
            if q.sql.strip().upper().startswith("INSERT")
        ]
    
    def filter_updates(self) -> List[QueryEvent]:
        """Get only UPDATE queries."""
        return [
            q for q in self.queries
            if q.sql.strip().upper().startswith("UPDATE")
        ]
    
    def filter_deletes(self) -> List[QueryEvent]:
        """Get only DELETE queries."""
        return [
            q for q in self.queries
            if q.sql.strip().upper().startswith("DELETE")
        ]
    
    def __repr__(self) -> str:
        return f"<QueryLog: {self.count} queries>"


# Global query log reference (set during capture_queries context)
_active_query_log: Optional[QueryLog] = None


def get_active_query_log() -> Optional[QueryLog]:
    """Get the currently active query log, if any."""
    return _active_query_log


def log_query(sql: str, params: Optional[Union[Tuple, List, dict]] = None) -> None:
    """
    Log a query to the active query log, if one exists.
    
    Called by Database methods when query logging is active.
    """
    if _active_query_log is not None:
        _active_query_log.add(sql, params)


@asynccontextmanager
async def capture_queries():
    """
    Async context manager to capture all DB queries executed inside the block.
    
    Used in tests to assert query counts and debug N+1 issues.
    
    Usage:
        async with capture_queries() as log:
            posts = await Post.objects.all()
            for p in posts:
                # This might trigger N+1 if not preloaded
                _ = p.author
        
        print(f"Total queries: {log.count}")
        assert log.count <= 2, "N+1 detected!"
    
    Yields:
        QueryLog instance containing all captured queries
    """
    global _active_query_log
    
    # Save any existing log (for nested captures)
    previous_log = _active_query_log
    
    # Create new log for this context
    log = QueryLog()
    _active_query_log = log
    
    try:
        yield log
    finally:
        # Restore previous log (or None)
        _active_query_log = previous_log


__all__ = [
    "QueryEvent",
    "QueryLog",
    "capture_queries",
    "get_active_query_log",
    "log_query",
]
