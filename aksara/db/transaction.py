"""
Transaction helpers for the Aksara ORM.

v0.5.45: Adds transaction.atomic decorator and context manager support.
"""

from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Optional, TypeVar

from aksara.db.cleanup import release_owned_connection
from aksara.db.session import get_session, push_session, reset_session
from aksara.db.tenant_context import apply_tenant_context, reset_tenant_context

if TYPE_CHECKING:
    from contextvars import Token

    import asyncpg

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
            self._owns_connection = True
        else:
            self._connection = existing_connection

        try:
            if self._owns_connection:
                self._tenant_applied = True
                self._tenant_applied = await apply_tenant_context(self._connection)
                self._session_token = push_session(self._connection)
            self._transaction = self._connection.transaction()
            await self._transaction.start()
        except BaseException as exc:
            # A failed start is not a started transaction to commit/rollback.
            # Owned connections are reset by pool.release; borrowed connections
            # remain owned by the enclosing session/transaction.
            await self._cleanup(exc)
            raise
        return self._connection

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Commit on success or roll back on failure, then clean up the connection."""
        error = exc_val
        try:
            if self._transaction is not None:
                if exc_type is not None:
                    await self._transaction.rollback()
                else:
                    await self._transaction.commit()
        except BaseException as cleanup_error:
            if error is None:
                error = cleanup_error
                raise
            error.add_note(f"Transaction finalization also failed: {type(cleanup_error).__name__}")
        finally:
            await self._cleanup(error)

    async def _cleanup(self, original_error: BaseException | None) -> None:
        reset_error = None
        if self._session_token is not None:
            try:
                reset_session(self._session_token)
            except BaseException as cleanup_error:  # noqa: BLE001
                if original_error is None:
                    reset_error = cleanup_error
                    original_error = cleanup_error
                else:
                    original_error.add_note(
                        f"Session context reset also failed: {type(cleanup_error).__name__}"
                    )
            self._session_token = None
        connection, self._connection = self._connection, None
        owned, self._owns_connection = self._owns_connection, False
        reset = reset_tenant_context if self._tenant_applied else None
        self._transaction = None
        self._tenant_applied = False
        if owned and self._db is not None and connection is not None:
            await release_owned_connection(self._db.pool, connection, reset, original_error)
        if reset_error is not None:
            raise reset_error

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
