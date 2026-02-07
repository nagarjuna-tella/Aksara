"""
Aksara Database Query Tracing

Per-request query tracing for profiling and debugging.

v0.5.10: Introduces comprehensive query tracing with:
- Per-request query collection using contextvars
- Timing, row count, and call site tracking
- N+1 query detection heuristics
- Ring buffer storage for recent traces

Usage:
    # Automatic (via QueryTraceMiddleware):
    # Just enable db_trace_enabled in settings - traces are collected per-request.
    
    # Manual programmatic usage:
    from aksara.db.tracing import start_trace_session, stop_trace_session
    
    start_trace_session(request_id="my-request-123")
    # ... execute queries ...
    batch = stop_trace_session()
    print(f"Total queries: {batch.total_queries}")
"""

from __future__ import annotations

import hashlib
import re
import time
import traceback
from collections import defaultdict
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple, Union


# =============================================================================
# Query Trace Models
# =============================================================================

@dataclass
class DbQueryTrace:
    """
    Represents a single database query execution with full context.
    
    Attributes:
        sql: The SQL query string
        params: Query parameters (list, tuple, or dict)
        duration_ms: Query execution time in milliseconds
        rows_affected: Number of rows affected/returned (if available)
        operation: Query type (SELECT, INSERT, UPDATE, DELETE, OTHER)
        table: Primary table being queried (best-effort extraction)
        timestamp: When the query was executed
        stack_summary: Short call site info (file:line:function)
        request_id: Associated request ID (if in request context)
        tags: Additional categorization tags (e.g., ["orm", "raw"])
    """
    sql: str
    params: Optional[Union[Tuple, List, Dict]] = None
    duration_ms: float = 0.0
    rows_affected: Optional[int] = None
    operation: str = "OTHER"
    table: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    stack_summary: Optional[str] = None
    request_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Extract operation and table from SQL if not provided."""
        if self.operation == "OTHER":
            self.operation = _extract_operation(self.sql)
        if self.table is None:
            self.table = _extract_table(self.sql)
    
    @property
    def is_slow(self) -> bool:
        """Check if this query is considered slow based on settings."""
        from aksara.conf import settings
        threshold = getattr(settings, 'db_trace_slow_threshold_ms', 100.0)
        return self.duration_ms >= threshold
    
    @property
    def normalized_sql(self) -> str:
        """
        Return SQL with literals replaced by placeholders for grouping.
        
        Useful for detecting N+1 patterns where the same query shape
        is executed many times with different IDs.
        """
        return _normalize_sql(self.sql)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "sql": self.sql,
            "params": self.params,
            "duration_ms": round(self.duration_ms, 3),
            "rows_affected": self.rows_affected,
            "operation": self.operation,
            "table": self.table,
            "timestamp": self.timestamp.isoformat(),
            "stack_summary": self.stack_summary,
            "request_id": self.request_id,
            "tags": self.tags,
            "is_slow": self.is_slow,
        }


@dataclass
class DbQueryBatch:
    """
    Collection of queries from a single request/session.
    
    Provides aggregated statistics and N+1 detection.
    
    Attributes:
        request_id: The associated request ID
        queries: List of query traces
        path: HTTP request path (if from HTTP request)
        method: HTTP method (if from HTTP request)
        status_code: HTTP status code (if from HTTP request)
    """
    request_id: Optional[str] = None
    queries: List[DbQueryTrace] = field(default_factory=list)
    path: Optional[str] = None
    method: Optional[str] = None
    status_code: Optional[int] = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: Optional[datetime] = None
    
    @property
    def total_duration_ms(self) -> float:
        """Total time spent in database queries."""
        return sum(q.duration_ms for q in self.queries)
    
    @property
    def total_queries(self) -> int:
        """Total number of queries executed."""
        return len(self.queries)
    
    @property
    def slow_queries(self) -> int:
        """Number of slow queries."""
        return sum(1 for q in self.queries if q.is_slow)
    
    @property
    def n_plus_one_suspicions(self) -> List[str]:
        """
        Detect potential N+1 query patterns.
        
        Returns a list of warning messages for suspicious patterns.
        """
        return _detect_n_plus_one(self.queries)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "request_id": self.request_id,
            "path": self.path,
            "method": self.method,
            "status_code": self.status_code,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "total_duration_ms": round(self.total_duration_ms, 3),
            "total_queries": self.total_queries,
            "slow_queries": self.slow_queries,
            "n_plus_one_suspicions": self.n_plus_one_suspicions,
            "queries": [q.to_dict() for q in self.queries],
        }
    
    def to_summary_dict(self) -> Dict[str, Any]:
        """Convert to summary dictionary (without full query list)."""
        return {
            "request_id": self.request_id,
            "path": self.path,
            "method": self.method,
            "status_code": self.status_code,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "total_duration_ms": round(self.total_duration_ms, 3),
            "total_queries": self.total_queries,
            "slow_queries": self.slow_queries,
            "n_plus_one_suspicions": self.n_plus_one_suspicions,
        }


# =============================================================================
# Context Variable for Per-Request Tracing
# =============================================================================

# Holds the current trace session's queries
_trace_session_var: ContextVar[Optional[List[DbQueryTrace]]] = ContextVar(
    'db_trace_session', default=None
)

# Holds current request metadata
_trace_metadata_var: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
    'db_trace_metadata', default=None
)


# =============================================================================
# Recent Traces Storage (In-Memory Ring Buffer)
# =============================================================================

class TraceStorage:
    """
    Thread-safe in-memory storage for recent query batches.
    
    Uses a dict with size limit, evicting oldest entries when full.
    """
    
    def __init__(self, max_size: int = 100):
        self._storage: Dict[str, DbQueryBatch] = {}
        self._order: List[str] = []  # Track insertion order
        self._lock = Lock()
        self.max_size = max_size
    
    def store(self, batch: DbQueryBatch) -> None:
        """Store a query batch."""
        if not batch.request_id:
            return
        
        with self._lock:
            # Remove oldest if at capacity
            while len(self._storage) >= self.max_size and self._order:
                oldest = self._order.pop(0)
                self._storage.pop(oldest, None)
            
            # Store new batch
            self._storage[batch.request_id] = batch
            if batch.request_id in self._order:
                self._order.remove(batch.request_id)
            self._order.append(batch.request_id)
    
    def get(self, request_id: str) -> Optional[DbQueryBatch]:
        """Get a batch by request ID."""
        with self._lock:
            return self._storage.get(request_id)
    
    def get_recent(self, limit: int = 20) -> List[DbQueryBatch]:
        """Get recent batches (most recent first)."""
        with self._lock:
            ids = self._order[-limit:][::-1]
            return [self._storage[rid] for rid in ids if rid in self._storage]
    
    def get_all_queries(self) -> List[DbQueryTrace]:
        """Get all queries from all stored batches."""
        with self._lock:
            all_queries = []
            for batch in self._storage.values():
                all_queries.extend(batch.queries)
            return all_queries
    
    def get_stats(self) -> Dict[str, Any]:
        """Get aggregate statistics across all stored batches."""
        with self._lock:
            all_queries = []
            for batch in self._storage.values():
                all_queries.extend(batch.queries)
            
            if not all_queries:
                return {
                    "total_batches": 0,
                    "total_queries": 0,
                    "avg_queries_per_request": 0.0,
                    "total_slow_queries": 0,
                    "requests_with_slow_queries": 0,
                    "requests_with_n_plus_one": 0,
                }
            
            slow_count = sum(1 for q in all_queries if q.is_slow)
            requests_with_slow = sum(
                1 for b in self._storage.values() if b.slow_queries > 0
            )
            requests_with_n1 = sum(
                1 for b in self._storage.values() if b.n_plus_one_suspicions
            )
            
            return {
                "total_batches": len(self._storage),
                "total_queries": len(all_queries),
                "avg_queries_per_request": round(
                    len(all_queries) / len(self._storage), 2
                ) if self._storage else 0.0,
                "total_slow_queries": slow_count,
                "requests_with_slow_queries": requests_with_slow,
                "requests_with_n_plus_one": requests_with_n1,
            }
    
    def clear(self) -> None:
        """Clear all stored traces."""
        with self._lock:
            self._storage.clear()
            self._order.clear()


# Global storage instance
_trace_storage = TraceStorage(max_size=100)


# =============================================================================
# Tracing Functions
# =============================================================================

def is_tracing_enabled() -> bool:
    """Check if DB tracing is enabled in settings."""
    from aksara.conf import settings
    return getattr(settings, 'db_trace_enabled', False)


def start_trace_session(
    request_id: Optional[str] = None,
    path: Optional[str] = None,
    method: Optional[str] = None,
) -> None:
    """
    Start a new trace session for the current context.
    
    Args:
        request_id: The request identifier
        path: HTTP request path
        method: HTTP method
    """
    if not is_tracing_enabled():
        return
    
    _trace_session_var.set([])
    _trace_metadata_var.set({
        "request_id": request_id,
        "path": path,
        "method": method,
        "started_at": datetime.now(timezone.utc),
    })


def stop_trace_session(
    status_code: Optional[int] = None,
) -> Optional[DbQueryBatch]:
    """
    Stop the current trace session and return the collected batch.
    
    Args:
        status_code: HTTP response status code
        
    Returns:
        DbQueryBatch with all collected queries, or None if no session
    """
    queries = _trace_session_var.get()
    metadata = _trace_metadata_var.get()
    
    # Reset context vars
    _trace_session_var.set(None)
    _trace_metadata_var.set(None)
    
    if queries is None:
        return None
    
    # Build batch
    batch = DbQueryBatch(
        request_id=metadata.get("request_id") if metadata else None,
        queries=queries,
        path=metadata.get("path") if metadata else None,
        method=metadata.get("method") if metadata else None,
        status_code=status_code,
        started_at=metadata.get("started_at", datetime.now(timezone.utc)) if metadata else datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
    )
    
    # Store in ring buffer
    if batch.request_id:
        _trace_storage.store(batch)
    
    return batch


def record_query(
    sql: str,
    params: Optional[Union[Tuple, List, Dict]] = None,
    duration_ms: float = 0.0,
    rows_affected: Optional[int] = None,
    tags: Optional[List[str]] = None,
) -> None:
    """
    Record a query execution to the current trace session.
    
    This is called by the database engine after each query executes.
    
    Args:
        sql: The executed SQL
        params: Query parameters
        duration_ms: Execution time in milliseconds
        rows_affected: Number of rows affected/returned
        tags: Additional tags for categorization
    """
    session = _trace_session_var.get()
    if session is None:
        return
    
    # Check max queries limit
    from aksara.conf import settings
    max_queries = getattr(settings, 'db_trace_max_queries', 500)
    if len(session) >= max_queries:
        return
    
    # Get request ID from metadata
    metadata = _trace_metadata_var.get()
    request_id = metadata.get("request_id") if metadata else None
    
    # Capture call site (skip our own frames)
    stack_summary = _get_stack_summary(skip_frames=3)
    
    trace = DbQueryTrace(
        sql=sql,
        params=params,
        duration_ms=duration_ms,
        rows_affected=rows_affected,
        stack_summary=stack_summary,
        request_id=request_id,
        tags=tags or [],
    )
    
    session.append(trace)


def get_current_trace_session() -> Optional[List[DbQueryTrace]]:
    """Get the current trace session's queries, if active."""
    return _trace_session_var.get()


def get_recent_traces(limit: int = 20) -> List[DbQueryBatch]:
    """Get recent query batches from the storage."""
    return _trace_storage.get_recent(limit)


def get_trace_by_request_id(request_id: str) -> Optional[DbQueryBatch]:
    """Get a specific batch by request ID."""
    return _trace_storage.get(request_id)


def get_trace_stats() -> Dict[str, Any]:
    """Get aggregate statistics from stored traces."""
    return _trace_storage.get_stats()


def get_top_slow_queries(limit: int = 20) -> List[DbQueryTrace]:
    """Get the slowest queries across all stored batches."""
    all_queries = _trace_storage.get_all_queries()
    sorted_queries = sorted(all_queries, key=lambda q: q.duration_ms, reverse=True)
    return sorted_queries[:limit]


def clear_traces() -> None:
    """Clear all stored traces."""
    _trace_storage.clear()


# =============================================================================
# Helper Functions
# =============================================================================

def _extract_operation(sql: str) -> str:
    """Extract the SQL operation type from a query."""
    sql_upper = sql.strip().upper()
    if sql_upper.startswith("SELECT"):
        return "SELECT"
    elif sql_upper.startswith("INSERT"):
        return "INSERT"
    elif sql_upper.startswith("UPDATE"):
        return "UPDATE"
    elif sql_upper.startswith("DELETE"):
        return "DELETE"
    elif sql_upper.startswith("CREATE"):
        return "CREATE"
    elif sql_upper.startswith("DROP"):
        return "DROP"
    elif sql_upper.startswith("ALTER"):
        return "ALTER"
    elif sql_upper.startswith("BEGIN") or sql_upper.startswith("COMMIT") or sql_upper.startswith("ROLLBACK"):
        return "TRANSACTION"
    return "OTHER"


def _extract_table(sql: str) -> Optional[str]:
    """
    Best-effort extraction of the primary table from SQL.
    
    Handles common patterns:
    - SELECT ... FROM table
    - INSERT INTO table
    - UPDATE table SET
    - DELETE FROM table
    """
    sql_clean = re.sub(r'\s+', ' ', sql.strip())
    
    # SELECT ... FROM table
    match = re.search(r'FROM\s+["\']?(\w+)["\']?', sql_clean, re.IGNORECASE)
    if match:
        return match.group(1)
    
    # INSERT INTO table
    match = re.search(r'INSERT\s+INTO\s+["\']?(\w+)["\']?', sql_clean, re.IGNORECASE)
    if match:
        return match.group(1)
    
    # UPDATE table
    match = re.search(r'UPDATE\s+["\']?(\w+)["\']?', sql_clean, re.IGNORECASE)
    if match:
        return match.group(1)
    
    # DELETE FROM table
    match = re.search(r'DELETE\s+FROM\s+["\']?(\w+)["\']?', sql_clean, re.IGNORECASE)
    if match:
        return match.group(1)
    
    return None


def _normalize_sql(sql: str) -> str:
    """
    Normalize SQL by replacing literals with placeholders.
    
    This allows grouping queries that differ only in parameter values.
    """
    # Replace numeric literals
    normalized = re.sub(r'\b\d+\b', '?', sql)
    # Replace string literals (single quotes)
    normalized = re.sub(r"'[^']*'", "'?'", normalized)
    # Replace PostgreSQL positional params ($1, $2, etc.)
    normalized = re.sub(r'\$\d+', '$?', normalized)
    # Normalize whitespace
    normalized = re.sub(r'\s+', ' ', normalized.strip())
    return normalized


def _get_stack_summary(skip_frames: int = 2) -> Optional[str]:
    """
    Get a short summary of the call site.
    
    Returns format: "file.py:123:function_name"
    """
    try:
        # Get the call stack, excluding our own frames
        stack = traceback.extract_stack()
        
        # Skip internal frames (tracing code, db engine, etc.)
        for frame in reversed(stack[:-skip_frames]):
            filename = frame.filename
            # Skip aksara internal modules
            if 'aksara/db/' in filename or 'aksara/manager.py' in filename:
                continue
            # Skip asyncpg internals
            if 'asyncpg' in filename:
                continue
            # Skip other internal paths
            if '/site-packages/' in filename and 'aksara' not in filename:
                continue
            
            # Found a user frame
            short_file = filename.split('/')[-1] if '/' in filename else filename
            return f"{short_file}:{frame.lineno}:{frame.name}"
        
        return None
    except Exception:
        return None


def _detect_n_plus_one(queries: List[DbQueryTrace], threshold: int = 10) -> List[str]:
    """
    Detect potential N+1 query patterns.
    
    Groups queries by (operation, table, normalized_sql) and flags
    any group with more than `threshold` similar queries.
    
    Args:
        queries: List of query traces
        threshold: Minimum count to trigger warning (default: 10)
        
    Returns:
        List of warning messages
    """
    if not queries:
        return []
    
    # Group by normalized pattern
    groups: Dict[Tuple[str, Optional[str], str], int] = defaultdict(int)
    
    for q in queries:
        key = (q.operation, q.table, q.normalized_sql)
        groups[key] += 1
    
    warnings = []
    for (operation, table, _), count in groups.items():
        if count >= threshold:
            table_info = f"'{table}'" if table else "(unknown table)"
            warnings.append(
                f"Possible N+1: {count} similar {operation}s on {table_info}"
            )
    
    return warnings


__all__ = [
    # Models
    "DbQueryTrace",
    "DbQueryBatch",
    # Session management
    "start_trace_session",
    "stop_trace_session",
    "record_query",
    "get_current_trace_session",
    # Storage access
    "get_recent_traces",
    "get_trace_by_request_id",
    "get_trace_stats",
    "get_top_slow_queries",
    "clear_traces",
    # Utility
    "is_tracing_enabled",
]
