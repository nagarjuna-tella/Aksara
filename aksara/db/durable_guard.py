"""Mechanical guardrails for the durable same-database atomic boundary."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterator

if TYPE_CHECKING:
    import asyncpg

    from aksara.db.engine import Database


@dataclass
class DurableDatabaseGuard:
    """Mutable guard shared by copied ContextVar contexts.

    Sharing the object is deliberate: a child task that inherits the pinned
    session marks the owner's boundary invalid even when the child error is
    caught by application code.
    """

    database: Database
    connection: asyncpg.Connection
    owner_task: asyncio.Task[object] | None
    invalid_reason: str | None = None

    def invalidate(self, reason: str) -> None:
        if self.invalid_reason is None:
            self.invalid_reason = reason


_durable_database_guard: ContextVar[DurableDatabaseGuard | None] = ContextVar(
    "aksara_durable_database_guard",
    default=None,
)


def get_durable_database_guard() -> DurableDatabaseGuard | None:
    return _durable_database_guard.get()


@contextmanager
def durable_database_guard(
    database: Database,
    connection: asyncpg.Connection,
) -> Iterator[DurableDatabaseGuard]:
    if get_durable_database_guard() is not None:
        raise RuntimeError("durable database guard cannot be nested")
    guard = DurableDatabaseGuard(
        database=database,
        connection=connection,
        owner_task=asyncio.current_task(),
    )
    token: Token[DurableDatabaseGuard | None] = _durable_database_guard.set(guard)
    try:
        yield guard
    finally:
        _durable_database_guard.reset(token)


def validate_database_access(database: Database) -> None:
    """Reject a different database or inherited child-task session."""

    guard = get_durable_database_guard()
    if guard is None:
        return
    if database is not guard.database:
        guard.invalidate("a different Database instance was used")
        raise RuntimeError(
            "postgres_atomic handlers may use only their execution context Database"
        )
    if asyncio.current_task() is not guard.owner_task:
        guard.invalidate("a child task or thread used the inherited pinned connection")
        raise RuntimeError(
            "postgres_atomic database work must stay in the owning asyncio task"
        )


def reject_direct_pool_access(database: Database) -> None:
    guard = get_durable_database_guard()
    if guard is None:
        return
    validate_database_access(database)
    guard.invalidate("direct Database.pool access escaped the supported boundary")
    raise RuntimeError("direct pool access is forbidden inside postgres_atomic handlers")


def mark_database_error(error: BaseException) -> None:
    guard = get_durable_database_guard()
    if guard is not None:
        guard.invalidate(f"database error occurred: {type(error).__name__}")


__all__ = [
    "DurableDatabaseGuard",
    "durable_database_guard",
    "get_durable_database_guard",
    "mark_database_error",
    "reject_direct_pool_access",
    "validate_database_access",
]
