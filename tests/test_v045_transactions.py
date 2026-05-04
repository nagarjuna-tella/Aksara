"""
Tests for v0.5.45 transaction.atomic support.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest

from aksara.db import atomic
from aksara.db.engine import Database
from aksara.db.session import get_session, push_session, reset_session


def _build_database_with_pool(pool: Mock) -> Database:
    """Create a Database instance without running its initializer."""
    db = Database.__new__(Database)
    db._pool = pool
    return db


class TestDatabaseAcquire:
    """Tests for session-aware connection acquisition."""

    @pytest.mark.asyncio
    async def test_acquire_reuses_active_session(self):
        connection = object()
        token = push_session(connection)
        db = _build_database_with_pool(Mock())

        try:
            async with db.acquire() as acquired:
                assert acquired is connection
        finally:
            reset_session(token)

        assert not db.pool.acquire.called


class TestAtomicTransactions:
    """Tests for atomic transaction lifecycle behavior."""

    @pytest.mark.asyncio
    async def test_atomic_acquires_connection_and_commits(self, monkeypatch):
        transaction = Mock(start=AsyncMock(), commit=AsyncMock(), rollback=AsyncMock())
        connection = Mock(transaction=Mock(return_value=transaction))
        pool = Mock(acquire=AsyncMock(return_value=connection), release=AsyncMock())
        db = _build_database_with_pool(pool)
        monkeypatch.setattr(Database, "get_instance", classmethod(lambda cls: db))

        async with atomic() as active_connection:
            assert active_connection is connection
            assert get_session() is connection

        pool.acquire.assert_awaited_once()
        transaction.start.assert_awaited_once()
        transaction.commit.assert_awaited_once()
        transaction.rollback.assert_not_awaited()
        pool.release.assert_awaited_once_with(connection)
        assert get_session() is None

    @pytest.mark.asyncio
    async def test_atomic_rolls_back_on_exception(self, monkeypatch):
        transaction = Mock(start=AsyncMock(), commit=AsyncMock(), rollback=AsyncMock())
        connection = Mock(transaction=Mock(return_value=transaction))
        pool = Mock(acquire=AsyncMock(return_value=connection), release=AsyncMock())
        db = _build_database_with_pool(pool)
        monkeypatch.setattr(Database, "get_instance", classmethod(lambda cls: db))

        with pytest.raises(RuntimeError, match="boom"):
            async with atomic():
                raise RuntimeError("boom")

        transaction.start.assert_awaited_once()
        transaction.rollback.assert_awaited_once()
        transaction.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_nested_atomic_uses_existing_session_connection(self, monkeypatch):
        outer_transaction = Mock(start=AsyncMock(), commit=AsyncMock(), rollback=AsyncMock())
        inner_transaction = Mock(start=AsyncMock(), commit=AsyncMock(), rollback=AsyncMock())
        connection = Mock(transaction=Mock(side_effect=[outer_transaction, inner_transaction]))
        pool = Mock(acquire=AsyncMock(return_value=connection), release=AsyncMock())
        db = _build_database_with_pool(pool)
        monkeypatch.setattr(Database, "get_instance", classmethod(lambda cls: db))

        async with atomic():
            async with atomic():
                assert get_session() is connection

        pool.acquire.assert_awaited_once()
        pool.release.assert_awaited_once_with(connection)
        outer_transaction.start.assert_awaited_once()
        inner_transaction.start.assert_awaited_once()
        outer_transaction.commit.assert_awaited_once()
        inner_transaction.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_atomic_decorator_wraps_async_function(self, monkeypatch):
        transaction = Mock(start=AsyncMock(), commit=AsyncMock(), rollback=AsyncMock())
        connection = Mock(transaction=Mock(return_value=transaction))
        pool = Mock(acquire=AsyncMock(return_value=connection), release=AsyncMock())
        db = _build_database_with_pool(pool)
        monkeypatch.setattr(Database, "get_instance", classmethod(lambda cls: db))

        @atomic
        async def run(value: int) -> int:
            assert get_session() is connection
            return value + 1

        result = await run(4)

        assert result == 5
        transaction.start.assert_awaited_once()
        transaction.commit.assert_awaited_once()