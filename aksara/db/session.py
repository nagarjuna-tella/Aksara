"""
Database Session Management

Context variable based session management for request lifecycle.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import TYPE_CHECKING, Optional

from aksara.db.cleanup import release_owned_connection
from aksara.db.tenant_context import apply_tenant_context, reset_tenant_context

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
        self._tenant_applied = False
    
    async def __aenter__(self) -> "asyncpg.Connection":
        """Acquire connection and set in context."""
        self._connection = await self.db.pool.acquire()
        try:
            # Setup can fail after changing the connection's tenant setting.
            self._tenant_applied = True
            self._tenant_applied = await apply_tenant_context(self._connection)
            self._token = _session_context.set(self._connection)
        except BaseException as exc:
            await self.__aexit__(type(exc), exc, exc.__traceback__)
            raise
        return self._connection
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Release connection and clear context."""
        reset_error = None
        if self._token is not None:
            try:
                reset_session(self._token)
            except BaseException as cleanup_error:  # noqa: BLE001
                if exc_val is None:
                    reset_error = cleanup_error
                    exc_val = cleanup_error
                else:
                    exc_val.add_note(
                        f"Session context reset also failed: {type(cleanup_error).__name__}"
                    )
            self._token = None
        connection, self._connection = self._connection, None
        reset = reset_tenant_context if self._tenant_applied else None
        self._tenant_applied = False
        if connection is not None:
            await release_owned_connection(self.db.pool, connection, reset, exc_val)
        if reset_error is not None:
            raise reset_error
