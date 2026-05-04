"""
Database Session Management

Context variable based session management for request lifecycle.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    import asyncpg

# Context variable to store the current database connection
_session_context: ContextVar[Optional["asyncpg.Connection"]] = ContextVar(
    "aksara_session", default=None
)


def get_session() -> Optional["asyncpg.Connection"]:
    """
    Get the current database session from context.
    
    Returns:
        Current database connection or None if not in a request context.
    """
    return _session_context.get()


def set_session(session: Optional["asyncpg.Connection"]) -> None:
    """
    Set the current database session in context.
    
    Args:
        session: Database connection to set
    """
    _session_context.set(session)


def push_session(session: Optional["asyncpg.Connection"]) -> Token:
    """Push a session value and return the reset token."""
    return _session_context.set(session)


def reset_session(token: Token) -> None:
    """Reset the session context using a previously returned token."""
    _session_context.reset(token)


class session_context:
    """
    Context manager for database session lifecycle.
    
    Usage:
        async with session_context(db):
            # Session is available via get_session()
            pass
    """
    
    def __init__(self, db: "Database"):
        from aksara.db.engine import Database
        self.db = db
        self._connection: Optional["asyncpg.Connection"] = None
        self._token = None
    
    async def __aenter__(self) -> "asyncpg.Connection":
        """Acquire connection and set in context."""
        self._connection = await self.db.pool.acquire()
        self._token = _session_context.set(self._connection)
        return self._connection
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Release connection and clear context."""
        if self._token is not None:
            _session_context.reset(self._token)
        if self._connection is not None:
            await self.db.pool.release(self._connection)
            self._connection = None
