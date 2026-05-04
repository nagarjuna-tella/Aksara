"""
Transaction helpers for the Aksara ORM.

v0.5.45: Adds transaction.atomic decorator and context manager support.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Awaitable, Callable, Optional, TYPE_CHECKING, TypeVar

from aksara.db.session import get_session, push_session, reset_session
from aksara.db.tenant_context import apply_tenant_context, reset_tenant_context

if TYPE_CHECKING:
    import asyncpg
    from contextvars import Token

    from aksara.db.engine import Database


F = TypeVar("F", bound=Callable[..., Awaitable[Any]])


class TransactionManager:
    """Async transaction manager backed by asyncpg transactions."""

    def __init__(self, db: Optional["Database"] = None):
        self._db = db
        self._connection: Optional["asyncpg.Connection"] = None
        self._transaction: Optional[Any] = None
        self._session_token: Optional["Token"] = None
        self._owns_connection = False
        self._tenant_applied = False

    async def __aenter__(self) -> "asyncpg.Connection":
        """Start a transaction, reusing the active session connection when present."""
        from aksara.db.engine import Database

        self._db = self._db or Database.get_instance()
        existing_connection = get_session()
        if existing_connection is None:
            self._connection = await self._db.pool.acquire()
            self._tenant_applied = await apply_tenant_context(self._connection)
            self._session_token = push_session(self._connection)
            self._owns_connection = True
        else:
            self._connection = existing_connection

        self._transaction = self._connection.transaction()
        await self._transaction.start()
        return self._connection

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Commit on success or roll back on failure, then clean up the connection."""
        try:
            if self._transaction is not None:
                if exc_type is not None:
                    await self._transaction.rollback()
                else:
                    await self._transaction.commit()
        finally:
            if self._owns_connection and self._db is not None and self._connection is not None:
                if self._session_token is not None:
                    reset_session(self._session_token)
                    self._session_token = None
                if self._tenant_applied:
                    await reset_tenant_context(self._connection)
                await self._db.pool.release(self._connection)
            self._connection = None
            self._transaction = None
            self._owns_connection = False
            self._tenant_applied = False

    def __call__(self, func: F) -> F:
        """Allow the manager to be used directly as an async decorator."""
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            async with TransactionManager(db=self._db):
                return await func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]


class _AtomicFactory:
    """Factory that supports both decorator and context-manager usage."""

    def __call__(self, func: Optional[F] = None, *, db: Optional["Database"] = None):
        manager = TransactionManager(db=db)
        if func is None:
            return manager
        return manager(func)


atomic = _AtomicFactory()


__all__ = ["TransactionManager", "atomic"]