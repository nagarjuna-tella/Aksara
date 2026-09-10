"""Release-gate regressions for setup, cancellation and ownership boundaries."""

import asyncio
import os
from unittest.mock import AsyncMock, Mock

import asyncpg
import pytest
import pytest_asyncio

from aksara.db.engine import Database
from aksara.db.session import get_session, reset_session, session_context
from aksara.db.transaction import TransactionManager

CONTEXTS = [
    (session_context, "aksara.db.session"),
    (TransactionManager, "aksara.db.transaction"),
    (lambda db: db.acquire(), "aksara.db.engine"),
]


def database(pool):
    db = Database.__new__(Database)
    db._pool = pool
    return db


@pytest.mark.parametrize("context,module", CONTEXTS)
@pytest.mark.parametrize("failure", [RuntimeError, asyncio.CancelledError])
async def test_setup_failure_releases_and_preserves_error(
    monkeypatch, context, module, failure
):
    connection = Mock()
    pool = Mock(acquire=AsyncMock(return_value=connection), release=AsyncMock())
    original = failure("setup")
    monkeypatch.setattr(
        module + ".apply_tenant_context", AsyncMock(side_effect=original)
    )
    monkeypatch.setattr(
        module + ".reset_tenant_context", AsyncMock(side_effect=ValueError("reset"))
    )
    with pytest.raises(failure) as caught:
        async with context(database(pool)):
            pytest.fail("must not enter")
    assert caught.value is original
    pool.acquire.assert_awaited_once()
    pool.release.assert_awaited_once_with(connection)
    assert get_session() is None


@pytest.mark.parametrize("context,module", CONTEXTS)
async def test_reset_error_cannot_skip_release(monkeypatch, context, module):
    tx = Mock(start=AsyncMock(), commit=AsyncMock(), rollback=AsyncMock())
    connection = Mock(transaction=Mock(return_value=tx))
    pool = Mock(acquire=AsyncMock(return_value=connection), release=AsyncMock())
    monkeypatch.setattr(module + ".apply_tenant_context", AsyncMock(return_value=True))
    monkeypatch.setattr(
        module + ".reset_tenant_context", AsyncMock(side_effect=ValueError("reset"))
    )
    with pytest.raises(ValueError, match="reset"):
        async with context(database(pool)):
            pass
    pool.release.assert_awaited_once_with(connection)
    assert get_session() is None


async def test_start_failure_restores_outer_session_without_releasing_borrowed_connection():
    tx = Mock(start=AsyncMock(side_effect=RuntimeError("start")))
    connection = Mock(transaction=Mock(return_value=tx))
    pool = Mock(acquire=AsyncMock(return_value=connection), release=AsyncMock())
    db = database(pool)
    async with session_context(db):
        with pytest.raises(RuntimeError, match="start"):
            async with TransactionManager(db):
                pass
        assert get_session() is connection
        pool.release.assert_not_awaited()
    pool.release.assert_awaited_once_with(connection)
    assert get_session() is None


async def test_body_error_survives_rollback_and_release_errors():
    tx = Mock(start=AsyncMock(), rollback=AsyncMock(side_effect=ValueError("rollback")))
    connection = Mock(transaction=Mock(return_value=tx))
    pool = Mock(
        acquire=AsyncMock(return_value=connection),
        release=AsyncMock(side_effect=OSError("release")),
    )
    original = RuntimeError("body")
    with pytest.raises(RuntimeError) as caught:
        async with TransactionManager(database(pool)):
            raise original
    assert caught.value is original
    pool.release.assert_awaited_once()
    assert get_session() is None


@pytest.mark.parametrize(
    "context,module",
    [
        (session_context, "aksara.db.session"),
        (TransactionManager, "aksara.db.transaction"),
    ],
)
async def test_session_reset_failure_cannot_skip_release(monkeypatch, context, module):
    tx = Mock(start=AsyncMock(), commit=AsyncMock())
    connection = Mock(transaction=Mock(return_value=tx))
    pool = Mock(acquire=AsyncMock(return_value=connection), release=AsyncMock())
    original_reset = reset_session

    def fail_after_reset(token):
        original_reset(token)
        raise RuntimeError("context reset")

    monkeypatch.setattr(f"{module}.reset_session", fail_after_reset)
    with pytest.raises(RuntimeError, match="context reset"):
        async with context(database(pool)):
            pass
    pool.release.assert_awaited_once_with(connection)


@pytest_asyncio.fixture
async def real_pool():
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL required for real pool regression")
    pool = await asyncpg.create_pool(url, min_size=1, max_size=1)
    try:
        yield pool
    finally:
        await asyncio.wait_for(pool.close(), timeout=3)


@pytest.mark.parametrize("context,module", CONTEXTS)
async def test_repeated_setup_failures_restore_real_pool_capacity(
    real_pool, monkeypatch, context, module
):
    async def fail(connection):
        await connection.execute(
            "SELECT set_config('aksara.current_tenant_id', 'leftover', false)"
        )
        raise RuntimeError("tenant setup")

    monkeypatch.setattr(module + ".apply_tenant_context", fail)
    for _ in range(5):
        with pytest.raises(RuntimeError, match="tenant setup"):
            async with context(database(real_pool)):
                pass
        assert get_session() is None
        assert real_pool.get_idle_size() == 1
        async with real_pool.acquire(timeout=1) as connection:
            assert await connection.fetchval("SELECT 1") == 1
            assert await connection.fetchval(
                "SELECT current_setting('aksara.current_tenant_id', true)"
            ) in (None, "")


async def test_real_transaction_start_failure_returns_capacity(real_pool, monkeypatch):
    async def fail_start(self):
        raise RuntimeError("start failed")

    monkeypatch.setattr(asyncpg.transaction.Transaction, "start", fail_start)
    for _ in range(5):
        with pytest.raises(RuntimeError, match="start failed"):
            async with TransactionManager(database(real_pool)):
                pass
        assert get_session() is None
        assert real_pool.get_idle_size() == 1
        async with real_pool.acquire(timeout=1) as connection:
            assert await connection.fetchval("SELECT 1") == 1


@pytest.mark.parametrize("context,module", CONTEXTS)
async def test_real_setup_cancellation_returns_capacity(
    real_pool, monkeypatch, context, module
):
    entered = asyncio.Event()

    async def setup(connection):
        entered.set()
        await connection.execute("SELECT pg_sleep(30)")

    monkeypatch.setattr(module + ".apply_tenant_context", setup)

    async def worker():
        try:
            async with context(database(real_pool)):
                pass
        finally:
            assert get_session() is None

    task = asyncio.create_task(worker())
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=3)
    assert real_pool.get_idle_size() == 1
    async with real_pool.acquire(timeout=1) as connection:
        assert await connection.fetchval("SELECT 1") == 1


@pytest.mark.parametrize("context,module", CONTEXTS)
async def test_cancellation_during_release_waits_for_release(
    monkeypatch, context, module
):
    entered = asyncio.Event()
    finish = asyncio.Event()
    released = asyncio.Event()

    async def release(connection):
        entered.set()
        await finish.wait()
        released.set()

    tx = Mock(start=AsyncMock(), commit=AsyncMock())
    connection = Mock(transaction=Mock(return_value=tx))
    pool = Mock(
        acquire=AsyncMock(return_value=connection),
        release=AsyncMock(side_effect=release),
    )

    async def worker():
        try:
            async with context(database(pool)):
                pass
        finally:
            assert get_session() is None

    task = asyncio.create_task(worker())
    await entered.wait()
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    finish.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert released.is_set()
    pool.release.assert_awaited_once()


@pytest.mark.parametrize("context,module", CONTEXTS)
async def test_real_reset_failure_still_returns_clean_connection(
    real_pool, monkeypatch, context, module
):
    monkeypatch.setattr(module + ".apply_tenant_context", AsyncMock(return_value=True))
    monkeypatch.setattr(
        module + ".reset_tenant_context",
        AsyncMock(side_effect=RuntimeError("reset failed")),
    )
    with pytest.raises(RuntimeError, match="reset failed"):
        async with context(database(real_pool)) as connection:
            await connection.execute(
                "SELECT set_config('aksara.current_tenant_id', 'leftover', false)"
            )
    assert get_session() is None
    assert real_pool.get_idle_size() == 1
    async with real_pool.acquire(timeout=1) as connection:
        assert await connection.fetchval(
            "SELECT current_setting('aksara.current_tenant_id', true)"
        ) in (None, "")


async def test_real_cancelled_transaction_start_returns_capacity(
    real_pool, monkeypatch
):
    entered = asyncio.Event()
    original_start = asyncpg.transaction.Transaction.start

    async def start(self):
        await original_start(self)
        entered.set()
        await self._connection.execute("SELECT pg_sleep(30)")

    monkeypatch.setattr(asyncpg.transaction.Transaction, "start", start)

    async def worker():
        try:
            async with TransactionManager(database(real_pool)):
                pass
        finally:
            assert get_session() is None

    task = asyncio.create_task(worker())
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=3)
    assert real_pool.get_idle_size() == 1
    async with real_pool.acquire(timeout=1) as connection:
        assert not connection.is_in_transaction()
        assert await connection.fetchval("SELECT 1") == 1
